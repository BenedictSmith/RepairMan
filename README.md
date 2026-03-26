# RepairMan

A personal repair project tracker built on markdown files and [Claude Code](https://claude.ai/claude-code). Track home, auto, and electronics repairs with YAML frontmatter — manage everything through natural language slash commands or edit directly in Obsidian.

Includes a SQLite backend and a live-updating web dashboard.

## How It Works

```
Obsidian / Claude Code
        |
   repairs/*.md          (markdown + YAML frontmatter)
        |
   db/sync.py            (import/export/sync)
        |
   SQLite + data.json    (structured data)
        |
   dashboard/index.html  (live web UI)
```

Each repair is a markdown file in `repairs/` with structured frontmatter:

```yaml
---
title: "Fix kitchen faucet"
status: in-progress
priority: high
started: 2026-03-26
completed:
parts: ["cartridge valve", "plumber's tape"]
cost: 12.50
tags: [plumbing, kitchen]
location: "kitchen"
---
```

Files are the source of truth. Edit them in Obsidian, through Claude Code slash commands, or with any text editor. The sync script bridges everything to SQLite and the web dashboard.

## Quick Start

```bash
# Clone the repo
git clone https://github.com/BenedictSmith/RepairMan.git
cd RepairMan

# Start the dashboard with live sync (watches for file changes)
python3 db/serve.py 5050

# Open http://localhost:5050
```

No dependencies beyond Python 3.9+ (uses only stdlib: `sqlite3`, `json`, `http.server`).

## Claude Code Commands

With [Claude Code](https://claude.ai/claude-code) in this project directory:

| Command | Description |
|---------|-------------|
| `/add-repair` | Create a new repair from the template |
| `/list-repairs` | List and filter repairs by status, tag, or priority |
| `/update-repair` | Update status, add notes, log parts and costs |
| `/repair-summary` | Summary of spending, status counts, and activity |

## Sync Script

The sync script keeps SQLite and the dashboard in sync with the markdown files.

```bash
python3 db/sync.py import   # Parse repairs/*.md into SQLite
python3 db/sync.py export   # Generate repairs/*.md from SQLite
python3 db/sync.py json     # Generate dashboard/data.json from SQLite
python3 db/sync.py sync     # import + json (most common)
```

## Dev Server

`serve.py` combines an HTTP server, file watcher, and Server-Sent Events for live browser updates:

```bash
python3 db/serve.py [port]   # default: 5050
```

- Watches `repairs/` for changes (1-second polling)
- Auto-syncs markdown to SQLite and regenerates `data.json`
- Pushes updates to the browser via SSE — no manual refresh needed

## Web Dashboard

A single-file static dashboard (`dashboard/index.html`) with:

- **Summary cards** — total repairs, active count, completed, total cost
- **Filterable table** — filter by status, priority, location, or tag
- **Sortable columns** — click any column header
- **Live updates** — changes in Obsidian appear in the browser automatically

## Frontmatter Schema

| Field | Type | Values |
|-------|------|--------|
| `title` | string | Short description of the repair |
| `status` | string | `not-started` `in-progress` `waiting-on-parts` `completed` `abandoned` |
| `priority` | string | `low` `medium` `high` `urgent` |
| `started` | date | `YYYY-MM-DD` |
| `completed` | date | `YYYY-MM-DD` (set when finished) |
| `parts` | list | Parts needed or purchased |
| `cost` | number | Running total cost |
| `tags` | list | Categories: `plumbing`, `electrical`, `auto`, `appliance`, etc. |
| `location` | string | Where the repair is: `kitchen`, `garage`, `car`, etc. |

## Project Structure

```
RepairMan/
  repairs/              # One .md file per repair (kebab-case)
  templates/repair.md   # Template for new repairs
  dashboard/
    index.html          # Static web dashboard
    data.json           # Generated — do not edit
  db/
    sync.py             # Import/export/sync script
    serve.py            # Dev server with file watcher + SSE
    repairman.db        # SQLite database (generated)
  .claude/commands/     # Claude Code slash command definitions
  CLAUDE.md             # Project instructions for Claude Code
```

## License

MIT
