# Claude Code Prompt for NarraCraft

Copy everything below the line and paste it into Claude Code in VS Code.

────────────────────────────────────────────────────────────

I'm building NarraCraft — a fully automated YouTube Shorts creation system for gaming and anime/manga lore content. The complete design, architecture, and specifications are already done. Your job is to implement, not redesign.

## Setup

1. Create a new directory called `narracraft/`
2. Read the file `CLAUDE_CODE_BRIEF.md` — this is the master build guide. It contains the full project structure, tech stack, database schema, API endpoints, build order, and all architectural decisions.
3. The following reference files contain exhaustive specs — read them as needed:
   - `config-schema.yaml` — every configuration setting for every module
   - `franchise-registry.yaml` — content data model (franchises, characters, narrators, voice settings)
   - `prompts/script_system.txt` — the 3-layer script generation prompt template
   - `youtube-shorts-monetization-checklist.md` — YouTube compliance rules
   - `pipeline-diagram.jsx` — interactive pipeline workflow (React component)
   - `dashboard-mockup.jsx` — UI theme system with 10 themes (React component)

## What to build first (Phase 1 — Skeleton)

Follow the build order in Section 7 of CLAUDE_CODE_BRIEF.md. Start with:

1. Initialize the project: `narracraft/` with git, .gitignore, README.md
2. `docker-compose.yml` with 3 services: backend (FastAPI), frontend (React), vectcut-api (placeholder)
3. Backend skeleton: FastAPI app with health check, config loader, SQLite database with the full schema from the brief
4. Frontend skeleton: Vite + React + TypeScript + shadcn/ui + Tailwind CSS
5. Theme system: implement all 10 themes from `dashboard-mockup.jsx` as a ThemeProvider context, with a Settings page that shows the theme picker grid
6. Sidebar navigation with routing to all 8 pages (Dashboard, Franchises, Assets, Discover, Queue, Pipeline, Analytics, Settings)
7. Dashboard page — implement the layout from the mockup, connected to the active theme

## Key principles

- **Config-driven**: everything reads from config-schema.yaml, nothing is hardcoded
- **All design decisions are final** — implement what the docs say, don't redesign
- **shadcn/ui + Tailwind** for all UI components, themed via CSS variables that each theme overrides
- **The theme system affects everything**: colors, fonts, card styles, and the in-context terminology (each theme has its own labels like "KINDLE" vs "SET SAIL" for the deploy button)
- **SQLite for all persistence** — no external DB needed
- **FastAPI with async** — all endpoints are async
- **Playwright session manager is the most critical shared component** — but don't build it yet in Phase 1

Start with Phase 1 now. After each step, show me what you've built and ask before proceeding to the next step.
