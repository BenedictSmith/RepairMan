#!/usr/bin/env python3
"""RepairMan dev server — serves the dashboard and auto-syncs on file changes.

Uses Server-Sent Events (SSE) to push reload notifications to the browser.

Usage:
    python db/serve.py [port]    # default port: 5050
"""

import http.server
import json
import os
import socketserver
import sys
import threading
import time
from pathlib import Path

# Reuse sync logic
from sync import DB_PATH, REPAIRS_DIR, JSON_PATH, import_all, export_json, init_db

DASHBOARD_DIR = JSON_PATH.parent
POLL_INTERVAL = 1  # seconds

# SSE clients — each is a wfile we can write to
sse_clients = []
sse_lock = threading.Lock()


def notify_clients():
    """Send an SSE event to all connected browsers."""
    with sse_lock:
        dead = []
        for client in sse_clients:
            try:
                client.write(b"data: reload\n\n")
                client.flush()
            except Exception:
                dead.append(client)
        for client in dead:
            sse_clients.remove(client)


def get_file_states(directory):
    """Get modification times for all .md files in a directory."""
    states = {}
    for f in directory.glob("*.md"):
        try:
            states[str(f)] = f.stat().st_mtime
        except OSError:
            pass
    return states


def watch_and_sync():
    """Poll repairs/ for changes and re-sync when detected."""
    print(f"Watching {REPAIRS_DIR} for changes...")
    last_states = get_file_states(REPAIRS_DIR)

    while True:
        time.sleep(POLL_INTERVAL)
        current_states = get_file_states(REPAIRS_DIR)

        if current_states != last_states:
            added = set(current_states) - set(last_states)
            removed = set(last_states) - set(current_states)
            modified = {f for f in set(current_states) & set(last_states)
                        if current_states[f] != last_states[f]}

            changes = []
            for f in added:
                changes.append(f"  + {Path(f).name}")
            for f in removed:
                changes.append(f"  - {Path(f).name}")
            for f in modified:
                changes.append(f"  ~ {Path(f).name}")

            print(f"\nChange detected:")
            print("\n".join(changes))

            try:
                import_all(DB_PATH, REPAIRS_DIR)
                export_json(DB_PATH, JSON_PATH)
                print("Synced — pushing update to browser.\n")
                notify_clients()
            except Exception as e:
                print(f"Sync error: {e}\n")

            last_states = current_states


class RepairManHandler(http.server.SimpleHTTPRequestHandler):
    """Serves static files + an SSE endpoint at /events."""

    def do_GET(self):
        if self.path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            with sse_lock:
                sse_clients.append(self.wfile)

            # Keep connection open
            try:
                while True:
                    time.sleep(1)
            except Exception:
                pass
            finally:
                with sse_lock:
                    if self.wfile in sse_clients:
                        sse_clients.remove(self.wfile)
        else:
            super().do_GET()

    def log_message(self, format, *args):
        if self.path != "/events":
            super().log_message(format, *args)


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def serve(port):
    """Start the HTTP server for the dashboard."""
    os.chdir(str(DASHBOARD_DIR))
    httpd = ThreadedHTTPServer(("", port), RepairManHandler)
    print(f"Dashboard: http://localhost:{port}")
    httpd.serve_forever()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5050

    # Initial sync
    print("Running initial sync...")
    import_all(DB_PATH, REPAIRS_DIR)
    export_json(DB_PATH, JSON_PATH)
    print()

    # Start watcher in background thread
    watcher = threading.Thread(target=watch_and_sync, daemon=True)
    watcher.start()

    # Serve dashboard (blocks)
    serve(port)


if __name__ == "__main__":
    main()
