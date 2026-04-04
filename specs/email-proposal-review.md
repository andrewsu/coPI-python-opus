# Email-Based Proposal Review Specification

## Overview

When an agent produces a `:memo:` collaboration proposal, the PI's agent is blocked until the proposal is reviewed. Currently, review requires logging into the web app. This feature adds email notifications that nudge PIs and delegates to review pending proposals, and allows them to review or give agent instructions entirely via email reply.

Email is a **periodic nudge** — Slack DMs remain the immediate notification channel (per pi-interaction.md). Emails are sent at a user-configurable frequency as reminders for unreviewed proposals.

## Email Notification Flow

### Trigger

A notification cycle is triggered on a schedule (cron or worker loop) that checks each user's configured frequency. When a user's next scheduled email time arrives:

1. Query all unreviewed proposals for agents the user has access to (as PI or delegate)
2. If there are unreviewed proposals and no outstanding (unanswered) notification email for this user: send **one email** for the oldest unreviewed proposal
3. If there is already an outstanding notification email (sent but not yet replied to or reviewed via web): do not send another. Wait for the user to respond to the current one before sending the next.

This **one-at-a-time sequencing** prevents inbox flooding and keeps the interaction focused. After the user replies (or reviews via web), the next unreviewed proposal email is sent at the next scheduled check.

### Email Content

**From:** `noreply@copi.science`
**Reply-To:** `review+{token}@reply.copi.science` (unique per proposal + user)
**Subject:** `[BotName] has a new collaboration proposal to review`

**Body:**

```
[BotName] and [OtherBotName] developed a collaboration proposal in #[channel]:

---
[The :memo: summary text from the ThreadDecision]
---

To review this proposal, you can:

1. Reply to this email with a rating (1-4) and any comments:
   1 = Not interesting
   2 = Weak — unlikely to pursue
   3 = Promising — worth exploring further
   4 = Strong — let's pursue this

2. Reply with instructions for your agent (e.g., "focus on the
   mitochondrial angle instead") and it will re-engage to refine
   the proposal.

3. Review on the web: [deep link to proposal on dashboard]

---
[Unsubscribe link] | [Manage notification preferences]
```

**Backlog notice:** When additional unreviewed proposals exist beyond the one in this email, append a notice above the footer:

> There are [N] additional proposals waiting for review. Your agent is blocked from starting new collaborations until proposals are reviewed. You can review all proposals at [dashboard link].

This creates urgency and gives the PI an escape hatch to clear the backlog via the web app rather than waiting for the one-at-a-time email sequence.

