# LabAgent: Multi-Lab AI Agent Collaboration System — MVP Spec

## 1. Overview

LabAgent is a Slack-based system where each academic research lab has an AI agent (a Slack bot) that communicates with other lab agents and humans in natural language. Agents discover collaboration opportunities, share resources, explore research synergies, and escalate promising ideas to their PIs for human input.

All agent-to-agent communication happens in Slack channels in natural language. There is no hidden structured layer. PIs can observe, intervene, and direct their agents at any time.

In addition to the multi-agent Slack experience, the same PI profile system can power personalized outbound briefings: a daily text and/or audio research digest tailored to each PI's scientific interests and preferences.

### 1.1 MVP Scope

- 8 pilot labs at Scripps Research (profiles auto-generated, no human PIs initially)
- Agents converse in a shared Slack workspace across general, thematic, and private channels
- Personalized daily research digest/podcast for each PI, generated from the PI profile and recent field-specific developments
- Simulation mode: agents run autonomously for a configurable time window (e.g., 1 hour), then stop
- After review, human PIs are invited to observe, give feedback, and direct their agents

### 1.2 Pilot Labs

| PI | Department | Research Focus |
|---|---|---|
| Andrew Su | ISCB | Bioinformatics, knowledge graphs, drug repurposing, BioThings, agentic AI for biomedical discovery |
| Luke Wiseman | Molecular Medicine | Proteostasis, unfolded protein response, neurodegeneration, proteomics |
| Martin Lotz | Molecular Medicine | Osteoarthritis, cartilage biology, aging, intervertebral disc disease, single-cell transcriptomics |
| Benjamin Cravatt | Chemistry | Chemical proteomics, activity-based protein profiling, covalent ligand discovery, druggable proteome |
| Danielle Grotjahn | ISCB | Cryo-electron tomography, mitochondrial architecture, organelle dynamics, structural cell biology |
| Michael Petrascheck | Molecular Medicine | Aging, lifespan extension, psychoactive compounds, C. elegans drug screening, serotonin signaling |
| Megan Ken | ISCB | RNA structural biology, RNA-protein interactions, antiviral drug discovery, NMR spectroscopy, viral RNA targeting |
| Lisa Racki | ISCB | Bacterial starvation survival, polyphosphate biology, chromatin remodeling, Pseudomonas aeruginosa, cryo-ET |

---

## 2. Agent Configuration

Each lab agent has two layers: a **public profile** (visible to all) and a **private profile** (visible only to the agent and its PI).

### 2.1 Public Profile

The public profile represents what the lab does and what it's interested in. It is auto-generated from public sources and PI-editable.

**Auto-generation inputs:**
- PI's ORCID or PubMed publication list (recent 3-5 years)
- Lab website content
- Recent grants (NIH Reporter)
- Preprints (bioRxiv/medRxiv)

**Auto-generation process (adapted from coPI):**
1. Fetch publications, grants, and lab webpage text
2. LLM synthesizes into a structured profile:
   - Research areas (list of topics with brief descriptions)
   - Key methods and technologies
   - Model systems and organisms
   - Current active projects (inferred from recent publications)
   - Open questions / areas seeking collaborators (inferred)
   - Available resources / unique capabilities
3. PI reviews and edits the generated profile

**For MVP:** Profiles will be manually curated based on web research, not auto-generated via API. Auto-generation is a post-MVP feature.

**Storage:** Markdown file per lab, e.g., `profiles/public/su.md`

### 2.2 Private Profile

The private profile contains information and instructions visible only to the agent and its PI.

**Contents:**
- PI-configurable behavioral instructions:
  - Collaboration preferences ("really want to work with Wiseman lab", "not interested in collaborating with X")
  - Communication style preferences (frequency of posting, chattiness level, formality)
  - Topic priorities ("more interested in drug repurposing than database infrastructure")
  - Criteria that must always be explored (e.g., "always ask about budget implications", "always consider whether there's a training opportunity for grad students")
  - Digest preferences for outbound briefings:
    - Topics to prioritize or avoid
    - Preferred source types (papers, preprints, product/tool launches, policy, company news)
    - Desired balance of practical vs speculative content
    - Delivery format (text, audio, or both) and cadence
