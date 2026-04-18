"""
EKS Cluster Upgrade Router — manages Kubernetes version upgrades
directly from the Keystone Portal (no Jira webhook needed).

All deployed EKS clusters are already tracked in the platform.
Platform engineers can initiate upgrades that progress through stages:

  1. Pre-Checks   — cluster health, version skew, PDBs, subnet IPs
  2. Control Plane — EKS managed control plane version bump (Terraform)
  3. Addons        — VPC CNI, CoreDNS, kube-proxy, karpenter (Terraform)
  4. Node Groups   — rolling update of worker nodes with new AMI (Terraform)
  5. Post-Checks   — node validation, GitOps reconciliation, load test

Rules:
  - N → N+1 only (no skipping minor versions)
  - No downgrades
  - Lower env first with 2-week grace period before prod
  - Control plane and nodes must stay on same version
  - Auto-rollback on failure
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.db_models import InfraRequestRecord, RequestEvent, RequestStatus

router = APIRouter(prefix="/api/upgrades", tags=["upgrades"])


# ─── EKS version matrix ─────────────────────────────────────────────────────
# Supported versions and their compatible addon versions.

EKS_VERSIONS = ["1.27", "1.28", "1.29", "1.30", "1.31", "1.32"]
LATEST_EKS_VERSION = "1.32"

ADDON_COMPATIBILITY: dict[str, dict[str, str]] = {
    "1.32": {"vpc-cni": "v1.19.2", "coredns": "v1.11.4", "kube-proxy": "v1.32.0", "karpenter": "1.2.0", "cluster-autoscaler": "1.32.0"},
    "1.31": {"vpc-cni": "v1.19.0", "coredns": "v1.11.3", "kube-proxy": "v1.31.3", "karpenter": "1.1.0", "cluster-autoscaler": "1.31.0"},
    "1.30": {"vpc-cni": "v1.18.6", "coredns": "v1.11.1", "kube-proxy": "v1.30.6", "karpenter": "0.37.0", "cluster-autoscaler": "1.30.0"},
    "1.29": {"vpc-cni": "v1.18.0", "coredns": "v1.11.1", "kube-proxy": "v1.29.7", "karpenter": "0.36.0", "cluster-autoscaler": "1.29.0"},
    "1.28": {"vpc-cni": "v1.16.4", "coredns": "v1.10.1", "kube-proxy": "v1.28.12", "karpenter": "0.35.0", "cluster-autoscaler": "1.28.0"},
    "1.27": {"vpc-cni": "v1.15.4", "coredns": "v1.10.1", "kube-proxy": "v1.27.16", "karpenter": "0.33.0", "cluster-autoscaler": "1.27.0"},
}

# Pre-check and post-check definitions
PRE_CHECK_ITEMS = [
    "cluster_health",
    "version_skew",
    "pdb_configured",
    "subnet_ips_available",
    "no_failing_pods",
    "api_deprecations_reviewed",
    "lower_env_validated",
]

POST_CHECK_ITEMS = [
    "nodes_correct_version",
    "control_plane_healthy",
    "flux_reconciliation",
    "pod_health",
    "load_test",
]


# ─── Request / Response models ──────────────────────────────────────────────

class UpgradeInitiate(BaseModel):
    """Body for POST /api/upgrades/initiate — start a cluster upgrade."""
    source_cluster_key: str = Field(..., description="Jira key of the deployed EKS cluster")
    target_version: str = Field(..., description="Target Kubernetes version (e.g. 1.32)")
    upgrade_strategy: str = Field(default="rolling", pattern=r"^(rolling|blue-green)$")
    node_max_unavailable: int = Field(default=1, ge=1, le=10)
    drain_timeout_seconds: int = Field(default=300, ge=60, le=3600)
    notification_slack_channel: str = ""
    notification_email: str = ""


class StageApproval(BaseModel):
    """Body for POST /api/upgrades/{key}/approve-stage."""
    stage: str = Field(..., pattern=r"^(control_plane|addons|node_groups)$")
    approved_by: str = ""


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _cluster_version(request_data: dict | None) -> str:
    """Extract the Kubernetes version from an EKS cluster's request_data."""
    if not request_data:
        return "1.30"
    return (
        request_data.get("cluster_version")
        or request_data.get("kubernetes_version")
        or "1.30"
    )


