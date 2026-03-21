# Tech Stack and Infrastructure Specification

## Overview

CoPI/LabAgent is a Python web application deployed via Docker Compose. PostgreSQL for structured data, filesystem markdown for agent profiles and working memory, PostgreSQL-backed job queue, ORCID OAuth authentication, Claude Opus/Sonnet for LLM operations, Slack Bolt for the agent system.

## Web Framework

- **Framework:** FastAPI with Python 3.11+
- **Templates:** Jinja2 (server-rendered HTML)
- **Styling:** Tailwind CSS (via CDN)
- **Key pages:**
  - Login (ORCID OAuth redirect)
  - Onboarding (profile review and edit)
  - Profile view/edit
  - Settings
  - Admin dashboard (`/admin/*`)

## Backend

- **API:** FastAPI route handlers
- **ORM:** SQLAlchemy 2.0 (async) with Alembic for migrations
- **Auth:** ORCID OAuth 2.0 via Authlib
- **Worker:** Separate process for long-running jobs (profile generation)
- **Agent system:** Slack Bolt SDK (Python) running as a separate process

## Database

- **PostgreSQL** — local Docker in development, AWS RDS in production
- **ORM:** SQLAlchemy 2.0 async
- Stores: users, researcher profiles, publications, job queue, agent activity logs
- Array fields stored as Postgres ARRAY columns
- JSONB for `user_submitted_texts` and `pending_profile`

## Filesystem

- **Agent public profiles:** `profiles/public/{lab}.md`
- **Agent private profiles + working memory:** `profiles/private/{lab}.md`
- **Prompts:** `prompts/` directory — editable without code changes
  - `prompts/profile-synthesis.md`
  - `prompts/agent-system.md`
  - `prompts/agent-respond-decision.md`
  - `prompts/agent-kickstart.md`

## Job Queue

PostgreSQL-backed queue (simple `jobs` table) for the pilot — avoids AWS SQS dependency at this scale.

**Job types:**
- `generate_profile` — run profile ingestion pipeline for a user
- `monthly_refresh` — check for new publications for a user

Worker process polls the jobs table on a configurable interval. Scale to AWS SQS when needed.

## LLM

- **Provider:** Anthropic Claude API
- **Models:**
  - `claude-opus-4-6` for profile synthesis (high quality, run infrequently)
  - `claude-sonnet-4-6` for agent response generation (cost-efficient, high volume)
- **Prompts:** Stored as markdown files in `prompts/` for easy editing

## External APIs

| API | Purpose | Auth |
|---|---|---|
| ORCID OAuth | User authentication | OAuth 2.0 Public API, `/authenticate` scope |
| ORCID Public API | Profile, grants, works | No auth needed for public data |
| PubMed E-utilities | Abstracts, article metadata | API key recommended (10 req/sec vs 3) |
| PMC E-utilities | Full-text methods sections | Same API key as PubMed |
| NCBI ID Converter | PMID ↔ PMCID conversion | No auth |
| Claude API | Profile synthesis, agent responses | API key |
| Slack API | Agent communication | Bot tokens per agent |

## Slack

- **SDK:** `slack-bolt` (Python) with Socket Mode — no public URL required
- **One Slack app per agent** (8 apps for 8 pilot labs)
- Each app has its own bot token (`xoxb-...`) and app-level token (`xapp-...`)
- See `agent-system.md` for full Slack configuration

## Hosting and Deployment

### Pilot

Single EC2 instance running everything via Docker Compose:

```
docker-compose.yml:
  - app       (FastAPI web server, port 8000)
  - worker    (job processor)
  - agent     (Slack simulation engine)
  - postgres  (database)
```

- Instance type: t3.small or t3.medium (~$15-30/month)
- HTTPS via Let's Encrypt (certbot) or AWS Certificate Manager
- Nginx reverse proxy in front of FastAPI

### Scaling Path

- Move Postgres to AWS RDS
- Move services to separate ECS (Fargate) containers
- Switch job queue to AWS SQS

## Environment Variables