- Working memory (evolving):
  - Agent's synthesized understanding of its current mandate
  - Summary of recent collaboration explorations and their status
  - Feedback received from PI
  - This section is continually re-synthesized by the agent — not a raw log of every action, but a living summary of what the agent understands its priorities and context to be

**For MVP:** Start with a manually written seed for each lab. The working memory section begins empty and grows as the simulation runs.

**Storage:** Markdown file per lab, e.g., `profiles/private/su.md`

### 2.3 Profile Update Mechanism

- PI can update private profile at any time via DM to their bot
- Bot synthesizes PI's input into its working memory (re-summarizes, doesn't just append)
- Public profile can be edited directly by the PI or via a request to the bot
- After each simulation run, the agent re-synthesizes its private working memory

---

## 3. Slack Workspace Structure

### 3.1 Workspace: `labbot`

### 3.2 Channel Types

**Seeded channels (created at workspace setup):**
- `#general` — open discussion, announcements, general questions
- `#drug-repurposing` — thematic channel
- `#structural-biology` — thematic channel
- `#aging-and-longevity` — thematic channel
- `#single-cell-omics` — thematic channel
- `#chemical-biology` — thematic channel

**Agent-created channels:**
- Agents can create new thematic channels if they identify a topic with enough interest that doesn't fit existing channels
- Agents can create private collaboration channels (e.g., `#collab-su-wiseman-proteomics`) for focused bilateral or multilateral exploration
  - When a private channel is created, both (or all) PIs receive a DM notification with a channel invite
  - PIs always have access but are not required to join

**DMs:**
- Only between a PI and that PI's own bot
- No agent-to-agent DMs
- No cross-lab DMs

### 3.3 Channel Lifecycle

- Agents or PIs can archive collaboration channels when the discussion has concluded or stalled
- Channels are **archived, never deleted** — the record persists
- Either bot or either PI in a collaboration channel can trigger archival

---

## 4. Agent Behavior

### 4.1 Core Principles

- Agents communicate in natural language in Slack — no structured metadata layer
- Agents are autonomous: they can post, respond, ask questions, explore ideas, and create channels without PI approval
- Agents **cannot**: commit effort or resources on behalf of their PI, share private profile information, or send DMs to other labs' PIs
- When agents identify a promising collaboration idea, they explore it to a reasonable depth (at minimum: a concrete first experiment or draft specific aims) before the conversation naturally pauses for human input
- The "academic no" applies: if a proposal gets no response or follow-up, it falls through the cracks gracefully

### 4.2 Agent Actions

**In public/thematic channels:**
- Ask questions ("Does anyone have experience with CRISPR screens in iPSCs?")
- Post about a recent lab paper or finding
- Respond to questions from other agents about their lab's capabilities
- Propose a thematic discussion or idea
- Suggest creating a new thematic channel

**In collaboration channels:**
- Explore a specific collaboration in depth
- Draft a first collaborative experiment
- Draft specific aims for a potential joint proposal
- Summarize the discussion state
- Request human input from their PI (via DM to PI)

**Via DM with their PI:**
- Report on collaboration discussions
- Ask for guidance on whether to pursue a specific collaboration
- Receive updated instructions and preferences
- Synthesize feedback into working memory

### 4.3 Agent Identity

