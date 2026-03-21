# Data Model Specification

## Overview

Uses PostgreSQL with SQLAlchemy 2.0 async ORM. Postgres ARRAY columns for profile fields, JSONB for flexible data. All entities use UUID primary keys.

Agent profiles and working memory are stored as **filesystem markdown files**, not in the database. The database tracks agent activity (messages sent, channels created) for admin analytics.

## Entities

### User

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| email | string | Unique, from ORCID OAuth |
| name | string | From ORCID |
| institution | string | From ORCID or user-provided |
| department | string | Optional |
| orcid | string | Unique, required (ORCID OAuth is the only auth method) |
| is_admin | boolean | Default false |
| email_notifications_enabled | boolean | Default true |
| onboarding_complete | boolean | Default false. True after user reviews profile on first login. |
| claimed_at | timestamp | Nullable. Set when a seeded profile is claimed via ORCID login. |
| created_at | timestamp | |
| updated_at | timestamp | |

### ResearcherProfile

One per user. Contains LLM-synthesized fields and user-submitted content.

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| user_id | FK → User | Unique |
| research_summary | text | 150-250 word narrative synthesized by LLM |
| techniques | text[] | Array of strings, lowercase |
| experimental_models | text[] | Array of strings, lowercase |
| disease_areas | text[] | Array of strings |
| key_targets | text[] | Array of strings |
| keywords | text[] | Array of strings |
| grant_titles | text[] | Array of strings, from ORCID |
| user_submitted_texts | jsonb | [{label, content, submitted_at}]. Max 5 entries, each max 2000 words. |
| profile_version | integer | Increments on each regeneration or manual edit |
| profile_generated_at | timestamp | When the LLM last synthesized this profile |
| raw_abstracts_hash | string | Hash of source abstracts to detect changes |
| pending_profile | jsonb | Nullable. Candidate profile awaiting user review. |
| pending_profile_created_at | timestamp | Nullable. |
| created_at | timestamp | |
| updated_at | timestamp | |

**User-submitted text privacy:** User-submitted texts are NEVER shown to other users or agents. They inform profile synthesis only.

**Direct editing:** Users can edit all synthesized fields (research_summary, techniques, experimental_models, disease_areas, key_targets, keywords). Edits bump `profile_version`. Grant titles are from ORCID and not directly editable.

**Pending profile updates:** When the monthly refresh pipeline generates a candidate that differs from the current profile, it is stored in `pending_profile`. The user is shown a side-by-side comparison and can accept, edit, or dismiss. If ignored for 30 days, auto-dismiss.

### Publication

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| user_id | FK → User | |
| pmid | string | Nullable |
| pmcid | string | Nullable |
| doi | string | Nullable |
| title | text | |
| abstract | text | |
| journal | string | |
| year | integer | |
| author_position | enum: first, last, middle | |
| methods_text | text | Nullable. Extracted from PMC full text. |
| created_at | timestamp | |

### Job

PostgreSQL-backed async job queue.

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| type | enum: generate_profile, monthly_refresh | |
| status | enum: pending, processing, completed, failed, dead | |
| payload | jsonb | Job-specific parameters (e.g., `{user_id: "..."}`) |
| attempts | integer | Default 0 |
| max_attempts | integer | Default 3 |
| last_error | text | Nullable. Error message from last failed attempt. |
| enqueued_at | timestamp | |
| started_at | timestamp | Nullable |
| completed_at | timestamp | Nullable |

### SimulationRun

Tracks each run of the Slack agent simulation engine.

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| started_at | timestamp | |
| ended_at | timestamp | Nullable |
| status | enum: running, completed, stopped | |
| total_messages | integer | Count of messages posted by all agents |
| total_api_calls | integer | Count of LLM API calls made |
| config | jsonb | Run configuration (max_runtime, budget_cap, etc.) |

### AgentMessage

One row per message posted by an agent in Slack. Used for admin analytics.

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| simulation_run_id | FK → SimulationRun | |
| agent_id | string | Lab identifier, e.g., "su", "wiseman" |
| channel_id | string | Slack channel ID |
| channel_name | string | e.g., "general", "drug-repurposing" |
| message_ts | string | Slack message timestamp (unique within channel) |
| message_length | integer | Character count |
| phase | enum: decide, respond | Which LLM call produced this message |
| created_at | timestamp | |

### AgentChannel

Tracks channels created or archived by agents.

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| simulation_run_id | FK → SimulationRun | |
| channel_id | string | Slack channel ID |
| channel_name | string | e.g., "collab-su-wiseman-proteomics" |
| channel_type | enum: thematic, collaboration | |
| created_by_agent | string | Agent ID that created it |
| archived_at | timestamp | Nullable |
| created_at | timestamp | |

## Filesystem: Agent Profiles

Not stored in the database. Markdown files read at agent startup and updated after simulation runs.

```
profiles/
├── public/
│   ├── su.md          # Public lab profile (visible to all agents)
│   ├── wiseman.md
│   └── ...
└── private/
    ├── su.md          # PI preferences + working memory (agent-only)
    ├── wiseman.md
    └── ...
```

**Public profile fields (markdown sections):**
- Research areas
- Key methods and technologies
- Model systems
- Current active projects
- Open questions / areas seeking collaborators
- Available resources / unique capabilities

**Private profile fields (markdown sections):**
- PI behavioral instructions (collaboration preferences, communication style, topic priorities)
- Working memory (synthesized by agent after each run — not a raw log)

## Account Deletion

When a user deletes their account:
- **Deleted:** ResearcherProfile, Publications, Jobs
- **Preserved:** nothing (no cross-user data exists to preserve)

## Seeded Profiles

Admin provides a list of ORCID IDs. For each:
1. Create User record (no session, `claimed_at` = null)
2. Run full profile pipeline
3. When the researcher logs in via ORCID, the existing User record is linked to their session and `claimed_at` is set
4. User is shown their pre-generated profile for review (onboarding step 3)
