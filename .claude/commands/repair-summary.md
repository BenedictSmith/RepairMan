# Repair Summary

Generate a summary of all repair projects.

## Instructions

1. Read all `.md` files in the `repairs/` directory
2. Parse YAML frontmatter and the `## Cost Breakdown` table from each file

3. Generate a summary with these sections:

### Status Breakdown
Count repairs by status:
- Not started: X
- In progress: X
- Waiting on parts: X
- Completed: X
- Abandoned: X

### Cost Summary
- Total spent across all repairs: $X.XX
- Parts total: $X.XX
- Labour total: $X.XX
- Other costs: $X.XX
- Total for completed repairs: $X.XX
- Total for active (non-completed) repairs: $X.XX
- Most expensive repair: "title" ($X.XX)

### Priority Overview
- Urgent: list titles
- High: list titles
- Medium: count
- Low: count

### Recent Activity
Show the 5 most recently started or updated repairs.

### By Location
Group repair counts by location.

### By Tag
Group repair counts by tag.

If `repairs/` is empty, tell the user to get started with `/add-repair`.
