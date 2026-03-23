"""GrantBot — searches for funding opportunities and posts to Slack.

Usage:
    python -m src.agent.grantbot [--dry-run] [--channel funding-opportunities]

GrantBot is independent of the simulation engine. It:
1. Loads all researcher profiles to extract search keywords
2. Searches Grants.gov for open opportunities matching those keywords
3. Uses an LLM to score relevance and draft Slack posts
4. Posts to a Slack channel, tagging relevant researchers
5. Tracks posted opportunities to avoid duplicates
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer

from src.config import get_settings
from src.services.grants import search_opportunities, fetch_opportunity_detail

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

PROFILES_DIR = Path("profiles/public")
POSTED_LOG = Path("/tmp/grantbot_posted.json")

app = typer.Typer()


def _load_researcher_profiles() -> dict[str, dict[str, Any]]:
    """Load all public profiles and extract searchable fields.

    Returns {agent_id: {name, keywords, disease_areas, techniques, ...}}
    """
    profiles = {}
    for md_file in sorted(PROFILES_DIR.glob("*.md")):
        agent_id = md_file.stem
        text = md_file.read_text(encoding="utf-8")

        profile: dict[str, Any] = {"agent_id": agent_id, "raw": text}

        # Extract PI name from first heading
        for line in text.splitlines():
            if line.startswith("# ") and "Lab" in line:
                profile["name"] = line.replace("# ", "").replace(" Lab — Public Profile", "").strip()
                break

        # Extract keywords section
        profile["keywords"] = _extract_list_section(text, "Keywords")
        profile["disease_areas"] = _extract_list_section(text, "Disease Areas")
        profile["techniques"] = _extract_list_section(text, "Key Methods and Technologies")
        profile["targets"] = _extract_list_section(text, "Key Molecular Targets")

        profiles[agent_id] = profile

    logger.info("Loaded %d researcher profiles", len(profiles))
    return profiles


def _extract_list_section(text: str, section_name: str) -> list[str]:
    """Extract bullet-pointed or comma-separated items from a markdown section."""
    items = []
    in_section = False
    for line in text.splitlines():
        if section_name.lower() in line.lower() and line.startswith("##"):
            in_section = True
            continue
        if in_section:
            if line.startswith("##"):
                break
            line = line.strip()
            if line.startswith("- "):
                items.append(line[2:].strip())
            elif line and not line.startswith("#"):
                # Comma-separated keywords
                items.extend(kw.strip() for kw in line.split(",") if kw.strip())
    return items


def _build_search_queries(profiles: dict[str, dict]) -> list[str]:
    """Build a deduplicated set of search queries from all profiles.

    Prioritizes disease areas (best match for grant language), then
    high-level keywords. Avoids overly specific technique names that
    won't match FOA descriptions.
    """
    # Priority 1: Disease areas (most grant-relevant)
    priority_queries: list[str] = []
    seen: set[str] = set()

    for profile in profiles.values():
        for da in profile.get("disease_areas", []):
            simplified = da.split("(")[0].strip()
            if len(simplified.split()) <= 5 and simplified.lower() not in seen:
                seen.add(simplified.lower())
                priority_queries.append(simplified.lower())

    # Priority 2: Keywords (broader research themes)
    keyword_queries: list[str] = []
    for profile in profiles.values():
        for kw in profile.get("keywords", []):
            if len(kw.split()) <= 4 and kw.lower() not in seen:
                seen.add(kw.lower())
                keyword_queries.append(kw.lower())

    # Interleave: disease areas first, then keywords
    queries = priority_queries + keyword_queries
    logger.info(
        "Built %d search queries (%d disease areas, %d keywords)",
        len(queries), len(priority_queries), len(keyword_queries),
    )
    return queries


def _load_posted_log() -> set[str]:
    """Load the set of already-posted opportunity numbers."""
    if POSTED_LOG.exists():
        data = json.loads(POSTED_LOG.read_text(encoding="utf-8"))
        return set(data.get("posted", []))
    return set()


def _save_posted_log(posted: set[str]) -> None:
    """Save the set of posted opportunity numbers."""
    POSTED_LOG.parent.mkdir(parents=True, exist_ok=True)
    POSTED_LOG.write_text(
        json.dumps({"posted": sorted(posted), "updated_at": datetime.now(timezone.utc).isoformat()}),
        encoding="utf-8",
    )


async def _score_and_draft(
    opportunity: dict[str, Any],
    profiles: dict[str, dict],
) -> dict[str, Any] | None:
    """Use LLM to score relevance and draft a Slack post.

    Returns {post_text, relevant_agents, score} or None if not relevant.
    """
    from src.services.llm import generate_agent_response

    # Build a compact summary of all researcher interests
    researcher_lines = []
    for agent_id, profile in profiles.items():
        name = profile.get("name", agent_id)
        areas = ", ".join(profile.get("disease_areas", [])[:5])
        keywords = ", ".join(profile.get("keywords", [])[:5])
        researcher_lines.append(f"- **{name}** ({agent_id}): {areas}. Keywords: {keywords}")

    researchers_summary = "\n".join(researcher_lines)

    opp_text = f"""Title: {opportunity.get('title', '')}
