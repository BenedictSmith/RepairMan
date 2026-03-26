# RepairMan

> Personal repair project tracker using markdown files with YAML frontmatter. Claude Code is the interface — slash commands to create, search, update, and summarize repairs.

## How It Works

- Each repair is a `.md` file in `repairs/` with YAML frontmatter
- Frontmatter tracks: status, priority, dates, cost, tags
- The `## Cost Breakdown` markdown table is the source of truth for cost line items
- The `cost:` frontmatter field is auto-computed from the table total
- The `templates/repair.md` file defines the default frontmatter schema
- SQLite database and web dashboard auto-sync via file watcher

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
cost: number           # Auto-computed total from Cost Breakdown table
tags: list             # Categories (plumbing, electrical, auto, appliance, etc.)
location: string       # Where the repair is (kitchen, garage, car, etc.)
```

## Cost Breakdown Table

Each repair has a `## Cost Breakdown` section in the markdown body:

```markdown
| Item | Type | Cost |
|------|------|------|
| Part name | parts | $10.50 |
| Labour description | labour | $75.00 |
```

- **Type** must be: `parts`, `labour`, or `other`
- **Cost** values prefixed with `$`
- The table is the source of truth — editable in Obsidian or via `/update-repair`
- The `cost:` frontmatter field is auto-synced to match the table total

## File Boundaries

- **Editable**: `repairs/`, `templates/`
- **Read-only**: `CLAUDE.md`, `.claude/`
- **Never touch**: `.git/`

## Key Conventions

- One file per repair, named with kebab-case: `fix-kitchen-faucet.md`
- Always use the template frontmatter fields — don't invent new ones without updating the template
- Dates in ISO format: `YYYY-MM-DD`
- Cost items go in the `## Cost Breakdown` table — the `cost:` frontmatter field is auto-computed
- Progress notes go under `## Progress` as bullet points with dates

## Verification

When creating or updating repairs:
1. Frontmatter must be valid YAML
2. Status must be one of the allowed values
3. File must be in `repairs/` directory
