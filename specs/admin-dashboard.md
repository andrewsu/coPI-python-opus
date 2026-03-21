# Admin Dashboard Specification

## Overview

A read-only admin dashboard for monitoring platform activity and inspecting data. Accessible only to users with `is_admin = true` at `/admin`. Server-rendered with Jinja2 templates, minimal styling using Tailwind.

## Access Control

- All `/admin/*` routes check `is_admin` on the session user. Non-admins get a 403.
- The admin link is only shown in the nav for admin users.
- `is_admin` is set via CLI only — no self-service admin promotion.

## Dashboard Pages

### 1. Users Overview (`/admin/users`)

Default landing page. Table of all users.

**Columns:**
- Name
- Institution
- Department
- ORCID (linked to orcid.org)
- Profile status: `no_profile` | `generating` | `complete` | `pending_update`
- Publication count
- Profile version
- Joined date
- Claimed (yes/no — null for unclaimed seeded profiles)

**Filters:**
- Profile status
- Institution
- Claimed vs. unclaimed

**Row click** → user detail page.

### 2. User Detail (`/admin/users/{id}`)

Full view of a single user's data.

**Sections:**

**Account:**
- Name, email, ORCID, institution, department
- Admin status, onboarding complete, claimed_at

**Profile:**
- Research summary
- Techniques, experimental models, disease areas, key targets, keywords
- Grant titles
- Profile version and generation timestamp
- Pending profile (if any) — show side-by-side diff vs current

**Publications:**
- Table: title, journal, year, author position, PMID/DOI links
- Whether methods text was extracted (yes/no)

**Jobs:**
- All jobs for this user: type, status, attempts, enqueued/completed timestamps, last error

### 3. Job Queue (`/admin/jobs`)

All jobs across all users.

**Summary counts** (above table): total, pending, processing, completed, failed, dead

**Columns:**
- Type (Generate Profile, Monthly Refresh)
- Status (color-coded badge: pending=yellow, processing=blue, completed=green, failed=red, dead=gray)
- User name
- Attempts (N/maxN)
- Enqueued timestamp
- Completed timestamp
- Last error (truncated, shown for failed/dead)

**Filters:**
- Status
- Type

**Sortable:** Type, Status, Enqueued, Completed

### 4. Agent Activity (`/admin/activity`)

Analytics on Slack simulation runs.

**Summary cards:**
- Total simulation runs
- Total messages sent (all time)
- Total channels created (all time)
- Most active agent (by message count, all time)

**Simulation Runs Table:**
- Start time, end time, status
- Total messages, total API calls
- Config summary (max runtime, budget cap)
- Row click → run detail

**Run Detail (`/admin/activity/{run_id}`):**

Per-run breakdown:

*Messages by agent* — table: agent name, message count, avg message length

*Messages by channel* — table: channel name, message count, which agents participated

*Channels created this run* — table: channel name, type (thematic/collaboration), created by agent, archived (yes/no)

*Message timeline* — ordered list of all messages: timestamp, agent, channel, first 100 chars of message

### 5. User Impersonation

Admins can assume the identity of any user to see the app as they see it.

**Entry point:** ORCID text input + "Go" button in admin header, available on all `/admin/*` pages.

**Flow:**
1. Admin enters ORCID, clicks Go
2. `POST /api/admin/impersonate` validates ORCID, looks up user, sets `copi-impersonate` httpOnly cookie
3. If ORCID doesn't exist, fetch from ORCID public API and create a User record (unclaimed)
4. Admin is redirected to `/` and sees the app as that user
5. Amber banner at top of every page: "Impersonating [Name] (ORCID)" with "Stop Impersonating" button
6. Stop calls `DELETE /api/admin/impersonate`, clears cookie, redirects to `/admin`

**Implementation:**
- `copi-impersonate` cookie stores target user's database ID
- Session middleware checks this cookie; if present and session user has `is_admin`, overrides session user identity
- Cookie expires after 24 hours, httpOnly, secure in production, sameSite=lax

## API Routes

| Route | Purpose |
|---|---|
| `GET /admin/users` | Users overview |
| `GET /admin/users/{id}` | User detail |
| `GET /admin/jobs` | Job queue |
| `GET /admin/activity` | Agent activity overview |
| `GET /admin/activity/{run_id}` | Simulation run detail |
| `POST /api/admin/impersonate` | Start impersonating a user |
| `DELETE /api/admin/impersonate` | Stop impersonating |

## Design Principles

- **Read-only.** No edit/delete/trigger actions in v1 (except impersonation). Admin actions stay in CLI.
- **Server-rendered.** Jinja2 templates, no client-side data fetching.
- **Minimal styling.** Tailwind. Tables, basic badges. No charts library — just numbers and text.
- **No pagination in v1.** For pilot scale, load all data. Add pagination later.
