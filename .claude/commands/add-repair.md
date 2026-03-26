# Add New Repair

Create a new repair tracking file.

## Instructions

1. Ask the user for:
   - **Title**: What needs repairing?
   - **Priority**: low / medium / high / urgent (default: medium)
   - **Location**: Where is the repair? (kitchen, garage, car, etc.)
   - **Tags**: Categories like plumbing, electrical, auto, appliance
   - **Problem description**: What's broken?

2. Read the template at `templates/repair.md`

3. Create a new file in `repairs/` using kebab-case naming derived from the title (e.g., "Fix kitchen faucet" → `fix-kitchen-faucet.md`)

4. Replace all `{{PLACEHOLDER}}` values:
   - `{{TITLE}}`: The repair title
   - `{{DATE}}`: Today's date in YYYY-MM-DD format
   - `{{LOCATION}}`: The location provided
   - Fill in the Problem section with the description

5. If the user mentions any parts or costs upfront, add rows to the `## Cost Breakdown` table:
   ```
   | Item | Type | Cost |
   |------|------|------|
   | Item name | parts | $10.00 |
   ```
   Types: `parts`, `labour`, `other`. Update the `cost:` field in frontmatter to match the table total.

6. Confirm creation and show the user the file path.

$ARGUMENTS will contain any details the user already provided — extract what you can and only ask for missing required fields (title is required, everything else has defaults).
