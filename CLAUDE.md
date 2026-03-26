# RepairMan

> Personal repair project tracker using markdown files with YAML frontmatter. Claude Code is the interface — slash commands to create, search, update, and summarize repairs.

## How It Works

- Each repair is a `.md` file in `repairs/` with YAML frontmatter
- Frontmatter tracks: status, priority, dates, parts, cost, tags
- The `templates/repair.md` file defines the default frontmatter schema
- Claude reads/searches files directly — no database

## Commands

```bash
/add-repair          # Create a new repair from template
/list-repairs        # List and filter repairs by status/tag/priority
/update-repair       # Update a repair's status, notes, or frontmatter
/repair-summary      # Summarize spending, status counts, and activity
```

## Frontmatter Schema

```yaml
title: string          # Short description of the repair
status: string         # not-started | in-progress | waiting-on-parts | completed | abandoned
priority: string       # low | medium | high | urgent
started: date          # YYYY-MM-DD
completed: date        # YYYY-MM-DD (when finished)
parts: list            # Parts needed or purchased
cost: number           # Total cost so far
tags: list             # Categories (plumbing, electrical, auto, appliance, etc.)
location: string       # Where the repair is (kitchen, garage, car, etc.)
```

## File Boundaries

- **Editable**: `repairs/`, `templates/`
- **Read-only**: `CLAUDE.md`, `.claude/`
- **Never touch**: `.git/`

## Key Conventions

- One file per repair, named with kebab-case: `fix-kitchen-faucet.md`
- Always use the template frontmatter fields — don't invent new ones without updating the template
- Dates in ISO format: `YYYY-MM-DD`
- Cost is a running total, not per-line-item
- Progress notes go under `## Progress` as bullet points with dates

## Verification

When creating or updating repairs:
1. Frontmatter must be valid YAML
2. Status must be one of the allowed values
3. File must be in `repairs/` directory
