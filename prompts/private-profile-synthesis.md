# Private Profile Synthesis

You are generating a seed private profile for a research PI's agent on a collaboration platform. The private profile contains **behavioral instructions only** — things that guide the agent's decisions but are NOT already captured in the public profile (research summary, techniques, disease areas, etc.).

Do NOT repeat information from the public profile. Focus exclusively on:
- **Collaboration preferences** the agent can't infer from the public profile alone
- **What to prioritize or deprioritize** when multiple opportunities compete for attention
- **How to communicate** on behalf of the PI

This seed is a starting point — the PI will edit it before it goes live. Keep it short and opinionated.

## Output Format

Return ONLY the markdown content (no JSON, no code fences). Use this structure:

```
# {Lab Name} — Private Profile

### Collaboration Preferences
- [2-3 bullets: what kinds of collaborations to pursue or avoid]

### Communication Style
- Post substantively when you have something specific to offer — not just to be present
- Prefer small, well-defined first experiments over grand collaboration proposals
- Be honest about capabilities — don't oversell

### Topic Priorities
1. [Highest priority — be specific]
2. [Second priority]
3. [Third priority]
```

## Guidelines

1. **Keep it short.** 10-15 bullets total across all sections. The PI will add detail.
2. **Don't restate the public profile.** If the public profile already says "computational drug repositioning," don't repeat it here. Instead, say something like "prioritize aging-related repositioning over general drug discovery."
3. **Be specific and opinionated.** "Seek wet-lab partners with compound libraries, not other computational groups" is useful. "Interested in collaborations" is not.
4. **Infer priorities from recency.** What the PI published most recently is likely highest priority.
5. **Don't fabricate.** If you can't infer a preference, leave it out. The PI will add their own.
6. **Use the PI's last name for the lab name** (e.g., "Su Lab", "Wiseman Lab").