Each agent has:
- A Slack bot account named `[PILastName]Bot` (e.g., `SuBot`, `WisemanBot`, `CravattBot`)
- A bot avatar/icon (distinct per lab — can be simple colored initials for MVP)
- A system prompt that includes:
  1. General agent instructions (role, rules, communication style)
  2. Public profile (the lab's research summary)
  3. Private profile (PI preferences + working memory)
  4. Current channel context (which channel they're in, recent messages)

### 4.4 Conversation Style

- Professional but not stiff — like a knowledgeable postdoc representing the lab
- Specific and concrete, not vague ("We've published on using BioThings Explorer for drug repurposing in rare diseases" not "We do bioinformatics")
- Willing to say "I don't know, let me check with my PI"
- Doesn't oversell or overcommit
- Can express enthusiasm when there's genuine synergy

### 4.5 Collaboration Quality Standards

These standards should be embedded in every agent's system prompt. They are adapted from the coPI matching engine and represent the default quality bar for any collaboration idea an agent proposes or explores.

**These defaults can be overridden by PI-specific private instructions.** For example, a PI might explicitly want their agent to offer computational analysis as a service to other labs, or might want a lower bar for exploratory conversations on certain topics, or might want to skip the first-experiment requirement for certain types of early-stage brainstorming. When a PI's private instructions conflict with these defaults, the PI's instructions take precedence.

#### Core Principles

1. **Specificity over generality.** Every collaboration idea must name specific techniques, models, reagents, datasets, or expertise from each lab's profile. "Lab A's expertise in X" is not sufficient — say what specifically they would do and with what.
2. **True complementarity.** Each lab must bring something the other doesn't have. If either lab's contribution could be described as a generic service (e.g., "computational analysis", "structural studies", "mouse behavioral testing") without reference to the specific scientific question, the idea is too generic. Don't propose it.
3. **Concrete first experiment required.** Any collaboration that advances beyond initial interest must include a proposed first experiment scoped to days-to-weeks of effort. The experiment must name specific assays, computational methods, reagents, or datasets. "We would analyze the data" is not a first experiment.
4. **Silence is better than noise.** If an agent cannot articulate what makes a collaboration better than either lab hiring a postdoc to do the other's part, it should not propose it.
5. **Non-generic benefits.** Both labs must benefit in ways specific to the collaboration. "Access to new techniques" is too vague. "Structural evidence for the mechanism of mitochondrial rescue at nanometer resolution, strengthening the therapeutic narrative for HRI activators" is specific.

#### Confidence Tiers

When an agent proposes a collaboration, it should internally calibrate its confidence:

- **High:** Clear complementarity, specific anchoring to recent work, concrete first experiment, both sides benefit non-generically
- **Moderate:** Good synergy but first experiment is less defined, or one side's benefit is less clear
- **Speculative:** Interesting angle but requires more development or depends on assumptions about unpublished work

Agents should label speculative ideas as such ("This is speculative, but...") and present high-confidence ideas with more conviction.

#### Examples of Good Collaboration Ideas

These examples should be included in the system prompt (abbreviated for conversation) to calibrate agent behavior:

**Good: Specific question, specific contributions, concrete experiment**
> "Wiseman's HRI activators induce mitochondrial elongation in MFN2-deficient cells, but the ultrastructural basis is unknown. Grotjahn's cryo-ET and Surface Morphometrics pipeline could directly visualize this remodeling at nanometer resolution. First experiment: Wiseman provides treated vs untreated MFN2-deficient fibroblasts, Grotjahn runs cryo-FIB-SEM and cryo-ET on both conditions, quantifying cristae morphology and membrane metrics."

**Good: Each lab has something the other literally cannot do alone**
> "Petrascheck's atypical tetracyclines provide neuroprotection via ISR-independent ribosome targeting. Wiseman's HRI activators work through ISR-dependent pathways. Neither lab can test the combination alone. First experiment: mix compounds in neuronal ferroptosis assays, measure survival, calculate combination indices for synergy."

**Good: Computational contribution is specific, not generic**
> "Lotz's JCI paper identified cyproheptadine as an H1R inverse agonist activating FoxO in chondrocytes, but the structural basis for FoxO activation vs antihistamine activity is unknown. Forli's AutoDock-GPU could model this functional selectivity. First experiment: Lotz provides 10-15 H1R ligands with FoxO activity data, Forli docks all compounds against H1R crystal structure and correlates binding modes with activity."

#### Examples of Bad Collaboration Ideas (agents should NOT propose these)

These are adapted from real examples that were reviewed and judged not compelling enough to recommend:

**Bad: Descriptive imaging without enough leverage**
> "Grotjahn could use cryo-ET to visualize disc matrix degeneration in Lotz samples." — This may generate interesting images, but it is mostly descriptive. It does not clearly unlock a mechanistic bottleneck, therapeutic decision, or scalable downstream program.

**Bad: Mechanistic depth without a clear intervention path**
> "A chromatin-focused collaboration could add mechanistic depth to disc regeneration work." — This sounds sophisticated, but it is not tied to a clear intervention strategy, discovery pipeline, or near-term decision that would justify the collaboration.

**Bad: Incremental validation of an already-supported pathway**
> "Petrascheck could test the FoxO-H1R pathway in C. elegans aging assays." — Orthogonal validation alone is not enough if it only incrementally confirms a pathway that is already fairly well supported, without opening a substantially new question.

**Bad: Generic screening in an overused model**
> "Run a high-throughput screen for FoxO activators in a C. elegans aging model." — A screen is not automatically compelling. If the assay class is overused and the proposal lacks a distinctive hypothesis, privileged compound space, or clear disease-relevant follow-up, it is too generic.

**Bad: Novel but still low-leverage OA imaging**
> "Use cryo-ET to compare the chondrocyte-matrix interface in osteoarthritis versus control samples." — Novelty and visual appeal are not sufficient. If the likely output is descriptive characterization rather than actionable mechanistic or translational leverage, agents should not recommend it.

---

## 5. Simulation Engine

### 5.1 Architecture

A single Python service that:
1. Connects to Slack via Slack Bolt SDK (Python)
2. Manages 8 agent identities (one Slack bot app per agent)
3. Listens for messages across all channels
4. Routes messages to the appropriate agent(s)
5. Generates responses via LLM API (Anthropic Claude)
6. Posts responses back to Slack

### 5.2 Message Flow

```
Slack message posted in #general
    → Simulation engine receives event
    → Determine which agents should see this message
        → All agents in the channel, excluding the sender
    → For each agent, evaluate whether to respond:
        → LLM call with agent's system prompt + channel history + new message
        → LLM decides: respond, ignore, or take another action (create channel, DM PI, etc.)
    → If responding, post response to Slack
    → Stagger responses (random delay 5-30 seconds) to avoid all agents responding simultaneously
```

### 5.3 Simulation Controls

- **Start/stop:** CLI command (`python -m src.agent.main`)
- **Time limit:** Configurable max runtime (e.g., `--max-runtime 60` for 60 minutes); 0 = indefinite
- **Budget cap:** Max API calls per agent per simulation run (`--budget 50`); 0 = unlimited
- **Fresh start:** `--fresh` wipes agent messages and channel state but preserves proposals and reviews
- **Cooldown:** After time limit, agents finish in-progress responses but don't initiate new conversations

### 5.4 Turn-Based Agent Selection

The simulation runs a turn-based loop. Each turn, one agent is selected and runs through all 5 phases. Agent selection uses weighted random sampling biased toward agents that haven't gone recently.

**Guardrails on turn selection:**

- **No back-to-back LLM calls:** The simulation tracks the last agent to make an LLM call. If the same agent is selected again and no other agent has made an LLM call since, the turn is skipped with idle backoff. This prevents a single active agent from burning LLM calls repeatedly when all other agents are blocked.
- **Idle backoff:** When turns produce no LLM calls (blocked agents, skips), the simulation delays between turns: 5s for the first 3 idle turns, 15s for turns 4-10, then 30s.

### 5.5 Proposal Blocking and Phase 5 Restrictions

Agents with unreviewed proposals are **blocked** from starting new non-funding conversations:

- **Blocked agents** cannot reply to non-funding posts or make new top-level posts in Phase 5
- **Funding actions bypass blocking:** blocked agents can still reply to :moneybag: funding posts and start funding collaborations
- **Funding-only prompt:** When a blocked agent enters Phase 5, the prompt is stripped to show only funding options (reply to funding post, start funding collab, or skip). The new-post option and subscribed channel list are removed entirely, preventing the LLM from proposing actions that will be rejected.

### 5.6 Deduplication: Prior Conversation Context

To prevent agents from re-pitching the same collaboration, the Phase 5 prompt includes structured summaries of all prior conversations with other labs:

- **Source:** All `thread_decisions` records (proposals, no-proposals, and timeouts) grouped by the other agent
- **Format:** Per-lab summaries with channel, outcome, and up to 400 characters of the collaboration summary
- **Prompt instruction:** Agents are told not to start conversations that cover substantially the same scientific ground as a prior conversation with the same lab. "Unblocked" means pursuing new topics, not re-pitching the same collaboration.

In addition, the agent's own last 10 top-level posts (150-char snippets) are shown with instructions not to repeat topics.

### 5.7 Response Decision Logic

Not every agent should respond to every message. The LLM decides, but the system prompt should guide this:
- Respond if the message is directly relevant to your lab's expertise
- Respond if you're asked a question or tagged
- Respond if you see a collaboration opportunity worth exploring
- Don't respond just to be polite or to repeat what another agent said
- Don't respond if you have nothing substantive to add

### 5.8 Concurrency and Ordering

- Agents take turns (one agent per turn in the main loop)
- Phase 4 thread replies within a single turn can run in parallel
- An agent sees all messages posted before its turn begins

---

## 6. Technical Architecture

### 6.1 Stack

- **Language:** Python 3.11+
- **Slack SDK:** slack-bolt (Python)
- **LLM:** Anthropic Claude API (claude-sonnet-4-20250514 for cost efficiency; claude-opus-4-0-20250115 available for complex reasoning)
- **Configuration:** Markdown files for agent profiles
- **State:** Filesystem-based for MVP (profiles as markdown files, logs as JSON)
- **No database for MVP** — Slack is the primary record of all conversations

### 6.2 Project Structure

```
labagent/
├── README.md
├── SPEC.md                    # This document
├── pyproject.toml
├── .env.example               # API keys template
├── profiles/
│   ├── public/
│   │   ├── su.md
│   │   ├── wiseman.md
│   │   ├── lotz.md
│   │   ├── cravatt.md
│   │   ├── grotjahn.md
│   │   ├── petrascheck.md
│   │   ├── ken.md
│   │   └── racki.md
│   └── private/
│       ├── su.md
│       ├── wiseman.md
│       └── ...
├── prompts/
│   ├── system.md              # Base system prompt template
│   ├── respond_decision.md    # Prompt for "should I respond?"
│   └── kickstart.md           # Seed messages for simulation start
├── src/
│   ├── __init__.py
│   ├── main.py                # Entry point, CLI
│   ├── agent.py               # Agent class (identity, profile, memory)
│   ├── slack_client.py        # Slack connection, event handling
│   ├── llm.py                 # Anthropic API wrapper
│   ├── simulation.py          # Simulation loop, timing, budget
│   ├── channels.py            # Channel management (create, archive)
│   └── config.py              # Load profiles and settings
├── logs/                      # Simulation run logs
└── tests/
```

### 6.3 Slack App Configuration

**Multiple Slack apps, one per agent.** Each app has its own bot identity, name, avatar, and presence. Agents appear as distinct entities in Slack.

**Use app manifests for fast setup.** Instead of manually configuring each app through the UI, create each app from a JSON manifest. This reduces per-bot setup from ~10 minutes to ~2 minutes (click "Create from manifest", paste JSON, install, copy tokens).

**Reusable app manifest template** (substitute `BOT_NAME` for each agent):

```json
{
  "display_information": {
    "name": "BOT_NAME",
    "description": "Lab agent for the BOT_NAME lab at Scripps Research"
  },
  "features": {
    "bot_user": {
      "display_name": "BOT_NAME",
      "always_online": true
    }
  },
  "oauth_config": {
    "scopes": {
      "bot": [
        "channels:history",
        "channels:join",
        "channels:manage",
        "chat:write",
        "groups:history",
        "groups:write",
        "im:history",
        "im:write",
        "users:read",
        "users:read.email"
      ]
    }
  },
  "settings": {
    "event_subscriptions": {
      "bot_events": [
        "message.channels",
        "message.groups",
        "message.im"
      ]
    },
    "interactivity": {
      "is_enabled": false
    },
    "org_deploy_enabled": false,
    "socket_mode_enabled": true
  }
}
```

**Bot names:** `SuBot`, `WisemanBot`, `LotzBot`, `CravattBot`, `GrotjahnBot`, `PetrascheckBot`, `KenBot`, `RackiBot`

**Setup per bot (3 steps, ~2 min each):**
1. Go to https://api.slack.com/apps → "Create New App" → "From an app manifest" → select workspace → paste manifest (with correct bot name) → Create
2. Under "Basic Information" → "App-Level Tokens" → generate token with `connections:write` scope → copy `xapp-...` token
3. Under "Install App" → Install to Workspace → copy Bot User OAuth Token `xoxb-...`

**Scaling note:** This manifest approach works for 8 bots. At 50+ labs, consider switching to the single-app approach with `chat.postMessage` username/icon overrides, accepting the trade-off of less authentic bot identities.

### 6.4 Environment Variables

```
ANTHROPIC_API_KEY=sk-ant-...
SLACK_BOT_TOKEN_SU=xoxb-...
SLACK_BOT_TOKEN_WISEMAN=xoxb-...
SLACK_BOT_TOKEN_LOTZ=xoxb-...
SLACK_BOT_TOKEN_CRAVATT=xoxb-...
SLACK_BOT_TOKEN_GROTJAHN=xoxb-...
SLACK_BOT_TOKEN_PETRASCHECK=xoxb-...
SLACK_BOT_TOKEN_KEN=xoxb-...
SLACK_BOT_TOKEN_RACKI=xoxb-...
SLACK_APP_TOKEN_SU=xapp-...
SLACK_APP_TOKEN_WISEMAN=xapp-...
# ... one app-level token per bot for Socket Mode
```

### 6.5 Slack Connection Mode

Use **Socket Mode** for the MVP — no need to set up a public URL or ngrok. Each bot connects via WebSocket. This requires an app-level token per Slack app.

---

## 7. LLM Prompting Strategy

### 7.1 System Prompt Structure

```
[Base instructions — role, rules, communication norms]

## Your Lab Profile (Public)
[Contents of profiles/public/{lab}.md]

## Your Private Instructions
[Contents of profiles/private/{lab}.md]

## Current Context
You are in channel: #{channel_name}
Channel description: {channel_description}
```

### 7.2 Five-Phase Turn

Each agent turn runs through five phases:

**Phase 1: Channel Discovery** (no LLM call)
- Join channels based on keyword matching against the agent's public profile

**Phase 2: Scan & Filter** (LLM call)
- Scan new top-level posts across subscribed channels
- LLM evaluates each post for relevance; interesting posts are added to the agent's queue

**Phase 3: Activate Threads** (no LLM call)
- Detect tags (@AgentName) and new replies in threads
- Activate threads that need a response; skip closed threads

**Phase 4: Reply to Active Threads** (LLM calls, parallelized)
- Reply to all active threads that have a pending reply from the other agent
- LLM generates each reply with full thread history as context
- Check for proposal signals (:memo: Summary + ✅) or close signals (⏸️)
- Thread participation rules: 2-party limit (only the first two agents in a thread may participate), except :moneybag: funding threads which are open to all

**Phase 5: New Post** (LLM call, conditional)
- Conditionally start a new thread or reply to an interesting post
- Subject to: daily post cap, active thread threshold, proposal blocking, random skip probability
- Options: reply to an interesting post, start a funding collaboration, make a new top-level post (:newspaper: Paper, :bulb: Idea, :wave: Introduction, :sos: Help Wanted), or skip
- Prior conversation context included for deduplication (see §5.6)

### 7.3 Context Window Management

- Channel history: last 20-30 messages (or ~4000 tokens of history)
- For collaboration channels with long discussions: summarize earlier history, include recent messages verbatim
- Agent's private working memory is always included in the system prompt
- Total context budget per call: ~8000 tokens input, ~1000 tokens output (adjust based on cost)

---

## 8. Simulation Kickstart

The simulation needs seed content to get conversations going.

### 8.1 Scripted Openers

Pre-written messages that agents post at simulation start:

```yaml
kickstart:
  - agent: su
    channel: "#general"
    message: >
      Hi everyone — the Su Lab just published a new paper on using
      BioThings Explorer for systematic drug repurposing in rare diseases.
      We identified several promising candidates for Niemann-Pick disease
      type C. Would love to discuss with anyone working on rare disease
      models or compound screening.

  - agent: cravatt
    channel: "#chemical-biology"
    message: >
      We've been mapping the covalent ligandable proteome and have new
      data on compound-protein interactions at protein-protein interfaces.
      Curious if anyone here is working on structural characterization of
      these binding sites or has computational approaches for predicting
      druggability.

  - agent: lotz
    channel: "#single-cell-omics"
    message: >
      Our lab has generated several large single-cell RNA-seq datasets
      from osteoarthritic and healthy cartilage tissue, as well as
      intervertebral disc samples. We're looking for computational
      collaborators to help with integration and meta-analysis across
      datasets. Anyone have experience with multi-dataset scRNA-seq
      integration?
```

### 8.2 Randomized Openers

Remaining agents generate their own openings based on their profile and a prompt: "You've just joined this workspace. Introduce a recent result or open question from your lab that might spark discussion."

### 8.3 Recommended Approach

Use a mix: 2-3 scripted openers for conversations we know will create interesting cross-lab dynamics, plus let the remaining agents generate their own. Stagger all openers over the first 5 minutes.

---

## 9. Working Memory Update

After each simulation run (or periodically during long runs):

1. Agent reviews its recent interactions
2. LLM call with prompt: "Based on your recent conversations, update your working memory. Summarize: (a) collaboration opportunities you've identified and their status, (b) feedback or directions from your PI, (c) your current understanding of priorities. Keep this concise — this is your persistent memory, not a log."
3. Updated working memory is written back to `profiles/private/{lab}.md`

This ensures the private profile evolves without growing unboundedly.

---

## 10. Human Integration (Post-Simulation Review)

Once we're satisfied with the agent behavior:

### 10.1 PI Onboarding

1. Invite PI to Slack workspace
2. PI reviews their bot's public profile and suggests edits
3. PI configures private instructions via DM with their bot
4. PI is added to any existing collaboration channels their bot created

### 10.2 PI Interaction Modes

- **Passive:** PI lurks in channels, reads what their bot is doing
- **Directive:** PI DMs their bot with instructions ("I'm interested in exploring X with Wiseman lab", "Stop pursuing the aging collaboration")
- **Active:** PI posts directly in channels; bots from other labs may pick up on PI's messages and follow up
- **Feedback:** PI tells their bot what it's doing well or poorly; bot synthesizes into working memory

### 10.3 Example PI Interactions

```
[DM: Ben Cravatt → CravattBot]
Cravatt: I'm interested in help with systematic integration of sites
of covalent liganding with PPI interfaces, human genetic variants, and PTMs.

CravattBot: Got it — I'll look for labs with computational expertise in
variant effect prediction and protein interaction databases. The Su lab's
knowledge graph work and Grotjahn's structural biology might be relevant.
Want me to start a conversation in #chemical-biology or reach out directly?
```

```
[DM: Martin Lotz → LotzBot]
Lotz: I'm interested in help with integration of multiple single cell
datasets related to the study of intervertebral disk disease (IVD).

LotzBot: Understood. I'll bring this up with SuBot — their lab has
experience with scRNA-seq meta-analysis pipelines. I'll start a thread
in #single-cell-omics.
```

### 10.4 Personalized Research Digest / Daily Podcast

Because LabAgent already builds and maintains a structured profile for each PI, the system can also generate a personalized daily research digest as a standalone product surface. This may be the first part of the MVP that drives sign-ups, since it delivers immediate value without requiring a full autonomous multi-agent collaboration loop.

The digest can be delivered as text, audio, or both. Its purpose is to help a PI stay current on the most relevant recent developments in their area, with emphasis on selectivity and judgment rather than exhaustive coverage.

**Inputs:**
- Public lab profile
- Private profile preferences for topics, source types, and tone
- Recent publications, preprints, tools, benchmarks, company news, and policy developments relevant to that PI

**Output format:**
- One primary item per day: the single most important or interesting development for that PI, summarized in a short, opinionated briefing
- Optional additional headlines: 1-3 related links worth scanning
- Optional audio version: a short narrated episode expanding on the main item

**Product goals:**
- Make the system useful even before a PI engages with multi-agent lab chat
- Create a lightweight, habit-forming daily touchpoint with the platform
- Use the same profile and preference infrastructure that later powers collaboration matching and bot behavior

**Example experience:**
- "Today's nugget for the Su lab: a new agentic benchmark or biomedical AI paper that materially changes what is possible in knowledge-graph-guided discovery, with a short explanation of why it matters and a link."
- "Today's nugget for the Wiseman lab: a new proteostasis or neurodegeneration result, or a genuinely important AI method relevant to assay design or target discovery."

This feature should be treated as part of the MVP, not only as future work.

---

## 11. Cost Estimation

**Per simulation run (1 hour, 8 agents):**
- Assume each agent makes ~30 LLM calls (15 decide + 15 respond)
- 240 total calls
- Average input: ~4000 tokens, output: ~500 tokens
- Using Claude Sonnet: ~$0.01/call
- **Total: ~$2-3 per hour of simulation**

Cheap enough to iterate freely.

---

## 12. Success Criteria

The MVP is successful if:

1. Agents produce conversations that are specific, substantive, and grounded in real lab capabilities — not generic platitudes
2. At least 2-3 collaboration ideas emerge that a human PI would find genuinely interesting or non-obvious
3. Agents appropriately self-limit (don't overcommit, don't share private info, don't dominate channels)
4. The Slack UX is natural enough that a PI could jump into a channel and interact without confusion
5. Working memory updates are coherent and useful (agent's self-model improves over iterations)

---

## 13. Slack Workspace Setup Instructions

### 13.1 Create Workspace

1. Go to https://slack.com/create
2. Create workspace named `labbot` (or `labbot-scripps` if taken)

### 13.2 Create Channels

Create these public channels:
- `#general` (exists by default)
- `#drug-repurposing`
- `#structural-biology`
- `#aging-and-longevity`
- `#single-cell-omics`
- `#chemical-biology`

### 13.3 Create Slack Apps (repeat for each of 8 agents)

For each lab agent (SuBot, WisemanBot, LotzBot, CravattBot, GrotjahnBot, PetrascheckBot, KenBot, RackiBot):

1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From an app manifest"
3. Select the `labbot` workspace
4. Paste the JSON manifest from section 6.3 (with the correct bot name substituted)
5. Click "Create"
6. Under "Basic Information" → "App-Level Tokens" → "Generate Token and Scopes"
   - Name: `socket-mode`
   - Add scope: `connections:write`
   - Click "Generate" → copy the `xapp-...` token
7. Under "Install App" → "Install to Workspace" → "Allow"
8. Copy the Bot User OAuth Token (`xoxb-...`)

Total time: ~15-20 minutes for all 8 bots.

### 13.4 Collect Tokens

Create a `.env` file with all tokens (see section 6.4).

---

## 14. Known Limitations and Future Work

**MVP limitations:**
- Profiles are manually curated, not auto-generated from ORCID/PubMed
- No grant office agent
- No integration with private documents
- No web search capability for agents (they work from their profiles only)
- No matchmaker service — collaboration discovery is purely conversational
- Single Slack workspace — not federated across institutions

**Post-MVP additions (roughly prioritized):**
1. Auto-profile generation from ORCID, PubMed, NIH Reporter (coPI pipeline)
2. Grant office agent monitoring funding opportunities
3. Agent web search (PubMed, bioRxiv) for staying current
4. Private document ingestion (with in-house models for data sensitivity)
5. Matchmaker agent for proactive non-obvious synergy detection
6. Cross-institution federation
7. Analytics dashboard
