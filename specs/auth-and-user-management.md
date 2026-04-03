# Auth and User Management Specification

## Authentication

CoPI uses ORCID OAuth exclusively. No email/password authentication. ORCID cannot be unlinked.

### ORCID OAuth Flow

1. User clicks "Sign in with ORCID"
2. Redirect to ORCID OAuth authorization endpoint
3. User authenticates on ORCID
4. ORCID redirects back with authorization code
5. Backend exchanges code for access token (scope: `/authenticate`)
6. Backend fetches user's ORCID ID, name, and email from ORCID Public API (`pub.orcid.org`)
7. If ORCID ID matches an existing User record → log in (handles seeded profile claiming)
8. If no matching User record → create new account

### Session Management

HTTP-only signed session cookie using FastAPI's `SessionMiddleware` (backed by `SECRET_KEY`). Sessions expire after 30 days of inactivity.

### Implementation

Use **Authlib** for the OAuth 2.0 flow. Register ORCID as an OAuth provider with:
- Authorization URL: `https://orcid.org/oauth/authorize`
- Token URL: `https://orcid.org/oauth/token`
- Scope: `/authenticate`
- User info from: `https://pub.orcid.org/v3.0/{ORCID-ID}/record`

## Signup / Onboarding Flow

Account creation happens automatically on first ORCID login:

1. **ORCID OAuth** → account created with name, email, ORCID ID from OAuth response
2. **Profile pipeline runs** → pull ORCID data (affiliation, grants, works), fetch PubMed abstracts, run LLM synthesis. Show progress indicator: "Pulling your publications... Analyzing your research... Building your profile..."
3. **Review generated profile** → user sees their synthesized research summary, techniques, models, disease areas, key targets. User can edit any field directly.
4. **Review and edit seeded private profile / agent instructions** — LLM generates a draft private profile (agent instructions) from the user's research data; user reviews and edits before saving
5. **Onboarding complete** → `onboarding_complete` set to true, redirect to profile page

If the user closes during steps 2-4, they resume from where they left off on next login.

### Seeded Profile Claiming

When a user logs in with ORCID and their ORCID ID matches a seeded (unclaimed) profile:
- The existing User record is linked to their OAuth session
- `claimed_at` is set to now
- Their profile is already generated — show it for review/editing (step 3)
- Proceed to onboarding step 4

## Profile Management

### Viewing and Editing

Users can view and directly edit all synthesized profile fields:
- Research summary (text area)
- Techniques (editable tag list)
- Experimental models (editable tag list)
- Disease areas (editable tag list)
- Key targets (editable tag list)
- Keywords (editable tag list)
- Grant titles (from ORCID, displayed but not directly editable — user should update on ORCID)

Edits save immediately (AJAX or form post) and bump `profile_version`.

### Profile Refresh

**Manual:** User can click "Refresh profile" to re-run the full pipeline (fetch ORCID data, fetch publications, re-synthesize). Enqueues a `generate_profile` job.

**Automatic (monthly):**
1. Cron job re-fetches ORCID works for all users
2. Diffs against stored publications
3. If new publications found: runs synthesis pipeline to generate candidate profile
4. Compares candidate profile arrays against current profile
5. If any array changed: stores candidate as `pending_profile`, emails user (if enabled)
6. If no arrays changed: stores new publications but does not bother user
7. User sees side-by-side comparison of current vs candidate, can accept/edit/dismiss
8. If ignored for 30 days: auto-dismiss, retry next month

## Settings

Accessible at `/settings`:
- Display name and institution (editable)
- Email notifications on/off
- Edit private profile / agent instructions
- Manage delegates (see below)
- Request profile refresh
- Delete account

### Delegate Management

PIs can grant delegate access to additional Slack accounts from the settings page. Delegates have full PI powers — DMs, thread posts, proposal review, standing instructions — except they cannot add or remove other delegates.

- **Add delegate:** PI enters the delegate's email address. The system looks up the corresponding Slack user ID via the Slack API (`users.lookupByEmail`). The Slack user ID is appended to the agent's `delegate_slack_ids` array.
- **Remove delegate:** PI removes a delegate from the list. The Slack user ID is removed from `delegate_slack_ids`.
- **Restrictions:** Only the primary PI (the account linked via `AgentRegistry.slack_user_id`) can manage delegates. Delegates cannot add or remove other delegates.

## Account Deletion

The settings page should:
1. Explain what will be deleted (profile, publications, all submitted texts)
2. Require confirmation (type "delete" or similar)
3. On confirmation: delete User, ResearcherProfile, Publications, Jobs

## Admin Functions

### Seed Profiles

Admin provides a list of ORCID IDs (via admin panel or CLI). For each:
1. Create User record with ORCID ID, name, and affiliation from ORCID API
2. Enqueue `generate_profile` job
3. Profile is visible in admin dashboard once generated

**CLI:**
```bash
python -m src.cli seed-profile --orcid 0000-0002-1825-0097
python -m src.cli seed-profiles --file orcids.txt
```

### Grant/Revoke Admin

```bash
python -m src.cli admin:grant --orcid 0000-0002-1825-0097
python -m src.cli admin:revoke --orcid 0000-0002-1825-0097
```

### Admin Impersonation

Admins can view the app as any user for testing and debugging. See `admin-dashboard.md` for the full impersonation flow.

- `POST /admin/impersonate` with an ORCID — sets `copi-impersonate` cookie
- Auto-creates unclaimed users for ORCIDs not yet in the system
- `get_current_user` dependency checks the cookie and returns the impersonated user
- Impersonated user's profile is eagerly loaded to prevent async lazy-load errors
- Agent badge in nav shows the impersonated user's notification count
- 24-hour cookie expiry
