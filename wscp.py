import os
import socket
import json
import time
import uuid
import hashlib
import threading
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zipfile import ZipFile
from datetime import datetime
from urllib.parse import unquote, urlparse, parse_qs

try:
    from textual.app import App, ComposeResult
    from textual.widgets import Button, Static, Checkbox
    from textual.containers import Vertical, Horizontal, VerticalScroll
    TEXTUAL_AVAILABLE = True
except Exception:
    TEXTUAL_AVAILABLE = False

UPLOAD_FOLDER = "shared_files"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_ROOT = os.path.abspath(os.path.join(BASE_DIR, UPLOAD_FOLDER))

os.makedirs(UPLOAD_ROOT, exist_ok=True)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024 * 1024  # 10 GB hard safety cap
STREAM_CHUNK_SIZE = 1024 * 1024  # 1 MB
TASK_TTL_SECONDS = 3600

TASKS = {}
TASKS_LOCK = threading.Lock()

# Ask permission once at server start
ALLOW_UPLOADS = input("Give uploading permissions (Y/N): ").strip().lower() == 'y'
ALLOWED_PATHS = set()


def _cleanup_tasks():
    cutoff = time.time() - TASK_TTL_SECONDS
    with TASKS_LOCK:
        old_ids = [tid for tid, t in TASKS.items() if t.get("updated_at", 0) < cutoff]
        for tid in old_ids:
            TASKS.pop(tid, None)


def create_task(kind, message="Queued"):
    _cleanup_tasks()
    task_id = uuid.uuid4().hex
    now = time.time()
    with TASKS_LOCK:
        TASKS[task_id] = {
            "task_id": task_id,
            "kind": kind,
            "status": "queued",
            "phase": "queued",
            "message": message,
            "bytes_done": 0,
            "total_bytes": 0,
            "percent": 0,
            "speed_bps": 0,
            "hash_sha256": None,
            "error": None,
            "created_at": now,
            "updated_at": now,
            "started_at": now,
        }
    return task_id


def update_task(task_id, **updates):
    if not task_id:
        return
    with TASKS_LOCK:
        task = TASKS.get(task_id)
        if not task:
            return
        task.update(updates)
        task["updated_at"] = time.time()


def update_task_progress(task_id, bytes_done=None, total_bytes=None, phase=None, message=None):
    if not task_id:
        return
    with TASKS_LOCK:
        task = TASKS.get(task_id)
        if not task:
            return
        if bytes_done is not None:
            task["bytes_done"] = max(0, int(bytes_done))
        if total_bytes is not None:
            task["total_bytes"] = max(0, int(total_bytes))
        if phase is not None:
            task["phase"] = phase
        if message is not None:
            task["message"] = message
        task["status"] = "running"
        elapsed = max(time.time() - task.get("started_at", time.time()), 0.001)
        task["speed_bps"] = int(task.get("bytes_done", 0) / elapsed)
        total = task.get("total_bytes", 0)
        if total > 0:
            task["percent"] = min(100, int((task.get("bytes_done", 0) * 100) / total))
        task["updated_at"] = time.time()


def finish_task(task_id, message="Completed", hash_sha256=None):
    if not task_id:
        return
    with TASKS_LOCK:
        task = TASKS.get(task_id)
        if not task:
            return
        if hash_sha256:
            task["hash_sha256"] = hash_sha256
        total = task.get("total_bytes", 0)
        if total > 0:
            task["bytes_done"] = total
        task["percent"] = 100
        task["status"] = "done"
        task["phase"] = "done"
        task["message"] = message
        task["updated_at"] = time.time()


def fail_task(task_id, error_message):
    if not task_id:
        return
    with TASKS_LOCK:
        task = TASKS.get(task_id)
        if not task:
            return
        task["status"] = "error"
        task["phase"] = "error"
        task["message"] = "Failed"
        task["error"] = str(error_message)
        task["updated_at"] = time.time()


def get_task(task_id):
    with TASKS_LOCK:
        task = TASKS.get(task_id)
        if not task:
            return None
        return dict(task)


def sanitize_filename(filename):
    cleaned = os.path.basename((filename or "").replace("\x00", "")).strip()
    return cleaned or f"upload_{int(time.time())}.bin"


def sanitize_folder_name(folder_name):
    raw = (folder_name or "").replace("\x00", "").strip()
    raw = raw.replace("\\", "/").split("/")[-1].strip()
    if not raw or raw in (".", ".."):
        return None
    invalid_chars = set('<>:"/\\|?*')
    if any(ch in invalid_chars for ch in raw):
        return None
    if raw.endswith(" ") or raw.endswith("."):
        return None
    return raw


def get_unique_file_path(directory, filename):
    base_name = sanitize_filename(filename)
    stem, ext = os.path.splitext(base_name)
    candidate = os.path.join(directory, base_name)
    counter = 1
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{stem} ({counter}){ext}")
        counter += 1
    return candidate


def get_unique_dir_path(directory, folder_name):
    base_name = sanitize_folder_name(folder_name) or f"folder_{int(time.time())}"
    candidate = os.path.join(directory, base_name)
    counter = 1
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{base_name} ({counter})")
        counter += 1
    return candidate


def parse_bool(value):
    return str(value).lower() in ("1", "true", "yes", "y", "on")


def is_likely_text_file(file_path, sample_size=65536):
    try:
        with open(file_path, "rb") as f:
            sample = f.read(sample_size)
    except OSError:
        return False

    if not sample:
        return True
    if b"\x00" in sample:
        return False

    try:
        decoded = sample.decode("utf-8")
    except UnicodeDecodeError:
        decoded = sample.decode("utf-8", errors="ignore")
        if not decoded:
            return False

    printable = sum(1 for ch in decoded if ch.isprintable() or ch in "\r\n\t")
    ratio = printable / max(len(decoded), 1)
    return ratio >= 0.86


def collect_files_for_paths(client_paths):
    files = []
    for raw in client_paths:
        abs_path = resolve_client_path(unquote(raw))
        if not ALLOW_UPLOADS and not is_target_allowed(abs_path):
            continue
        if os.path.isfile(abs_path):
            rel = os.path.relpath(abs_path, UPLOAD_ROOT).replace("\\", "/")
            files.append((abs_path, rel, os.path.getsize(abs_path)))
        elif os.path.isdir(abs_path):
            for root, _, names in os.walk(abs_path):
                for name in names:
                    file_abs = os.path.join(root, name)
                    if not ALLOW_UPLOADS and not is_target_allowed(file_abs):
                        continue
                    rel = os.path.relpath(file_abs, UPLOAD_ROOT).replace("\\", "/")
                    try:
                        size = os.path.getsize(file_abs)
                    except OSError:
                        size = 0
                    files.append((file_abs, rel, size))
    return files


def is_target_allowed(abs_path):
    """Direct access rule: target must be selected or inside a selected folder."""
    if ALLOW_UPLOADS:
        return True
    if not ALLOWED_PATHS:
        return False

    norm = os.path.abspath(abs_path)
    for allowed in ALLOWED_PATHS:
        if norm == allowed or norm.startswith(allowed + os.sep):
            return True
    return False


def is_path_visible(abs_path):
    """Navigation rule: show selected targets and parent folders leading to them."""
    if ALLOW_UPLOADS:
        return True
    if not ALLOWED_PATHS:
        return False

    norm = os.path.abspath(abs_path)
    if is_target_allowed(norm):
        return True

    if os.path.isdir(norm):
        prefix = norm + os.sep
        for allowed in ALLOWED_PATHS:
            if allowed.startswith(prefix):
                return True
    return False

def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def to_web_path(abs_path):
    """Convert absolute filesystem path to client-facing path token."""
    rel = os.path.relpath(abs_path, UPLOAD_ROOT)
    if rel == ".":
        return UPLOAD_FOLDER
    return f"{UPLOAD_FOLDER}/" + rel.replace("\\", "/")

def resolve_client_path(raw_path=None):
    """Resolve and constrain client path tokens to UPLOAD_ROOT."""
    if not raw_path:
        return UPLOAD_ROOT

    normalized = raw_path.replace("\\", "/").strip()
    if normalized in ("", "/", UPLOAD_FOLDER):
        return UPLOAD_ROOT

    if normalized.startswith(UPLOAD_FOLDER + "/"):
        rel = normalized[len(UPLOAD_FOLDER) + 1:]
    else:
        rel = normalized.lstrip("/")

    candidate = os.path.abspath(os.path.join(UPLOAD_ROOT, rel))
    if candidate == UPLOAD_ROOT or candidate.startswith(UPLOAD_ROOT + os.sep):
        return candidate

    return UPLOAD_ROOT


