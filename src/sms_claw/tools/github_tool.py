"""GitHub tools — search repos and create issues."""

from __future__ import annotations

from langchain_core.tools import tool

from sms_claw.core.config import get_settings
from sms_claw.core.logging import get_logger
from sms_claw.tools.registry import register_tool

log = get_logger(__name__)
_s = get_settings()


def _gh():  # type: ignore[return]
    if not _s.github_token:
        return None
    from github import Github  # type: ignore[import-untyped]

    return Github(_s.github_token)


@register_tool
@tool
def github_search(query: str) -> str:
    """Search GitHub for repositories. Returns top 3 results with star counts."""
    gh = _gh()
    if not gh:
        return "GitHub not configured. Set GITHUB_TOKEN."
    try:
        repos = list(gh.search_repositories(query=query, sort="stars", order="desc"))[
            :3
        ]
        return (
            "\n".join(
                f"- {r.full_name} ⭐{r.stargazers_count}: {r.description or 'No description'}"
                for r in repos
            )
            or "No results."
        )
    except Exception as exc:
        log.error("github_search_error", error=str(exc), exc_info=True)
        return f"GitHub search failed: {exc}"


@register_tool
@tool
def github_create_issue(repo: str, title: str, body: str) -> str:
    """
    Create a GitHub issue. 'repo' must be 'owner/repo-name'.
    Always confirm with the user before creating.
    """
    gh = _gh()
    if not gh:
        return "GitHub not configured. Set GITHUB_TOKEN."
    try:
        issue = gh.get_repo(repo).create_issue(title=title, body=body)
        log.info("github_issue_created", repo=repo, issue=issue.number)
        return f"Issue #{issue.number} created: {issue.html_url}"
    except Exception as exc:
        log.error("github_issue_error", repo=repo, error=str(exc), exc_info=True)
        return f"Failed to create issue: {exc}"
