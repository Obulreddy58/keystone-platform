"""
ArgoCD GitOps Onboarding Router — sets up ArgoCD projects and
ApplicationSets for teams deploying to EKS clusters.

Initiated directly from the Keystone Portal (no Jira webhook).
Platform engineers select a deployed EKS cluster, name their services,
and the platform generates:

  1. ArgoCD AppProject with team RBAC
  2. ApplicationSet with matrix generator (envs × services)
  3. Helm chart scaffolding per service
  4. Per-environment value overrides
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db_models import InfraRequestRecord, RequestEvent, RequestStatus

router = APIRouter(prefix="/api/argocd", tags=["argocd"])


# ─── Request / Response models ──────────────────────────────────────────────

class OnboardRequest(BaseModel):
    """Body for POST /api/argocd/onboard."""
    source_cluster_key: str = Field(..., description="Jira key of the deployed EKS cluster")
    project_name: str = Field(..., pattern=r"^[a-z][a-z0-9\-]{2,39}$",
                              description="ArgoCD project name")
    namespace: str = Field(..., pattern=r"^[a-z][a-z0-9\-]{1,62}$",
                           description="Base Kubernetes namespace")
    services: list[str] = Field(..., min_length=1, max_length=20,
                                description="Service names to onboard")
    environments: list[str] = Field(default=["dev", "staging", "prod"])
    image_registry: str = Field(default="")


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/clusters")
async def list_eligible_clusters(db: AsyncSession = Depends(get_db)):
    """
    List deployed EKS clusters eligible for ArgoCD onboarding.
    Shows whether each cluster already has an ArgoCD project.
    """
    stmt = (
        select(InfraRequestRecord)
        .where(InfraRequestRecord.request_type == "eks-cluster")
        .where(InfraRequestRecord.status == RequestStatus.DEPLOYED)
        .order_by(InfraRequestRecord.team_name)
    )
    result = await db.execute(stmt)
    clusters = result.scalars().all()

    # Find existing ArgoCD onboarding records
    argo_stmt = (
        select(InfraRequestRecord)
        .where(InfraRequestRecord.request_type == "argocd-onboarding")
        .where(InfraRequestRecord.status.notin_([
            RequestStatus.FAILED,
            RequestStatus.CANCELLED,
        ]))
    )
    argo_result = await db.execute(argo_stmt)
    existing_argo = {}
    for a in argo_result.scalars().all():
        key = (a.request_data or {}).get("source_cluster_key", "")
        if key:
            existing_argo[key] = a

    items = []
    for c in clusters:
        rd = c.request_data or {}
        do = c.deployment_outputs or {}
        argo = existing_argo.get(c.jira_ticket_key)
        items.append({
            "jira_ticket_key": c.jira_ticket_key,
            "cluster_name": c.resource_name or rd.get("cluster_name", ""),
            "team_name": c.team_name,
            "environment": c.environment,
            "account_id": c.account_id,
            "github_group": c.github_group,
            "github_repo": c.github_repo,
            "cluster_endpoint": do.get("cluster_endpoint", ""),
            "cluster_version": rd.get("cluster_version") or rd.get("kubernetes_version", ""),
            "has_argocd": argo is not None,
            "argocd_key": argo.jira_ticket_key if argo else None,
            "argocd_status": (argo.status.value if hasattr(argo.status, "value") else argo.status) if argo else None,
        })

    return items


@router.get("")
async def list_onboarding_requests(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List all ArgoCD onboarding requests."""
    stmt = (
        select(InfraRequestRecord)
        .where(InfraRequestRecord.request_type == "argocd-onboarding")
        .order_by(InfraRequestRecord.created_at.desc())
    )
    if status:
        stmt = stmt.where(InfraRequestRecord.status == status)
    result = await db.execute(stmt)
    records = result.scalars().all()

    items = []
    for r in records:
        rd = r.request_data or {}
        items.append({
            "id": r.id,
            "jira_ticket_key": r.jira_ticket_key,
            "project_name": rd.get("project_name", ""),
            "cluster_name": r.resource_name,
            "team_name": r.team_name,
            "environment": r.environment,
            "account_id": r.account_id,
            "status": r.status.value if hasattr(r.status, "value") else r.status,
            "services": rd.get("services", []),
            "environments": rd.get("environments", []),
            "namespace": rd.get("namespace", ""),
            "image_registry": rd.get("image_registry", ""),
            "source_cluster_key": rd.get("source_cluster_key", ""),
            "cluster_endpoint": rd.get("cluster_endpoint", ""),
            "files_created": r.files_created or 0,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "deployed_at": r.deployed_at.isoformat() if r.deployed_at else None,
        })

    return items


