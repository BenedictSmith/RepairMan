# Update Repair

Update an existing repair project.

## Instructions

1. If $ARGUMENTS names a specific repair, find it in `repairs/`. Otherwise, list all repairs and ask which one to update.

2. Read the current repair file and show the user a summary of its current state.

3. Ask what to update (or use details from $ARGUMENTS):
   - **Status change**: Update the `status` field. If changing to `completed`, also set the `completed` date to today.
   - **Add progress note**: Append a dated bullet point under `## Progress`
   - **Update cost**: Update the `cost` field in frontmatter
   - **Add parts**: Append to the `parts` list and the parts table
   - **Change priority**: Update the `priority` field
   - **Add notes**: Append to the `## Notes` section

4. Use the Edit tool to make changes — do not rewrite the entire file.

5. Show the user what changed.