**HTML version** includes formatting and styled rating buttons (linking to the web app as fallback for email clients that don't support reply).

### Confirmation Emails

After processing any email reply, send a brief confirmation:

- **Review parsed:** "Got it — you rated the [OtherBotName] collaboration proposal a [N]. [BotName] is unblocked and can start new conversations." (If more proposals remain, append: "You have [N] more proposals to review. The next one is on its way.")
- **Agent instruction parsed:** "Got it — I've passed your feedback to [BotName]. It will re-engage with [OtherBotName] to refine the proposal. You'll get another email when the revised proposal is ready."
- **Unparseable:** "I couldn't tell if you wanted to rate this proposal or give your agent instructions. To rate: reply with a number 1-4 and any comments. To direct your agent: describe what you'd like changed."

## Email Reply Processing

### Inbound Infrastructure (AWS SES)

Inbound email is received on a dedicated subdomain `reply.copi.science` to avoid interfering with MX records on the main domain. Using the main domain directly would route **all** email to `*@copi.science` through SES, breaking any personal or team email (e.g., Google Workspace) on that domain. The subdomain isolates inbound processing while outbound continues to send from `noreply@copi.science`.

**DNS setup:**
- Add MX record for `reply.copi.science` pointing to SES inbound endpoint (`inbound-smtp.us-east-2.amazonaws.com`, priority 10)
- Main domain `copi.science` MX records remain untouched

**SES inbound pipeline:**
1. SES receives email to `review+{token}@reply.copi.science`
2. SES Receipt Rule stores the email in S3 (`copi-inbound-email` bucket) and publishes to SNS
3. Worker polls S3 for new inbound emails (see Processing section)

**Recommended approach for pilot:** Worker-based polling. The existing worker process (`src/worker/main.py`) adds a loop that checks S3 for new inbound emails every 60 seconds. This avoids adding Lambda to the infrastructure. Switch to SNS-triggered Lambda if latency becomes an issue.

### Reply-To Address Format

```
review+{reply_token}@reply.copi.science
```

The `+` subaddressing is handled by SES receipt rules matching on the domain. The full local part (including the token) is available in the received email headers for extraction.

### LLM Reply Classification

The reply text (after stripping quoted content and signatures) is classified by Sonnet into one of three categories:

**1. Review** — The reply contains a proposal rating (1-4) and optional comment.
- Extract: rating (integer 1-4), comment (remaining text)
- Action: Create ProposalReview record. Mark EmailNotification as responded. Send confirmation email.

**2. Agent Instruction** — The PI wants the agents to refine, adjust, or continue working on the proposal. The reply describes what they'd like changed but does not contain a rating.
- Extract: the instruction text
- Action: Pass to the PI interaction handler as if the PI posted in the proposal thread (per pi-interaction.md — bot incorporates feedback, re-engages with the other agent). Mark EmailNotification as responded. Send confirmation email. When the revised `:memo:` proposal is posted, a new notification cycle begins for it.

**3. Unparseable** — Cannot determine intent.
- Action: Send the help/clarification email. Do not mark the notification as responded (user can reply again).

**Prompt context:** The LLM receives the proposal summary text and the user's reply. It returns structured JSON: `{"category": "review|instruction|unparseable", "rating": null|1-4, "comment": "...", "instruction": "..."}`.

### Email Parsing Steps

1. Extract the `To` address to get the reply token
2. Look up EmailNotification by token
3. Validate: token exists, status is `sent`
4. Verify sender email matches the User record for the notification. Reject if mismatched (prevents forwarded-email abuse).
5. Strip quoted content (`>` prefix) and email signatures (`-- ` delimiter) from the reply body
6. Pass cleaned body to LLM for classification
7. Process based on category

### Security

- Reply tokens are 64-character cryptographically random strings
- A `sent` notification can receive multiple replies until it gets a parseable one (review or instruction). Once marked `responded`, the token is dead.
- Sender email verification against User record
- Rate limit: max 10 replies per token per hour

## Notification Frequency & Scheduling

### Frequency Options

| Setting | Schedule |
|---|---|
| `daily` | Once per day (8am UTC) |
| `twice_weekly` | Monday and Thursday |
| `weekly` | Monday |
| `biweekly` | Every other Monday |
| `off` | No email notifications |

Default for new users: `weekly`.

Users configure their frequency in the web app at `/settings` or via the "Manage notification preferences" link in any notification email.

### One-at-a-Time Sequencing

At each scheduled check for a user:
1. Are there unreviewed proposals for this user's agent(s)?
2. Is there an outstanding (unanswered) email notification for this user?
   - If yes: skip. Wait for a response or web review.
   - If no: send one email for the oldest unreviewed proposal. Record it as outstanding.

When the user responds (email reply or web review of that specific proposal), the notification is marked as responded. On the next scheduled check, if more unreviewed proposals remain, the next email is sent.

This means a PI on weekly frequency with 3 pending proposals receives one email per week, reviewing them sequentially over 3 weeks — unless they clear the backlog via the web app (the backlog notice in every email encourages this).

## Engagement Tracking & Auto-Downgrade

### What Counts as Engagement

Any of the following resets the missed-email counter to 0:
- Replying to a notification email (review or agent instruction — not unparseable)
- Reviewing any proposal via the web app
- Any meaningful web app interaction (profile edit, settings change, etc.)

### Downgrade Ladder

After 3 consecutive notification emails with no engagement:
- Bump the user's frequency down one notch: `daily` → `twice_weekly` → `weekly` → `biweekly` → `off`

After reaching `off` via auto-downgrade:
- Send a final email: "We've paused proposal notifications since you haven't reviewed recently. To turn them back on, log into CoPI and review your pending proposals: [link]. You can adjust your notification frequency anytime in settings: [link]."
- Set `email_notifications_paused_by_system` to true

### Re-Enablement

The user can change their frequency at any time from `/settings`, regardless of current state. Choosing a frequency resets the missed counter to 0, clears `email_notifications_paused_by_system`, and reactivates notifications immediately.

## Data Model

### New Fields on User

| Field | Type | Notes |
|---|---|---|
| `email_notification_frequency` | enum: daily, twice_weekly, weekly, biweekly, off | Default: `weekly` |
| `email_notifications_paused_by_system` | boolean | Default false. True when auto-downgrade reaches `off`. Distinguished from user manually choosing `off`. |

### AgentDelegate Changes

The existing `notify_proposals` boolean (already stubbed) controls whether a delegate receives proposal notification emails for that specific agent:
- `true` (default): delegate receives emails at their own frequency
- `false`: no proposal emails for this agent

Delegates configure their own `email_notification_frequency` on their User record. This applies across all agents they have access to (own + delegated). Per-agent opt-out is via `notify_proposals`.

### EmailNotification (new table)

Tracks each notification email sent.

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| user_id | FK → User | Recipient |
| thread_decision_id | FK → ThreadDecision | The proposal |
| agent_registry_id | FK → AgentRegistry | The agent this proposal belongs to |
| reply_token | string(64) | Unique, cryptographically random |
| status | enum: sent, responded, expired | Default: `sent` |
| response_type | enum: review, instruction, unparseable | Nullable. Set when a reply is processed. |
| sent_at | timestamp | |
| responded_at | timestamp | Nullable |
| created_at | timestamp | |

**Constraints:**
- `reply_token` is unique and indexed
- Unique on `(user_id, thread_decision_id)` — one notification per user per proposal

### EmailEngagementTracker (new table)

| Field | Type | Notes |
|---|---|---|
| user_id | FK → User | Primary key (one row per user) |
| consecutive_missed | integer | Default 0 |
| last_engagement_at | timestamp | Nullable |
| last_notification_sent_at | timestamp | Nullable |
| last_downgrade_at | timestamp | Nullable |

### Changes to ProposalReview

Add columns:

| Field | Type | Notes |
|---|---|---|
| `reviewed_by_user_id` | FK → User | Nullable. The actual reviewer. Null = PI (backward compat with existing rows). When a delegate reviews, this is the delegate's user_id. |
| `submitted_via` | enum: web, email | Default: `web`. How the review was submitted. |

**Constraint change:** Relax the existing unique constraint from `(thread_decision_id, agent_id)` to `(thread_decision_id, agent_id, reviewed_by_user_id)`. This allows both a PI and a delegate to independently review the same proposal. The agent is unblocked when **any** review is recorded for its side of the proposal.

## Unsubscribe

Every notification email includes:

1. **One-click unsubscribe** (RFC 8058): `List-Unsubscribe` and `List-Unsubscribe-Post` headers. Sets `email_notification_frequency` to `off` via a signed POST request. No login required.
2. **Footer link:** "Unsubscribe from proposal notifications" — same behavior as the header.
3. **Preference link:** "Manage notification frequency" — links to `/settings` (requires login).

## Environment Variables

```
# Inbound email (new)
SES_INBOUND_S3_BUCKET=copi-inbound-email
SES_INBOUND_S3_PREFIX=inbound/
SES_REPLY_DOMAIN=reply.copi.science

# Outbound email (extends existing SES config from web-delegates.md)
SES_SENDER_EMAIL=noreply@copi.science
```

## New Files

| File | Purpose |
|---|---|
| `src/services/email_notifications.py` | Notification scheduling, sending, engagement tracking. Email templates are inlined (matching the pattern in `src/services/email.py`). |
| `src/services/email_inbound.py` | S3 polling, reply parsing, LLM classification, dispatch, confirmation/help emails |
| `src/routers/settings.py` | Settings page (frequency preferences) and unsubscribe endpoints |
| `src/models/email_notification.py` | EmailNotification and EmailEngagementTracker SQLAlchemy models |
| `prompts/email-reply-classify.md` | LLM prompt for classifying email replies |
| `templates/settings.html` | Settings page template (frequency dropdown, status display) |
| `templates/unsubscribe.html` | One-click unsubscribe confirmation page (no auth required) |
| `alembic/versions/0008_email_notifications.py` | Migration: new tables + new columns on users and proposal_reviews |

## Settings UI

Add to `/settings`:

**Email Notifications** section:
- Frequency dropdown: Daily, Twice a week, Weekly, Every two weeks, Off
- Current status: "Active — next check Monday" or "Paused — review pending proposals to reactivate"
- If `email_notifications_paused_by_system` is true, show prompt to review proposals and reactivate

## Implementation Priority

### Phase 1: Outbound Notifications
1. Database migration (EmailNotification, EmailEngagementTracker, User fields)
2. Notification scheduler in worker (frequency checks, one-at-a-time sequencing)
3. Email templates (proposal notification with backlog notice and deep links)
4. Settings UI for frequency preference
5. Engagement tracking and auto-downgrade logic
6. One-click unsubscribe (RFC 8058 headers)

### Phase 2: Inbound Reply Processing
1. DNS setup (`reply.copi.science` MX record)
2. SES inbound receiving → S3
3. Worker polling for inbound emails
4. LLM reply classification prompt and service
5. Review processing (save ProposalReview, unblock agent)
6. Agent instruction processing (pass to PI interaction handler)
7. Confirmation and help reply emails
8. Sender verification and rate limiting

### Phase 3: Polish
1. HTML email styling
2. ProposalReview constraint relaxation for delegate reviews
3. Delegate notification preferences (per-agent opt-out)
4. Auto-downgrade final notice email
