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
            data        TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON repairs(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_priority ON repairs(priority)")
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

    lines = [
        "---",
        f'title: "{fm.get("title", "")}"',
        f'status: {fm.get("status", "not-started")}',
        f'priority: {fm.get("priority", "medium")}',
        f'started: {fm.get("started", "")}',
        f'completed: {fm.get("completed") or ""}',
        f'parts: {format_array_for_frontmatter(fm.get("parts", []))}',
        f'cost: {cost_str}',
        f'tags: {format_array_for_frontmatter(fm.get("tags", []), quoted=False)}',
        f'location: "{fm.get("location", "")}"',
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
        "## Parts List",
        "",
        body.get("parts list", "| Part | Source | Cost | Ordered | Received |\n|------|--------|------|---------|----------|"),
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

    data = {
        "title": fm.get("title", repair_id),
        "status": fm.get("status", "not-started"),
        "priority": fm.get("priority", "medium"),
        "started": fm.get("started"),
        "completed": fm.get("completed"),
        "parts": fm.get("parts", []),
        "cost": fm.get("cost", 0) or 0,
        "tags": fm.get("tags", []),
        "location": fm.get("location", ""),
        "body": body_sections,
    }

    conn.execute("""
        INSERT INTO repairs (id, title, status, priority, started, completed, cost, location, tags, parts, data, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title, status=excluded.status, priority=excluded.priority,
            started=excluded.started, completed=excluded.completed, cost=excluded.cost,
            location=excluded.location, tags=excluded.tags, parts=excluded.parts,
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
        json.dumps(data["parts"]),
        json.dumps(data),
    ))


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
        SELECT id, title, status, priority, started, completed, cost, location, tags, parts
        FROM repairs ORDER BY
            CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
            started DESC
    """).fetchall()

    repairs = []
    summary = {
        "total": 0,
        "total_cost": 0,
        "by_status": {},
        "by_priority": {},
        "by_location": {},
        "by_tag": {},
    }

    for row in rows:
        tags = json.loads(row["tags"]) if row["tags"] else []
        parts = json.loads(row["parts"]) if row["parts"] else []
        repair = {
            "id": row["id"],
            "title": row["title"],
            "status": row["status"],
            "priority": row["priority"],
            "started": row["started"],
            "completed": row["completed"],
            "cost": row["cost"] or 0,
            "location": row["location"] or "",
            "tags": tags,
            "parts": parts,
        }
        repairs.append(repair)

        # Aggregate summary
        summary["total"] += 1
        summary["total_cost"] += repair["cost"]
        summary["by_status"][repair["status"]] = summary["by_status"].get(repair["status"], 0) + 1
        summary["by_priority"][repair["priority"]] = summary["by_priority"].get(repair["priority"], 0) + 1
        if repair["location"]:
            summary["by_location"][repair["location"]] = summary["by_location"].get(repair["location"], 0) + 1
        for tag in tags:
            summary["by_tag"][tag] = summary["by_tag"].get(tag, 0) + 1

    summary["total_cost"] = round(summary["total_cost"], 2)

    output = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "repairs": repairs,
        "summary": summary,
    }

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    conn.close()
    print(f"Wrote {json_path} ({summary['total']} repairs, ${summary['total_cost']:.2f} total)")


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
