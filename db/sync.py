#!/usr/bin/env python3
"""RepairMan sync script — bridges markdown files, SQLite, and the web dashboard.

Usage:
    python db/sync.py import   # Parse repairs/*.md → insert/update SQLite
    python db/sync.py export   # Read SQLite → generate repairs/*.md
    python db/sync.py json     # Read SQLite → write dashboard/data.json
    python db/sync.py sync     # import + json (most common)
"""

import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Paths relative to this script
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
REPAIRS_DIR = PROJECT_DIR / "repairs"
DB_PATH = SCRIPT_DIR / "repairman.db"
JSON_PATH = PROJECT_DIR / "dashboard" / "data.json"

PRIORITY_ORDER = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
VALID_STATUSES = {"not-started", "in-progress", "waiting-on-parts", "completed", "abandoned"}
VALID_PRIORITIES = {"low", "medium", "high", "urgent"}
VALID_COST_TYPES = {"parts", "labour", "other"}


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def init_db(db_path):
    conn = sqlite3.connect(str(db_path), timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS repairs (
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'not-started',
            priority    TEXT NOT NULL DEFAULT 'medium',
            started     TEXT,
            completed   TEXT,
            cost        REAL DEFAULT 0,
            location    TEXT DEFAULT '',
            tags        TEXT DEFAULT '[]',
            parts       TEXT DEFAULT '[]',
            cost_items  TEXT DEFAULT '[]',
            data        TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON repairs(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_priority ON repairs(priority)")

    # Migrations: add columns if missing
    cursor = conn.execute("PRAGMA table_info(repairs)")
    columns = {row[1] for row in cursor.fetchall()}
    if "cost_items" not in columns:
        conn.execute("ALTER TABLE repairs ADD COLUMN cost_items TEXT DEFAULT '[]'")
    if "currency" not in columns:
        conn.execute("ALTER TABLE repairs ADD COLUMN currency TEXT DEFAULT 'kr'")

    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Frontmatter parser (no PyYAML needed — schema is rigid)
# ---------------------------------------------------------------------------

def parse_inline_array(value):
    """Parse a YAML inline array like ["a", "b"] or [a, b]."""
    inner = value.strip()[1:-1].strip()
    if not inner:
        return []
    # Try JSON first (handles double-quoted items)
    try:
        return json.loads(value.strip())
    except (json.JSONDecodeError, ValueError):
        pass
    # Fall back to comma splitting for unquoted items
    items = []
    for item in inner.split(","):
        item = item.strip().strip('"').strip("'")
        if item:
            items.append(item)
    return items


def parse_frontmatter(text):
    """Extract YAML frontmatter from markdown text.

    Handles both inline arrays [a, b] and multi-line YAML lists:
      key:
        - item1
        - item2
    """
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    raw_fm = parts[1].strip()
    body = parts[2]

    fm = {}
    lines = raw_fm.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if ":" not in line or line.startswith("  "):
            i += 1
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()

        if not val:
            # Check if next lines are multi-line list items (  - item)
            list_items = []
            while i + 1 < len(lines) and lines[i + 1].startswith("  - "):
                list_items.append(lines[i + 1].strip().removeprefix("- ").strip().strip('"').strip("'"))
                i += 1
            if list_items:
                fm[key] = list_items
            else:
                fm[key] = None
            i += 1
            continue
        elif val.startswith("["):
            fm[key] = parse_inline_array(val)
        elif key == "cost":
            try:
                fm[key] = float(val)
            except ValueError:
                fm[key] = 0
        else:
            fm[key] = val.strip('"').strip("'")

        i += 1

    return fm, body


def parse_body_sections(body):
    """Split markdown body into sections by ## headings."""
    sections = {}
    current_heading = None
    current_lines = []

    for line in body.splitlines():
        match = re.match(r"^## (.+)$", line)
        if match:
            if current_heading is not None:
                sections[current_heading] = "\n".join(current_lines).strip()
            current_heading = match.group(1).strip().lower()
            current_lines = []
        else:
            current_lines.append(line)

    if current_heading is not None:
        sections[current_heading] = "\n".join(current_lines).strip()

    return sections


# ---------------------------------------------------------------------------
# Cost Breakdown table parser
# ---------------------------------------------------------------------------

def parse_cost_table(body_text):
    """Parse the ## Cost Breakdown markdown table from the body.

    Expected format:
        | Item | Type | Cost |
        |------|------|------|
        | Cartridge valve | parts | $10.50 |

    Returns a list of dicts: [{"description": str, "type": str, "cost": float}]
    """
    items = []

    # Find the Cost Breakdown section
    match = re.search(r"## Cost Breakdown\s*\n(.*?)(?=\n## |\Z)", body_text, re.DOTALL)
    if not match:
        return items

    table_text = match.group(1)

    for line in table_text.splitlines():
        line = line.strip()
        # Skip header row, separator row, empty lines
        if not line or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")]
        # split on | gives empty strings at start/end: ['', 'Item', 'Type', 'Cost', '']
        cells = [c for c in cells if c != ""]

        if len(cells) < 3:
            continue

        # Skip header and separator rows
        if cells[0].lower() in ("item", "---", "------") or set(cells[0]) <= {"-", " ", ":"}:
            continue
        # Skip separator-like rows
        if all(set(c) <= {"-", " ", ":"} for c in cells):
            continue

        description = cells[0].strip()
        cost_type = cells[1].strip().lower()
        cost_str = cells[2].strip().lstrip("$€£").replace("kr", "").replace(",", "").strip().rstrip("$€£")

        try:
            cost = float(cost_str)
        except ValueError:
            cost = 0

        if cost_type not in VALID_COST_TYPES:
            cost_type = "other"

        items.append({
            "description": description,
            "type": cost_type,
            "cost": cost,
        })

    return items


CURRENCY_FORMAT = {
    "kr":  {"suffix": " kr"},
    "$":   {"prefix": "$"},
    "€":   {"suffix": " €"},
    "£":   {"prefix": "£"},
}


def format_cost(amount, currency="kr"):
    """Format a cost amount with the given currency symbol."""
    fmt = CURRENCY_FORMAT.get(currency, {"suffix": " " + currency})
    return fmt.get("prefix", "") + f"{amount:.2f}" + fmt.get("suffix", "")


def generate_cost_table(cost_items, currency="kr"):
    """Generate a markdown Cost Breakdown table from cost_items list."""
    lines = [
        "| Item | Type | Cost |",
        "|------|------|------|",
    ]
    for item in cost_items:
        cost_str = format_cost(item["cost"], currency)
        lines.append(f"| {item['description']} | {item['type']} | {cost_str} |")
    return "\n".join(lines)


def compute_cost_total(cost_items):
    """Sum all cost_items and return rounded total."""
    return round(sum(item["cost"] for item in cost_items), 2)


def update_frontmatter_cost(filepath, new_cost):
    """Update the cost: field in a markdown file's frontmatter without rewriting the whole file."""
    text = filepath.read_text(encoding="utf-8")
    cost_str = int(new_cost) if new_cost == int(new_cost) else new_cost

    # Match cost: <number> in frontmatter (between --- delimiters)
    updated = re.sub(
        r"(?m)^(cost:\s*).*$",
        f"\\g<1>{cost_str}",
        text,
        count=1,
    )

    if updated != text:
        filepath.write_text(updated, encoding="utf-8")
        return True
    return False


# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------

def format_array_for_frontmatter(items, quoted=True):
    """Format a list as a YAML inline array."""
    if not items:
        return "[]"
    if quoted:
        return "[" + ", ".join(f'"{item}"' for item in items) + "]"
    return "[" + ", ".join(str(item) for item in items) + "]"


def generate_markdown(record):
    """Generate a full markdown file from a data record dict."""
    fm = record
    body = fm.get("body", {})

    cost = fm.get("cost", 0) or 0
    cost_str = int(cost) if cost == int(cost) else cost

    currency = fm.get("currency", "kr")
    cost_items = fm.get("cost_items", [])
    cost_table = generate_cost_table(cost_items, currency)

    lines = [
        "---",
        f'title: "{fm.get("title", "")}"',
        f'status: {fm.get("status", "not-started")}',
        f'priority: {fm.get("priority", "medium")}',
        f'started: {fm.get("started", "")}',
        f'completed: {fm.get("completed") or ""}',
        f'cost: {cost_str}',
        f'tags: {format_array_for_frontmatter(fm.get("tags", []), quoted=False)}',
        f'location: "{fm.get("location", "")}"',
        f'currency: {currency}',
        "---",
        "",
        "## Problem",
        "",
        body.get("problem", ""),
        "",
        "## Research",
        "",
        body.get("research", ""),
        "",
        "## Progress",
        "",
        body.get("progress", ""),
        "",
        "## Cost Breakdown",
        "",
        cost_table,
        "",
        "## Notes",
        "",
        body.get("notes", ""),
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Import: markdown → SQLite
# ---------------------------------------------------------------------------

def import_repair(conn, repair_id, filepath):
    """Parse a markdown repair file and upsert into the database."""
    text = filepath.read_text(encoding="utf-8")
    fm, body_text = parse_frontmatter(text)
    body_sections = parse_body_sections(body_text)

    # Parse cost items from the Cost Breakdown table (source of truth)
    cost_items = parse_cost_table(body_text)
    computed_cost = compute_cost_total(cost_items)

    # Use computed cost from table if there are items, otherwise fall back to frontmatter
    if cost_items:
        cost = computed_cost
    else:
        cost = fm.get("cost", 0) or 0

    data = {
        "title": fm.get("title", repair_id),
        "status": fm.get("status", "not-started"),
        "priority": fm.get("priority", "medium"),
        "started": fm.get("started"),
        "completed": fm.get("completed"),
        "cost": cost,
        "cost_items": cost_items,
        "tags": fm.get("tags", []),
        "location": fm.get("location", ""),
        "currency": fm.get("currency", "kr"),
        "body": body_sections,
    }

    conn.execute("""
        INSERT INTO repairs (id, title, status, priority, started, completed, cost, location, tags, parts, cost_items, currency, data, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title, status=excluded.status, priority=excluded.priority,
            started=excluded.started, completed=excluded.completed, cost=excluded.cost,
            location=excluded.location, tags=excluded.tags, parts=excluded.parts,
            cost_items=excluded.cost_items, currency=excluded.currency,
            data=excluded.data, updated_at=datetime('now')
    """, (
        repair_id,
        data["title"],
        data["status"],
        data["priority"],
        data["started"],
        data["completed"],
        data["cost"],
        data["location"],
        json.dumps(data["tags"]),
        json.dumps([]),  # parts — legacy, always empty now
        json.dumps(data["cost_items"]),
        data["currency"],
        json.dumps(data),
    ))

    # Write computed cost back to frontmatter if it drifts from the table total
    if cost_items:
        fm_cost = fm.get("cost", 0) or 0
        if abs(fm_cost - computed_cost) > 0.001:
            update_frontmatter_cost(filepath, computed_cost)
            print(f"    updated cost: {fm_cost} → {computed_cost}")


def import_all(db_path, repairs_dir):
    """Import all markdown files from repairs/ into SQLite."""
    conn = init_db(db_path)
    count = 0
    for filepath in sorted(repairs_dir.glob("*.md")):
        repair_id = filepath.stem
        import_repair(conn, repair_id, filepath)
        count += 1
        print(f"  imported: {repair_id}")
    conn.commit()
    conn.close()
    print(f"Imported {count} repairs into {db_path.name}")


# ---------------------------------------------------------------------------
# Export: SQLite → markdown
# ---------------------------------------------------------------------------

def export_all(db_path, repairs_dir):
    """Export all repairs from SQLite to markdown files."""
    conn = init_db(db_path)
    rows = conn.execute("SELECT id, data FROM repairs ORDER BY id").fetchall()
    count = 0
    for row in rows:
        record = json.loads(row["data"])
        md = generate_markdown(record)
        filepath = repairs_dir / f"{row['id']}.md"
        filepath.write_text(md, encoding="utf-8")
        count += 1
        print(f"  exported: {row['id']}")
    conn.close()
    print(f"Exported {count} repairs to {repairs_dir}")


# ---------------------------------------------------------------------------
# JSON export: SQLite → dashboard/data.json
# ---------------------------------------------------------------------------

def export_json(db_path, json_path):
    """Export repairs to JSON for the web dashboard."""
    conn = init_db(db_path)
    rows = conn.execute("""
        SELECT id, title, status, priority, started, completed, cost, location, tags, cost_items, currency
        FROM repairs ORDER BY
            CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
            started DESC
    """).fetchall()

    repairs = []
    summary = {
        "total": 0,
        "total_cost": 0,
        "parts_cost": 0,
        "labour_cost": 0,
        "other_cost": 0,
        "by_status": {},
        "by_priority": {},
        "by_currency": {},
        "by_tag": {},
    }

    for row in rows:
        tags = json.loads(row["tags"]) if row["tags"] else []
        cost_items = json.loads(row["cost_items"]) if row["cost_items"] else []
        repair = {
            "id": row["id"],
            "title": row["title"],
            "status": row["status"],
            "priority": row["priority"],
            "started": row["started"],
            "completed": row["completed"],
            "cost": row["cost"] or 0,
            "cost_items": cost_items,
            "location": row["location"] or "",
            "currency": row["currency"] or "kr",
            "tags": tags,
        }
        repairs.append(repair)

        # Aggregate summary
        summary["total"] += 1
        summary["total_cost"] += repair["cost"]
        for item in cost_items:
            cost_type = item.get("type", "other")
            if cost_type == "parts":
                summary["parts_cost"] += item["cost"]
            elif cost_type == "labour":
                summary["labour_cost"] += item["cost"]
            else:
                summary["other_cost"] += item["cost"]
        summary["by_status"][repair["status"]] = summary["by_status"].get(repair["status"], 0) + 1
        summary["by_priority"][repair["priority"]] = summary["by_priority"].get(repair["priority"], 0) + 1
        currency = repair["currency"]
        summary["by_currency"][currency] = summary["by_currency"].get(currency, 0) + 1
        for tag in tags:
            summary["by_tag"][tag] = summary["by_tag"].get(tag, 0) + 1

    summary["total_cost"] = round(summary["total_cost"], 2)
    summary["parts_cost"] = round(summary["parts_cost"], 2)
    summary["labour_cost"] = round(summary["labour_cost"], 2)
    summary["other_cost"] = round(summary["other_cost"], 2)

    output = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "repairs": repairs,
        "summary": summary,
    }

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    conn.close()
    print(f"Wrote {json_path} ({summary['total']} repairs, {summary['total_cost']:.2f} kr total)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "import":
        import_all(DB_PATH, REPAIRS_DIR)
    elif cmd == "export":
        export_all(DB_PATH, REPAIRS_DIR)
    elif cmd == "json":
        export_json(DB_PATH, JSON_PATH)
    elif cmd == "sync":
        import_all(DB_PATH, REPAIRS_DIR)
        export_json(DB_PATH, JSON_PATH)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
