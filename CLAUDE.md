# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goal

CLI application integrating with xAI APIs.

- Phase 1 (done): video generation
- Phase 2 (done): image generation (`xai image generate`)
- Phase 3 (done): image batch generation (`xai image batch`)
- Phase 4 (done): image editing / image-to-image (`xai image edit`)

## xAI API Reference

- Video generation: https://docs.x.ai/developers/model-capabilities/video/generation
- Image generation & editing: https://docs.x.ai/developers/model-capabilities/images/generation
- Batch API: https://docs.x.ai/developers/advanced-api-usage/batch-api
- Rate limits: https://docs.x.ai/developers/rate-limits
- Base URL: `https://api.x.ai/v1`
- Auth: `Authorization: Bearer $XAI_API_KEY`

---

## Orchestration — You Are the Lead

The main Claude Code session is the orchestrator. Do not delegate orchestration to a sub-agent. The `orchestrator` agent definition is only for `claude --agent orchestrator` sessions; it cannot re-dispatch sub-agents when invoked as a sub-agent itself (sub-agents cannot spawn other sub-agents per the official spec).

### When to use sub-agents (sequential, dependent work)

Spawn specialist sub-agents one at a time when tasks depend on each other's output. Follow the **four-phase loop**:

**Phase 0 — Clarify**: Read CLAUDE.md, scan existing source files, identify which specialists are needed. Ask one focused question if the request is ambiguous.

**Phase 1 — Plan**: Order tasks by dependency:
- PM → AI engineer → CLI engineer → QA → SRE (full feature)
- Skip to the relevant specialist for single-domain changes

**Phase 2 — Dispatch**: Send each specialist a context packet:
```
Context from prior work:
- [key facts: types, file paths, interfaces, decisions already made]

Your task: [specific, scoped]
Read first: [file list]
Acceptance criteria:
- [verifiable outcomes]
Key constraint: [the one rule they must not break]
```

**Phase 3 — Verify**: After each return, confirm output meets acceptance criteria and interfaces align before dispatching the next specialist. Re-dispatch with corrections rather than fixing it yourself.

### When to use agent teams (parallel, independent work)

Use agent teams when tasks do not depend on each other and benefit from simultaneous exploration. Tell Claude naturally:

```
Create an agent team to [task]. Spawn teammates using:
- principal-ai-engineer for [subtask A]
- principal-cli-engineer for [subtask B]
- principal-qa for [subtask C]
```

Best practices from the official spec:
- 3–5 teammates maximum; coordination overhead increases beyond that
- 5–6 tasks per teammate keeps everyone productive
- Each teammate must own **different files** — two teammates editing the same file causes overwrites
- Use `require plan approval` for risky changes before a teammate implements
- Teammates receive CLAUDE.md automatically; give task-specific context in the spawn prompt

Good agent team use cases for this project:
- Parallel code review (security / performance / test coverage — three independent lenses)
- Investigating a bug with competing hypotheses (multiple theories tested simultaneously)
- Building independent modules that will be integrated later

### Routing table

| Request | Mode | Specialists | Order |
|---|---|---|---|
| New end-to-end feature | sub-agents | pm → ai-engineer → cli-engineer → qa → sre | sequential |
| Bug in API client | sub-agents | ai-engineer → qa | sequential |
| Bug in CLI output | sub-agents | cli-engineer → qa | sequential |
| Tests for existing code | sub-agents | qa | direct |
| Scope / acceptance criteria | sub-agents | pm | direct |
| CI/CD, packaging, release | sub-agents | sre | direct |
| Parallel code review | agent team | qa (×3 lenses) | parallel |
| Competing bug hypotheses | agent team | ai-engineer + cli-engineer | parallel |

---

## Sub-Agent Team

| Agent | Responsibility |
|---|---|
| `principal-pm` | Feature scope, acceptance criteria, phased roadmap |
| `principal-ai-engineer` | xAI API client, video generation, polling, error handling |
| `principal-cli-engineer` | CLI commands, UX, output formatting, config |
| `principal-qa` | Tests, coverage, release sign-off |
| `principal-sre` | Packaging, CI/CD, PyPI release, versioning |

The `orchestrator` agent definition is available for `claude --agent orchestrator` sessions where it runs as the main thread and can dispatch sub-agents via the `Agent` tool.

---

## End of Conversation

After every conversation that adds or changes features, always:
1. Update `README.md` to reflect new commands, usage examples, and feature scope
2. Update `CLAUDE.md` if project goals, API references, or agent routing have changed
