"""Profile revision tracking service.

Records every change to public profiles, private profiles, and working memory
with full attribution (who, how, when).
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.profile_revision import ProfileRevision

logger = logging.getLogger(__name__)


async def create_revision(
    db: AsyncSession,
    *,
    agent_registry_id: uuid.UUID,
    profile_type: str,
    content: str,
    changed_by_user_id: uuid.UUID | None = None,
    mechanism: str,
    change_summary: str | None = None,
) -> ProfileRevision:
    """Create a profile revision record.

    Args:
        db: Database session.
        agent_registry_id: The AgentRegistry UUID.
        profile_type: One of "public", "private", "memory".
        content: Full markdown content after the change.
        changed_by_user_id: The user who initiated the change (None for agent/system).
        mechanism: One of "web", "slack_dm", "agent", "pipeline", "monthly_refresh".
        change_summary: Optional short description of what changed.

    Returns:
        The created ProfileRevision.
    """
    revision = ProfileRevision(
        agent_registry_id=agent_registry_id,
        profile_type=profile_type,
        content=content,
        changed_by_user_id=changed_by_user_id,
        mechanism=mechanism,
        change_summary=change_summary,
    )
    db.add(revision)
    await db.flush()
    logger.debug(
        "Created %s profile revision for agent %s via %s",
        profile_type, agent_registry_id, mechanism,
    )
    return revision


async def get_revision_history(
    db: AsyncSession,
    *,
    agent_registry_id: uuid.UUID,
    profile_type: str,
    limit: int = 50,
) -> list[ProfileRevision]:
    """Get revision history for a profile, most recent first.

    Args:
        db: Database session.
        agent_registry_id: The AgentRegistry UUID.
        profile_type: One of "public", "private", "memory".
        limit: Maximum number of revisions to return.

    Returns:
        List of ProfileRevision ordered by created_at descending.
    """
    result = await db.execute(
        select(ProfileRevision)
        .where(
            ProfileRevision.agent_registry_id == agent_registry_id,
            ProfileRevision.profile_type == profile_type,
        )
        .order_by(ProfileRevision.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
