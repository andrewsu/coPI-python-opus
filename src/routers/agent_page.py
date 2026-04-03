"""My Agent page router."""

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.dependencies import get_current_user
from src.models import (
    AgentMessage,
    AgentRegistry,
    ProposalReview,
    ResearcherProfile,
    ThreadDecision,
    User,
)
from src.services.profile_export import export_private_profile

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="templates")

PROFILES_DIR = Path("profiles")
SLACK_INVITE_URL = (
    "https://join.slack.com/t/labbot-workspace/shared_invite/"
    "zt-3sxfrrisw-t4hRz4aMfZZPxThxUaTGKA"
)


def _template_context(request: Request, user: User, **kwargs) -> dict:
    impersonated = getattr(user, "_is_impersonated", False)
    real_admin = getattr(user, "_real_admin", None)
    ctx = {
        "request": request,
        "current_user": real_admin if impersonated else user,
        "user": user,
        "impersonation_banner": user if impersonated else None,
        "active_page": "agent",
    }
    ctx.update(kwargs)
    return ctx


# --------------------------------------------------------------------------
# Main dashboard
# --------------------------------------------------------------------------


@router.get("", response_class=HTMLResponse)
async def my_agent(
    request: Request,
    slack_error: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """My Agent page — dispatches to one of three states."""
    # Look up agent record for this user
    result = await db.execute(
        select(AgentRegistry).where(AgentRegistry.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()

    if not agent:
        # State 1: No agent
        has_profile = (
            current_user.onboarding_complete
            and current_user.profile
            and current_user.profile.research_summary
        )
        return templates.TemplateResponse(
            request,
            "agent/request.html",
            _template_context(
                request, current_user, agent=None, has_profile=has_profile
            ),
        )

    if agent.status == "pending":
        # State 2: Pending approval
        return templates.TemplateResponse(
            request,
            "agent/request.html",
            _template_context(request, current_user, agent=agent),
        )

    # State 3: Active agent — show dashboard
    aid = agent.agent_id

    # Stats
    posts_count_result = await db.execute(
        select(func.count(AgentMessage.id)).where(
            AgentMessage.agent_id == aid,
            AgentMessage.phase == "new_post",
        )
    )
    posts_count = posts_count_result.scalar() or 0

    threads_count_result = await db.execute(
        select(func.count(distinct(AgentMessage.thread_ts))).where(
            AgentMessage.agent_id == aid,
            AgentMessage.phase == "thread_reply",
        )
    )
    threads_count = threads_count_result.scalar() or 0

    # Proposals where this agent is involved
    proposals_result = await db.execute(
        select(ThreadDecision)
        .where(
            ThreadDecision.outcome == "proposal",
            (ThreadDecision.agent_a == aid) | (ThreadDecision.agent_b == aid),
        )
        .order_by(ThreadDecision.decided_at.desc())
    )
    proposals = proposals_result.scalars().all()

    # Get existing reviews by this agent
    reviewed_ids_result = await db.execute(
        select(ProposalReview.thread_decision_id).where(
            ProposalReview.agent_id == aid
        )
    )
    reviewed_ids = {r[0] for r in reviewed_ids_result}

    # Separate into reviewed and unreviewed
    unreviewed = []
    reviewed = []
    for p in proposals:
        other = p.agent_b if p.agent_a == aid else p.agent_a
        entry = {"proposal": p, "other_agent": other}
        if p.id in reviewed_ids:
            # Get the review
            rev_result = await db.execute(
                select(ProposalReview).where(
                    ProposalReview.thread_decision_id == p.id,
                    ProposalReview.agent_id == aid,
                )
            )
            entry["review"] = rev_result.scalar_one_or_none()
            reviewed.append(entry)
        else:
            unreviewed.append(entry)

    # Private profile path
    private_profile_path = PROFILES_DIR / "private" / f"{aid}.md"
    has_private_profile = private_profile_path.exists()

    # Resolve delegate display names
    delegates = []
    if agent.delegate_slack_ids:
        delegates = _resolve_delegate_names(agent.delegate_slack_ids)

    return templates.TemplateResponse(
        request,
        "agent/dashboard.html",
        _template_context(
            request,
            current_user,
            agent=agent,
            posts_count=posts_count,
            threads_count=threads_count,
            proposals_total=len(proposals),
            unreviewed=unreviewed,
            reviewed=reviewed,
            has_private_profile=has_private_profile,
            slack_invite_url=SLACK_INVITE_URL,
            slack_error=slack_error,
            delegates=delegates,
            delegate_error=request.query_params.get("delegate_error"),
        ),
    )


# --------------------------------------------------------------------------
# Request an agent
# --------------------------------------------------------------------------


@router.post("/request")
async def request_agent(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit an agent request."""
    # Must have complete profile
    if not current_user.onboarding_complete or not current_user.profile:
        raise HTTPException(status_code=400, detail="Complete your profile first")

    # Check if already has an agent
    existing = await db.execute(
        select(AgentRegistry).where(AgentRegistry.user_id == current_user.id)
    )
    if existing.scalar_one_or_none():
        return RedirectResponse(url="/agent", status_code=302)

    # Create pending agent request
    # agent_id is the last name, lowercased, ASCII-only
    last_name = current_user.name.split()[-1].lower()
    agent_id = "".join(c for c in last_name if c.isalpha())

    # Ensure uniqueness — append first initial if collision
    collision = await db.execute(
        select(AgentRegistry).where(AgentRegistry.agent_id == agent_id)
    )
    if collision.scalar_one_or_none():
        first_initial = current_user.name[0].lower()
        agent_id = f"{first_initial}{agent_id}"

    agent = AgentRegistry(
        agent_id=agent_id,
        user_id=current_user.id,
        bot_name=f"{current_user.name.split()[-1]}Bot",
        pi_name=current_user.name,
        status="pending",
    )
    db.add(agent)
    await db.commit()

    return RedirectResponse(url="/agent", status_code=302)


# --------------------------------------------------------------------------
# Proposal review
# --------------------------------------------------------------------------


@router.post("/proposals/{thread_decision_id}/review")
async def review_proposal(
    thread_decision_id: uuid.UUID,
    request: Request,
    rating: int = Form(...),
    comment: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rate a proposal (1-4)."""
    if rating < 1 or rating > 4:
        raise HTTPException(status_code=400, detail="Rating must be 1-4")

    # Get agent for current user
    agent_result = await db.execute(
        select(AgentRegistry).where(AgentRegistry.user_id == current_user.id)
    )
    agent = agent_result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="No agent found")

    # Verify the thread decision exists and involves this agent
    td_result = await db.execute(
        select(ThreadDecision).where(ThreadDecision.id == thread_decision_id)
    )
    td = td_result.scalar_one_or_none()
    if not td:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if agent.agent_id not in (td.agent_a, td.agent_b):
        raise HTTPException(status_code=403, detail="Not your proposal")

    # Check for existing review
    existing = await db.execute(
        select(ProposalReview).where(
            ProposalReview.thread_decision_id == thread_decision_id,
            ProposalReview.agent_id == agent.agent_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already reviewed")

    review = ProposalReview(
        thread_decision_id=thread_decision_id,
        agent_id=agent.agent_id,
        user_id=current_user.id,
        rating=rating,
        comment=comment.strip() or None,
    )
    db.add(review)
    await db.commit()

    return RedirectResponse(url="/agent", status_code=302)


@router.post("/proposals/{thread_decision_id}/reopen")
async def reopen_proposal(
    thread_decision_id: uuid.UUID,
    request: Request,
    guidance: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reopen a proposal thread with PI guidance posted via the bot."""
    guidance = guidance.strip()
    if not guidance:
        raise HTTPException(status_code=400, detail="Guidance text is required")

    # Get agent for current user
    agent_result = await db.execute(
        select(AgentRegistry).where(AgentRegistry.user_id == current_user.id)
    )
    agent = agent_result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="No agent found")

    # Verify the thread decision exists and involves this agent
    td_result = await db.execute(
        select(ThreadDecision).where(ThreadDecision.id == thread_decision_id)
    )
    td = td_result.scalar_one_or_none()
    if not td:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if agent.agent_id not in (td.agent_a, td.agent_b):
        raise HTTPException(status_code=403, detail="Not your proposal")

    # Post guidance to Slack thread via the agent's bot token
    try:
        from slack_sdk import WebClient
        from src.config import get_settings
        settings = get_settings()
        env_tokens = settings.get_slack_tokens()
        bot_token = env_tokens.get(agent.agent_id, {}).get("bot")

        if not bot_token or bot_token.startswith("xoxb-placeholder"):
            raise HTTPException(status_code=500, detail="No bot token available")

        client = WebClient(token=bot_token)

        # Resolve channel name to ID
        channels_result = client.conversations_list(types="public_channel,private_channel", limit=200)
        channel_id = None
        for ch in channels_result.get("channels", []):
            if ch["name"] == td.channel:
                channel_id = ch["id"]
                break

        if not channel_id:
            raise HTTPException(status_code=500, detail=f"Channel #{td.channel} not found")

        # Post as the bot, attributing to PI
        message = f"*PI guidance from {current_user.name}:*\n\n{guidance}"
        client.chat_postMessage(
            channel=channel_id,
            text=message,
            thread_ts=td.thread_id,
        )
        logger.info(
            "PI %s posted guidance in proposal thread %s via %s",
            current_user.name, td.thread_id, agent.agent_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to post PI guidance to Slack: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to post to Slack: {str(exc)[:100]}")

    # Mark as reviewed (so the proposal thread poll picks it up and reopens)
    existing = await db.execute(
        select(ProposalReview).where(
            ProposalReview.thread_decision_id == thread_decision_id,
            ProposalReview.agent_id == agent.agent_id,
        )
    )
    if not existing.scalar_one_or_none():
        review = ProposalReview(
            thread_decision_id=thread_decision_id,
            agent_id=agent.agent_id,
            user_id=current_user.id,
            rating=0,  # 0 = reopened with guidance, not a rating
            comment=f"[Reopened] {guidance[:500]}",
        )
        db.add(review)
        await db.commit()

    return RedirectResponse(url="/agent", status_code=302)


# --------------------------------------------------------------------------
# Private profile view/edit
# --------------------------------------------------------------------------


@router.get("/profile", response_class=HTMLResponse)
async def view_private_profile(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """View agent's private profile."""
    agent_result = await db.execute(
        select(AgentRegistry).where(AgentRegistry.user_id == current_user.id)
    )
    agent = agent_result.scalar_one_or_none()
    if not agent or agent.status != "active":
        return RedirectResponse(url="/agent", status_code=302)

    profile_path = PROFILES_DIR / "private" / f"{agent.agent_id}.md"
    content = profile_path.read_text() if profile_path.exists() else ""

    return templates.TemplateResponse(
        request,
        "agent/profile.html",
        _template_context(
            request, current_user, agent=agent, profile_content=content, editing=False
        ),
    )


@router.get("/profile/edit", response_class=HTMLResponse)
async def edit_private_profile(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Edit agent's private profile."""
    agent_result = await db.execute(
        select(AgentRegistry).where(AgentRegistry.user_id == current_user.id)
    )
    agent = agent_result.scalar_one_or_none()
    if not agent or agent.status != "active":
        return RedirectResponse(url="/agent", status_code=302)

    profile_path = PROFILES_DIR / "private" / f"{agent.agent_id}.md"
    content = profile_path.read_text() if profile_path.exists() else ""

    return templates.TemplateResponse(
        request,
        "agent/profile.html",
        _template_context(
            request, current_user, agent=agent, profile_content=content, editing=True
        ),
    )


@router.post("/profile/save")
async def save_private_profile(
    request: Request,
    content: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save private profile to disk and database."""
    agent_result = await db.execute(
        select(AgentRegistry).where(AgentRegistry.user_id == current_user.id)
    )
    agent = agent_result.scalar_one_or_none()
    if not agent or agent.status != "active":
        return RedirectResponse(url="/agent", status_code=302)

    # Write to disk
    profile_path = PROFILES_DIR / "private" / f"{agent.agent_id}.md"
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(content)

    # Persist to DB
    profile_result = await db.execute(
        select(ResearcherProfile).where(ResearcherProfile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()
    if profile:
        profile.private_profile_md = content.strip() or None
        await db.commit()

    return RedirectResponse(url="/agent/profile", status_code=302)


# --------------------------------------------------------------------------
# Slack username
# --------------------------------------------------------------------------


@router.post("/slack")
async def connect_slack(
    request: Request,
    email: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Look up the PI's Slack user ID from their email address."""
    agent_result = await db.execute(
        select(AgentRegistry).where(AgentRegistry.user_id == current_user.id)
    )
    agent = agent_result.scalar_one_or_none()
    if not agent:
        return RedirectResponse(url="/agent", status_code=302)

    email = email.strip()
    slack_user_id = None
    error = None

    # Use any available bot token to do the lookup
    try:
        from slack_sdk import WebClient
        from src.config import get_settings
        settings = get_settings()
        env_tokens = settings.get_slack_tokens()

        # Find first valid bot token
        bot_token = None
        for tokens in env_tokens.values():
            t = tokens.get("bot", "")
            if t and not t.startswith("xoxb-placeholder"):
                bot_token = t
                break

        if not bot_token:
            error = "No Slack bot token available to perform lookup."
        else:
            client = WebClient(token=bot_token)
            result = client.users_lookupByEmail(email=email)
            slack_user_id = result["user"]["id"]
    except Exception as exc:
        error_msg = str(exc)
        if "users_not_found" in error_msg:
            error = f"No Slack user found with email {email}. Have you joined the workspace first?"
        else:
            logger.warning("Slack lookup failed for %s: %s", email, exc)
            error = f"Slack lookup failed: {error_msg[:100]}"

    if slack_user_id:
        agent.slack_user_id = slack_user_id
        await db.commit()
        return RedirectResponse(url="/agent", status_code=302)

    # Re-render dashboard with error
    # We need to rebuild the full dashboard context
    return RedirectResponse(
        url="/agent?slack_error=" + (error or "Unknown error"),
        status_code=302,
    )


def _get_bot_token() -> str | None:
    """Get the first valid Slack bot token for API calls."""
    from src.config import get_settings
    settings = get_settings()
    env_tokens = settings.get_slack_tokens()
    for tokens in env_tokens.values():
        t = tokens.get("bot", "")
        if t and not t.startswith("xoxb-placeholder"):
            return t
    return None


def _resolve_delegate_names(slack_ids: list[str]) -> list[dict]:
    """Resolve Slack user IDs to display names."""
    from slack_sdk import WebClient
    bot_token = _get_bot_token()
    if not bot_token:
        return [{"slack_id": sid, "name": sid} for sid in slack_ids]

    client = WebClient(token=bot_token)
    delegates = []
    for sid in slack_ids:
        try:
            info = client.users_info(user=sid)
            name = info["user"].get("real_name") or info["user"].get("name") or sid
            delegates.append({"slack_id": sid, "name": name})
        except Exception:
            delegates.append({"slack_id": sid, "name": sid})
    return delegates


# --------------------------------------------------------------------------
# Delegate management
# --------------------------------------------------------------------------


@router.post("/delegates/add")
async def add_delegate(
    request: Request,
    email: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a delegate Slack account to this agent."""
    agent_result = await db.execute(
        select(AgentRegistry).where(AgentRegistry.user_id == current_user.id)
    )
    agent = agent_result.scalar_one_or_none()
    if not agent or agent.status != "active":
        return RedirectResponse(url="/agent", status_code=302)

    email = email.strip()
    error = None

    try:
        from slack_sdk import WebClient
        bot_token = _get_bot_token()
        if not bot_token:
            error = "No Slack bot token available."
        else:
            client = WebClient(token=bot_token)
            result = client.users_lookupByEmail(email=email)
            slack_user_id = result["user"]["id"]

            # Don't add if it's the primary PI
            if slack_user_id == agent.slack_user_id:
                error = "That's your own account — no need to add as delegate."
            else:
                # Don't add duplicates
                current_delegates = list(agent.delegate_slack_ids or [])
                if slack_user_id in current_delegates:
                    error = "That account is already a delegate."
                else:
                    current_delegates.append(slack_user_id)
                    agent.delegate_slack_ids = current_delegates
                    await db.commit()
                    logger.info(
                        "Delegate %s added to agent %s by %s",
                        slack_user_id, agent.agent_id, current_user.name,
                    )
                    return RedirectResponse(url="/agent", status_code=302)
    except Exception as exc:
        error_msg = str(exc)
        if "users_not_found" in error_msg:
            error = f"No Slack user found with email {email}."
        else:
            logger.warning("Delegate lookup failed for %s: %s", email, exc)
            error = f"Lookup failed: {error_msg[:100]}"

    return RedirectResponse(
        url="/agent?delegate_error=" + (error or "Unknown error"),
        status_code=302,
    )


@router.post("/delegates/{slack_user_id}/remove")
async def remove_delegate(
    slack_user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a delegate Slack account from this agent."""
    agent_result = await db.execute(
        select(AgentRegistry).where(AgentRegistry.user_id == current_user.id)
    )
    agent = agent_result.scalar_one_or_none()
    if not agent or agent.status != "active":
        return RedirectResponse(url="/agent", status_code=302)

    current_delegates = list(agent.delegate_slack_ids or [])
    if slack_user_id in current_delegates:
        current_delegates.remove(slack_user_id)
        agent.delegate_slack_ids = current_delegates if current_delegates else None
        await db.commit()
        logger.info(
            "Delegate %s removed from agent %s by %s",
            slack_user_id, agent.agent_id, current_user.name,
        )

    return RedirectResponse(url="/agent", status_code=302)