Number: {opportunity.get('number', '')}
Agency: {opportunity.get('agency', '')}
Close Date: {opportunity.get('close_date', 'Not specified')}
Description: {opportunity.get('description', '')[:2000]}
Synopsis: {opportunity.get('synopsis', '')[:2000]}"""

    system_prompt = """You are GrantBot, an AI assistant that identifies relevant federal funding opportunities for researchers at Scripps Research.

Your task: evaluate whether a funding opportunity is relevant to any of the researchers listed below, and if so, draft a concise Slack post about it.

IMPORTANT RULES:
- Only flag opportunities that are genuinely relevant — a clear match between the FOA's scientific scope and a researcher's expertise
- Tag specific researchers who should pay attention (use their agent_id)
- Be concise: 3-5 sentences max describing the opportunity and why it's relevant
- If the opportunity is not relevant to any researcher, respond with just: {"relevant": false}
- Multi-PI or collaborative grants that could involve 2+ labs are especially worth flagging
- Use Slack mrkdwn formatting: *bold* (single asterisks), _italic_ (underscores). Do NOT use **double asterisks** or emoji.

Choose the best Slack channel for the post:
- "drug-repurposing" — drug repurposing, therapeutic development, pharmacology
- "structural-biology" — structural methods, cryo-EM, crystallography, molecular visualization
- "aging-and-longevity" — aging, longevity, neurodegeneration, age-related disease
- "single-cell-omics" — single-cell sequencing, transcriptomics, genomics, multiomics
- "chemical-biology" — chemical probes, proteomics, covalent ligands, ABPP
- "funding-opportunities" — broad/cross-cutting opportunities that don't fit a specific topic
- "general" — very broad opportunities relevant to many researchers

Respond in JSON format:
{
  "relevant": true/false,
  "score": 1-10,
  "relevant_agents": ["agent_id1", "agent_id2"],
  "channel": "funding-opportunities",
  "post_text": "the Slack post text"
}"""

    user_msg = f"""## Researchers at Scripps Research

{researchers_summary}

## Funding Opportunity