def list_shareable_entries():
    entries = []
    for root, dirs, files in os.walk(UPLOAD_ROOT):
        dirs.sort()
        files.sort()
        for name in dirs:
            abs_path = os.path.join(root, name)
            rel = os.path.relpath(abs_path, UPLOAD_ROOT).replace("\\", "/")
            entries.append({"abs": abs_path, "rel": rel, "kind": "Folder"})
        for name in files:
            abs_path = os.path.join(root, name)
            rel = os.path.relpath(abs_path, UPLOAD_ROOT).replace("\\", "/")
            entries.append({"abs": abs_path, "rel": rel, "kind": "File"})
    return entries


if TEXTUAL_AVAILABLE:
    class AccessSelectorApp(App):
        BINDINGS = [
            ("ctrl+a", "select_all_items", "Select All"),
            ("ctrl+d", "clear_items", "Clear"),
        ]

        CSS = """
        Screen {
            background: #0a0a0a;
            color: #ffffff;
        }
        #title {
            padding: 1 2 0 2;
            text-style: bold;
            color: #ffffff;
        }
        #hint {
            padding: 0 2 1 2;
            color: #bbbbbb;
        }
        #list {
            height: 1fr;
            margin: 0 2;
            border: solid #3a3a3a;
            padding: 0 1;
        }
        #status {
            padding: 1 2 0 2;
            color: #d0d0d0;
        }
        #actions {
            height: auto;
            padding: 1 2;
        }
        Button {
            margin-right: 1;
            min-width: 16;
        }
        Checkbox {
            margin: 0;
            padding: 0 1;
        }
        """

        def __init__(self, entries):
            super().__init__()
            self.entries = entries
            self.status = None

        def compose(self) -> ComposeResult:
            yield Vertical(
                Static("Download-Only Access Selector", id="title"),
                Static("Mouse: click checkboxes to select. Ctrl+A select all, Ctrl+D clear.", id="hint"),
                VerticalScroll(id="list"),
                Static("Selected: 0", id="status"),
                Horizontal(
                    Button("Select All", id="select_all"),
                    Button("Clear", id="clear"),
                    Button("Start Server", id="start", variant="success"),
                    Button("Cancel", id="cancel", variant="error"),
                    id="actions",
                ),
            )

        def on_mount(self) -> None:
            self.status = self.query_one("#status", Static)
            list_view = self.query_one("#list", VerticalScroll)
            for idx, item in enumerate(self.entries):
                icon = "[DIR]" if item["kind"] == "Folder" else "[FILE]"
                cb = Checkbox(f"{icon} {item['rel']}", id=f"entry-{idx}")
                list_view.mount(cb)
            self.update_status()

        def get_selected_indices(self):
            selected = []
            for cb in self.query(Checkbox):
                if cb.value and cb.id and cb.id.startswith("entry-"):
                    selected.append(int(cb.id.split("-", 1)[1]))
            return selected

        def update_status(self):
            self.status.update(f"Selected: {len(self.get_selected_indices())} / {len(self.entries)}")

        def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
            self.update_status()

        def action_select_all_items(self):
            for cb in self.query(Checkbox):
                cb.value = True
            self.update_status()

        def action_clear_items(self):
            for cb in self.query(Checkbox):
                cb.value = False
            self.update_status()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "select_all":
                self.action_select_all_items()
            elif event.button.id == "clear":
                self.action_clear_items()
            elif event.button.id == "start":
                selected_indices = self.get_selected_indices()
                if not selected_indices:
                    self.status.update("Select at least one item to continue.")
                    return
                selected_paths = {self.entries[i]["abs"] for i in selected_indices}
                self.exit(selected_paths)
            elif event.button.id == "cancel":
                self.exit(None)


def cli_access_selector(entries):
    if not entries:
        return set()

    selected_indexes = set()
    search_term = ""
    max_show = 25

    def current_filtered_indexes():
        if not search_term:
            return list(range(len(entries)))
        needle = search_term.lower()
        return [
            i for i, item in enumerate(entries)
            if needle in item["rel"].lower() or needle in item["kind"].lower()
        ]

    def print_visible(filtered, shown):
        print("\n=== Access Selector ===")
        print("1. Search   2. Select (space numbers)   3. Select all   4. Done")
        if search_term:
            print(f"Filter: '{search_term}'")
        print(f"Visible: {len(filtered)} | Selected: {len(selected_indexes)}")
        print("----------------------------------------")
        if not filtered:
            print("No entries match current filter.")
            return
        for n, idx in enumerate(shown, start=1):
            item = entries[idx]
            mark = "[x]" if idx in selected_indexes else "[ ]"
            kind_mark = "D" if item["kind"] == "Folder" else "F"
            print(f"{n:4d}. {mark} [{kind_mark}] {item['rel']}")
        if len(filtered) > len(shown):
            print(f"... showing first {len(shown)} only. Use search to narrow.")

    def parse_toggle_numbers(spec, shown):
        toggles = []
        if not spec:
            return toggles
        spec = spec.replace(",", " ")
        parts = [p.strip() for p in spec.split() if p.strip()]
        for part in parts:
            if "-" in part:
                left, right = part.split("-", 1)
                if left.isdigit() and right.isdigit():
                    start = int(left)
                    end = int(right)
                    if start > end:
                        start, end = end, start
                    for num in range(start, end + 1):
                        if 1 <= num <= len(shown):
                            toggles.append(shown[num - 1])
            elif part.isdigit():
                num = int(part)
                if 1 <= num <= len(shown):
                    toggles.append(shown[num - 1])
        return toggles

    while True:
        filtered = current_filtered_indexes()
        shown = filtered[:max_show]
        print_visible(filtered, shown)
        try:
            raw = input("action (1/2/3/4, c clear, n none, q quit): ").strip()
        except EOFError:
            return set()
        if not raw:
            continue

        lowered = raw.lower()
        if lowered in ("q", "quit", "exit"):
            return set()
        if lowered in ("4", "done", "start"):
            return {entries[i]["abs"] for i in sorted(selected_indexes)}
        if lowered in ("c", "clear-search"):
            search_term = ""
            continue
        if lowered in ("3", "a", "all"):
            for idx in filtered:
                selected_indexes.add(idx)
            continue
        if lowered in ("n", "none", "clear"):
            selected_indexes.clear()
            continue

        if lowered == "1" or lowered.startswith("1 "):
            term = raw[1:].strip()
            if not term:
                term = input("search text: ").strip()
            search_term = term
            continue

        if lowered == "2" or lowered.startswith("2 "):
            spec = raw[1:].strip()
            if not spec:
                spec = input("numbers (space-separated or range e.g. 1 3-5): ").strip()
            toggles = parse_toggle_numbers(spec, shown)
            if not toggles:
                print("No valid numbers to toggle.")
            for idx in toggles:
                if idx in selected_indexes:
                    selected_indexes.remove(idx)
                else:
                    selected_indexes.add(idx)
            continue

        print("Unknown action.")


def get_download_only_allowlist():
    entries = list_shareable_entries()
    if not entries:
        return set()
    print("[i] Download-only selector started (CLI mode).")
    return cli_access_selector(entries)

def build_folder_tree(path=None):
    """Build nested folder structure (folders only)"""
    if path is None:
        path = UPLOAD_ROOT
    
    tree = {
        "name": os.path.basename(path) or "[root]",
        "path": to_web_path(path),
        "children": []
    }
    
    try:
        for item in sorted(os.listdir(path)):
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path) and is_path_visible(item_path):
                tree["children"].append(build_folder_tree(item_path))
    except PermissionError:
        pass
    
    return tree

def get_folder_contents(path=None):
    """Get files and folders in a directory with metadata"""
    if path is None:
        path = UPLOAD_ROOT
    
    items = []
    try:
        for item in sorted(os.listdir(path)):
            item_path = os.path.join(path, item)
            if not is_path_visible(item_path):
                continue
            is_dir = os.path.isdir(item_path)
            
            try:
                mod_time = os.path.getmtime(item_path)
                date_str = datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d %H:%M:%S")
            except:
                date_str = "Unknown"
            
            size = 0
            if not is_dir:
                try:
                    size = os.path.getsize(item_path)
                except:
                    pass
            
            is_text_file = (not is_dir) and is_likely_text_file(item_path)
            
            items.append({
                "name": item,
                "path": to_web_path(item_path),
                "is_dir": is_dir,
                "size": size,
                "date": date_str,
                "is_text": is_text_file
            })
    except PermissionError:
        pass
    
    return items


class CustomHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            
            html = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <title>🎉 File Sharing Server</title>
                <link href="https://fonts.googleapis.com/css2?family=Inter:wght@500;700&display=swap" rel="stylesheet">
                <style>
                    * {{
                        margin: 0;
                        padding: 0;
                        box-sizing: border-box;
                    }}

                    :root {{
                        --bg-0: #000000;
                        --bg-1: #080808;
                        --bg-2: #101010;
                        --bg-3: #171717;
                        --line-1: #242424;
                        --line-2: #343434;
                        --text-1: #ffffff;
                        --text-2: #d5d5d5;
                        --text-3: #9b9b9b;
                        --radius-1: 8px;
                        --radius-2: 10px;
                        --btn-h: 34px;
                    }}
                    
                    body {{
                        font-family: 'Inter', sans-serif;
                        background-color: var(--bg-0);
                        color: var(--text-1);
                        display: flex;
                        flex-direction: column;
                        height: 100vh;
                    }}

                    button {{
                        font-family: 'Inter', sans-serif;
                    }}
                    
                    .container {{
                        display: flex;
                        flex: 1;
                        overflow: hidden;
                    }}
                    
                    .sidebar {{
                        width: 280px;
                        background: linear-gradient(180deg, #0d0d0d 0%, #090909 100%);
                        border-right: 1px solid var(--line-1);
                        overflow-y: auto;
                        padding: 20px 15px;
                        font-size: 13px;
                    }}
                    
                    .main-content {{
                        flex: 1;
                        display: flex;
                        flex-direction: column;
                        overflow: hidden;
                        background-color: var(--bg-0);
                    }}
                    
                    .toolbar {{
                        background-color: var(--bg-2);
                        border-bottom: 1px solid var(--line-1);
                        padding: 12px 20px;
                        display: flex;
                        gap: 8px;
                        align-items: center;
                        justify-content: flex-start;
                    }}
                    
                    .toolbar .spacer {{
                        flex: 1;
                    }}
                    
                    .toolbar .bulk-actions {{
                        display: none;
                        gap: 8px;
                    }}
                    
                    .toolbar .bulk-actions.show {{
                        display: flex;
                    }}

                    .toolbar button,
                    .breadcrumb button,
                    .close-btn,
                    .action-btn,
                    .dialog-content button {{
                        height: var(--btn-h);
                        border-radius: var(--radius-1);
                        border: 1px solid var(--line-2);
                        padding: 0 12px;
                        cursor: pointer;
                        font-size: 12px;
                        font-weight: 600;
                        letter-spacing: 0.04em;
                        transition: all 0.18s ease;
                        display: inline-flex;
                        align-items: center;
                        justify-content: center;
                        gap: 6px;
                    }}

                    .toolbar button,
                    .dialog-content button {{
                        background-color: var(--text-1);
                        color: #050505;
                        border-color: var(--text-1);
                    }}

                    .toolbar button:hover,
                    .dialog-content button:hover {{
                        background-color: #e8e8e8;
                        border-color: #e8e8e8;
                    }}

                    .toolbar button[disabled] {{
                        opacity: 0.4;
                        cursor: not-allowed;
                    }}

                    .breadcrumb button,
                    .close-btn,
                    .action-btn {{
                        background-color: var(--bg-3);
                        color: var(--text-1);
                    }}

                    .breadcrumb button:hover,
                    .close-btn:hover,
                    .action-btn:hover {{
                        background-color: #232323;
                        border-color: #5a5a5a;
                    }}

                    .toolbar button:focus-visible,
                    .breadcrumb button:focus-visible,
                    .close-btn:focus-visible,
                    .action-btn:focus-visible,
                    .dialog-content button:focus-visible {{
                        outline: 2px solid #9a9a9a;
                        outline-offset: 2px;
                    }}

                    #sidebar-toggle {{
                        width: var(--btn-h);
                        padding: 0;
                    }}

                    #bulk-zip,
                    #bulk-download {{
                        min-width: 108px;
                    }}
                    
                    .sidebar.hidden {{
                        display: none;
                    }}
                    
                    .main-content.fullwidth {{
                        width: 100%;
                    }}
                    
                    .breadcrumb {{
                        background-color: #0d0d0d;
                        border-bottom: 1px solid var(--line-1);
                        padding: 12px 20px;
                        display: flex;
                        align-items: center;
                        gap: 8px;
                        font-size: 12px;
                    }}
                    
                    .breadcrumb span {{
                        color: var(--text-3);
                    }}
                    
                    .table-container {{
                        flex: 1;
                        overflow: auto;
                        padding: 18px;
                        background: linear-gradient(180deg, #050505 0%, #000000 100%);
                    }}
                    
                    .file-table {{
                        width: 100%;
                        min-width: 920px;
                        table-layout: fixed;
                        border-collapse: separate;
                        border-spacing: 0;
                        background-color: #050505;
                        border: 1px solid #1f1f1f;
                        border-radius: var(--radius-2);
                        overflow: hidden;
                    }}
                    
                    .file-table thead {{
                        position: sticky;
                        top: 0;
                        z-index: 10;
                    }}
                    
                    .file-table th {{
                        background-color: #0f0f0f;
                        color: #ffffff;
                        padding: 0 12px;
                        text-align: left;
                        border-bottom: 1px solid #2b2b2b;
                        font-weight: 600;
                        font-size: 11px;
                        letter-spacing: 0.08em;
                        text-transform: uppercase;
                        height: 42px;
                        vertical-align: middle;
                    }}

                    .file-table th.col-size {{
                        text-align: right;
                        padding-right: 22px;
                    }}
                    
                    .file-table td {{
                        padding: 0 12px;
                        border-bottom: 1px solid #191919;
                        color: #d0d0d0;
                        font-size: 12px;
                        height: 48px;
                        line-height: 1;
                        vertical-align: middle;
                    }}
                    
                    .file-table tbody tr {{
                        height: 48px;
                    }}
                    
                    .file-table tbody tr:hover {{
                        background-color: #0b0b0b;
                    }}

                    .file-table tbody tr.folder-row td.col-name {{
                        cursor: pointer;
                    }}
                    
                    .file-table tbody tr:last-child td {{
                        border-bottom: none;
                    }}

                    .col-select {{
                        width: 52px;
                        text-align: center;
                        padding: 0 8px;
                    }}

                    .col-name {{
                        width: 34%;
                    }}

                    .col-size {{
                        width: 14%;
                        text-align: right;
                        padding-right: 22px;
                        color: #b8b8b8;
                        font-variant-numeric: tabular-nums;
                    }}

                    .col-type {{
                        width: 12%;
                        color: #b8b8b8;
                    }}

                    .col-date {{
                        width: 22%;
                        color: #a6a6a6;
                        font-variant-numeric: tabular-nums;
                    }}

                    .col-action {{
                        width: 18%;
                    }}
                    
                    .filename {{
                        color: #ffffff;
                        cursor: pointer;
                        font-weight: 500;
                        white-space: nowrap;
                        overflow: hidden;
                        text-overflow: ellipsis;
                    }}
                    
                    .filename:hover {{
                        color: #f1f1f1;
                    }}
                    
                    .action-slot {{
                        display: flex;
                        align-items: center;
                        justify-content: flex-start;
                        gap: 8px;
                        min-height: 48px;
                    }}
                    
                    .action-btn {{
                        height: 30px;
                        min-width: 64px;
                        padding: 0 12px;
                        font-size: 11px;
                        letter-spacing: 0.06em;
                    }}

                    .action-placeholder {{
                        color: #5a5a5a;
                        font-size: 13px;
                        font-weight: 600;
                    }}
                    
                    .tree-item {{
                        margin: 4px 0;
                        color: var(--text-2);
                        padding: 8px 10px;
                        border-radius: var(--radius-1);
                        border: 1px solid transparent;
                        transition: all 0.2s;
                    }}
                    
                    .tree-item.folder {{
                        cursor: pointer;
                        user-select: none;
                    }}
                    
                    .tree-item.folder:hover {{
                        background-color: #171717;
                        border-color: #2f2f2f;
                        color: var(--text-1);
                    }}
                    
                    .tree-item.active {{
                        background-color: #1f1f1f;
                        border-color: #3a3a3a;
                        color: var(--text-1);
                        font-weight: 600;
                    }}
                    
                    .tree-children {{
                        margin-left: 12px;
                        display: none;
                    }}
                    
                    .tree-children.open {{
                        display: block;
                    }}
                    
                    .tree-toggle {{
                        cursor: pointer;
                        color: #7d7d7d;
                        margin-right: 6px;
                        user-select: none;
                        font-weight: bold;
                    }}
                    
                    .modal {{
                        display: none;
                        position: fixed;
                        z-index: 1000;
                        left: 0;
                        top: 0;
                        width: 100%;
                        height: 100%;
                        background-color: rgba(0, 0, 0, 0.8);
                    }}
                    
                    .modal.show {{
                        display: flex;
                        align-items: center;
                        justify-content: center;
                    }}
                    
                    .modal-content {{
                        background: linear-gradient(180deg, #121212 0%, #0d0d0d 100%);
                        padding: 18px;
                        border: 1px solid #2d2d2d;
                        border-radius: 12px;
                        width: 85%;
                        height: 85%;
                        display: flex;
                        flex-direction: column;
                        position: relative;
                        box-shadow: 0 10px 40px rgba(0,0,0,0.7);
                    }}
                    
                    .modal-header {{
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        margin-bottom: 15px;
                        border-bottom: 1px solid #2a2a2a;
                        padding-bottom: 12px;
                    }}
                    
                    .modal-header h2 {{
                        color: var(--text-1);
                        font-size: 16px;
                        font-weight: 600;
                    }}
                    
                    .modal-body {{
                        flex: 1;
                        overflow: auto;
                        background-color: #080808;
                        border: 1px solid #1f1f1f;
                        border-radius: var(--radius-1);
                        padding: 12px;
                        font-family: 'Courier New', monospace;
                        font-size: 12px;
                        white-space: pre-wrap;
                        word-wrap: break-word;
                        color: var(--text-1);
                    }}
                    
                    .row-checkbox {{
                        width: 20px;
                        height: 20px;
                        cursor: pointer;
                        accent-color: #ffffff;
                    }}
                    
                    .custom-dialog {{
                        position: fixed;
                        top: 0;
                        left: 0;
                        width: 100%;
                        height: 100%;
                        background-color: rgba(0, 0, 0, 0.78);
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        z-index: 1000;
                    }}
                    
                    .dialog-content {{
                        background: linear-gradient(180deg, #1a1a1a 0%, #121212 100%);
                        border: 1px solid #3a3a3a;
                        border-radius: 12px;
                        padding: 24px 28px;
                        max-width: 420px;
                        width: calc(100% - 28px);
                        text-align: center;
                        color: var(--text-1);
                        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6);
                    }}
                    
                    .dialog-content p {{
                        margin: 0 0 24px 0;
                        font-size: 13px;
                        line-height: 1.5;
                        color: #dddddd;
                    }}

                    .dialog-title {{
                        font-size: 15px;
                        font-weight: 700;
                        margin-bottom: 10px;
                        color: var(--text-1);
                    }}

                    .dialog-subtitle {{
                        font-size: 12px;
                        color: var(--text-3);
                        margin-bottom: 14px;
                    }}

                    .dialog-row {{
                        display: flex;
                        align-items: center;
                        justify-content: space-between;
                        gap: 12px;
                        margin: 10px 0;
                    }}

                    .dialog-row input[type="checkbox"] {{
                        width: 16px;
                        height: 16px;
                        accent-color: #ffffff;
                    }}

                    .dialog-row label {{
                        font-size: 12px;
                        color: var(--text-2);
                        display: flex;
                        align-items: center;
                        gap: 8px;
                    }}

                    .dialog-content input[type="file"] {{
                        width: 100%;
                        margin: 8px 0 14px;
                        color: var(--text-2);
                        font-size: 12px;
                    }}

                    .dialog-actions {{
                        display: flex;
                        justify-content: flex-end;
                        gap: 10px;
                        margin-top: 14px;
                    }}

                    .dialog-actions .ghost-btn {{
                        background: var(--bg-3);
                        color: var(--text-1);
                        border: 1px solid var(--line-2);
                    }}

                    .progress-wrap {{
                        width: 100%;
                        height: 10px;
                        border-radius: 999px;
                        border: 1px solid #303030;
                        background: #090909;
                        overflow: hidden;
                        margin: 12px 0 10px;
                    }}

                    .progress-fill {{
                        height: 100%;
                        width: 0%;
                        background: linear-gradient(90deg, #f4f4f4 0%, #bdbdbd 100%);
                        transition: width 0.18s ease;
                    }}

                    .progress-meta {{
                        display: flex;
                        justify-content: space-between;
                        font-size: 11px;
                        color: var(--text-3);
                        margin-bottom: 8px;
                    }}

                    .dialog-result {{
                        margin-top: 10px;
                        font-size: 12px;
                        color: var(--text-2);
                        word-break: break-all;
                    }}

                    .drop-overlay {{
                        position: fixed;
                        inset: 0;
                        z-index: 1100;
                        display: none;
                        align-items: center;
                        justify-content: center;
                        background: rgba(0, 0, 0, 0.72);
                    }}

                    .drop-overlay.show {{
                        display: flex;
                    }}

                    .drop-panel {{
                        width: min(560px, calc(100% - 28px));
                        border: 1px dashed #6a6a6a;
                        border-radius: 12px;
                        background: linear-gradient(180deg, #141414 0%, #0e0e0e 100%);
                        padding: 26px;
                        text-align: center;
                        color: var(--text-2);
                        font-size: 13px;
                    }}
                    .mode-badge {{
                        margin-left: 8px;
                        font-size: 11px;
                        color: #0a0a0a;
                        background: #d8d8d8;
                        border: 1px solid #d8d8d8;
                        border-radius: 999px;
                        padding: 5px 10px;
                        font-weight: 700;
                        letter-spacing: 0.04em;
                        text-transform: uppercase;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="sidebar" id="sidebar"></div>
                    <div class="main-content">
                        <div class="toolbar">
                            <button id="sidebar-toggle" aria-label="Toggle sidebar">⇆</button>
                            <button id="upload-btn">Upload</button>
                            <button id="mkdir-btn">New Folder</button>
                            {"<span class='mode-badge'>Restricted Share</span>" if not ALLOW_UPLOADS else ""}
                            <div class="spacer"></div>
                            <div class="bulk-actions" id="bulk-actions">
                                <button id="bulk-zip">Zip</button>
                                <button id="bulk-download">Download</button>
                            </div>
                        </div>
                        <div class="breadcrumb" id="breadcrumb"></div>
                        <div class="table-container">
                            <table class="file-table">
                                <thead>
                                    <tr>
                                        <th class="col-select"></th>
                                        <th class="col-name">File Name</th>
                                        <th class="col-size">Size</th>
                                        <th class="col-type">Type</th>
                                        <th class="col-date">Date</th>
                                        <th class="col-action">Action</th>
                                    </tr>
                                </thead>
                                <tbody id="file-table"></tbody>
                            </table>
                        </div>
                    </div>
                </div>
                
                <div class="modal" id="file-modal">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h2 id="modal-title">File Viewer</h2>
                            <button class="close-btn" onclick="document.getElementById('file-modal').classList.remove('show')">✕</button>
                        </div>
                        <div class="modal-body" id="modal-body"></div>
                    </div>
                </div>

                <div class="drop-overlay" id="drop-overlay">
                    <div class="drop-panel">Drop files here to upload</div>
                </div>
                
                <script>
                    let currentPath = "{UPLOAD_FOLDER}";
                    const uploadsEnabled = {str(ALLOW_UPLOADS).lower()};
                    const modal = document.getElementById('file-modal');
                    const dropOverlay = document.getElementById('drop-overlay');
                    let itemMap = new Map();
                    let selectedItems = new Set();
                    let dragCounter = 0;

                    function ensureWriteEnabled() {{
                        if (!uploadsEnabled) {{
                            showDialog('Server is in download-only mode. Upload and folder creation are disabled.');
                            return false;
                        }}
                        return true;
                    }}

                    function createDialogContainer(title, subtitle = '') {{
                        const dialogDiv = document.createElement('div');
                        dialogDiv.className = 'custom-dialog';

                        const content = document.createElement('div');
                        content.className = 'dialog-content';

                        const h = document.createElement('div');
                        h.className = 'dialog-title';
                        h.textContent = title;
                        content.appendChild(h);

                        if (subtitle) {{
                            const sub = document.createElement('div');
                            sub.className = 'dialog-subtitle';
                            sub.textContent = subtitle;
                            content.appendChild(sub);
                        }}

                        dialogDiv.appendChild(content);
                        document.body.appendChild(dialogDiv);
                        return {{ dialogDiv, content }};
                    }}

                    function showDialog(message) {{
                        const ui = createDialogContainer('Notice', '');
                        const p = document.createElement('p');
                        p.textContent = message;
                        ui.content.appendChild(p);

                        const actions = document.createElement('div');
                        actions.className = 'dialog-actions';
                        const btn = document.createElement('button');
                        btn.textContent = 'OK';
                        btn.onclick = function() {{ ui.dialogDiv.remove(); }};
                        actions.appendChild(btn);
                        ui.content.appendChild(actions);
                    }}

                    function createProgressDialog(title, subtitle = '') {{
                        const ui = createDialogContainer(title, subtitle);

                        const status = document.createElement('div');
                        status.className = 'dialog-subtitle';
                        status.textContent = 'Preparing...';
                        ui.content.appendChild(status);

                        const wrap = document.createElement('div');
                        wrap.className = 'progress-wrap';
                        const fill = document.createElement('div');
                        fill.className = 'progress-fill';
                        wrap.appendChild(fill);
                        ui.content.appendChild(wrap);

                        const meta = document.createElement('div');
                        meta.className = 'progress-meta';
                        const pct = document.createElement('span');
                        pct.textContent = '0%';
                        const speed = document.createElement('span');
                        speed.textContent = '';
                        meta.appendChild(pct);
                        meta.appendChild(speed);
                        ui.content.appendChild(meta);

                        const result = document.createElement('div');
                        result.className = 'dialog-result';
                        ui.content.appendChild(result);

                        const actions = document.createElement('div');
                        actions.className = 'dialog-actions';
                        const closeBtn = document.createElement('button');
                        closeBtn.className = 'ghost-btn';
                        closeBtn.textContent = 'Close';
                        closeBtn.onclick = function() {{ ui.dialogDiv.remove(); }};
                        actions.appendChild(closeBtn);
                        ui.content.appendChild(actions);

                        return {{
                            setStatus: (msg) => status.textContent = msg,
                            setProgress: (percent) => {{
                                const p = Math.max(0, Math.min(100, Math.round(percent || 0)));
                                fill.style.width = p + '%';
                                pct.textContent = p + '%';
                            }},
                            setSpeed: (msg) => speed.textContent = msg || '',
                            setResult: (msg) => result.textContent = msg || '',
                            close: () => ui.dialogDiv.remove(),
                        }};
                    }}

                    function formatSpeed(bytesPerSecond) {{
                        if (!bytesPerSecond || bytesPerSecond <= 0) return '';
                        return formatSize(bytesPerSecond) + '/s';
                    }}

                    async function createTask(kind) {{
                        const res = await fetch('/task/new?kind=' + encodeURIComponent(kind));
                        if (!res.ok) throw new Error('Failed to create task');
                        const payload = await res.json();
                        return payload.task_id;
                    }}

                    async function getTask(taskId) {{
                        const res = await fetch('/progress?task_id=' + encodeURIComponent(taskId));
                        if (!res.ok) throw new Error('Progress unavailable');
                        return await res.json();
                    }}

                    async function waitForTaskCompletion(taskId, progressUi) {{
                        const started = Date.now();
                        while (Date.now() - started < 120000) {{
                            const task = await getTask(taskId);
                            if (progressUi) {{
                                progressUi.setProgress(task.percent || 0);
                                progressUi.setStatus(task.message || task.phase || 'Working...');
                                progressUi.setSpeed(formatSpeed(task.speed_bps));
                            }}
                            if (task.status === 'done') return task;
                            if (task.status === 'error') throw new Error(task.error || 'Task failed');
                            await new Promise(resolve => setTimeout(resolve, 350));
                        }}
                        throw new Error('Operation timeout');
                    }}

                    function xhrUpload(url, file, onProgress) {{
                        return new Promise((resolve, reject) => {{
                            const xhr = new XMLHttpRequest();
                            xhr.open('POST', url, true);
                            xhr.onload = function() {{
                                if (xhr.status >= 200 && xhr.status < 300) resolve(xhr.responseText);
                                else reject(new Error('Upload failed (' + xhr.status + ')'));
                            }};
                            xhr.onerror = function() {{ reject(new Error('Upload failed')); }};
                            xhr.upload.onprogress = function(event) {{
                                if (event.lengthComputable && onProgress) onProgress(event.loaded, event.total);
                            }};
                            xhr.send(file);
                        }});
                    }}

                    function xhrDownloadBlob(url, method, body, onProgress) {{
                        return new Promise((resolve, reject) => {{
                            const xhr = new XMLHttpRequest();
                            xhr.open(method, url, true);
                            xhr.responseType = 'blob';
                            xhr.onload = function() {{
                                if (xhr.status >= 200 && xhr.status < 300) resolve(xhr.response);
                                else reject(new Error('Download failed (' + xhr.status + ')'));
                            }};
                            xhr.onerror = function() {{ reject(new Error('Download failed')); }};
                            xhr.onprogress = function(event) {{
                                if (event.lengthComputable && onProgress) onProgress(event.loaded, event.total);
                            }};
                            if (body) {{
                                xhr.setRequestHeader('Content-Type', 'application/json');
                                xhr.send(body);
                            }} else {{
                                xhr.send();
                            }}
                        }});
                    }}

                    function saveBlob(blob, fileName) {{
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = fileName;
                        document.body.appendChild(a);
                        a.click();
                        a.remove();
                        setTimeout(() => URL.revokeObjectURL(url), 1500);
                    }}

                    function openUploadDialog() {{
                        if (!ensureWriteEnabled()) return;
                        const ui = createDialogContainer('Upload Files', 'Upload to: ' + currentPath);

                        const fileInput = document.createElement('input');
                        fileInput.type = 'file';
                        fileInput.multiple = true;
                        ui.content.appendChild(fileInput);

                        const options = document.createElement('div');
                        options.className = 'dialog-row';
                        const hashLabel = document.createElement('label');
                        const hashCheck = document.createElement('input');
                        hashCheck.type = 'checkbox';
                        hashLabel.appendChild(hashCheck);
                        hashLabel.appendChild(document.createTextNode('Calculate SHA-256 after upload'));
                        options.appendChild(hashLabel);
                        ui.content.appendChild(options);

                        const actions = document.createElement('div');
                        actions.className = 'dialog-actions';
                        const cancelBtn = document.createElement('button');
                        cancelBtn.className = 'ghost-btn';
                        cancelBtn.textContent = 'Cancel';
                        cancelBtn.onclick = function() {{ ui.dialogDiv.remove(); }};
                        const startBtn = document.createElement('button');
                        startBtn.textContent = 'Start Upload';
                        startBtn.onclick = async function() {{
                            const files = Array.from(fileInput.files || []);
                            if (files.length === 0) {{
                                showDialog('Select at least one file.');
                                return;
                            }}
                            ui.dialogDiv.remove();
                            for (const file of files) {{
                                await uploadSingleFile(file, hashCheck.checked);
                            }}
                            loadFolderContents(currentPath);
                            loadFolderTree();
                        }};
                        actions.appendChild(cancelBtn);
                        actions.appendChild(startBtn);
                        ui.content.appendChild(actions);
                    }}

                    async function uploadSingleFile(file, withHash) {{
                        const taskId = await createTask('upload');
                        const progress = createProgressDialog('Uploading', file.name);
                        try {{
                            const uploadUrl = '/upload-raw?task_id=' + encodeURIComponent(taskId) +
                                '&path=' + encodeURIComponent(currentPath) +
                                '&filename=' + encodeURIComponent(file.name) +
                                '&hash=' + (withHash ? '1' : '0');

                            const responseText = await xhrUpload(uploadUrl, file, (loaded, total) => {{
                                progress.setProgress((loaded / Math.max(total, 1)) * 100);
                                progress.setStatus('Uploading...');
                            }});

                            const task = await waitForTaskCompletion(taskId, progress);
                            const response = JSON.parse(responseText);
                            const resultText = task.hash_sha256 ? 'SHA-256: ' + task.hash_sha256 : 'Upload complete';
                            progress.setStatus('Completed');
                            progress.setProgress(100);
                            progress.setResult(resultText + ' | Saved as: ' + response.name);
                        }} catch (e) {{
                            progress.setStatus('Failed');
                            progress.setResult(e.message);
                        }}
                    }}

                    async function uploadFilesBatch(files, withHash = false) {{
                        if (!ensureWriteEnabled()) return;
                        if (!files || files.length === 0) return;
                        for (const file of files) {{
                            await uploadSingleFile(file, withHash);
                        }}
                        await loadFolderContents(currentPath);
                        await loadFolderTree();
                    }}

                    function openMkdirDialog() {{
                        if (!ensureWriteEnabled()) return;
                        const ui = createDialogContainer('Create Folder', 'Location: ' + currentPath);

                        const input = document.createElement('input');
                        input.type = 'text';
                        input.placeholder = 'Folder name';
                        input.style.width = '100%';
                        input.style.height = '34px';
                        input.style.padding = '0 10px';
                        input.style.borderRadius = '8px';
                        input.style.border = '1px solid #3a3a3a';
                        input.style.background = '#0f0f0f';
                        input.style.color = '#ffffff';
                        ui.content.appendChild(input);

                        const actions = document.createElement('div');
                        actions.className = 'dialog-actions';
                        const cancelBtn = document.createElement('button');
                        cancelBtn.className = 'ghost-btn';
                        cancelBtn.textContent = 'Cancel';
                        cancelBtn.onclick = function() {{ ui.dialogDiv.remove(); }};
                        const createBtn = document.createElement('button');
                        createBtn.textContent = 'Create';
                        createBtn.onclick = async function() {{
                            const name = (input.value || '').trim();
                            if (!name) {{
                                showDialog('Enter a folder name.');
                                return;
                            }}
                            try {{
                                const res = await fetch('/mkdir', {{
                                    method: 'POST',
                                    headers: {{ 'Content-Type': 'application/json' }},
                                    body: JSON.stringify({{ path: currentPath, name }}),
                                }});
                                const data = await res.json();
                                if (!res.ok) throw new Error(data.error || 'Failed to create folder');
                                ui.dialogDiv.remove();
                                await loadFolderContents(currentPath);
                                await loadFolderTree();
                            }} catch (e) {{
                                showDialog(e.message);
                            }}
                        }};
                        actions.appendChild(cancelBtn);
                        actions.appendChild(createBtn);
                        ui.content.appendChild(actions);
                        input.focus();
                    }}

                    function openDownloadDialog(filePath, fileName) {{
                        const ui = createDialogContainer('Download File', fileName);
                        const options = document.createElement('div');
                        options.className = 'dialog-row';
                        const hashLabel = document.createElement('label');
                        const hashCheck = document.createElement('input');
                        hashCheck.type = 'checkbox';
                        hashLabel.appendChild(hashCheck);
                        hashLabel.appendChild(document.createTextNode('Calculate SHA-256 while downloading'));
                        options.appendChild(hashLabel);
                        ui.content.appendChild(options);

                        const actions = document.createElement('div');
                        actions.className = 'dialog-actions';
                        const cancelBtn = document.createElement('button');
                        cancelBtn.className = 'ghost-btn';
                        cancelBtn.textContent = 'Cancel';
                        cancelBtn.onclick = function() {{ ui.dialogDiv.remove(); }};
                        const startBtn = document.createElement('button');
                        startBtn.textContent = 'Download';
                        startBtn.onclick = async function() {{
                            ui.dialogDiv.remove();
                            await startFileDownload(filePath, fileName, hashCheck.checked);
                        }};
                        actions.appendChild(cancelBtn);
                        actions.appendChild(startBtn);
                        ui.content.appendChild(actions);
                    }}

                    async function startFileDownload(filePath, fileName, withHash) {{
                        const taskId = await createTask('download');
                        const progress = createProgressDialog('Downloading', fileName);
                        try {{
                            const url = '/download?path=' + encodeURIComponent(filePath) +
                                '&task_id=' + encodeURIComponent(taskId) +
                                '&hash=' + (withHash ? '1' : '0');
                            const blob = await xhrDownloadBlob(url, 'GET', null, (loaded, total) => {{
                                progress.setStatus('Downloading...');
                                if (total > 0) progress.setProgress((loaded / total) * 100);
                            }});
                            saveBlob(blob, fileName);
                            const task = await waitForTaskCompletion(taskId, progress);
                            progress.setStatus('Completed');
                            progress.setProgress(100);
                            progress.setResult(task.hash_sha256 ? 'SHA-256: ' + task.hash_sha256 : 'Download complete');
                        }} catch (e) {{
                            progress.setStatus('Failed');
                            progress.setResult(e.message);
                        }}
                    }}

                    async function startZipDownload(paths, archiveName) {{
                        const taskId = await createTask('zip');
                        const progress = createProgressDialog('Preparing ZIP', archiveName);
                        try {{
                            const blob = await xhrDownloadBlob(
                                '/zip-download?task_id=' + encodeURIComponent(taskId),
                                'POST',
                                JSON.stringify({{ paths: paths, archive_name: archiveName }}),
                                (loaded, total) => {{
                                    progress.setStatus('Downloading ZIP...');
                                    if (total > 0) progress.setProgress((loaded / total) * 100);
                                }}
                            );
                            saveBlob(blob, archiveName);
                            await waitForTaskCompletion(taskId, progress);
                            progress.setStatus('Completed');
                            progress.setProgress(100);
                            progress.setResult('ZIP download complete');
                        }} catch (e) {{
                            progress.setStatus('Failed');
                            progress.setResult(e.message);
                        }}
                    }}
                    
                    async function loadFolderTree() {{
                        try {{
                            const res = await fetch('/folder-tree');
                            const tree = await res.json();
                            const sidebar = document.getElementById('sidebar');
                            sidebar.innerHTML = '';
                            renderTree(tree, sidebar);
                        }} catch (e) {{
                            console.error('Error loading folder tree:', e);
                        }}
                    }}
                    
                    function renderTree(node, container, depth = 0) {{
                        const div = document.createElement('div');
                        div.className = 'tree-item folder';
                        div.style.marginLeft = (depth * 15) + 'px';
                        
                        let html = '<span class="tree-toggle">+ </span>';
                        html += '📁 ' + node.name;
                        
                        div.innerHTML = html;
                        div.dataset.path = node.path;
                        
                        const toggle = div.querySelector('.tree-toggle');
                        const childrenDiv = document.createElement('div');
                        childrenDiv.className = 'tree-children';
                        
                        if (node.children.length === 0) {{
                            toggle.style.visibility = 'hidden';
                        }}
                        
                        toggle.addEventListener('click', (e) => {{
                            e.stopPropagation();
                            childrenDiv.classList.toggle('open');
                            toggle.textContent = childrenDiv.classList.contains('open') ? '- ' : '+ ';
                        }});
                        
                        div.addEventListener('click', () => {{
                            loadFolderContents(node.path);
                            updateBreadcrumb(node.path);
                        }});
                        
                        node.children.forEach(child => {{
                            renderTree(child, childrenDiv, depth + 1);
                        }});
                        
                        container.appendChild(div);
                        container.appendChild(childrenDiv);
                    }}
                    
                    async function loadFolderContents(path) {{
                        currentPath = path;
                        try {{
                            const res = await fetch('/files-metadata?path=' + encodeURIComponent(path));
                            if (!res.ok) throw new Error('Failed to open folder');
                            const items = await res.json();
                            renderTable(items);
                        }} catch (e) {{
                            console.error('Error loading folder contents:', e);
                        }}
                    }}
                    
                    function renderTable(items) {{
                        const tbody = document.getElementById('file-table');
                        tbody.innerHTML = '';
                        itemMap = new Map();
                        
                        items.forEach(item => {{
                            itemMap.set(item.path, item);
                            const row = document.createElement('tr');
                            const ext = item.name.substring(item.name.lastIndexOf('.')).toLowerCase();
                            const isTextFile = !!item.is_text;
                            
                            let filename = item.name;
                            if (item.is_dir) filename += '/';
                            
                            let sizeStr = '';
                            if (!item.is_dir) {{
                                sizeStr = formatSize(item.size);
                            }}
                            
                            let typeStr = item.is_dir ? 'Folder' : ext || 'File';
                            
                            // Checkbox cell
                            const checkboxCell = document.createElement('td');
                            checkboxCell.className = 'col-select';
                            const checkbox = document.createElement('input');
                            checkbox.type = 'checkbox';
                            checkbox.className = 'row-checkbox';
                            checkbox.dataset.path = item.path;
                            checkbox.addEventListener('change', updateBulkActions);
                            checkboxCell.appendChild(checkbox);
                            row.appendChild(checkboxCell);
                            
                            // Filename cell
                            const filenameCell = document.createElement('td');
                            filenameCell.className = 'filename col-name';
                            filenameCell.textContent = filename;
                            filenameCell.dataset.path = item.path;
                            filenameCell.dataset.isdir = item.is_dir;
                            if (item.is_dir) row.classList.add('folder-row');
                            row.appendChild(filenameCell);
                            
                            const sizeCell = document.createElement('td');
                            sizeCell.className = 'col-size';
                            sizeCell.textContent = sizeStr;
                            row.appendChild(sizeCell);
                            
                            const typeCell = document.createElement('td');
                            typeCell.className = 'col-type';
                            typeCell.textContent = typeStr;
                            row.appendChild(typeCell);
                            
                            const dateCell = document.createElement('td');
                            dateCell.className = 'col-date';
                            dateCell.textContent = item.date;
                            row.appendChild(dateCell);
                            
                            const actionCell = document.createElement('td');
                            actionCell.className = 'col-action';
                            const actionSlot = document.createElement('div');
                            actionSlot.className = 'action-slot';
                            
                            if (item.is_dir) {{
                                const zipBtn = document.createElement('button');
                                zipBtn.className = 'action-btn zip';
                                zipBtn.textContent = 'ZIP';
                                zipBtn.dataset.path = item.path;
                                zipBtn.dataset.name = item.name;
                                actionSlot.appendChild(zipBtn);
                            }} else {{
                                const downloadBtn = document.createElement('button');
                                downloadBtn.className = 'action-btn download';
                                downloadBtn.textContent = 'DOWNLOAD';
                                downloadBtn.dataset.file = item.path;
                                downloadBtn.dataset.name = item.name;
                                actionSlot.appendChild(downloadBtn);

                                if (isTextFile) {{
                                const viewBtn = document.createElement('button');
                                viewBtn.className = 'action-btn view';
                                viewBtn.textContent = 'VIEW';
                                viewBtn.dataset.file = item.path;
                                viewBtn.dataset.name = item.name;
                                actionSlot.appendChild(viewBtn);
                                }}
                            }}
                            
                            actionCell.appendChild(actionSlot);
                            row.appendChild(actionCell);

                            if (item.is_dir) {{
                                row.addEventListener('click', function(e) {{
                                    if (e.target.closest('button') || e.target.closest('input')) return;
                                    loadFolderContents(item.path);
                                    updateBreadcrumb(item.path);
                                }});
                            }}

                            tbody.appendChild(row);
                        }});
                        
                        // Attach event listeners
                        document.querySelectorAll('.filename').forEach(el => {{
                            el.addEventListener('click', function() {{
                                const path = this.dataset.path;
                                const isDir = this.dataset.isdir === 'true' || this.dataset.isdir === true;
                                if (isDir && path) {{
                                    loadFolderContents(path);
                                    updateBreadcrumb(path);
                                }}
                            }});
                        }});
                        
                        document.querySelectorAll('.view').forEach(el => {{
                            el.addEventListener('click', function() {{
                                const filePath = this.dataset.file;
                                const fileName = this.dataset.name;
                                viewFile(filePath, fileName);
                            }});
                        }});
                        
                        document.querySelectorAll('.zip').forEach(el => {{
                            el.addEventListener('click', function() {{
                                const folderPath = this.dataset.path;
                                const folderName = this.dataset.name;
                                startZipDownload([folderPath], folderName + '.zip');
                            }});
                        }});

                        document.querySelectorAll('.download').forEach(el => {{
                            el.addEventListener('click', function() {{
                                openDownloadDialog(this.dataset.file, this.dataset.name);
                            }});
                        }});
                    }}
                    
                    function formatSize(bytes) {{
                        if (bytes === 0) return '0 B';
                        const k = 1024;
                        const sizes = ['B', 'KB', 'MB', 'GB'];
                        const i = Math.floor(Math.log(bytes) / Math.log(k));
                        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
                    }}
                    
                    async function viewFile(filePath, fileName) {{
                        try {{
                            const res = await fetch('/view?path=' + encodeURIComponent(filePath));
                            if (!res.ok) {{
                                const msg = await res.text();
                                throw new Error(msg || 'Preview unavailable');
                            }}
                            const content = await res.text();
                            document.getElementById('modal-title').textContent = '📄 ' + fileName;
                            document.getElementById('modal-body').textContent = content;
                            modal.classList.add('show');
                        }} catch (e) {{
                            showDialog('Error loading file: ' + e.message);
                        }}
                    }}
                    
                    function updateBulkActions() {{
                        selectedItems.clear();
                        document.querySelectorAll('.row-checkbox:checked').forEach(checkbox => {{
                            selectedItems.add(checkbox.dataset.path);
                        }});
                        
                        const bulkActionsDiv = document.getElementById('bulk-actions');
                        if (selectedItems.size > 0) {{
                            bulkActionsDiv.classList.add('show');
                        }} else {{
                            bulkActionsDiv.classList.remove('show');
                        }}
                    }}
                    
                    document.getElementById('bulk-zip').addEventListener('click', function() {{
                        if (selectedItems.size === 0) return;
                        startZipDownload(Array.from(selectedItems), 'selected-items.zip');
                    }});
                    
                    document.getElementById('bulk-download').addEventListener('click', async function() {{
                        if (selectedItems.size === 0) return;
                        const selected = Array.from(selectedItems);
                        if (selected.length === 1) {{
                            const one = itemMap.get(selected[0]);
                            if (one && !one.is_dir) {{
                                openDownloadDialog(one.path, one.name);
                                return;
                            }}
                        }}
                        startZipDownload(selected, 'bulk-download.zip');
                    }});

                    document.getElementById('upload-btn').addEventListener('click', function() {{
                        openUploadDialog();
                    }});

                    document.getElementById('mkdir-btn').addEventListener('click', function() {{
                        openMkdirDialog();
                    }});
                    
                    function updateBreadcrumb(path) {{
                        // Remove the base upload folder path to get relative parts
                        const basePath = path.replace(/\\\\/g, '/');
                        const parts = basePath.split('/').filter(p => p && p !== 'shared_files');
                        
                        const breadcrumbDiv = document.getElementById('breadcrumb');
                        breadcrumbDiv.innerHTML = '';
                        
                        // Root button
                        const rootBtn = document.createElement('button');
                        rootBtn.textContent = '🌲';
                        rootBtn.addEventListener('click', function() {{
                            loadFolderContents('{UPLOAD_FOLDER}');
                            updateBreadcrumb('{UPLOAD_FOLDER}');
                        }});
                        breadcrumbDiv.appendChild(rootBtn);
                        
                        let currentPath = '{UPLOAD_FOLDER}';
                        parts.forEach((part) => {{
                            const sep = document.createElement('span');
                            sep.textContent = ' / ';
                            breadcrumbDiv.appendChild(sep);
                            
                            currentPath = currentPath + '/' + part;
                            const btn = document.createElement('button');
                            btn.textContent = part;
                            btn.addEventListener('click', (function(path) {{
                                return function() {{
                                    loadFolderContents(path);
                                    updateBreadcrumb(path);
                                }};
                            }})(currentPath));
                            breadcrumbDiv.appendChild(btn);
                        }});
                    }}
                    
                    // Sidebar toggle
                    document.getElementById('sidebar-toggle').addEventListener('click', () => {{
                        const sidebar = document.getElementById('sidebar');
                        const mainContent = document.querySelector('.main-content');
                        sidebar.classList.toggle('hidden');
                        mainContent.classList.toggle('fullwidth');
                        const toggleBtn = document.getElementById('sidebar-toggle');
                        toggleBtn.textContent = sidebar.classList.contains('hidden') ? '☰' : '⇆';
                    }});

                    document.addEventListener('dragenter', (e) => {{
                        if (!uploadsEnabled) return;
                        e.preventDefault();
                        dragCounter += 1;
                        dropOverlay.classList.add('show');
                    }});

                    document.addEventListener('dragover', (e) => {{
                        if (!uploadsEnabled) return;
                        e.preventDefault();
                    }});

                    document.addEventListener('dragleave', (e) => {{
                        if (!uploadsEnabled) return;
                        e.preventDefault();
                        dragCounter = Math.max(0, dragCounter - 1);
                        if (dragCounter === 0) dropOverlay.classList.remove('show');
                    }});

                    document.addEventListener('drop', async (e) => {{
                        e.preventDefault();
                        dragCounter = 0;
                        dropOverlay.classList.remove('show');
                        if (!ensureWriteEnabled()) return;
                        const files = Array.from(e.dataTransfer?.files || []);
                        if (files.length === 0) return;
                        await uploadFilesBatch(files, false);
                    }});

                    if (!uploadsEnabled) {{
                        const uploadBtn = document.getElementById('upload-btn');
                        const mkdirBtn = document.getElementById('mkdir-btn');
                        uploadBtn.style.display = 'none';
                        mkdirBtn.style.display = 'none';
                    }}
                    
                    // Load on page load
                    if (document.readyState === 'loading') {{
                        window.addEventListener('load', () => {{
                            loadFolderTree();
                            loadFolderContents('{UPLOAD_FOLDER}');
                            updateBreadcrumb('{UPLOAD_FOLDER}');
                        }});
                    }} else {{
                        // DOMContentLoaded already fired
                        loadFolderTree();
                        loadFolderContents('{UPLOAD_FOLDER}');
                        updateBreadcrumb('{UPLOAD_FOLDER}');
                    }}
                </script>
            </body>
            </html>
            """
            
            self.wfile.write(html.encode("utf-8"))
        
        elif self.path == "/folder-tree":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            tree = build_folder_tree()
            self.wfile.write(json.dumps(tree).encode("utf-8"))

        elif self.path.startswith("/task/new"):
            parsed = urlparse(self.path)
            kind = parse_qs(parsed.query).get("kind", ["generic"])[0]
            task_id = create_task(kind, f"{kind.capitalize()} started")
            self.send_json(200, {"task_id": task_id})

        elif self.path.startswith("/progress"):
            parsed = urlparse(self.path)
            task_id = parse_qs(parsed.query).get("task_id", [""])[0]
            task = get_task(task_id)
            if not task:
                self.send_json(404, {"error": "Task not found"})
                return
            self.send_json(200, task)
        
        elif self.path.startswith("/files-metadata"):
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            
            # Parse path from query string
            parsed = urlparse(self.path)
            path = parse_qs(parsed.query).get("path", [UPLOAD_FOLDER])[0]
            path = resolve_client_path(unquote(path))
            if not is_path_visible(path):
                self.send_json(403, {"error": "Path not allowed in restricted mode"})
                return
            
            items = get_folder_contents(path)
            self.wfile.write(json.dumps(items).encode("utf-8"))
        
        elif self.path.startswith("/view"):
            parsed = urlparse(self.path)
            raw_path = parse_qs(parsed.query).get("path", [""])[0]
            file_path = resolve_client_path(unquote(raw_path))

            if file_path and os.path.isfile(file_path):
                if not is_target_allowed(file_path):
                    self.send_error(403, "Access denied")
                    return
                if not is_likely_text_file(file_path):
                    self.send_error(415, "Binary file preview is not supported")
                    return
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    self.send_response(200)
                    self.send_header("Content-type", "text/plain; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(content.encode("utf-8"))
                except Exception as e:
                    self.send_error(500, f"Error: {e}")
            else:
                self.send_error(404, "File not found")
        
        elif self.path.startswith("/download?"):
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            raw_path = query.get("path", [""])[0]
            task_id = query.get("task_id", [""])[0] or None
            hash_requested = parse_bool(query.get("hash", ["0"])[0])
            file_path = resolve_client_path(unquote(raw_path))
            if not os.path.isfile(file_path):
                if task_id:
                    fail_task(task_id, "File not found")
                self.send_error(404, "File not found")
                return
            if not is_target_allowed(file_path):
                if task_id:
                    fail_task(task_id, "Access denied")
                self.send_error(403, "Access denied")
                return
            self.stream_download(file_path, os.path.basename(file_path), task_id=task_id, hash_requested=hash_requested)

        elif self.path.startswith("/download/"):
            file_name = self.path[len("/download/"):]
            file_path = resolve_client_path(f"{UPLOAD_FOLDER}/{unquote(file_name)}")
            if os.path.isfile(file_path):
                if not is_target_allowed(file_path):
                    self.send_error(403, "Access denied")
                    return
                self.stream_download(file_path, os.path.basename(file_path), task_id=None, hash_requested=False)
            else:
                self.send_error(404, "File not found")
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/upload-raw":
            if not ALLOW_UPLOADS:
                self.send_json(403, {"error": "Uploading not allowed"})
                return
            self.handle_upload_raw(parsed)
            return

        if parsed.path == "/zip-download":
            self.handle_zip_download(parsed)
            return

        if parsed.path == "/mkdir":
            if not ALLOW_UPLOADS:
                self.send_json(403, {"error": "Write actions are disabled in download-only mode"})
                return
            self.handle_mkdir()
            return

        self.send_error(404, "Not Found")

    def send_json(self, status_code, payload):
        self.send_response(status_code)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def stream_download(self, file_path, download_name, task_id=None, hash_requested=False):
        file_size = os.path.getsize(file_path)
        if task_id:
            update_task_progress(task_id, bytes_done=0, total_bytes=file_size, phase="downloading", message="Downloading")

        hasher = hashlib.sha256() if hash_requested else None

        try:
            self.send_response(200)
            self.send_header("Content-Disposition", f"attachment; filename=\"{download_name}\"")
            self.send_header("Content-type", "application/octet-stream")
            self.send_header("Content-Length", str(file_size))
            self.end_headers()

            bytes_sent = 0
            with open(file_path, "rb") as file_obj:
                while True:
                    chunk = file_obj.read(STREAM_CHUNK_SIZE)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    bytes_sent += len(chunk)
                    if hasher:
                        hasher.update(chunk)
                    if task_id:
                        update_task_progress(task_id, bytes_done=bytes_sent, total_bytes=file_size, phase="downloading", message="Downloading")

            if task_id:
                digest = hasher.hexdigest() if hasher else None
                finish_task(task_id, message="Download completed", hash_sha256=digest)
        except (BrokenPipeError, ConnectionResetError):
            if task_id:
                fail_task(task_id, "Client disconnected")
        except Exception as e:
            if task_id:
                fail_task(task_id, str(e))
            else:
                self.send_error(500, f"Error: {e}")

    def handle_upload_raw(self, parsed_url):
        query = parse_qs(parsed_url.query)
        target_path = resolve_client_path(unquote(query.get("path", [UPLOAD_FOLDER])[0]))
        file_name = sanitize_filename(unquote(query.get("filename", ["upload.bin"])[0]))
        task_id = query.get("task_id", [""])[0] or create_task("upload", "Upload started")
        hash_requested = parse_bool(query.get("hash", ["0"])[0])

        if not os.path.isdir(target_path):
            self.send_json(400, {"error": "Target folder not found"})
            fail_task(task_id, "Target folder not found")
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            self.send_json(400, {"error": "Empty upload payload"})
            fail_task(task_id, "Empty upload payload")
            return

        if content_length > MAX_UPLOAD_BYTES:
            self.send_json(413, {"error": "Upload too large"})
            fail_task(task_id, "Upload too large")
            return

        file_path = get_unique_file_path(target_path, file_name)
        bytes_written = 0
        hasher = hashlib.sha256() if hash_requested else None

        try:
            update_task_progress(task_id, bytes_done=0, total_bytes=content_length, phase="uploading", message="Uploading")
            with open(file_path, "wb") as out:
                remaining = content_length
                while remaining > 0:
                    read_size = min(STREAM_CHUNK_SIZE, remaining)
                    chunk = self.rfile.read(read_size)
                    if not chunk:
                        break
                    out.write(chunk)
                    bytes_written += len(chunk)
                    remaining -= len(chunk)
                    if hasher:
                        hasher.update(chunk)
                    update_task_progress(task_id, bytes_done=bytes_written, total_bytes=content_length, phase="uploading", message="Uploading")

            if bytes_written != content_length:
                raise IOError("Upload interrupted")

            digest = hasher.hexdigest() if hasher else None
            finish_task(task_id, message="Upload completed", hash_sha256=digest)
            self.send_json(200, {
                "ok": True,
                "task_id": task_id,
                "name": os.path.basename(file_path),
                "path": to_web_path(file_path),
                "size": bytes_written,
                "sha256": digest,
            })
        except Exception as e:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass
            fail_task(task_id, str(e))
            self.send_json(500, {"error": str(e), "task_id": task_id})

    def handle_zip_download(self, parsed_url):
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            self.send_json(400, {"error": "Missing request body"})
            return

        try:
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except Exception:
            self.send_json(400, {"error": "Invalid JSON body"})
            return

        task_id = parse_qs(parsed_url.query).get("task_id", [""])[0] or create_task("zip", "ZIP started")
        paths = payload.get("paths") or []
        archive_name = sanitize_filename(payload.get("archive_name") or "archive.zip")
        if not archive_name.lower().endswith(".zip"):
            archive_name += ".zip"

        files = collect_files_for_paths(paths)
        if not files:
            fail_task(task_id, "No valid files selected")
            self.send_json(400, {"error": "No valid files selected"})
            return

        total_bytes = sum(size for _, _, size in files)
        update_task_progress(task_id, bytes_done=0, total_bytes=total_bytes, phase="zipping", message="Building ZIP")

        temp_zip_path = None
        processed = 0
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_zip:
                temp_zip_path = temp_zip.name

            with ZipFile(temp_zip_path, "w") as zip_ref:
                for file_abs, arcname, size in files:
                    zip_ref.write(file_abs, arcname=arcname)
                    processed += size
                    update_task_progress(task_id, bytes_done=processed, total_bytes=total_bytes, phase="zipping", message="Building ZIP")

            zip_size = os.path.getsize(temp_zip_path)
            self.send_response(200)
            self.send_header("Content-Disposition", f"attachment; filename=\"{archive_name}\"")
            self.send_header("Content-type", "application/zip")
            self.send_header("Content-Length", str(zip_size))
            self.end_headers()

            sent = 0
            with open(temp_zip_path, "rb") as zf:
                while True:
                    chunk = zf.read(STREAM_CHUNK_SIZE)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    sent += len(chunk)
                    update_task_progress(task_id, bytes_done=sent, total_bytes=zip_size, phase="downloading", message="Downloading ZIP")

            finish_task(task_id, message="ZIP download completed")
        except (BrokenPipeError, ConnectionResetError):
            fail_task(task_id, "Client disconnected")
        except Exception as e:
            fail_task(task_id, str(e))
            if not self.wfile.closed:
                self.send_json(500, {"error": str(e)})
        finally:
            if temp_zip_path and os.path.exists(temp_zip_path):
                try:
                    os.remove(temp_zip_path)
                except OSError:
                    pass

    def handle_mkdir(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            self.send_json(400, {"error": "Missing request body"})
            return

        try:
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except Exception:
            self.send_json(400, {"error": "Invalid JSON body"})
            return

        target_path = resolve_client_path(unquote(payload.get("path", UPLOAD_FOLDER)))
        if not os.path.isdir(target_path):
            self.send_json(400, {"error": "Target folder not found"})
            return

        folder_name = sanitize_folder_name(payload.get("name", ""))
        if not folder_name:
            self.send_json(400, {"error": "Invalid folder name"})
            return

        new_dir = get_unique_dir_path(target_path, folder_name)
        try:
            os.makedirs(new_dir, exist_ok=False)
        except OSError as e:
            self.send_json(500, {"error": str(e)})
            return

        self.send_json(200, {
            "ok": True,
            "name": os.path.basename(new_dir),
            "path": to_web_path(new_dir),
        })


def main():
    global ALLOWED_PATHS
    print("=== 🎉 HTTP File Sharing Server ===")

    if not ALLOW_UPLOADS:
        print("[i] Download-only mode: select files/folders clients can access.")
        selected = get_download_only_allowlist()
        if not selected:
            print("[-] No items selected. Server not started.")
            return
        ALLOWED_PATHS = {os.path.abspath(p) for p in selected}
        print(f"[+] Restricted access set with {len(ALLOWED_PATHS)} selected items.")

    server_ip = get_lan_ip()
    port = 8000

    httpd = ThreadingHTTPServer(("0.0.0.0", port), CustomHandler)
    print(f"[+] Server running at http://{server_ip}:{port}")
    print("[+] Share this link with others in your LAN.")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[-] Server stopped.")


if __name__ == "__main__":
    main()
