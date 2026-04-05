---
name: Phase 1 scope and user stories
description: Established scope for xAI CLI Phase 1 video generation feature, including US-1 through US-4
type: project
---

Phase 1 of the xAI CLI covers video generation only. No source code exists yet — this is a greenfield project.

Defined user stories as of 2026-04-05:
- US-1: `xai video generate "<prompt>"` — text-to-video
- US-2: `xai video status <id>` — check generation status
- US-3: `xai video download <id>` — download completed video
- US-4: `xai video generate "<prompt>" --image <path-or-url>` — image-to-video (first-frame animation)

**Why:** User requested US-4 spec as the first feature addition; it extends the existing `generate` command rather than adding a new sub-command.

**How to apply:** Any new Phase 1 story must fit under `xai video [generate|status|download]`. A new top-level command or a new sub-command group would signal Phase 2 scope creep.