{opp_text}"""

    try:
        settings = get_settings()
        response = await generate_agent_response(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": user_msg}],
            model=settings.llm_agent_model_sonnet,
            max_tokens=500,
            log_meta={"agent_id": "grantbot", "phase": "score"},
        )

        # Parse JSON response — handle code fences and extra text
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if "```" in cleaned:
                cleaned = cleaned[:cleaned.index("```")]
            cleaned = cleaned.strip()
        # Find the first JSON object
        start = cleaned.find("{")
        if start >= 0:
            depth = 0
            for i, ch in enumerate(cleaned[start:], start):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        cleaned = cleaned[start:i + 1]
                        break

        result = json.loads(cleaned)
        if result.get("relevant") and result.get("score", 0) >= 4:
            return result
        return None
    except Exception as exc:
        logger.warning("LLM scoring failed for %s: %s", opportunity.get("number"), exc)
        return None


async def run_grantbot(
    channel: str = "funding-opportunities",
    dry_run: bool = False,
    max_queries: int = 30,
    max_posts: int = 10,
) -> list[dict]:
    """Main GrantBot pipeline.

    Returns list of posted opportunities.
    """
    settings = get_settings()

    # 1. Load researcher profiles
    profiles = _load_researcher_profiles()
    if not profiles:
        logger.error("No researcher profiles found in %s", PROFILES_DIR)
        return []

    # 2. Build search queries
    queries = _build_search_queries(profiles)
    if max_queries:
        queries = queries[:max_queries]

    # 3. Load already-posted log
    posted = _load_posted_log()
    logger.info("Already posted %d opportunities", len(posted))

    # 4. Search Grants.gov
    all_opps: dict[str, dict] = {}  # number -> opportunity
    for query in queries:
        try:
            opps = await search_opportunities(query, rows=10)
            for opp in opps:
                num = opp.get("number", "")
                if num and num not in posted and num not in all_opps:
                    all_opps[num] = opp
        except Exception as exc:
            logger.warning("Search failed for '%s': %s", query, exc)

    logger.info("Found %d new opportunities (after dedup and filtering posted)", len(all_opps))

    if not all_opps:
        logger.info("No new opportunities to process")
        return []

    # 5. Fetch details for top opportunities (limit API calls)
    detailed_opps = []
    for num, opp in list(all_opps.items())[:50]:
        if opp.get("id"):
            try:
                detail = await fetch_opportunity_detail(str(opp["id"]))
                if detail:
                    detailed_opps.append(detail)
                    continue
            except Exception as exc:
                logger.debug("Detail fetch failed for %s: %s", num, exc)
        detailed_opps.append(opp)

    # 6. Score and draft posts using LLM
    scored: list[dict] = []
    for opp in detailed_opps:
        result = await _score_and_draft(opp, profiles)
        if result:
            result["opportunity"] = opp
            scored.append(result)

    # Sort by score descending, take top N
    scored.sort(key=lambda x: x.get("score", 0), reverse=True)
    to_post = scored[:max_posts]

    logger.info("Scored %d opportunities, posting top %d", len(scored), len(to_post))

    # 7. Post to Slack (or dry-run)
    posted_list = []
    slack_client = None

    if not dry_run:
        from slack_sdk import WebClient
        bot_token = getattr(settings, "slack_bot_token_grantbot", "")
        if not bot_token or bot_token.startswith("xoxb-placeholder"):
            # Fall back to using SuBot's token for now
            bot_token = settings.slack_bot_token_su
            logger.info("No grantbot Slack token — using SuBot's token as fallback")
        if bot_token and not bot_token.startswith("xoxb-placeholder"):
            slack_client = WebClient(token=bot_token)

    for item in to_post:
        opp = item["opportunity"]
        opp_num = opp.get("number", "unknown")
        post_text = item.get("post_text", "")
        relevant_agents = item.get("relevant_agents", [])
        target_channel = item.get("channel", "funding-opportunities")

        # Build the full post
        close_date = opp.get("close_date", "Not specified")
        grants_url = f"https://www.grants.gov/search-results-detail/{opp.get('id', '')}"
        header = f":moneybag: *Funding Opportunity*\n*{opp.get('title', '')}*\n{opp_num} | Closes: {close_date}\n{grants_url}\n\n"
        full_post = header + post_text

        if relevant_agents:
            mentions = ", ".join(f"{aid.capitalize()} lab" for aid in relevant_agents)
            full_post += f"\n\n_Potentially relevant to: {mentions}_"

        if dry_run:
            logger.info("DRY RUN — would post to #%s:\n%s\n", target_channel, full_post)
        elif slack_client:
            try:
                slack_client.chat_postMessage(channel=f"#{target_channel}", text=full_post)
                logger.info("Posted opportunity %s to #%s", opp_num, target_channel)
            except Exception as exc:
                logger.error("Failed to post %s to #%s: %s", opp_num, target_channel, exc)
                continue

        posted.add(opp_num)
        posted_list.append({
            "number": opp_num,
            "title": opp.get("title"),
            "score": item.get("score"),
            "channel": target_channel,
        })

    # 8. Save posted log (only if not dry run)
    if not dry_run:
        _save_posted_log(posted)

    logger.info("GrantBot run complete: %d opportunities posted", len(posted_list))
    return posted_list


@app.command()
def main(
    channel: str = typer.Option("funding-opportunities", "--channel", help="Slack channel to post to"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview posts without sending to Slack"),
    max_queries: int = typer.Option(30, "--max-queries", help="Max number of search queries"),
    max_posts: int = typer.Option(10, "--max-posts", help="Max opportunities to post per run"),
):
    """Search for funding opportunities and post relevant ones to Slack."""
    results = asyncio.run(run_grantbot(
        channel=channel,
        dry_run=dry_run,
        max_queries=max_queries,
        max_posts=max_posts,
    ))
    if results:
        typer.echo(f"\nPosted {len(results)} opportunities:")
        for r in results:
            typer.echo(f"  [{r['score']}/10] {r['number']}: {r['title']}")
    else:
        typer.echo("No new relevant opportunities found.")


if __name__ == "__main__":
    app()
