# Update Repair

Update an existing repair project.

## Instructions

1. If $ARGUMENTS names a specific repair, find it in `repairs/`. Otherwise, list all repairs and ask which one to update.

2. Read the current repair file and show the user a summary of its current state.

3. Ask what to update (or use details from $ARGUMENTS):
   - **Status change**: Update the `status` field. If changing to `completed`, also set the `completed` date to today.
   - **Add progress note**: Append a dated bullet point under `## Progress`
   - **Add cost item**: Add a row to the `## Cost Breakdown` table with `| Item name | type | $X.XX |` where type is `parts`, `labour`, or `other`. Then update the `cost:` field in frontmatter to equal the sum of all Cost Breakdown rows.
   - **Remove cost item**: Remove a row from the Cost Breakdown table. Update the `cost:` field to match the new total.
   - **Change priority**: Update the `priority` field
   - **Add notes**: Append to the `## Notes` section

4. When modifying cost items, ALWAYS recalculate the `cost:` frontmatter field as the sum of all `Cost` column values in the Cost Breakdown table.

5. Use the Edit tool to make changes — do not rewrite the entire file.

6. Show the user what changed.
