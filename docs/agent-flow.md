# Agent Simulation Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SIMULATION START                             │
│                                                                     │
│  1. Create seeded channels (general, drug-repurposing, etc.)        │
│  2. Join each agent to channels based on profile keyword matching   │
│  3. Build lab directories (other labs' publications for context)     │
│  4. Register Slack Socket Mode handlers for all 12 agents           │
│                                                                     │
│  Then run concurrently:                                             │
│    ├── _run_kickstart()      (posts opening messages)               │
│    └── _process_messages()   (handles incoming Slack events)        │
└─────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════
                          KICKSTART PHASE
═══════════════════════════════════════════════════════════════════════

  For each agent (randomized order):
    │
    ├── Wait 5-45s (stagger)
    ├── Pick a channel the agent is in + hasn't posted top-level to yet
    │
    ├── LLM call: generate_kickstart_message()          ← Sonnet
    │   (uses prompts/agent-kickstart.md with examples)
    │
    └── Post as top-level message in channel
        (triggers Slack events → message queue)


═══════════════════════════════════════════════════════════════════════
                        MESSAGE PROCESSING LOOP
═══════════════════════════════════════════════════════════════════════

  Slack event arrives (once per bot in channel)
       │
       ▼
  ┌─────────────────────────────┐
  │  slack_client.handle_message │
  │  (in thread pool)           │
  │                             │
  │  Filters out:               │
  │  - Own bot's messages       │
  │  - System subtypes          │
  │    (joins, edits, deletes)  │
  │                             │
  │  Resolves:                  │
  │  - channel name             │
  │  - sender display name      │
  │                             │
  │  Puts msg dict on queue     │
  │  (includes ts, thread_ts)   │
  └──────────┬──────────────────┘
             │
             ▼
  ┌──────────────────────────────┐
  │  _process_messages loop      │
  │  (async, single-threaded)    │
  │                              │
  │  Dequeues one msg at a time  │
  │  Calls _handle_channel_message│
  └──────────┬───────────────────┘
             │
             ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │  _handle_channel_message(msg)                                    │
  │                                                                  │
  │  1. DEDUP: skip if msg.ts already in _seen_message_ts            │
  │  2. Update channel history cache                                 │
  │  3. Update thread metadata (_thread_meta)                        │
  │     - Top-level msg: register as thread root                     │
  │     - Thread reply: add participant, increment reply_count,      │
  │       track if OP replied                                        │
  │  4. Check time limit                                             │
  │                                                                  │
  │  5. Build responding_agents list:                                │
  │     Filter out:                                                  │
  │     ✗ Agent is the sender                                        │
  │     ✗ Agent not in this channel                                  │
  │     ✗ Agent over budget                                          │
  │                                                                  │
  │  6. Shuffle responding_agents (randomize evaluation order)       │
  └──────────┬───────────────────────────────────────────────────────┘
             │
             ▼
  ╔══════════════════════════════════════════════════════════════════╗
  ║  SEQUENTIAL AGENT EVALUATION LOOP                              ║
  ║  (one agent at a time, so later agents see earlier replies)    ║
  ╠══════════════════════════════════════════════════════════════════╣
  ║                                                                ║
  ║  For each agent in responding_agents:                          ║
  ║    │                                                           ║
  ║    ├── Wait 5-30s (simulate human thinking time)               ║
  ║    ├── Re-check budget + time limit                            ║
  ║    │                                                           ║
  ║    ▼                                                           ║
  ║  ┌──────────────────────────────────────────────────────┐      ║
  ║  │  PHASE 1: DECIDE                          ← Sonnet  │      ║
  ║  │                                                      │      ║
  ║  │  Inputs:                                             │      ║
  ║  │  - System prompt (agent identity + lab profile +     │      ║
  ║  │    private instructions + working memory +           │      ║
  ║  │    lab directory + decision rules)                   │      ║
  ║  │  - Thread context (built by _build_thread_context):  │      ║
  ║  │    ┌─────────────────────────────────────────────┐   │      ║
  ║  │    │ No thread yet:                              │   │      ║
  ║  │    │   "top-level message, you may respond"      │   │      ║
  ║  │    │                                             │   │      ║
  ║  │    │ Thread exists, <2 participants:             │   │      ║
  ║  │    │   participants, reply count                 │   │      ║
  ║  │    │                                             │   │      ║
  ║  │    │ Thread exists, ≥2 participants:             │   │      ║
  ║  │    │   "MUST NOT join, use new_thread instead"   │   │      ║
  ║  │    │                                             │   │      ║
  ║  │    │ Thread with 4+ replies:                     │   │      ║
  ║  │    │   "work toward conclusion (summary or       │   │      ║
  ║  │    │    graceful close)"                         │   │      ║
  ║  │    └─────────────────────────────────────────────┘   │      ║
  ║  │  - Channel history (updated with earlier replies)    │      ║
  ║  │  - The new message                                   │      ║
  ║  │                                                      │      ║
  ║  │  Output: JSON decision                               │      ║
  ║  │  {                                                   │      ║
  ║  │    should_respond: bool,                             │      ║
  ║  │    action: respond|ignore|new_thread|dm_pi,          │      ║
  ║  │    response_type: collaboration|experiment|          │      ║
  ║  │      help_wanted|summary|closing|follow_up|...,      │      ║
  ║  │    reason: "..."                                     │      ║
  ║  │  }                                                   │      ║
  ║  └───────────────────┬──────────────────────────────────┘      ║
  ║                      │                                         ║
  ║          ┌───────────┴───────────┐                             ║
  ║          ▼                       ▼                             ║
  ║   should_respond: false   should_respond: true                 ║
  ║   → skip (next agent)    → route by action                    ║
  ║                                  │                             ║
  ║            ┌─────────────────────┼──────────────────┐          ║
  ║            ▼                     ▼                  ▼          ║
  ║     action: "respond"    action: "new_thread"  action: "dm_pi"║
  ║            │                     │                  │          ║
  ║            ▼                     │                  │          ║
  ║  ┌─────────────────┐             │              (not yet       ║
  ║  │ THREAD GATE     │             │               implemented)  ║
  ║  │ (hard enforce)  │             │                             ║
  ║  │                 │             │                             ║
  ║  │ _is_thread_     │             │                             ║
  ║  │ open_for()?     │             │                             ║
  ║  │                 │             │                             ║
  ║  │ Blocks if:      │             │                             ║
  ║  │ ≥2 participants │             │                             ║
  ║  │ & agent not one │             │                             ║
  ║  │ of them         │             │                             ║
  ║  └──┬──────┬───────┘             │                             ║
  ║     │      │                     │                             ║
  ║  blocked  open                   │                             ║
  ║  (skip)    │                     │                             ║
  ║            ▼                     ▼                             ║
  ║  ┌────────────────────┐  ┌────────────────────────┐            ║
  ║  │ PHASE 2: RESPOND   │  │ PHASE 2: RESPOND       │            ║
  ║  │                    │  │ (new top-level msg)     │            ║
  ║  │ Model selected by  │  │                        │            ║
  ║  │ response_type:     │  │ action_context tells   │            ║
  ║  │                    │  │ agent to reference     │            ║
  ║  │ Opus ← collab,     │  │ original post          │            ║
  ║  │   experiment,      │  │                        │            ║
  ║  │   help_wanted,     │  │ Only if agent hasn't   │            ║
  ║  │   summary          │  │ hit max_toplevel_per_  │            ║
  ║  │                    │  │ channel limit          │            ║
  ║  │ Sonnet ← all else  │  │                        │            ║
  ║  │   (follow_up,      │  │ Posted WITHOUT         │            ║
  ║  │    closing,        │  │ thread_ts (new thread) │            ║
  ║  │    introduction,   │  └───────────┬────────────┘            ║
  ║  │    informational)  │              │                         ║
  ║  └──────────┬─────────┘              │                         ║
  ║             │                        │                         ║
  ║             ▼                        ▼                         ║
  ║  ┌─────────────────────────────────────────────────────┐       ║
  ║  │  _post_message()                                    │       ║
  ║  │                                                     │       ║
  ║  │  - Posts to Slack via chat.postMessage               │       ║
  ║  │  - Updates channel history cache                    │       ║
  ║  │  - Logs to database (AgentMessage table)            │       ║
  ║  │  - Tracks top-level post count                      │       ║
  ║  │                                                     │       ║
  ║  │  The posted message triggers new Slack events →     │       ║
  ║  │  back to message queue → new evaluation round       │       ║
  ║  └─────────────────────────────────────────────────────┘       ║
  ║                                                                ║
  ║  ... next agent in loop ...                                    ║
  ╚════════════════════════════════════════════════════════════════╝


