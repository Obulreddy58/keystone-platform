"""
Template Renderer — loads Jinja2 templates from the local app/templates/
directory, renders them with user-provided values, and returns files ready
to be committed to the keystone-infra-live repo.

Flow:
  1. Determine which modules are needed for the request type (blueprint)
  2. Load .j2 template files from app/templates/{request_type}/**
  3. Render templates with Jinja2 using user-provided values
  4. Return dict of {file_path_in_infra_live_repo: rendered_content}

The rendered files land in keystone-infra-live at paths like:
  {team_name}/{environment}/{region}/{request_type}/{resource_name}/terragrunt.hcl
"""

from __future__ import annotations

from pathlib import Path

import structlog
from jinja2 import BaseLoader, Environment, StrictUndefined

from app.config import settings
from app.models.requests import InfraRequest

logger = structlog.get_logger()

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

BLUEPRINTS: dict[str, list[str]] = {
    "eks-cluster":      ["vpc", "eks", "eks-addons"],
    "rds-database":     ["rds"],
    "s3-bucket":        ["s3"],
    "ecs-service":      ["vpc", "ecs-fargate", "alb"],
    "redis":            ["elasticache"],
    "lambda":           ["lambda"],
    "dynamodb":         ["dynamodb"],
    "msk":              ["vpc", "msk"],
    "route53":          ["route53"],
    "vpc":              ["vpc"],
    "xcr-onboarding":   ["xcr-onboarding"],
    "sre-onboarding":   ["vpc-peering", "observability-stack"],
    "eks-upgrade":      ["control-plane", "addons", "node-groups"],
    "aws-account":      ["account-factory", "account-baseline"],
    "argocd-onboarding": ["argocd-project", "argocd-applicationset", "helm-charts", "env-values"],
    "documentdb-database": ["documentdb"],
    "iceberg-table": ["glue-iceberg", "s3-datalake"],
    "vector-store": ["vector-store"],
    "lake-formation": ["lake-formation"],
    "data-access": ["data-access-iam"],
    "data-classification": ["macie-classification"],
    "cross-account-share": ["ram-share"],
}


class TemplateRenderer:
    """Loads local Jinja2 templates, renders with user values."""

    def __init__(self) -> None:
        self._jinja_env = Environment(
            loader=BaseLoader(),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, request: InfraRequest) -> dict[str, str]:
        """
        Load local templates for the request type, render with user values.

        Returns:
            dict mapping file path (in infra-live repo) → rendered content
            e.g. {"platform/prod/eu-central-1/vpc/keystone/terragrunt.hcl": "..."}
        """
        request_type = getattr(request, "request_type", None)
        if not request_type:
            raise ValueError("Request model must have a request_type field")

        if request_type not in BLUEPRINTS:
            raise ValueError(f"No blueprint defined for request type: {request_type}")

        # 1. Load .j2 templates from local app/templates/{request_type}/
        template_dir = TEMPLATES_DIR / request_type
        if not template_dir.is_dir():
            raise FileNotFoundError(
                f"No template directory found: {template_dir}"
            )

        all_templates = self._load_local_templates(template_dir)
        if not all_templates:
            raise FileNotFoundError(
                f"No .j2 template files found in {template_dir}"
            )

        logger.info(
            "templates_loaded",
            request_type=request_type,
            file_count=len(all_templates),
        )

        # 2. Build context from request model
        context = request.model_dump()
        context["aws_region"] = settings.default_aws_region
        context["iac_github_org"] = settings.iac_github_org
        context["iac_repo_prefix"] = settings.iac_repo_prefix
        context["iac_template_ref"] = settings.iac_template_ref

        resource_name = self._get_resource_name(request)
        env_label = request.environment or "default"
        region = settings.default_aws_region
        rendered_files: dict[str, str] = {}

        # 3. Render each template
        for template_rel_path, template_content in all_templates.items():
            try:
                tmpl = self._jinja_env.from_string(template_content)
                rendered = tmpl.render(**context)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to render {request_type}/{template_rel_path}: {e}"
                ) from e

            # Build the output file path in keystone-infra-live repo
            # Strip .j2 suffix
            output_path = template_rel_path.removesuffix(".j2")

            # Replace placeholders
            output_path = output_path.replace("__env__", env_label)
            output_path = output_path.replace("__name__", resource_name)

            # Path pattern: {team}/{env}/{region}/{module_dir}/{resource}/file
            # template_rel_path is like "vpc/terragrunt.hcl.j2" or "terragrunt.hcl.j2"
            if "/" in output_path:
                # Template has subdirectory structure (e.g. vpc/terragrunt.hcl)
                module_dir = output_path.split("/")[0]
                filename = "/".join(output_path.split("/")[1:])
                repo_path = f"{request.team_name}/{env_label}/{region}/{module_dir}/{resource_name}/{filename}"
            else:
                # Single file, use request_type as module dir
                repo_path = f"{request.team_name}/{env_label}/{region}/{request_type}/{resource_name}/{output_path}"

            repo_path = repo_path.replace("\\", "/")
            rendered_files[repo_path] = rendered

            logger.info(
                "template_rendered",
                template=template_rel_path,
                output=repo_path,
            )

        # 4. Generate hierarchy files (account.hcl, env.hcl, region.hcl)
        account_id = getattr(request, "account_id", "") or context.get("account_id", "")
        team = request.team_name or "default"

        # {team}/account.hcl
        account_hcl_path = f"{team}/account.hcl"
        rendered_files[account_hcl_path] = (
            f"# Account configuration — {team}\n"
            f"# Auto-generated by Keystone Platform\n\n"
            f"locals {{\n"
            f'  account_name = "{team}"\n'
            f'  account_id   = "{account_id}"\n'
            f"}}\n"
        )

        # {team}/{env}/env.hcl
        env_hcl_path = f"{team}/{env_label}/env.hcl"
        rendered_files[env_hcl_path] = (
            f"# Environment configuration\n"
            f"# Auto-generated by Keystone Platform\n\n"
            f"locals {{\n"
            f'  environment = "{env_label}"\n'
            f"}}\n"
        )

        # {team}/{env}/{region}/region.hcl
        region_hcl_path = f"{team}/{env_label}/{region}/region.hcl"
        rendered_files[region_hcl_path] = (
            f"# Region configuration\n"
            f"# Auto-generated by Keystone Platform\n\n"
            f"locals {{\n"
            f'  aws_region = "{region}"\n'
            f"}}\n"
        )

        logger.info(
            "hierarchy_files_generated",
            account_hcl=account_hcl_path,
            env_hcl=env_hcl_path,
            region_hcl=region_hcl_path,
        )

        return rendered_files

    def _load_local_templates(self, template_dir: Path) -> dict[str, str]:
        """Recursively load all .j2 files from a local directory."""
        templates: dict[str, str] = {}
        for j2_file in sorted(template_dir.rglob("*.j2")):
            rel_path = j2_file.relative_to(template_dir).as_posix()
            templates[rel_path] = j2_file.read_text(encoding="utf-8")
        return templates

    @staticmethod
    def _get_resource_name(request: InfraRequest) -> str:
        """Extract the primary resource name from a request."""
        for field in [
            "cluster_name", "db_name", "bucket_name", "service_name",
            "function_name", "table_name", "vpc_name", "domain_name",
            "account_name", "summary", "store_name", "data_lake_name",
            "access_name", "classification_name", "share_name", "database_name",
        ]:
            name = getattr(request, field, None)
            if name:
                return name
        return f"{request.team_name}-{getattr(request, 'request_type', 'resource')}"


renderer = TemplateRenderer()
