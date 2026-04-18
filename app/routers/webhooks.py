"""
Jira Webhook Router — receives webhooks from Jira Service Management,
parses the request form fields, renders templates, and creates GitHub PRs.
"""

from __future__ import annotations

import hashlib
import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Request
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.db_models import AccountStatus, InfraRequestRecord, RequestEvent, RequestStatus, TeamAccount
from app.models.requests import REQUEST_TYPE_MAP, InfraRequest
from app.services.github_pr import github_service
from app.services.jira import jira_service
from app.services.renderer import renderer

logger = structlog.get_logger()
router = APIRouter(prefix="/webhook", tags=["webhooks"])


# ─── Jira custom field mapping ──────────────────────────────────────────────
# Map your Jira custom field IDs to our model field names.
# Update these to match YOUR Jira instance's field IDs.
# You find these in Jira Admin → Issues → Custom Fields → click field → ID in URL
JIRA_FIELD_MAP: dict[str, str] = {
    "customfield_10100": "request_type",     # Dropdown: eks-cluster, rds-database, etc.
    "customfield_10101": "account_id",       # Text: AWS account ID
    "customfield_10102": "environment",      # Dropdown: dev, staging, prod
    "customfield_10103": "team_name",        # Text: team name
    "customfield_10104": "cluster_name",     # Text: cluster/resource name
    "customfield_10105": "cluster_version",  # Text: K8s version
    "customfield_10106": "vpc_cidr",         # Text: VPC CIDR
    "customfield_10107": "node_instance_type",
    "customfield_10108": "node_min_size",
    "customfield_10109": "node_max_size",
    "customfield_10110": "node_desired_size",
    "customfield_10111": "github_team_slug",
    "customfield_10112": "cost_center",
    "customfield_10113": "private_cluster",
    "customfield_10114": "enable_karpenter",
    "customfield_10115": "db_name",
    "customfield_10116": "engine",
    "customfield_10117": "engine_version",
    "customfield_10118": "instance_class",
    "customfield_10119": "allocated_storage",
    "customfield_10120": "multi_az",
    "customfield_10121": "deletion_protection",
    "customfield_10122": "backup_retention_days",
    "customfield_10123": "existing_vpc_id",
    "customfield_10124": "bucket_name",
    "customfield_10125": "service_name",
    "customfield_10126": "function_name",
    "customfield_10127": "table_name",
    "customfield_10128": "domain_name",
    "customfield_10129": "vpc_name",
    "customfield_10140": "github_group",  # Team's GitHub org/group
    "customfield_10141": "github_repo",   # Team's infra repo name
    # ─── XCR Onboarding (Cluster Onboarding Request) fields ─────────────────
    "customfield_10150": "business_unit",       # Business Unit/Segment
    "customfield_10151": "client_services",     # Client Services
    "customfield_10152": "component",            # Component
    "customfield_10153": "primary_contact_email",# Primary Contact Email
    "customfield_10154": "cloud",                # Cloud (AWS, Azure, GCP)
    "customfield_10155": "cluster_type",         # Cluster Type
    "customfield_10156": "release_type",         # Release Type
    "customfield_10157": "size",                 # Size
    "customfield_10158": "connectivity",         # Connectivity
    "customfield_10159": "keycloak_group_name",  # Keycloak Group Name
    # ─── AWS Account Request fields ─────────────────────────────────────────
    "customfield_10160": "team_display_name",     # Team Display Name
    "customfield_10161": "product_owner_email",   # Product Owner Email
    "customfield_10162": "ou_path",               # Organizational Unit
    "customfield_10163": "account_email_prefix",  # Account Email Prefix
    "customfield_10164": "enable_vpc",            # Bootstrap VPC?
    "customfield_10165": "enable_guardduty",      # Enable GuardDuty?
    "customfield_10166": "enable_cloudtrail",     # Enable CloudTrail?
    # SRE Onboarding fields
    "customfield_10170": "central_monitoring_vpc_id",
    "customfield_10171": "central_monitoring_vpc_cidr",
    "customfield_10172": "central_monitoring_account_id",
    "customfield_10173": "prometheus_remote_write_url",
    "customfield_10174": "team_vpc_id",
    "customfield_10175": "team_vpc_cidr",
    "customfield_10176": "enable_otel_collector",
    "customfield_10177": "enable_tracing",
    "customfield_10178": "tracing_endpoint",
    "customfield_10179": "enable_logging",
    "customfield_10180": "logging_endpoint",
    "customfield_10181": "scrape_interval",
    "customfield_10182": "metrics_retention_hours",
    "customfield_10183": "grafana_org_name",
    # SRE SLO/SLI fields
    "customfield_10184": "slo_availability_target",
    "customfield_10185": "slo_latency_p99_ms",
    "customfield_10186": "slo_error_rate_threshold",
    "customfield_10187": "error_budget_burn_alert",
    # Incident management fields
    "customfield_10188": "incident_tool",
    "customfield_10189": "pagerduty_service_id",
    "customfield_10190": "opsgenie_team_id",
    "customfield_10191": "escalation_policy",
    "customfield_10192": "oncall_rotation_name",
    "customfield_10193": "oncall_primary_email",
    "customfield_10194": "oncall_secondary_email",
    # Runbooks & notifications
    "customfield_10195": "enable_runbooks",
    "customfield_10196": "runbook_wiki_space",
    "customfield_10197": "notification_slack_channel",
    "customfield_10198": "notification_email",
    # summary, description, and reporter come from standard fields
}


