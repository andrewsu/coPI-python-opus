# Email Reply Classification Prompt

You are classifying an email reply to a collaboration proposal notification sent by CoPI, a research collaboration platform.

The user was sent a proposal summary and asked to either:
1. Rate it 1-4 (with optional comments)
2. Give instructions for their AI agent to refine the proposal

## Classification Categories

### "review"
The reply contains a proposal rating (1-4) and optionally a comment.
- Look for numbers 1-4 anywhere in the reply
- Common patterns: "3", "Rating: 3", "I'd give this a 3", "3/4", "3 - looks promising"
- The rest of the text is the comment

### "instruction"
The reply describes what the user wants changed or refined about the proposal. There is no rating number.
- Common patterns: "Tell them to focus on...", "I want to explore the mitochondrial angle", "Ask them about...", "This needs more detail on..."
- Extract the full instruction text

### "unparseable"
Cannot determine whether this is a review or an instruction.
- Very short or ambiguous replies ("ok", "thanks", "interesting")
- Replies that seem unrelated to the proposal

## Output Format

Respond with only a JSON object:
```json
{"category": "review|instruction|unparseable", "rating": null or 1-4, "comment": "extracted comment or empty string", "instruction": "extracted instruction or empty string"}
```