```
# ORCID OAuth
ORCID_CLIENT_ID=
ORCID_CLIENT_SECRET=
ORCID_REDIRECT_URI=

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/copi

# Claude API
ANTHROPIC_API_KEY=

# NCBI
NCBI_API_KEY=

# App
SECRET_KEY=                  # for session signing
BASE_URL=https://copi.science

# Slack — one pair per agent
SLACK_BOT_TOKEN_SU=xoxb-...
SLACK_APP_TOKEN_SU=xapp-...
SLACK_BOT_TOKEN_WISEMAN=xoxb-...
SLACK_APP_TOKEN_WISEMAN=xapp-...
SLACK_BOT_TOKEN_LOTZ=xoxb-...
SLACK_APP_TOKEN_LOTZ=xapp-...
SLACK_BOT_TOKEN_CRAVATT=xoxb-...
SLACK_APP_TOKEN_CRAVATT=xapp-...
SLACK_BOT_TOKEN_GROTJAHN=xoxb-...
SLACK_APP_TOKEN_GROTJAHN=xapp-...
SLACK_BOT_TOKEN_PETRASCHECK=xoxb-...
SLACK_APP_TOKEN_PETRASCHECK=xapp-...
SLACK_BOT_TOKEN_KEN=xoxb-...
SLACK_APP_TOKEN_KEN=xapp-...
SLACK_BOT_TOKEN_RACKI=xoxb-...
SLACK_APP_TOKEN_RACKI=xapp-...
```

## Project Structure

```
copi-python/
├── pyproject.toml
├── .env.example
├── docker-compose.yml
├── docker-compose.prod.yml
├── Dockerfile
├── alembic/                    # Database migrations
│   └── versions/
├── profiles/
│   ├── public/                 # Lab public profiles (markdown)
│   │   ├── su.md
│   │   ├── wiseman.md
│   │   └── ...
│   └── private/               # Lab private profiles + working memory (markdown)
│       ├── su.md
│       └── ...
├── prompts/                    # LLM prompt files (markdown)
│   ├── profile-synthesis.md
│   ├── agent-system.md
│   ├── agent-respond-decision.md
│   └── agent-kickstart.md
├── src/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app factory
│   ├── config.py               # Settings from env vars
│   ├── database.py             # SQLAlchemy engine and session
│   ├── models/                 # SQLAlchemy models
│   │   ├── user.py
│   │   ├── profile.py
│   │   ├── publication.py
│   │   ├── job.py
│   │   └── agent_activity.py
│   ├── routers/                # FastAPI routers
│   │   ├── auth.py             # ORCID OAuth flow
│   │   ├── profile.py          # Profile view/edit
│   │   ├── onboarding.py       # Signup flow
│   │   └── admin.py            # Admin dashboard
│   ├── services/
│   │   ├── orcid.py            # ORCID API client
│   │   ├── pubmed.py           # PubMed/PMC fetching
│   │   ├── llm.py              # Anthropic API wrapper
│   │   └── profile_pipeline.py # Orchestrates ingestion steps
│   ├── worker/
│   │   └── main.py             # Job queue worker process
│   └── agent/
│       ├── main.py             # Simulation engine entry point
│       ├── agent.py            # Agent class
│       ├── slack_client.py     # Slack connection per agent
│       ├── simulation.py       # Simulation loop, timing, budget
│       └── channels.py         # Channel management
├── templates/                  # Jinja2 HTML templates
│   ├── base.html
│   ├── login.html
│   ├── onboarding/
│   │   ├── profile_review.html
│   │   └── complete.html
│   ├── profile/
│   │   ├── view.html
│   │   └── edit.html
│   └── admin/
│       ├── users.html
│       ├── user_detail.html
│       ├── jobs.html
│       └── activity.html
├── static/
└── tests/
```

## Development Workflow

- Docker Compose for local development (mirrors production)
- Alembic for schema migrations (`alembic upgrade head`)
- Prompts editable as markdown files without code changes
- `pytest` with `pytest-asyncio` for testing
- `ruff` for linting and formatting

## Monitoring

### Pilot
- Structured logging to stdout (JSON format, captured by Docker/CloudWatch)
- Health check endpoint: `GET /api/health`
- Admin dashboard shows job queue status and agent activity

### Later
- Sentry for error tracking
- CloudWatch alarms for worker failures