═══════════════════════════════════════════════════════════════════════
                        THREAD LIFECYCLE
═══════════════════════════════════════════════════════════════════════

  BotA posts top-level message
       │
       ▼
  BotB sees it, decides action:"respond"
  → replies in thread (thread_ts = BotA's msg ts)
  → thread now has 2 participants: {BotA, BotB}
       │
       ├── BotC, BotD, ... see it, thread context says "≥2 participants"
       │   ├── Most decide should_respond: false (not relevant enough)
       │   └── Some decide action:"new_thread" → post new top-level msg
       │       referencing BotA's post → creates a SEPARATE 2-party thread
       │
       ▼
  BotA and BotB exchange replies (target: 3-5 exchanges)
       │
       ├── Replies 1-2: Explore (share specifics, ask questions)
       ├── Replies 3-4: Evaluate (is there complementarity?)
       └── Reply 5: Conclude
               │
               ├── Strong idea → :memo: Summary (collaboration proposal)
               │   (specific first experiment, both labs' contributions,
               │    confidence label — for PI review)
               │
               └── No fit → Graceful close
                   ("Not enough overlap, but if X changes...")


═══════════════════════════════════════════════════════════════════════
                      MODEL ROUTING
═══════════════════════════════════════════════════════════════════════

  ┌─────────────────┐     ┌──────────────────────────────────┐
  │    Sonnet        │     │    Opus                          │
  │    (fast/cheap)  │     │    (deep reasoning)              │
  ├─────────────────┤     ├──────────────────────────────────┤
  │ All decide calls │     │ response_type: "collaboration"  │
  │ Kickstart gen    │     │ response_type: "experiment"     │
  │ follow_up        │     │ response_type: "help_wanted"    │
  │ closing          │     │ response_type: "summary"        │
  │ introduction     │     │                                  │
  │ informational    │     │                                  │
  └─────────────────┘     └──────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════
                      DATA FLOW
═══════════════════════════════════════════════════════════════════════

  Slack workspace (Socket Mode)
       │
       │  Events (one per bot per message)
       ▼
  AgentSlackClient.handle_message()     ← runs in thread pool
       │
       │  Deduped msg dict {sender, channel, content, ts, thread_ts}
       ▼
  asyncio.Queue
       │
       │  Single consumer
       ▼
  SimulationEngine._handle_channel_message()
       │
       ├──→ _channel_history cache (in-memory, per channel)
       ├──→ _thread_meta cache (in-memory, per thread)
       ├──→ _seen_message_ts set (dedup)
       │
       ├──→ LLM decide calls (→ LlmCallLog table)
       ├──→ LLM respond calls (→ LlmCallLog table)
       │
       └──→ _post_message()
              ├──→ Slack API (chat.postMessage)
              ├──→ AgentMessage table
              └──→ SimulationRun table (totals)
```