def _version_index(version: str) -> int:
    """Return index in EKS_VERSIONS, or -1 if unknown."""
    try:
        return EKS_VERSIONS.index(version)
    except ValueError:
        return -1


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/clusters")
async def list_eks_clusters(db: AsyncSession = Depends(get_db)):
    """
    List all deployed EKS clusters with upgrade eligibility info.
    This is the main view — shows every cluster the platform manages.
    """
    stmt = (
        select(InfraRequestRecord)
        .where(InfraRequestRecord.request_type == "eks-cluster")
        .where(InfraRequestRecord.status == RequestStatus.DEPLOYED)
        .order_by(InfraRequestRecord.team_name)
    )
    result = await db.execute(stmt)
    clusters = result.scalars().all()

    # Also fetch active upgrades to show per-cluster status
    upgrade_stmt = (
        select(InfraRequestRecord)
        .where(InfraRequestRecord.request_type == "eks-upgrade")
        .where(InfraRequestRecord.status.notin_([
            RequestStatus.DEPLOYED,
            RequestStatus.FAILED,
            RequestStatus.CANCELLED,
        ]))
    )
    upgrade_result = await db.execute(upgrade_stmt)
    active_upgrades = {
        (u.request_data or {}).get("source_request_key"): u
        for u in upgrade_result.scalars().all()
    }

    items = []
    for c in clusters:
        rd = c.request_data or {}
        current_ver = _cluster_version(rd)
        ver_idx = _version_index(current_ver)
        upgradeable = ver_idx >= 0 and ver_idx < len(EKS_VERSIONS) - 1
        next_version = EKS_VERSIONS[ver_idx + 1] if upgradeable else None
        versions_behind = max(0, len(EKS_VERSIONS) - 1 - ver_idx) if ver_idx >= 0 else 0

        active = active_upgrades.get(c.jira_ticket_key)

        # Current addon versions from the compatibility matrix
        current_addons = ADDON_COMPATIBILITY.get(current_ver, {})
        next_addons = ADDON_COMPATIBILITY.get(next_version, {}) if next_version else {}

        items.append({
            "jira_ticket_key": c.jira_ticket_key,
            "cluster_name": c.resource_name or rd.get("cluster_name", ""),
            "team_name": c.team_name,
            "environment": c.environment,
            "account_id": c.account_id,
            "github_group": c.github_group,
            "github_repo": c.github_repo,
            "current_version": current_ver,
            "latest_version": LATEST_EKS_VERSION,
            "next_version": next_version,
            "upgrade_available": upgradeable and active is None,
            "versions_behind": versions_behind,
            "deployed_at": c.deployed_at.isoformat() if c.deployed_at else None,
            "node_count": rd.get("node_desired_size") or rd.get("min_nodes") or 3,
            "node_instance_type": rd.get("node_instance_type") or rd.get("node_instance_types", ["m6i.xlarge"])[0] if rd.get("node_instance_types") else "m6i.xlarge",
            "node_min_size": rd.get("node_min_size") or rd.get("min_nodes") or 2,
            "node_max_size": rd.get("node_max_size") or rd.get("max_nodes") or 10,
            "node_desired_size": rd.get("node_desired_size") or rd.get("min_nodes") or 3,
            "ami_type": rd.get("ami_type", "AL2023_x86_64_STANDARD"),
            "enable_karpenter": rd.get("enable_karpenter", True),
            "active_upgrade_key": active.jira_ticket_key if active else None,
            # Addon version details for the upgrade form
            "current_addons": current_addons,
            "next_addons": next_addons,
        })

    return items


