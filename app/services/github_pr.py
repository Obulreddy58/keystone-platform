"""
GitHub Service — fetches templates from the iac org's module repos
and creates pull requests in the customer's team-specific infra repo.

Architecture:
  - iac org:   contains terraform module repos (e.g. iac/terraform-aws-vpc)
               each repo has a template/ dir with .hcl.j2 files
  - team repo: each team has their own infra repo (e.g. payments-team/infra)
               the API pushes rendered files here and opens a PR
"""

from __future__ import annotations

import base64
from pathlib import Path

import structlog
from github import Auth, Github, GithubException

from app.config import settings

logger = structlog.get_logger()


class GitHubService:
    """Fetches templates from iac org and creates PRs in team repos."""

    def __init__(self) -> None:
        self._gh = None

    def _client(self) -> Github:
        """Lazy-init the GitHub client so the app starts even without a token."""
        if self._gh is None:
            if not settings.github_token:
                raise RuntimeError("SELF_SERVICE_GITHUB_TOKEN is not set")
            auth = Auth.Token(settings.github_token)
            self._gh = Github(auth=auth)
        return self._gh

    # ─── Template Fetching (from iac org) ────────────────────────────────────

    def fetch_module_templates(self, module_name: str) -> dict[str, str]:
        """
        Fetch all template files from an iac module repo.

        For module_name="vpc", fetches from:
          iac/terraform-aws-vpc/template/**/*.j2

        Returns:
            dict of {relative_path: file_content}
            e.g. {"terragrunt.hcl.j2": "...", "vpc/terragrunt.hcl.j2": "..."}
        """
        repo_name = f"{settings.iac_github_org}/{settings.iac_repo_prefix}-{module_name}"
        template_dir = settings.iac_template_dir

        logger.info("fetching_templates", repo=repo_name, dir=template_dir)

        try:
            repo = self._client().get_repo(repo_name)
        except GithubException as e:
            raise FileNotFoundError(
                f"Module repo not found: {repo_name}"
            ) from e

        templates: dict[str, str] = {}
        self._fetch_dir_recursive(
            repo=repo,
            path=template_dir,
            ref=settings.iac_template_ref,
            base_path=template_dir,
            result=templates,
        )

        if not templates:
            raise FileNotFoundError(
                f"No template files found in {repo_name}/{template_dir}/"
            )

        logger.info(
            "templates_fetched",
            repo=repo_name,
            file_count=len(templates),
        )
        return templates

    def _fetch_dir_recursive(
        self,
        repo,
        path: str,
        ref: str,
        base_path: str,
        result: dict[str, str],
    ) -> None:
        """Recursively fetch all .j2 files from a GitHub directory."""
        try:
            contents = repo.get_contents(path, ref=ref)
        except GithubException:
            return

        if not isinstance(contents, list):
            contents = [contents]

        for item in contents:
            if item.type == "dir":
                self._fetch_dir_recursive(repo, item.path, ref, base_path, result)
            elif item.name.endswith(".j2"):
                # Relative path from the template/ directory
                rel_path = item.path
                if rel_path.startswith(base_path + "/"):
                    rel_path = rel_path[len(base_path) + 1:]

                content = base64.b64decode(item.content).decode("utf-8")
                result[rel_path] = content

    def fetch_blueprint_modules(self, module_names: list[str]) -> dict[str, dict[str, str]]:
        """
        Fetch templates from multiple module repos for a blueprint.

        For an EKS cluster blueprint that needs vpc + eks + eks-addons:
          module_names = ["vpc", "eks", "eks-addons"]

        Returns:
            dict of {module_name: {relative_path: file_content}}
        """
        all_templates: dict[str, dict[str, str]] = {}
        for module_name in module_names:
            all_templates[module_name] = self.fetch_module_templates(module_name)
        return all_templates

    # ─── PR Creation (in team's repo) ────────────────────────────────────────

    def ensure_repo_exists(
        self,
        *,
        github_group: str,
        github_repo: str,
    ) -> bool:
        """
        Ensure the target repo exists and is properly bootstrapped with:
        - Root terragrunt.hcl (S3 backend + provider with assume_role)
        - GitHub Actions workflows copied from keystone-workflows repo

        Returns True if the repo was just created, False if it already existed.
        """
        repo_full = f"{github_group}/{github_repo}"
        client = self._client()

        # Check if repo already exists
        existing_repo = None
        try:
            existing_repo = client.get_repo(repo_full)
            logger.info("repo_exists", repo=repo_full)
        except GithubException as e:
            if e.status != 404:
                raise

        if existing_repo:
            # Repo exists — verify bootstrap files are present
            self._ensure_bootstrap_files(existing_repo, repo_full)
            return False

        # Repo doesn't exist — create it
        logger.info("creating_repo", repo=repo_full)
        user = client.get_user()
        new_repo = user.create_repo(
            name=github_repo,
            description=f"Infrastructure-as-Code repo for {github_group} — managed by Keystone IDP",
            auto_init=True,
            private=False,
        )

        self._bootstrap_repo(new_repo, repo_full)
        logger.info("repo_created_and_bootstrapped", repo=repo_full)
        return True

    def _ensure_bootstrap_files(self, repo, repo_full: str) -> None:
        """Check if root terragrunt.hcl exists; if not, create it."""
        try:
            repo.get_contents("terragrunt.hcl")
        except GithubException as e:
            if e.status == 404:
                logger.info("bootstrap_missing", repo=repo_full)
                self._bootstrap_repo(repo, repo_full)
            else:
                raise

    def _bootstrap_repo(self, repo, repo_full: str) -> None:
        """Bootstrap a repo with root terragrunt.hcl + GitHub Actions workflows."""
        root_tg = (
            '# Root terragrunt.hcl — Keystone Infra-Live\n'
            '# Reads account.hcl / env.hcl / region.hcl from the directory hierarchy\n'
            '# and auto-configures S3 backend, provider, and assume_role.\n'
            '#\n'
            '# Directory layout:\n'
            '#   terragrunt.hcl           <- this file\n'
            '#   {team}/account.hcl       <- account_id, account_name\n'
            '#   {team}/{env}/env.hcl     <- environment\n'
            '#   {team}/{env}/{region}/region.hcl <- aws_region\n'
            '#   {team}/{env}/{region}/{module}/{resource}/terragrunt.hcl <- module\n'
            '\n'
            'locals {\n'
            '  account_vars = read_terragrunt_config(find_in_parent_folders("account.hcl"))\n'
            '  env_vars     = read_terragrunt_config(find_in_parent_folders("env.hcl"))\n'
            '  region_vars  = read_terragrunt_config(find_in_parent_folders("region.hcl"))\n'
            '\n'
            '  account_id   = local.account_vars.locals.account_id\n'
            '  account_name = local.account_vars.locals.account_name\n'
            '  environment  = local.env_vars.locals.environment\n'
            '  aws_region   = local.region_vars.locals.aws_region\n'
            '}\n'
            '\n'
            '# S3 backend — one state bucket per AWS account\n'
            'remote_state {\n'
            '  backend = "s3"\n'
            '  generate = {\n'
            '    path      = "backend.tf"\n'
            '    if_exists = "overwrite_terragrunt"\n'
            '  }\n'
            '  config = {\n'
            '    bucket         = "keystone-tfstate-${local.account_id}"\n'
            '    key            = "${path_relative_to_include()}/terraform.tfstate"\n'
            '    region         = local.aws_region\n'
            '    encrypt        = true\n'
            '    dynamodb_table = "keystone-tfstate-lock"\n'
            '  }\n'
            '}\n'
            '\n'
            '# AWS provider — assumes role into the target account\n'
            'generate "provider" {\n'
            '  path      = "provider.tf"\n'
            '  if_exists = "overwrite_terragrunt"\n'
            '  contents  = <<EOF\n'
            'provider "aws" {\n'
            '  region = "${local.aws_region}"\n'
            '\n'
            '  assume_role {\n'
            '    role_arn = "arn:aws:iam::${local.account_id}:role/GithubActionsRole"\n'
            '  }\n'
            '\n'
            '  default_tags {\n'
            '    tags = {\n'
            '      ManagedBy   = "terragrunt"\n'
            '      Platform    = "keystone"\n'
            '      Environment = "${local.environment}"\n'
            '      Account     = "${local.account_name}"\n'
            f'      Repository  = "{repo_full}"\n'
            '    }\n'
            '  }\n'
            '}\n'
            'EOF\n'
            '}\n'
        )

        # Create or update root terragrunt.hcl
        try:
            existing = repo.get_contents("terragrunt.hcl")
            repo.update_file(
                path="terragrunt.hcl",
                message="chore: update root terragrunt.hcl with account hierarchy",
                content=root_tg,
                sha=existing.sha,
            )
        except GithubException as e:
            if e.status == 404:
                repo.create_file(
                    path="terragrunt.hcl",
                    message="chore: bootstrap root terragrunt.hcl with S3 backend + assume_role",
                    content=root_tg,
                )
            else:
                raise

        # Copy the 3 caller workflows (they invoke reusable workflows from central repo)
        workflows_dir = Path(__file__).parent.parent.parent / "workflows"
        caller_files = [
            "pull-request.yaml",
            "deploy.yaml",
            "destroy.yaml",
        ]
        for wf_name in caller_files:
            wf_local = workflows_dir / wf_name
            wf_path = f".github/workflows/{wf_name}"
            try:
                # Skip if already exists
                repo.get_contents(wf_path)
                continue
            except GithubException:
                pass
            try:
                content = wf_local.read_text(encoding="utf-8")
                repo.create_file(
                    path=wf_path,
                    message=f"ci: add {wf_name} (calls keystone-workflows)",
                    content=content,
                )
                logger.info("workflow_added", file=wf_path, repo=repo_full)
            except Exception as e:
                logger.warning("workflow_add_failed", file=wf_path, error=str(e), repo=repo_full)

        logger.info("repo_created_and_bootstrapped", repo=repo_full)
        return True

    def create_pull_request(
        self,
        *,
        github_group: str,
        github_repo: str,
        branch_name: str,
        title: str,
        body: str,
        files: dict[str, str],
        labels: list[str] | None = None,
    ) -> str:
        """
        Create a branch, commit rendered files, and open a PR in the team's repo.

        Args:
            github_group: Team's GitHub org (e.g. "payments-team")
            github_repo: Team's infra repo name (e.g. "infra")
            branch_name: New branch name
            title: PR title
            body: PR description
            files: dict of {file_path: file_content} to commit
            labels: optional labels

        Returns:
            The PR URL
        """
        repo_full_name = f"{github_group}/{github_repo}"
        base_branch = settings.github_base_branch

        logger.info("creating_pr", repo=repo_full_name, branch=branch_name)

        try:
            repo = self._client().get_repo(repo_full_name)
        except GithubException as e:
            raise ValueError(
                f"Team repo not found: {repo_full_name}. "
                f"Ensure the repo exists and the GitHub token has access."
            ) from e

        # 1. Get the latest commit SHA on the base branch
        base_ref = repo.get_branch(base_branch)
        base_sha = base_ref.commit.sha

        # 2. Create the new branch
        try:
            repo.create_git_ref(
                ref=f"refs/heads/{branch_name}",
                sha=base_sha,
            )
        except GithubException as e:
            if e.status == 422:  # branch already exists
                logger.warning("branch_exists", branch=branch_name, repo=repo_full_name)
            else:
                raise

        # 3. Commit all files to the new branch
        for file_path, content in files.items():
            try:
                existing = repo.get_contents(file_path, ref=branch_name)
                repo.update_file(
                    path=file_path,
                    message=f"Update {file_path}",
                    content=content,
                    sha=existing.sha,
                    branch=branch_name,
                )
            except GithubException as e:
                if e.status == 404:
                    repo.create_file(
                        path=file_path,
                        message=f"Add {file_path}",
                        content=content,
                        branch=branch_name,
                    )
                else:
                    raise

            logger.info("file_committed", path=file_path, repo=repo_full_name)

        # 4. Create the Pull Request
        pr = repo.create_pull(
            title=title,
            body=body,
            head=branch_name,
            base=base_branch,
        )

        # 5. Add labels
        if labels:
            try:
                pr.add_to_labels(*labels)
            except GithubException:
                logger.warning("labels_failed", labels=labels, repo=repo_full_name)

        logger.info("pr_created", pr_url=pr.html_url, repo=repo_full_name)

        # Auto-merge is handled by the pull-request.yaml workflow:
        # PR created → plan runs → plan succeeds → workflow auto-merges → deploy runs
        return pr.html_url


github_service = GitHubService()
