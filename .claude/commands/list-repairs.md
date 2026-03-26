# List Repairs

List and filter repair projects.

## Instructions

1. Read all `.md` files in the `repairs/` directory
2. Parse the YAML frontmatter from each file
3. Apply any filters from $ARGUMENTS:
   - `status:in-progress` — filter by status
   - `priority:high` — filter by priority
   - `tag:plumbing` — filter by tag
   - `location:kitchen` — filter by location
   - No filter = show all

4. Display results as a table:

```
| Repair | Status | Priority | Started | Cost | Location |
|--------|--------|----------|---------|------|----------|
```

5. Sort by: urgent/high priority first, then by start date (newest first)

6. Show a summary line at the bottom:
   - Total repairs matching filter
   - Total cost across matched repairs

If `repairs/` is empty or doesn't exist, tell the user to create their first repair with `/add-repair`.