@router.get("")
async def list_upgrades(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List all upgrade operations with stage progress."""
    stmt = (
        select(InfraRequestRecord)
        .where(InfraRequestRecord.request_type == "eks-upgrade")
        .order_by(InfraRequestRecord.created_at.desc())
    )
    if status:
        stmt = stmt.where(InfraRequestRecord.status == status)
    result = await db.execute(stmt)
    upgrades = result.scalars().all()

    items = []
    for u in upgrades:
        rd = u.request_data or {}
        stages = rd.get("stages", {})
        items.append({
            "id": u.id,
            "jira_ticket_key": u.jira_ticket_key,
            "cluster_name": u.resource_name,
            "team_name": u.team_name,
            "environment": u.environment,
            "account_id": u.account_id,
            "status": u.status.value if hasattr(u.status, "value") else u.status,
            "current_version": rd.get("current_version", ""),
            "target_version": rd.get("target_version", ""),
            "upgrade_strategy": rd.get("upgrade_strategy", "rolling"),
            "pre_checks": rd.get("pre_checks", {}),
            "stages": stages,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "updated_at": u.updated_at.isoformat() if u.updated_at else None,
            "deployed_at": u.deployed_at.isoformat() if u.deployed_at else None,
            "notification_slack_channel": rd.get("notification_slack_channel", ""),
        })

    return items


@router.get("/{jira_key}")
async def get_upgrade_detail(jira_key: str, db: AsyncSession = Depends(get_db)):
    """Get full upgrade details including stage progress and timeline events."""
    stmt = (
        select(InfraRequestRecord)
        .where(InfraRequestRecord.jira_ticket_key == jira_key)
        .where(InfraRequestRecord.request_type == "eks-upgrade")
        .options(selectinload(InfraRequestRecord.events))
    )
    result = await db.execute(stmt)
    upgrade = result.scalar_one_or_none()
    if not upgrade:
        raise HTTPException(status_code=404, detail="Upgrade not found")
    return upgrade


@router.post("/initiate")
async def initiate_upgrade(
    body: UpgradeInitiate,
    db: AsyncSession = Depends(get_db),
):
    """
    Initiate an EKS cluster upgrade directly from the Keystone Portal.
    No Jira webhook — all cluster info is already tracked in the platform.

    Validates:
      - Cluster exists and is deployed
      - Target version is valid (N → N+1 only, no downgrades)
      - No concurrent upgrade on the same cluster
    """
    # 1. Look up source cluster
    stmt = select(InfraRequestRecord).where(
        InfraRequestRecord.jira_ticket_key == body.source_cluster_key
    )
    result = await db.execute(stmt)
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(404, "Source cluster not found")
    if cluster.status != RequestStatus.DEPLOYED:
        raise HTTPException(400, "Cluster must be in deployed state to upgrade")

    # 2. Validate version rules
    rd = cluster.request_data or {}
    current_ver = _cluster_version(rd)

    if body.target_version not in EKS_VERSIONS:
        raise HTTPException(400, f"Invalid target version. Supported: {EKS_VERSIONS}")

    cur_idx = _version_index(current_ver)
    tgt_idx = _version_index(body.target_version)

    if tgt_idx <= cur_idx:
        raise HTTPException(400, "Cannot downgrade. Target version must be higher than current.")
    if tgt_idx - cur_idx > 1:
        raise HTTPException(400, "Can only upgrade one minor version at a time (N → N+1).")

    # 3. Check for active upgrade on this cluster
    existing = await db.execute(
        select(InfraRequestRecord).where(
            InfraRequestRecord.request_type == "eks-upgrade",
            InfraRequestRecord.resource_name == (cluster.resource_name or ""),
            InfraRequestRecord.status.notin_([
                RequestStatus.DEPLOYED,
                RequestStatus.FAILED,
                RequestStatus.CANCELLED,
            ]),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "An upgrade is already in progress for this cluster.")

    # 4. Generate upgrade key
    count_result = await db.execute(
        select(func.count()).select_from(InfraRequestRecord).where(
            InfraRequestRecord.request_type == "eks-upgrade"
        )
    )
    count = count_result.scalar() or 0
    jira_key = f"UPGRADE-{count + 1:04d}"

    # 5. Build stage data
    target_addons = ADDON_COMPATIBILITY.get(body.target_version, {})
    current_addons = ADDON_COMPATIBILITY.get(current_ver, {})

    now = datetime.now(timezone.utc)

    upgrade_data = {
        "source_request_key": body.source_cluster_key,
        "cluster_name": cluster.resource_name,
        "cluster_arn": (cluster.deployment_outputs or {}).get("cluster_arn", ""),
        "current_version": current_ver,
        "target_version": body.target_version,
        "upgrade_strategy": body.upgrade_strategy,
        "node_max_unavailable": body.node_max_unavailable,
        "drain_timeout_seconds": body.drain_timeout_seconds,
        "enable_auto_rollback": True,
        "notification_slack_channel": body.notification_slack_channel,
        "notification_email": body.notification_email,
        "pre_checks": {
            "status": "pending",
            "checks": {item: "pending" for item in PRE_CHECK_ITEMS},
        },
        "stages": {
            "control_plane": {"status": "pending"},
            "addons": {
                "status": "pending",
                "components": {
                    name: {"from": current_addons.get(name, ""), "to": ver, "status": "pending"}
                    for name, ver in target_addons.items()
                },
            },
            "node_groups": {
                "status": "pending",
                "strategy": body.upgrade_strategy,
                "nodes_total": rd.get("node_desired_size") or rd.get("min_nodes") or 3,
                "nodes_upgraded": 0,
                "max_unavailable": body.node_max_unavailable,
            },
            "post_checks": {
                "status": "pending",
                "checks": {item: "pending" for item in POST_CHECK_ITEMS},
            },
        },
    }

    record = InfraRequestRecord(
        jira_ticket_key=jira_key,
        request_type="eks-upgrade",
        status=RequestStatus.PENDING,
        requester_email="platform-admin@company.com",
        team_name=cluster.team_name,
        cost_center=cluster.cost_center,
        resource_name=cluster.resource_name,
        environment=cluster.environment,
        account_id=cluster.account_id,
        github_group=cluster.github_group,
        github_repo=cluster.github_repo,
        files_created=3,
        file_paths=[
            f"{cluster.team_name}/{cluster.environment}/us-east-1/eks-upgrade/{cluster.resource_name}-{body.target_version}/control-plane/terragrunt.hcl",
            f"{cluster.team_name}/{cluster.environment}/us-east-1/eks-upgrade/{cluster.resource_name}-{body.target_version}/addons/terragrunt.hcl",
            f"{cluster.team_name}/{cluster.environment}/us-east-1/eks-upgrade/{cluster.resource_name}-{body.target_version}/node-groups/terragrunt.hcl",
        ],
        request_data=upgrade_data,
        created_at=now,
    )

    db.add(record)
    await db.flush()

    db.add(RequestEvent(
        request_id=record.id,
        event_type="upgrade_initiated",
        description=f"EKS upgrade initiated: {current_ver} → {body.target_version} for {cluster.resource_name}",
        metadata_json={
            "current_version": current_ver,
            "target_version": body.target_version,
            "strategy": body.upgrade_strategy,
            "initiated_from": "keystone_portal",
        },
        created_at=now,
    ))

    await db.commit()

    return {
        "jira_ticket_key": jira_key,
        "cluster_name": cluster.resource_name,
        "current_version": current_ver,
        "target_version": body.target_version,
        "status": "pending",
        "message": "Upgrade initiated. Pre-checks will run next.",
    }


@router.get("/versions/latest")
async def get_latest_version():
    """Return the latest supported EKS version and addon compatibility."""
    return {
        "latest_version": LATEST_EKS_VERSION,
        "supported_versions": EKS_VERSIONS,
        "addon_compatibility": ADDON_COMPATIBILITY,
    }
