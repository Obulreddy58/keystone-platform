"""
Jira Service — fetches ticket details and updates tickets with status/PR links.
Uses Jira REST API v3 with API token auth.
"""

from __future__ import annotations

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()


class JiraService:
    """Interacts with Jira Service Management REST API."""

    def __init__(self) -> None:
        self._base_url = settings.jira_base_url.rstrip("/") if settings.jira_base_url else ""
        self._auth = (settings.jira_user_email, settings.jira_api_token)

    def _check_configured(self) -> None:
        if not self._base_url:
            logger.warning("jira_not_configured", msg="JIRA_BASE_URL is empty, skipping Jira call")

    async def get_issue(self, issue_key: str) -> dict:
        """Fetch full issue details including custom fields."""
        if not self._base_url:
            return {}
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/rest/api/3/issue/{issue_key}",
                auth=self._auth,
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            return resp.json()

    async def add_comment(self, issue_key: str, message: str) -> None:
        """Add a comment to a Jira issue (ADF format)."""
        if not self._base_url:
            logger.warning("jira_skip_comment", issue=issue_key, msg="Jira not configured")
            return
        body = {
            "body": {
                "version": 1,
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": message}],
                    }
                ],
            }
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/rest/api/3/issue/{issue_key}/comment",
                auth=self._auth,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            resp.raise_for_status()

        logger.info("jira_comment_added", issue=issue_key)

    async def transition_issue(self, issue_key: str, transition_name: str) -> None:
        """Move an issue to a new status (e.g., 'In Progress', 'Pending Approval')."""
        if not self._base_url:
            logger.warning("jira_skip_transition", issue=issue_key, msg="Jira not configured")
            return
        async with httpx.AsyncClient() as client:
            # Get available transitions
            resp = await client.get(
                f"{self._base_url}/rest/api/3/issue/{issue_key}/transitions",
                auth=self._auth,
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            transitions = resp.json()["transitions"]

            # Find the matching transition
            target = next(
                (t for t in transitions if t["name"].lower() == transition_name.lower()),
                None,
            )
            if not target:
                available = [t["name"] for t in transitions]
                logger.warning(
                    "transition_not_found",
                    issue=issue_key,
                    target=transition_name,
                    available=available,
                )
                return

            # Execute the transition
            resp = await client.post(
                f"{self._base_url}/rest/api/3/issue/{issue_key}/transitions",
                auth=self._auth,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json={"transition": {"id": target["id"]}},
            )
            resp.raise_for_status()

        logger.info("jira_transition", issue=issue_key, status=transition_name)


jira_service = JiraService()
