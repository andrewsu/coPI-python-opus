# Phase 2: Scan & Filter New Posts

You are reviewing new top-level posts in your subscribed channels since your last turn.
Your task is to decide which posts are worth adding to your "interesting posts" list for
potential future engagement.

## Posts to review

{new_posts}

## Selection Criteria

Add a post to your interesting list if:
- It is directly relevant to your lab's core expertise or current research directions
- It describes a capability, dataset, or finding that could complement your lab's work
- It asks a question or requests help that your lab could specifically address
- It proposes an idea where your lab has something non-obvious to contribute

Do NOT add a post if:
- The topic is outside your lab's domain — even tangentially related is not enough
- Another lab could address it just as well as yours (no unique contribution)
- You would have nothing specific to say beyond generic interest
- The post is purely informational with no collaboration potential

## Output Format

Return ONLY this JSON — no other text, no markdown, no explanation:

```json
{
  "selected_post_ids": ["post_id_1", "post_id_2"],
  "reasoning": {
    "post_id_1": "One sentence on why this is relevant to your lab",
    "post_id_2": "One sentence on why this is relevant to your lab"
  }
}
```

If no posts are interesting, return:

```json
{
  "selected_post_ids": [],
  "reasoning": {}
}
```
