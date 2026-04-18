"""
Self-Service Infrastructure API — Configuration
Loads from environment variables (12-factor app).
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    app_name: str = "infra-self-service"
    debug: bool = False

    # Jira
    jira_base_url: str = ""  # https://yourcompany.atlassian.net
    jira_api_token: str = ""
    jira_user_email: str = ""
    jira_webhook_secret: str = ""  # shared secret to validate incoming webhooks

    # GitHub
    github_token: str = ""  # PAT or GitHub App token with cross-org access
    github_base_branch: str = "main"

    # GitHub — IAC org (where Terraform module templates live)
    iac_github_org: str = "Obulreddy58"  # org/user that contains all terraform module repos

    # Module repo naming convention in the iac org
    # e.g. Obulreddy58/keystone-modules
    iac_repo_prefix: str = "keystone-modules"

    # Branch/tag to fetch templates from (use tag for pinned versions)
    iac_template_ref: str = "main"

    # Directory inside each module repo that contains the terragrunt template files
    iac_template_dir: str = "template"

    # Infra-live repo — where rendered terragrunt files land as PRs
    infra_live_repo: str = "keystone-infra-live"  # repo name under iac_github_org

    # AWS
    default_aws_region: str = "eu-central-1"
    aws_account_id: str = "751106206844"
    aws_role_arn: str = "arn:aws:iam::751106206844:role/GithubActionsRole"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/selfservice"

    # Auth
    jwt_secret: str = "ux5Yi8V8wU/8rShF7BHeKM0Etp2zOAQ2rbRJcHJRf/xq4YqZqaLds6zfU8XA3vWI"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480  # 8 hours

    model_config = {"env_prefix": "SELF_SERVICE_", "case_sensitive": False}


settings = Settings()