def _verify_webhook_signature(body: bytes, signature: str) -> bool:
    """Verify Jira webhook signature using HMAC-SHA256."""
    if not settings.jira_webhook_secret:
        return True  # skip verification if no secret configured

    expected = hmac.new(
        settings.jira_webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def _extract_fields(issue_fields: dict) -> dict:
    """Extract custom fields from Jira issue and map to our model fields."""
    extracted: dict = {}

    for jira_field_id, model_field_name in JIRA_FIELD_MAP.items():
        value = issue_fields.get(jira_field_id)
        if value is None:
            continue

        # Jira dropdowns return {"value": "..."} objects
        if isinstance(value, dict) and "value" in value:
            value = value["value"]

        # Jira number fields might be float
        if isinstance(value, float) and value == int(value):
            value = int(value)

        extracted[model_field_name] = value

    # Standard fields
    if "summary" in issue_fields:
        extracted["summary"] = issue_fields["summary"]
        extracted.setdefault("cluster_name", issue_fields["summary"])

    if "description" in issue_fields and issue_fields["description"]:
        extracted.setdefault("description", issue_fields["description"])

    reporter = issue_fields.get("reporter", {})
    extracted["requester_email"] = reporter.get("emailAddress", "unknown@company.com")

    return extracted


@router.post("/jira")
async def handle_jira_webhook(
    request: Request,
    x_hub_signature: str = Header(default="", alias="X-Hub-Signature"),
    db: AsyncSession = Depends(get_db),
):
    """
    Main webhook endpoint — Jira sends a POST here when a request form is submitted.

    Flow:
    1. Validate webhook signature
    2. Parse the Jira issue fields
    3. Determine request type (eks-cluster, rds-database, etc.)
    4. Validate fields against the Pydantic model
    5. Render Terragrunt templates with the values
    6. Create a GitHub PR
    7. Update the Jira ticket with the PR link
    """
    body = await request.body()

    # 1. Verify webhook authenticity
    if not _verify_webhook_signature(body, x_hub_signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()

    # Only process issue creation events
    webhook_event = payload.get("webhookEvent", "")
    if webhook_event not in ("jira:issue_created", "jira:issue_updated"):
        return {"status": "ignored", "reason": f"Unhandled event: {webhook_event}"}

    issue = payload.get("issue", {})
    issue_key = issue.get("key", "UNKNOWN-0")
    issue_fields = issue.get("fields", {})

    logger.info("webhook_received", issue=issue_key, event=webhook_event)

    # 2. Extract form fields
    fields = _extract_fields(issue_fields)
    fields["jira_ticket_key"] = issue_key

    # 3. Determine request type
    request_type = fields.get("request_type", "")
    if request_type not in REQUEST_TYPE_MAP:
        msg = f"Unknown request type: '{request_type}'. Valid types: {list(REQUEST_TYPE_MAP.keys())}"
        logger.error("unknown_request_type", request_type=request_type, issue=issue_key)
        await jira_service.add_comment(issue_key, f"❌ Self-Service Error: {msg}")
        raise HTTPException(status_code=400, detail=msg)

    # 4. Validate against the model
    model_class = REQUEST_TYPE_MAP[request_type]
    try:
        infra_request: InfraRequest = model_class(**fields)
    except Exception as e:
        msg = f"Validation failed: {e}"
        logger.error("validation_failed", error=str(e), issue=issue_key)
        await jira_service.add_comment(issue_key, f"❌ Self-Service Validation Error:\n{msg}")
        raise HTTPException(status_code=422, detail=msg) from e

    # ─── Special flow: AWS Account Request ───────────────────────────────
    if request_type == "aws-account":
        return await _handle_account_request(infra_request, issue_key, db)

    # ─── Auto-lookup: resolve team_name → account_id, github_group ───────
    # If team_name is provided but account_id is empty, lookup from registry
    if infra_request.team_name and not infra_request.account_id:
        team_record = await _lookup_team_account(infra_request.team_name, db)
        if team_record:
            # Populate missing fields from the team registry
            fields["account_id"] = team_record.account_id
            if not infra_request.github_group:
                fields["github_group"] = team_record.github_group
            if not infra_request.github_repo or infra_request.github_repo == "infra":
                fields["github_repo"] = team_record.github_repo
            # Re-validate with the enriched fields
            try:
                infra_request = model_class(**fields)
            except Exception as e:
                msg = f"Validation failed after team lookup: {e}"
                logger.error("validation_failed_after_lookup", error=str(e), issue=issue_key)
                await jira_service.add_comment(issue_key, f"❌ Validation Error:\n{msg}")
                raise HTTPException(status_code=422, detail=msg) from e
            logger.info(
                "team_lookup_enriched",
                team=infra_request.team_name,
                account_id=infra_request.account_id,
            )

    # 5. Render templates
    try:
        rendered_files = renderer.render(infra_request)
    except Exception as e:
        msg = f"Template rendering failed: {e}"
        logger.error("render_failed", error=str(e), issue=issue_key)
        await jira_service.add_comment(issue_key, f"❌ Template Error:\n{msg}")
        raise HTTPException(status_code=500, detail=msg) from e

    logger.info("templates_rendered", file_count=len(rendered_files), issue=issue_key)

    # 6. Create GitHub PR
    branch_name = f"self-service/{issue_key}-{request_type}"
    resource_name = renderer._get_resource_name(infra_request)

    pr_body = (
        f"## Self-Service Infrastructure Request\n\n"
        f"| Field | Value |\n"
        f"|---|---|\n"
        f"| **Jira Ticket** | [{issue_key}]({settings.jira_base_url}/browse/{issue_key}) |\n"
        f"| **Request Type** | `{request_type}` |\n"
        f"| **Environment** | `{infra_request.environment}` |\n"
        f"| **Team** | `{infra_request.team_name}` |\n"
        f"| **Resource** | `{resource_name}` |\n"
        f"| **Requester** | {infra_request.requester_email} |\n"
        f"| **Account** | `{infra_request.account_id}` |\n"
        f"| **Target Repo** | `{infra_request.github_group}/{infra_request.github_repo}` |\n\n"
        f"### Files Created\n\n"
    )
    for file_path in sorted(rendered_files.keys()):
        pr_body += f"- `{file_path}`\n"

    pr_body += (
        f"\n---\n"
        f"*Auto-generated by Self-Service API. Do not edit manually.*\n"
        f"*Review the plan output, approve the PR, and merge to deploy.*"
    )

    try:
        pr_url = github_service.create_pull_request(
            github_group=infra_request.github_group,
            github_repo=infra_request.github_repo,
            branch_name=branch_name,
            title=f"[{issue_key}] {request_type}: {resource_name} ({infra_request.environment})",
            body=pr_body,
            files=rendered_files,
            labels=["self-service", request_type, infra_request.environment],
        )
    except Exception as e:
        msg = f"GitHub PR creation failed: {e}"
        logger.error("github_pr_failed", error=str(e), issue=issue_key)
        await jira_service.add_comment(issue_key, f"❌ GitHub Error:\n{msg}")
        raise HTTPException(status_code=502, detail=msg) from e
    # ─── Persist to database ─────────────────────────────────────────────
    pr_number = None
    if pr_url and "/pull/" in pr_url:
        try:
            pr_number = int(pr_url.rsplit("/pull/", 1)[1].rstrip("/"))
        except (ValueError, IndexError):
            pass

    db_record = InfraRequestRecord(
        jira_ticket_key=issue_key,
        request_type=request_type,
        status=RequestStatus.PENDING,
        requester_email=infra_request.requester_email,
        team_name=infra_request.team_name,
        cost_center=infra_request.cost_center,
        resource_name=resource_name,
        environment=infra_request.environment,
        account_id=infra_request.account_id,
        request_data=infra_request.model_dump(),
        github_group=infra_request.github_group,
        github_repo=infra_request.github_repo,
        pr_url=pr_url,
        pr_number=pr_number,
        branch_name=branch_name,
        files_created=len(rendered_files),
        file_paths=sorted(rendered_files.keys()),
    )
    db.add(db_record)
    await db.flush()

    event = RequestEvent(
        request_id=db_record.id,
        event_type="pr_created",
        description=f"PR created in {infra_request.github_group}/{infra_request.github_repo}",
        metadata_json={"pr_url": pr_url, "pr_number": pr_number, "branch": branch_name},
    )
    db.add(event)
    await db.commit()

    logger.info("request_persisted", issue=issue_key, db_id=db_record.id)
    # 7. Update Jira ticket
    await jira_service.add_comment(
        issue_key,
        f"✅ Infrastructure PR created successfully!\n\n"
        f"Pull Request: {pr_url}\n"
        f"Target Repo: {infra_request.github_group}/{infra_request.github_repo}\n\n"
        f"Next steps:\n"
        f"1. The CI pipeline will run terraform plan automatically\n"
        f"2. Platform team reviews and approves the PR\n"
        f"3. On merge, infrastructure deploys automatically\n"
        f"4. This ticket will be updated when deployment completes",
    )

    await jira_service.transition_issue(issue_key, "In Progress")

    logger.info(
        "request_processed",
        issue=issue_key,
        request_type=request_type,
        pr_url=pr_url,
        files=len(rendered_files),
    )

    return {
        "status": "success",
        "issue": issue_key,
        "request_type": request_type,
        "target_repo": f"{infra_request.github_group}/{infra_request.github_repo}",
        "pr_url": pr_url,
        "files_created": len(rendered_files),
    }


# ─── Helper: team account lookup ────────────────────────────────────────────

async def _lookup_team_account(
    team_name: str, db: AsyncSession
) -> TeamAccount | None:
    """Look up a team's account from the registry. Returns None if not found or not active."""
    stmt = select(TeamAccount).where(
        TeamAccount.team_name == team_name,
        TeamAccount.status == AccountStatus.ACTIVE,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# ─── Helper: handle aws-account requests ────────────────────────────────────

async def _handle_account_request(
    infra_request: InfraRequest,
    issue_key: str,
    db: AsyncSession,
) -> dict:
    """
    Special handler for aws-account requests.
    Instead of creating a PR immediately, this registers the team in the
    account registry with status=pending_approval and waits for admin approval.
    """
    team_name = infra_request.team_name
    environment = infra_request.environment or "dev"

    # Check duplicate
    existing = await db.execute(
        select(TeamAccount).where(TeamAccount.team_name == team_name)
    )
    if existing.scalar_one_or_none():
        msg = f"Team '{team_name}' already has an account registered"
        await jira_service.add_comment(issue_key, f"❌ {msg}")
        raise HTTPException(status_code=409, detail=msg)

    record = TeamAccount(
        team_name=team_name,
        team_display_name=getattr(infra_request, "team_display_name", team_name),
        product_owner_email=getattr(infra_request, "product_owner_email", infra_request.requester_email),
        cost_center=infra_request.cost_center,
        business_unit=getattr(infra_request, "business_unit", ""),
        account_name=f"{team_name}-{environment}",
        account_email=getattr(infra_request, "account_email_prefix", "") or f"aws+{team_name}-{environment}@company.com",
        environment=environment,
        github_group=infra_request.github_group,
        github_repo=infra_request.github_repo,
        jira_ticket_key=issue_key,
        status=AccountStatus.PENDING_APPROVAL,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    logger.info(
        "account_request_registered",
        team=team_name,
        issue=issue_key,
        status="pending_approval",
    )

    await jira_service.add_comment(
        issue_key,
        f"✅ AWS Account request registered for team **{team_name}**.\n\n"
        f"Status: **Pending Approval**\n\n"
        f"An admin will review and approve this request. "
        f"Once approved, the account will be automatically provisioned with:\n"
        f"- OIDC role for GitHub Actions CI/CD\n"
        f"- Terraform state bucket\n"
        f"- Security baseline (CloudTrail, GuardDuty, encryption defaults)\n"
        f"- GitHub infra repo: {infra_request.github_group}/{infra_request.github_repo}\n\n"
        f"You'll be notified when the account is ready.",
    )

    return {
        "status": "pending_approval",
        "issue": issue_key,
        "request_type": "aws-account",
        "team_name": team_name,
        "message": "Account request registered. Awaiting admin approval.",
    }