@router.post("/onboard")
async def onboard_argocd(
    body: OnboardRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Initiate ArgoCD onboarding for a deployed EKS cluster.
    Generates project YAML, ApplicationSet, Helm chart scaffolding,
    and per-environment value overrides.
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
        raise HTTPException(400, "Cluster must be in deployed state")

    # 2. Check for existing onboarding on this cluster
    existing = await db.execute(
        select(InfraRequestRecord).where(
            InfraRequestRecord.request_type == "argocd-onboarding",
            InfraRequestRecord.status.notin_([
                RequestStatus.FAILED,
                RequestStatus.CANCELLED,
            ]),
            InfraRequestRecord.resource_name == (cluster.resource_name or ""),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "ArgoCD is already onboarded for this cluster.")

    # 3. Validate service names
    for svc in body.services:
        if not svc or len(svc) > 63:
            raise HTTPException(400, f"Invalid service name: {svc}")

    # 4. Generate key
    count_result = await db.execute(
        select(func.count()).select_from(InfraRequestRecord).where(
            InfraRequestRecord.request_type == "argocd-onboarding"
        )
    )
    count = count_result.scalar() or 0
    jira_key = f"ARGO-{count + 1:04d}"

    # 5. Build file paths
    cluster_endpoint = (cluster.deployment_outputs or {}).get("cluster_endpoint", "")
    base_path = f"{cluster.team_name}/{cluster.environment}/us-east-1/argocd/{body.project_name}"
    file_paths = [
        f"{base_path}/project.yaml",
        f"{base_path}/applicationset.yaml",
    ]
    for svc in body.services:
        file_paths.extend([
            f"{base_path}/charts/{svc}/Chart.yaml",
            f"{base_path}/charts/{svc}/values.yaml",
            f"{base_path}/charts/{svc}/templates/_helpers.tpl",
            f"{base_path}/charts/{svc}/templates/deployment.yaml",
            f"{base_path}/charts/{svc}/templates/service.yaml",
            f"{base_path}/charts/{svc}/templates/ingress.yaml",
            f"{base_path}/charts/{svc}/templates/hpa.yaml",
            f"{base_path}/charts/{svc}/templates/pdb.yaml",
            f"{base_path}/charts/{svc}/templates/serviceaccount.yaml",
        ])
    for env in body.environments:
        for svc in body.services:
            file_paths.append(f"{base_path}/values/{env}/{svc}.yaml")

    now = datetime.now(timezone.utc)

    onboard_data = {
        "project_name": body.project_name,
        "source_cluster_key": body.source_cluster_key,
        "cluster_name": cluster.resource_name,
        "cluster_endpoint": cluster_endpoint,
        "namespace": body.namespace,
        "services": body.services,
        "environments": body.environments,
        "image_registry": body.image_registry or f"{cluster.account_id}.dkr.ecr.us-east-1.amazonaws.com",
        "service_count": len(body.services),
        "env_count": len(body.environments),
        "total_applications": len(body.services) * len(body.environments),
    }

    record = InfraRequestRecord(
        jira_ticket_key=jira_key,
        request_type="argocd-onboarding",
        status=RequestStatus.PENDING,
        requester_email="platform-admin@company.com",
        team_name=cluster.team_name,
        cost_center=cluster.cost_center,
        resource_name=cluster.resource_name,
        environment=cluster.environment,
        account_id=cluster.account_id,
        github_group=cluster.github_group,
        github_repo=cluster.github_repo,
        files_created=len(file_paths),
        file_paths=file_paths,
        request_data=onboard_data,
        created_at=now,
    )

    db.add(record)
    await db.flush()

    db.add(RequestEvent(
        request_id=record.id,
        event_type="argocd_onboard_initiated",
        description=f"ArgoCD GitOps onboarding initiated for {cluster.resource_name} with {len(body.services)} service(s)",
        metadata_json={
            "project_name": body.project_name,
            "services": body.services,
            "environments": body.environments,
            "initiated_from": "keystone_portal",
        },
        created_at=now,
    ))

    await db.commit()

    return {
        "jira_ticket_key": jira_key,
        "project_name": body.project_name,
        "cluster_name": cluster.resource_name,
        "services": body.services,
        "environments": body.environments,
        "total_applications": len(body.services) * len(body.environments),
        "files_created": len(file_paths),
        "status": "pending",
        "message": "ArgoCD onboarding initiated. Templates will be rendered and committed.",
    }
