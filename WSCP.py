import os
import time


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".ogg"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".aac"}
PDF_EXTENSIONS = {".pdf"}


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


def sanitize_entry_name(name, is_dir=False):
    raw = (name or "").replace("\x00", "").strip()
    raw = raw.replace("\\", "/").split("/")[-1].strip()
    if not raw or raw in (".", ".."):
        return None
    invalid_chars = set('<>:"/\\|?*')
    if any(ch in invalid_chars for ch in raw):
        return None
    if raw.endswith(" ") or raw.endswith("."):
        return None
    if is_dir:
        return sanitize_folder_name(raw)
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


def get_unique_target_path(directory, desired_name, is_dir):
    if is_dir:
        return get_unique_dir_path(directory, desired_name)
    return get_unique_file_path(directory, desired_name)


def count_path_units(abs_path):
    if os.path.isfile(abs_path):
        return 1
    if not os.path.isdir(abs_path):
        return 0

    total = 1
    for _, dirs, files in os.walk(abs_path):
        total += len(dirs) + len(files)
    return total


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


def is_image_file(file_path):
    _, ext = os.path.splitext(file_path or "")
    return ext.lower() in IMAGE_EXTENSIONS


def is_video_file(file_path):
    _, ext = os.path.splitext(file_path or "")
    return ext.lower() in VIDEO_EXTENSIONS


def is_audio_file(file_path):
    _, ext = os.path.splitext(file_path or "")
    return ext.lower() in AUDIO_EXTENSIONS


def is_pdf_file(file_path):
    _, ext = os.path.splitext(file_path or "")
    return ext.lower() in PDF_EXTENSIONS


def is_word_file(file_path):
    return False


def is_sheet_file(file_path):
    return False

import threading
import time
import uuid

TASK_TTL_SECONDS = 3600
TASKS = {}
TASKS_LOCK = threading.Lock()


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

import os
import socket
from datetime import datetime
from urllib.parse import unquote


def get_lan_ip():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        return "127.0.0.1"


def to_web_path(abs_path, upload_root, upload_folder):
    rel = os.path.relpath(abs_path, upload_root)
    if rel == ".":
        return upload_folder
    return f"{upload_folder}/" + rel.replace("\\", "/")


def resolve_client_path(raw_path, upload_root, upload_folder):
    if not raw_path:
        return upload_root

    normalized = raw_path.replace("\\", "/").strip()
    if normalized in ("", "/", upload_folder):
        return upload_root

    if normalized.startswith(upload_folder + "/"):
        rel = normalized[len(upload_folder) + 1 :]
    else:
        rel = normalized.lstrip("/")

    candidate = os.path.abspath(os.path.join(upload_root, rel))
    if candidate == upload_root or candidate.startswith(upload_root + os.sep):
        return candidate

    return upload_root


def is_target_allowed(abs_path, allow_uploads, allow_downloads, allowed_paths):
    if not allow_downloads:
        return False
    if not allowed_paths:
        return allow_uploads

    norm = os.path.abspath(abs_path)
    for allowed in allowed_paths:
        if norm == allowed or norm.startswith(allowed + os.sep):
            return True
    return False


def is_path_visible(abs_path, upload_root, allow_uploads, allow_downloads, allowed_paths):
    norm = os.path.abspath(abs_path)

    if allow_uploads and not allow_downloads:
        if norm == upload_root:
            return True
        if not allowed_paths:
            return False
        for allowed in allowed_paths:
            if norm == allowed or norm.startswith(allowed + os.sep):
                return True
        if os.path.isdir(norm):
            prefix = norm + os.sep
            for allowed in allowed_paths:
                if allowed.startswith(prefix):
                    return True
        return False

    if not allow_downloads:
        return norm == upload_root

    if allow_uploads and not allowed_paths:
        return True
    if not allowed_paths:
        return False
    if is_target_allowed(norm, allow_uploads, allow_downloads, allowed_paths):
        return True

    if os.path.isdir(norm):
        prefix = norm + os.sep
        for allowed in allowed_paths:
            if allowed.startswith(prefix):
                return True
    return False


def collect_files_for_paths(client_paths, upload_root, resolve_client_path_fn, is_target_allowed_fn):
    files = []
    for raw in client_paths:
        abs_path = resolve_client_path_fn(unquote(raw))
        if not is_target_allowed_fn(abs_path):
            continue
        if os.path.isfile(abs_path):
            rel = os.path.relpath(abs_path, upload_root).replace("\\", "/")
            files.append((abs_path, rel, os.path.getsize(abs_path)))
        elif os.path.isdir(abs_path):
            for root, _, names in os.walk(abs_path):
                for name in names:
                    file_abs = os.path.join(root, name)
                    if not is_target_allowed_fn(file_abs):
                        continue
                    rel = os.path.relpath(file_abs, upload_root).replace("\\", "/")
                    try:
                        size = os.path.getsize(file_abs)
                    except OSError:
                        size = 0
                    files.append((file_abs, rel, size))
    return files


def list_shareable_entries(upload_root):
    entries = []
    for root, dirs, files in os.walk(upload_root):
        dirs.sort()
        files.sort()
        for name in dirs:
            abs_path = os.path.join(root, name)
            rel = os.path.relpath(abs_path, upload_root).replace("\\", "/")
            entries.append({"abs": abs_path, "rel": rel, "kind": "Folder"})
        for name in files:
            abs_path = os.path.join(root, name)
            rel = os.path.relpath(abs_path, upload_root).replace("\\", "/")
            entries.append({"abs": abs_path, "rel": rel, "kind": "File"})
    return entries


def build_folder_tree(path, upload_root, upload_folder, is_path_visible_fn):
    tree = {
        "name": os.path.basename(path) or "[root]",
        "path": to_web_path(path, upload_root, upload_folder),
        "children": [],
    }

    try:
        for item in sorted(os.listdir(path)):
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path) and is_path_visible_fn(item_path):
                tree["children"].append(
                    build_folder_tree(item_path, upload_root, upload_folder, is_path_visible_fn)
                )
    except PermissionError:
        pass

    return tree


def get_folder_contents(
    path,
    upload_root,
    upload_folder,
    is_path_visible_fn,
    is_likely_text_file_fn,
    is_image_file_fn,
    is_video_file_fn,
    is_audio_file_fn,
    is_pdf_file_fn,
    is_word_file_fn,
    is_sheet_file_fn,
):
    items = []
    try:
        for item in sorted(os.listdir(path)):
            item_path = os.path.join(path, item)
            if not is_path_visible_fn(item_path):
                continue
            is_dir = os.path.isdir(item_path)

            try:
                mod_time = os.path.getmtime(item_path)
                date_str = datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                date_str = "Unknown"

            size = 0
            if not is_dir:
                try:
                    size = os.path.getsize(item_path)
                except Exception:
                    pass

            is_text_file = (not is_dir) and is_likely_text_file_fn(item_path)
            is_image = (not is_dir) and is_image_file_fn(item_path)
            is_video = (not is_dir) and is_video_file_fn(item_path)
            is_audio = (not is_dir) and is_audio_file_fn(item_path)
            is_pdf = (not is_dir) and is_pdf_file_fn(item_path)
            is_word = (not is_dir) and is_word_file_fn(item_path)
            is_sheet = (not is_dir) and is_sheet_file_fn(item_path)

            items.append(
                {
                    "name": item,
                    "path": to_web_path(item_path, upload_root, upload_folder),
                    "is_dir": is_dir,
                    "size": size,
                    "date": date_str,
                    "is_text": is_text_file,
                    "is_image": is_image,
                    "is_video": is_video,
                    "is_audio": is_audio,
                    "is_pdf": is_pdf,
                    "is_word": is_word,
                    "is_sheet": is_sheet,
                }
            )
    except PermissionError:
        pass

    return items

class _CoreAccessNamespace:
    pass


core_access = _CoreAccessNamespace()
core_access.get_lan_ip = get_lan_ip
core_access.to_web_path = to_web_path
core_access.resolve_client_path = resolve_client_path
core_access.is_target_allowed = is_target_allowed
core_access.is_path_visible = is_path_visible
core_access.collect_files_for_paths = collect_files_for_paths
core_access.list_shareable_entries = list_shareable_entries
core_access.build_folder_tree = build_folder_tree
core_access.get_folder_contents = get_folder_contents

try:
    from textual.app import App
    from textual.widgets import Button, Static, Checkbox
    from textual.containers import Vertical, Horizontal, VerticalScroll
    TEXTUAL_AVAILABLE = True
except Exception:
    TEXTUAL_AVAILABLE = False

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import FuzzyWordCompleter
    PROMPT_TOOLKIT_AVAILABLE = True
except Exception:
    PROMPT_TOOLKIT_AVAILABLE = False


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

        def compose(self):
            yield Vertical(
                Static("Download Access Selector", id="title"),
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
    max_show = 30
    active_view = []

    root_names = set()
    for item in entries:
        rel = item["rel"].replace("\\", "/")
        root_names.add(rel.split("/", 1)[0])
    root_indexes = [
        i for i, item in enumerate(entries)
        if item["rel"].replace("\\", "/").split("/", 1)[0] in root_names
        and "/" not in item["rel"].replace("\\", "/")
    ]

    if not root_indexes:
        root_indexes = list(range(len(entries)))

    def print_menu():
        print("\n=== Access Selector ===")
        print("1. Search")
        print("2. List directory and select files")
        print("3. Select all")
        print("4. Done")
        print("q. Quit")
        print(f"Selected: {len(selected_indexes)}")

    def current_filtered_indexes():
        if not search_term:
            return list(range(len(entries)))
        needle = search_term.lower()
        return [
            i for i, item in enumerate(entries)
            if needle in item["rel"].lower() or needle in item["kind"].lower()
        ]

    def print_visible(title, shown):
        print(f"\n--- {title} ---")
        print(f"Visible: {len(shown)} | Selected: {len(selected_indexes)}")
        print("----------------------------------------")
        if not shown:
            print("No entries to show.")
            return
        capped = shown[:max_show]
        for n, idx in enumerate(capped, start=1):
            item = entries[idx]
            mark = "[x]" if idx in selected_indexes else "[ ]"
            kind_mark = "D" if item["kind"] == "Folder" else "F"
            print(f"{n:4d}. {mark} [{kind_mark}] {item['rel']}")
        if len(shown) > len(capped):
            print(f"... showing first {len(capped)} of {len(shown)}.")

    def prompt_search_text():
        if PROMPT_TOOLKIT_AVAILABLE:
            words = [item["rel"] for item in entries]
            completer = FuzzyWordCompleter(words, WORD=True)
            session = PromptSession()
            return session.prompt(
                "search (live suggestions): ",
                completer=completer,
                complete_while_typing=True,
            ).strip()
        return input("search text: ").strip()

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
                        if 1 <= num <= min(len(shown), max_show):
                            toggles.append(shown[num - 1])
            elif part.isdigit():
                num = int(part)
                if 1 <= num <= min(len(shown), max_show):
                    toggles.append(shown[num - 1])
        return toggles

    while True:
        print_menu()
        try:
            raw = input("action: ").strip()
        except EOFError:
            return set()
        if not raw:
            continue

        lowered = raw.lower()
        if lowered in ("q", "quit", "exit"):
            return set()
        if lowered in ("4", "done", "start"):
            return {entries[i]["abs"] for i in sorted(selected_indexes)}

        if lowered in ("1", "search"):
            term = prompt_search_text()
            search_term = term
            active_view = current_filtered_indexes() if term else root_indexes[:]
            label = f"Search results for '{term}'" if term else "Directory listing"
            print_visible(label, active_view)
            if active_view:
                spec = input(
                    "Do u wanna select files or folders? numbers (q to quit, space-separated or range e.g. 1 3-5): "
                ).strip()
                if spec.lower() in ("q", "quit"):
                    active_view = []
                    continue
                if spec:
                    toggles = parse_toggle_numbers(spec, active_view)
                    if toggles:
                        for idx in toggles:
                            if idx in selected_indexes:
                                selected_indexes.remove(idx)
                            else:
                                selected_indexes.add(idx)
                        print(f"Selected now: {len(selected_indexes)}")
            continue

        if lowered in ("2", "list", "list directory"):
            search_term = ""
            active_view = root_indexes[:]
            print_visible("Directory listing", active_view)
            if active_view:
                spec = input(
                    "Do u wanna select files or folders? numbers (q to quit, space-separated or range e.g. 1 3-5): "
                ).strip()
                if spec.lower() in ("q", "quit"):
                    continue
                if spec:
                    toggles = parse_toggle_numbers(spec, active_view)
                    if toggles:
                        for idx in toggles:
                            if idx in selected_indexes:
                                selected_indexes.remove(idx)
                            else:
                                selected_indexes.add(idx)
                        print(f"Selected now: {len(selected_indexes)}")
                        return {entries[i]["abs"] for i in sorted(selected_indexes)}
            continue

        if lowered in ("3", "all", "select all"):
            target = list(range(len(entries)))
            for idx in target:
                selected_indexes.add(idx)
            print(f"Selected now: {len(selected_indexes)}")
            return {entries[i]["abs"] for i in sorted(selected_indexes)}

        print("Unknown action.")

def render_index_html(upload_folder, allow_uploads, allow_downloads, allowed_paths):
    UPLOAD_FOLDER = upload_folder
    ALLOW_UPLOADS = allow_uploads
    ALLOW_DOWNLOADS = allow_downloads
    ALLOWED_PATHS = allowed_paths
    return f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <title>WSCP - File Sharing Server</title>
                <link rel="icon" type="image/x-icon" href="/favicon.ico">
                <link rel="shortcut icon" href="/favicon.ico">
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

                    .toolbar .bulk-management {{
                        display: none;
                        gap: 8px;
                    }}

                    .toolbar .bulk-management.show {{
                        display: flex;
                    }}

                    .toolbar .search-wrap {{
                        display: none;
                        align-items: center;
                        gap: 8px;
                        min-width: 220px;
                        max-width: 420px;
                        flex: 1 1 300px;
                    }}

                    .toolbar .search-wrap.show {{
                        display: flex;
                    }}

                    .toolbar .search-wrap input {{
                        flex: 1;
                        height: var(--btn-h);
                        border-radius: var(--radius-1);
                        border: 1px solid var(--line-2);
                        padding: 0 10px;
                        background: #0f0f0f;
                        color: var(--text-1);
                        font-size: 12px;
                    }}

                    .toolbar .search-wrap input:focus-visible {{
                        outline: 2px solid #9a9a9a;
                        outline-offset: 2px;
                    }}

                    #search-close {{
                        width: var(--btn-h);
                        min-width: var(--btn-h);
                        padding: 0;
                        font-size: 14px;
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
                    #bulk-download,
                    #bulk-delete,
                    #bulk-move {{
                        min-width: 108px;
                    }}
                    
                    .sidebar.hidden {{
                        display: none;
                    }}

                    .sidebar-backdrop {{
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
                        min-width: 1120px;
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
                        width: 30%;
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
                        width: 20%;
                        color: #a6a6a6;
                        font-variant-numeric: tabular-nums;
                    }}

                    .col-action {{
                        width: 280px;
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
                        gap: 6px;
                        min-height: 48px;
                    }}
                    
                    .action-btn {{
                        height: 30px;
                        min-width: 78px;
                        padding: 0 12px;
                        font-size: 10px;
                        letter-spacing: 0.04em;
                    }}

                    .action-btn.manage-action {{
                        display: none;
                    }}

                    body.manage-mode .action-btn.manage-action {{
                        display: inline-flex;
                    }}

                    .tree-item.drop-target,
                    tr.drop-target td {{
                        background-color: #1a1a1a !important;
                        border-color: #646464 !important;
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
                        display: inline-block;
                        transition: all 0.15s ease;
                    }}
                    
                    .tree-toggle:hover {{
                        transform: scale(1.3);
                        color: #b8b8b8;
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

                    .doc-preview-frame {{
                        width: 100%;
                        height: 100%;
                        min-height: 420px;
                        border: 0;
                        border-radius: 8px;
                        background: #080808;
                    }}

                    .doc-preview-message {{
                        font-family: 'Inter', sans-serif;
                        font-size: 13px;
                        color: var(--text-2);
                        line-height: 1.5;
                        margin-bottom: 12px;
                    }}

                    .doc-preview-actions {{
                        display: flex;
                        gap: 10px;
                        flex-wrap: wrap;
                    }}

                    .sheet-preview-table {{
                        width: 100%;
                        border-collapse: collapse;
                        font-family: 'Inter', sans-serif;
                        font-size: 12px;
                    }}

                    .sheet-preview-table th,
                    .sheet-preview-table td {{
                        border: 1px solid #242424;
                        padding: 6px 8px;
                        text-align: left;
                        vertical-align: top;
                        max-width: 260px;
                        overflow: hidden;
                        text-overflow: ellipsis;
                        white-space: nowrap;
                    }}

                    .sheet-preview-table th {{
                        background: #141414;
                        color: #fafafa;
                        font-weight: 600;
                    }}

                    .image-viewer-body {{
                        flex: 1;
                        display: flex;
                        flex-direction: column;
                        gap: 10px;
                        min-height: 0;
                    }}

                    .image-nav {{
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        gap: 10px;
                    }}

                    .image-nav-btn {{
                        min-width: 44px;
                        height: 34px;
                        border-radius: 8px;
                        border: 1px solid #3a3a3a;
                        background: #151515;
                        color: var(--text-1);
                        cursor: pointer;
                        font-size: 16px;
                    }}

                    .image-nav-btn:disabled {{
                        opacity: 0.45;
                        cursor: not-allowed;
                    }}

                    .image-counter {{
                        min-width: 72px;
                        text-align: center;
                        color: var(--text-3);
                        font-size: 12px;
                    }}

                    .image-preview-wrap {{
                        flex: 1;
                        min-height: 0;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        border: 1px solid #1f1f1f;
                        border-radius: var(--radius-1);
                        background: #080808;
                        overflow: hidden;
                        padding: 10px;
                    }}

                    .image-preview {{
                        max-width: 100%;
                        max-height: 100%;
                        object-fit: contain;
                    }}

                    .video-viewer-body {{
                        flex: 1;
                        display: flex;
                        flex-direction: column;
                        gap: 10px;
                        min-height: 0;
                    }}

                    .video-nav {{
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        gap: 10px;
                    }}

                    .video-nav-btn {{
                        min-width: 44px;
                        height: 34px;
                        border-radius: 8px;
                        border: 1px solid #3a3a3a;
                        background: #151515;
                        color: var(--text-1);
                        cursor: pointer;
                        font-size: 16px;
                    }}

                    .video-nav-btn:disabled {{
                        opacity: 0.45;
                        cursor: not-allowed;
                    }}

                    .video-counter {{
                        min-width: 72px;
                        text-align: center;
                        color: var(--text-3);
                        font-size: 12px;
                    }}

                    .video-preview-wrap {{
                        flex: 1;
                        min-height: 0;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        border: 1px solid #1f1f1f;
                        border-radius: var(--radius-1);
                        background: #080808;
                        overflow: hidden;
                        padding: 10px;
                    }}

                    .video-preview {{
                        max-width: 100%;
                        max-height: 100%;
                        width: 100%;
                        background: #000;
                    }}

                    .audio-player-body {{
                        flex: 1;
                        display: flex;
                        flex-direction: column;
                        gap: 12px;
                        min-height: 0;
                    }}

                    .audio-nav {{
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        gap: 10px;
                    }}

                    .audio-nav-btn {{
                        min-width: 44px;
                        height: 34px;
                        border-radius: 8px;
                        border: 1px solid #3a3a3a;
                        background: #151515;
                        color: var(--text-1);
                        cursor: pointer;
                        font-size: 16px;
                    }}

                    .audio-nav-btn:disabled {{
                        opacity: 0.45;
                        cursor: not-allowed;
                    }}

                    .audio-counter {{
                        min-width: 72px;
                        text-align: center;
                        color: var(--text-3);
                        font-size: 12px;
                    }}

                    .audio-preview-wrap {{
                        border: 1px solid #1f1f1f;
                        border-radius: var(--radius-1);
                        background: #080808;
                        padding: 18px 14px;
                    }}

                    .audio-preview {{
                        width: 100%;
                    }}
                    
                    .row-checkbox {{
                        width: 20px;
                        height: 20px;
                        cursor: pointer;
                        accent-color: #24d061;
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

                    .move-tree {{
                        width: 100%;
                        max-height: 240px;
                        overflow: auto;
                        border: 1px solid #3a3a3a;
                        border-radius: 8px;
                        background: #0f0f0f;
                        text-align: left;
                        padding: 6px 0;
                    }}

                    .move-tree-item {{
                        display: flex;
                        align-items: center;
                        gap: 8px;
                        height: 30px;
                        padding-right: 10px;
                        border-left: 2px solid transparent;
                        color: var(--text-2);
                        cursor: pointer;
                    }}

                    .move-tree-item:hover {{
                        background: #171717;
                        color: var(--text-1);
                    }}

                    .move-tree-item.selected {{
                        background: #1f1f1f;
                        border-left-color: #7a7a7a;
                        color: var(--text-1);
                    }}

                    .move-tree-toggle {{
                        width: 14px;
                        text-align: center;
                        color: #7d7d7d;
                        font-size: 11px;
                        user-select: none;
                        flex: 0 0 14px;
                        display: inline-block;
                        transition: all 0.15s ease;
                        cursor: pointer;
                    }}
                    
                    .move-tree-toggle:hover {{
                        transform: scale(1.3);
                        color: #b8b8b8;
                    }}

                    .move-tree-label {{
                        font-size: 12px;
                        white-space: nowrap;
                        overflow: hidden;
                        text-overflow: ellipsis;
                    }}

                    .move-tree-children {{
                        display: none;
                    }}

                    .move-tree-children.open {{
                        display: block;
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

                    .toast-host {{
                        position: fixed;
                        right: 16px;
                        bottom: 16px;
                        z-index: 1200;
                        display: flex;
                        flex-direction: column;
                        gap: 8px;
                        pointer-events: none;
                    }}

                    .toast {{
                        min-width: 220px;
                        max-width: 340px;
                        padding: 10px 12px;
                        border-radius: 10px;
                        border: 1px solid #3a3a3a;
                        background: #111111;
                        color: #f3f3f3;
                        font-size: 12px;
                        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.35);
                        opacity: 0;
                        transform: translateY(6px);
                        transition: opacity 0.16s ease, transform 0.16s ease;
                    }}

                    .toast.show {{
                        opacity: 1;
                        transform: translateY(0);
                    }}

                    .toast.success {{
                        border-color: #4c7f4c;
                    }}

                    @media (max-width: 1024px) {{
                        #sidebar-toggle {{
                            position: fixed;
                            top: 10px;
                            left: 10px;
                            z-index: 1205;
                            width: 40px;
                            height: 40px;
                        }}

                        .sidebar.mobile-open + .sidebar-backdrop + .main-content #sidebar-toggle {{
                            left: calc(min(84vw, 320px) - 50px);
                        }}

                        .sidebar {{
                            position: fixed;
                            left: 0;
                            top: 0;
                            bottom: 0;
                            width: min(84vw, 320px);
                            max-width: 320px;
                            transform: translateX(-105%);
                            transition: transform 0.2s ease;
                            z-index: 1150;
                        }}

                        .sidebar.mobile-open {{
                            transform: translateX(0);
                        }}

                        .sidebar.hidden {{
                            display: block !important;
                        }}

                        .sidebar-backdrop {{
                            position: fixed;
                            inset: 0;
                            background: rgba(0, 0, 0, 0.35);
                            z-index: 1140;
                        }}

                        .sidebar-backdrop.show {{
                            display: block;
                        }}

                        .main-content {{
                            width: 100%;
                            min-width: 0;
                        }}

                        .main-content.fullwidth {{
                            width: 100%;
                        }}

                        .col-action {{
                            width: 240px;
                        }}

                        .toolbar {{
                            padding-left: 58px;
                            gap: 8px;
                            flex-wrap: wrap;
                        }}
                    }}

                    @media (max-width: 768px) {{
                        body {{
                            overflow-x: hidden;
                        }}

                        .container {{
                            height: 100vh;
                            height: 100dvh;
                        }}

                        .toolbar {{
                            padding: 10px 10px 10px 58px;
                            gap: 8px;
                            flex-wrap: wrap;
                            align-items: stretch;
                        }}

                        .toolbar .spacer {{
                            display: none;
                        }}

                        .toolbar > button,
                        .bulk-actions button,
                        .bulk-management button {{
                            min-height: 40px;
                            padding: 0 10px;
                            font-size: 11px;
                        }}

                        .toolbar .search-wrap.show {{
                            order: 100;
                            width: 100%;
                            max-width: none;
                        }}

                        .mode-badge {{
                            order: 99;
                            margin-left: 0;
                            margin-top: 2px;
                        }}

                        .breadcrumb {{
                            padding: 8px 10px;
                            overflow-x: auto;
                            white-space: nowrap;
                            -webkit-overflow-scrolling: touch;
                        }}

                        .table-container {{
                            padding: 8px;
                            overflow-x: hidden;
                        }}

                        .file-table {{
                            min-width: 0;
                            border-collapse: separate;
                            border-spacing: 0 10px;
                            background: transparent;
                            border: 0;
                        }}

                        .file-table thead {{
                            display: none;
                        }}

                        .file-table,
                        .file-table tbody,
                        .file-table tr,
                        .file-table td {{
                            display: block;
                            width: 100%;
                        }}

                        .file-table tr {{
                            background: #0f0f0f;
                            border: 1px solid #222;
                            border-radius: 10px;
                            padding: 8px;
                            margin: 0;
                        }}

                        .file-table td {{
                            border: 0;
                            padding: 5px 8px;
                            display: flex;
                            justify-content: space-between;
                            align-items: center;
                            gap: 10px;
                        }}

                        .file-table td::before {{
                            content: attr(data-label);
                            font-size: 10px;
                            color: var(--text-3);
                            text-transform: uppercase;
                            letter-spacing: 0.04em;
                            flex: 0 0 74px;
                        }}

                        .file-table td.col-name {{
                            display: block;
                            font-size: 14px;
                            font-weight: 600;
                        }}

                        .file-table td.col-name::before {{
                            content: attr(data-label);
                            display: block;
                            margin-bottom: 3px;
                        }}

                        .file-table td.col-select {{
                            display: flex;
                            justify-content: flex-start;
                        }}

                        .file-table td.col-select::before {{
                            flex: 0 0 74px;
                        }}

                        .row-checkbox {{
                            width: 24px;
                            height: 24px;
                        }}

                        .col-action {{
                            width: 100%;
                            min-width: 0;
                        }}

                        .action-slot {{
                            justify-content: flex-start;
                            flex-wrap: wrap;
                        }}

                        .action-btn {{
                            min-width: 72px;
                            height: 36px;
                            font-size: 10px;
                        }}

                        .modal-content {{
                            width: calc(100% - 16px);
                            height: min(88vh, 760px);
                            height: min(88dvh, 760px);
                            padding: 12px;
                        }}

                        .dialog-content {{
                            width: calc(100% - 16px);
                            padding: 16px;
                        }}

                        .image-nav-btn,
                        .video-nav-btn,
                        .audio-nav-btn,
                        .close-btn {{
                            min-width: 42px;
                            height: 42px;
                        }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="sidebar hidden" id="sidebar"></div>
                    <div class="sidebar-backdrop" id="sidebar-backdrop"></div>
                    <div class="main-content">
                        <div class="toolbar">
                            <button id="sidebar-toggle" aria-label="Toggle sidebar">â‡†</button>
                            <button id="upload-btn">Upload</button>
                            <button id="mkdir-btn">New Folder</button>
                            <button id="manage-btn">Manage</button>
                            <button id="search-toggle">Search</button>
                            <div class="search-wrap" id="search-wrap">
                                <input id="search-input" type="text" placeholder="Search files in current folder" aria-label="Search files" />
                                <button id="search-close" aria-label="Close search">âœ•</button>
                            </div>
                            {"<span class='mode-badge'>Download Only</span>" if (not ALLOW_UPLOADS) else ("<span class='mode-badge'>Upload Only</span>" if (ALLOW_UPLOADS and not ALLOW_DOWNLOADS) else ("<span class='mode-badge'>Restricted Downloads</span>" if bool(ALLOWED_PATHS) else ""))}
                            <div class="spacer"></div>
                            <div class="bulk-actions" id="bulk-actions">
                                <button id="bulk-zip">Zip</button>
                                <button id="bulk-download">Download</button>
                            </div>
                            <div class="bulk-management" id="bulk-management">
                                <button id="bulk-delete">Delete Selected</button>
                                <button id="bulk-move">Move Selected</button>
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
                            <button class="close-btn" id="file-close-btn">âœ•</button>
                        </div>
                        <div class="modal-body" id="modal-body"></div>
                    </div>
                </div>

                <div class="modal" id="image-modal">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h2 id="image-modal-title">Image Viewer</h2>
                            <button class="close-btn" id="image-close-btn">âœ•</button>
                        </div>
                        <div class="image-viewer-body">
                            <div class="image-nav">
                                <button class="image-nav-btn" id="image-prev-btn" aria-label="Previous image">&#x2039;</button>
                                <span class="image-counter" id="image-counter">0 / 0</span>
                                <button class="image-nav-btn" id="image-next-btn" aria-label="Next image">&#x203A;</button>
                            </div>
                            <div class="image-preview-wrap">
                                <img class="image-preview" id="image-preview" alt="Image preview" />
                            </div>
                        </div>
                    </div>
                </div>

                <div class="modal" id="video-modal">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h2 id="video-modal-title">Video Player</h2>
                            <button class="close-btn" id="video-close-btn">âœ•</button>
                        </div>
                        <div class="video-viewer-body">
                            <div class="video-nav">
                                <button class="video-nav-btn" id="video-prev-btn" aria-label="Previous video">&#x2039;</button>
                                <span class="video-counter" id="video-counter">0 / 0</span>
                                <button class="video-nav-btn" id="video-next-btn" aria-label="Next video">&#x203A;</button>
                            </div>
                            <div class="video-preview-wrap">
                                <video class="video-preview" id="video-preview" controls></video>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="modal" id="audio-modal">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h2 id="audio-modal-title">Audio Player</h2>
                            <button class="close-btn" id="audio-close-btn">âœ•</button>
                        </div>
                        <div class="audio-player-body">
                            <div class="audio-nav">
                                <button class="audio-nav-btn" id="audio-prev-btn" aria-label="Previous audio">&#x2039;</button>
                                <span class="audio-counter" id="audio-counter">0 / 0</span>
                                <button class="audio-nav-btn" id="audio-next-btn" aria-label="Next audio">&#x203A;</button>
                            </div>
                            <div class="audio-preview-wrap">
                                <audio class="audio-preview" id="audio-preview" controls></audio>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="drop-overlay" id="drop-overlay">
                    <div class="drop-panel">Drop files here to upload</div>
                </div>

                <div class="toast-host" id="toast-host"></div>
                
                <script>
                    let currentPath = "{UPLOAD_FOLDER}";
                    const uploadsEnabled = {str(ALLOW_UPLOADS).lower()};
                    const downloadsEnabled = {str(ALLOW_DOWNLOADS).lower()};
                    const modal = document.getElementById('file-modal');
                    const modalTitle = document.getElementById('modal-title');
                    const modalBody = document.getElementById('modal-body');
                    const imageModal = document.getElementById('image-modal');
                    const imageModalTitle = document.getElementById('image-modal-title');
                    const imagePreview = document.getElementById('image-preview');
                    const imagePrevBtn = document.getElementById('image-prev-btn');
                    const imageNextBtn = document.getElementById('image-next-btn');
                    const imageCounter = document.getElementById('image-counter');
                    const videoModal = document.getElementById('video-modal');
                    const videoModalTitle = document.getElementById('video-modal-title');
                    const videoPreview = document.getElementById('video-preview');
                    const videoPrevBtn = document.getElementById('video-prev-btn');
                    const videoNextBtn = document.getElementById('video-next-btn');
                    const videoCounter = document.getElementById('video-counter');
                    const sidebarBackdrop = document.getElementById('sidebar-backdrop');
                    const audioModal = document.getElementById('audio-modal');
                    const audioModalTitle = document.getElementById('audio-modal-title');
                    const audioPreview = document.getElementById('audio-preview');
                    const audioPrevBtn = document.getElementById('audio-prev-btn');
                    const audioNextBtn = document.getElementById('audio-next-btn');
                    const audioCounter = document.getElementById('audio-counter');
                    const dropOverlay = document.getElementById('drop-overlay');
                    const toastHost = document.getElementById('toast-host');
                    const searchToggleBtn = document.getElementById('search-toggle');
                    const searchWrap = document.getElementById('search-wrap');
                    const searchInput = document.getElementById('search-input');
                    const searchCloseBtn = document.getElementById('search-close');
                    let itemMap = new Map();
                    let currentFolderItems = [];
                    let searchQuery = '';
                    let selectedItems = new Set();
                    let expandedTreePaths = new Set();
                    let dragCounter = 0;
                    let manageMode = false;
                    let imageFilesInCurrentFolder = [];
                    let activeImageIndex = -1;
                    let videoFilesInCurrentFolder = [];
                    let activeVideoIndex = -1;
                    let audioFilesInCurrentFolder = [];
                    let activeAudioIndex = -1;
                    const INTERNAL_MOVE_MIME = 'application/x-wscp-items';

                    function ensureWriteEnabled() {{
                        if (!uploadsEnabled) {{
                            showDialog('Uploads are disabled in this mode.');
                            return false;
                        }}
                        return true;
                    }}

                    function isMobileViewport() {{
                        return window.matchMedia('(max-width: 1024px)').matches;
                    }}

                    function updateSidebarToggleIcon() {{
                        const sidebar = document.getElementById('sidebar');
                        const toggleBtn = document.getElementById('sidebar-toggle');
                        if (!sidebar || !toggleBtn) return;
                        if (isMobileViewport()) {{
                            toggleBtn.textContent = sidebar.classList.contains('mobile-open') ? 'âœ•' : 'â˜°';
                            return;
                        }}
                        toggleBtn.textContent = sidebar.classList.contains('hidden') ? 'â˜°' : 'â‡†';
                    }}

                    function closeMobileSidebar() {{
                        if (!isMobileViewport()) return;
                        const sidebar = document.getElementById('sidebar');
                        if (!sidebar) return;
                        sidebar.classList.remove('mobile-open');
                        if (sidebarBackdrop) sidebarBackdrop.classList.remove('show');
                        updateSidebarToggleIcon();
                    }}

                    function applyResponsiveLayout(initial = false) {{
                        const sidebar = document.getElementById('sidebar');
                        const mainContent = document.querySelector('.main-content');
                        if (!sidebar || !mainContent) return;

                        if (isMobileViewport()) {{
                            sidebar.classList.remove('hidden');
                            mainContent.classList.add('fullwidth');
                            if (initial) sidebar.classList.remove('mobile-open');
                            if (sidebarBackdrop) sidebarBackdrop.classList.remove('show');
                        }} else {{
                            sidebar.classList.remove('mobile-open');
                            if (sidebarBackdrop) sidebarBackdrop.classList.remove('show');
                            if (initial) {{
                                sidebar.classList.remove('hidden');
                                mainContent.classList.remove('fullwidth');
                            }}
                        }}

                        updateSidebarToggleIcon();
                    }}

                    function setManageMode(enabled) {{
                        manageMode = !!enabled;
                        document.body.classList.toggle('manage-mode', manageMode);
                        const btn = document.getElementById('manage-btn');
                        if (btn) btn.textContent = manageMode ? 'Done' : 'Manage';
                        updateBulkActions();
                    }}

                    function showToast(message, kind = 'success') {{
                        if (!toastHost) return;
                        const toast = document.createElement('div');
                        toast.className = 'toast ' + kind;
                        toast.textContent = message;
                        toastHost.appendChild(toast);
                        requestAnimationFrame(() => toast.classList.add('show'));
                        setTimeout(() => {{
                            toast.classList.remove('show');
                            setTimeout(() => toast.remove(), 180);
                        }}, 1700);
                    }}

                    function clearSelection() {{
                        selectedItems.clear();
                        document.querySelectorAll('.row-checkbox').forEach(cb => {{
                            cb.checked = false;
                        }});
                        updateBulkActions();
                    }}

                    function isInternalMoveDrag(event) {{
                        const types = Array.from(event.dataTransfer?.types || []);
                        return types.includes(INTERNAL_MOVE_MIME);
                    }}

                    function isExternalFilesDrag(event) {{
                        const types = Array.from(event.dataTransfer?.types || []);
                        return types.includes('Files');
                    }}

                    function getDraggedInternalPaths(event) {{
                        try {{
                            const raw = event.dataTransfer?.getData(INTERNAL_MOVE_MIME) || '[]';
                            const paths = JSON.parse(raw);
                            if (!Array.isArray(paths)) return [];
                            return Array.from(new Set(paths.filter(Boolean)));
                        }} catch (_) {{
                            return [];
                        }}
                    }}

                    function getSelectedOrSinglePaths(primaryPath) {{
                        if (selectedItems.has(primaryPath) && selectedItems.size > 0) {{
                            return Array.from(selectedItems);
                        }}
                        return [primaryPath];
                    }}

                    async function postJson(url, payload) {{
                        const res = await fetch(url, {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: JSON.stringify(payload),
                        }});
                        const data = await res.json();
                        if (!res.ok) throw new Error(data.error || 'Operation failed');
                        return data;
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
                            await uploadFilesBatch(files, hashCheck.checked);
                        }};
                        actions.appendChild(cancelBtn);
                        actions.appendChild(startBtn);
                        ui.content.appendChild(actions);
                    }}

                    async function uploadSingleFile(file, withHash, autoCloseOnSuccess = false) {{
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
                            if (autoCloseOnSuccess) {{
                                setTimeout(() => progress.close(), 450);
                            }}
                        }} catch (e) {{
                            progress.setStatus('Failed');
                            progress.setResult(e.message);
                        }}
                    }}

                    async function uploadFilesBatch(files, withHash = false) {{
                        if (!ensureWriteEnabled()) return;
                        if (!files || files.length === 0) return;
                        if (files.length === 1) {{
                            await uploadSingleFile(files[0], withHash, false);
                            await loadFolderContents(currentPath);
                            await loadFolderTree();
                            return;
                        }}

                        const progress = createProgressDialog('Uploading Files', files.length + ' file(s)');
                        let successCount = 0;
                        const failed = [];

                        for (let i = 0; i < files.length; i += 1) {{
                            const file = files[i];
                            const taskId = await createTask('upload');
                            progress.setProgress(0);
                            progress.setStatus('Uploading (' + (i + 1) + '/' + files.length + '): ' + file.name);
                            progress.setResult('');

                            try {{
                                const uploadUrl = '/upload-raw?task_id=' + encodeURIComponent(taskId) +
                                    '&path=' + encodeURIComponent(currentPath) +
                                    '&filename=' + encodeURIComponent(file.name) +
                                    '&hash=' + (withHash ? '1' : '0');

                                await xhrUpload(uploadUrl, file, (loaded, total) => {{
                                    progress.setProgress((loaded / Math.max(total, 1)) * 100);
                                    progress.setStatus('Uploading (' + (i + 1) + '/' + files.length + '): ' + file.name);
                                }});

                                await waitForTaskCompletion(taskId, {{
                                    setProgress: (p) => progress.setProgress(p),
                                    setStatus: (msg) => progress.setStatus('Processing (' + (i + 1) + '/' + files.length + '): ' + file.name + (msg ? ' - ' + msg : '')),
                                    setSpeed: (msg) => progress.setSpeed(msg),
                                }});

                                successCount += 1;
                            }} catch (e) {{
                                failed.push(file.name + ': ' + e.message);
                            }}
                        }}

                        progress.setSpeed('');
                        progress.setProgress(100);
                        if (failed.length === 0) {{
                            progress.setStatus('Completed');
                            progress.setResult('Uploaded ' + successCount + ' file(s) successfully.');
                        }} else {{
                            progress.setStatus('Completed with errors');
                            const preview = failed.slice(0, 3).join(' | ');
                            const more = failed.length > 3 ? ' | +' + (failed.length - 3) + ' more error(s)' : '';
                            progress.setResult('Uploaded ' + successCount + '/' + files.length + ' file(s). ' + preview + more);
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

                    function flattenFolderTree(node, depth = 0, acc = []) {{
                        const children = node.children || [];
                        acc.push({{
                            path: node.path,
                            name: node.name,
                            depth,
                            hasChildren: children.length > 0,
                            fullPath: node.path,
                        }});
                        children.forEach(child => flattenFolderTree(child, depth + 1, acc));
                        return acc;
                    }}

                    async function openRenameDialog(itemPath, itemName) {{
                        if (!ensureWriteEnabled()) return;
                        const ui = createDialogContainer('Rename', 'From: ' + itemName);

                        const input = document.createElement('input');
                        input.type = 'text';
                        input.value = itemName;
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

                        const renameBtn = document.createElement('button');
                        renameBtn.textContent = 'Rename';
                        renameBtn.onclick = async function() {{
                            const newName = (input.value || '').trim();
                            if (!newName) {{
                                showDialog('Enter a new name.');
                                return;
                            }}
                            try {{
                                await postJson('/rename', {{ path: itemPath, new_name: newName }});
                                ui.dialogDiv.remove();
                                clearSelection();
                                await loadFolderContents(currentPath);
                                await loadFolderTree();
                                showToast('Renamed successfully');
                            }} catch (e) {{
                                showDialog(e.message);
                            }}
                        }};

                        actions.appendChild(cancelBtn);
                        actions.appendChild(renameBtn);
                        ui.content.appendChild(actions);
                        input.focus();
                        input.select();
                    }}

                    async function runBulkDelete(paths) {{
                        const taskId = await createTask('bulk-delete');
                        const progress = createProgressDialog('Deleting', paths.length + ' item(s)');
                        progress.setStatus('Deleting...');

                        try {{
                            const waitPromise = waitForTaskCompletion(taskId, progress);
                            const res = await postJson('/bulk-delete?task_id=' + encodeURIComponent(taskId), {{ paths }});
                            await waitPromise;
                            progress.setStatus('Completed');
                            progress.setProgress(100);
                            progress.setResult('Deleted ' + (res.deleted || paths.length) + ' item(s)');
                        }} catch (e) {{
                            progress.setStatus('Failed');
                            progress.setResult(e.message);
                            throw e;
                        }}
                    }}

                    async function openDeleteConfirmDialog(paths, titleText) {{
                        if (!ensureWriteEnabled()) return;
                        const list = Array.isArray(paths) ? paths : [paths];
                        const ui = createDialogContainer('Delete Permanently', titleText || (list.length + ' item(s) selected'));

                        const msg = document.createElement('p');
                        msg.textContent = list.length === 1
                            ? 'This will permanently delete the selected item.'
                            : 'This will permanently delete ' + list.length + ' selected items.';
                        ui.content.appendChild(msg);

                        const confirmLabel = document.createElement('label');
                        confirmLabel.style.display = 'flex';
                        confirmLabel.style.alignItems = 'center';
                        confirmLabel.style.gap = '8px';
                        confirmLabel.style.marginTop = '12px';
                        const confirmCheck = document.createElement('input');
                        confirmCheck.type = 'checkbox';
                        confirmLabel.appendChild(confirmCheck);
                        confirmLabel.appendChild(document.createTextNode('I understand this cannot be undone'));
                        ui.content.appendChild(confirmLabel);

                        const actions = document.createElement('div');
                        actions.className = 'dialog-actions';
                        const cancelBtn = document.createElement('button');
                        cancelBtn.className = 'ghost-btn';
                        cancelBtn.textContent = 'Cancel';
                        cancelBtn.onclick = function() {{ ui.dialogDiv.remove(); }};

                        const deleteBtn = document.createElement('button');
                        deleteBtn.textContent = 'Delete';
                        deleteBtn.onclick = async function() {{
                            if (!confirmCheck.checked) {{
                                showDialog('Please confirm permanent deletion.');
                                return;
                            }}
                            try {{
                                if (list.length === 1) {{
                                    await postJson('/delete', {{ path: list[0] }});
                                }} else {{
                                    await runBulkDelete(list);
                                }}
                                ui.dialogDiv.remove();
                                clearSelection();
                                await loadFolderContents(currentPath);
                                await loadFolderTree();
                                showToast('Deleted successfully');
                            }} catch (e) {{
                                showDialog(e.message);
                            }}
                        }};

                        actions.appendChild(cancelBtn);
                        actions.appendChild(deleteBtn);
                        ui.content.appendChild(actions);
                    }}

                    async function runBulkMove(paths, destinationPath) {{
                        const taskId = await createTask('bulk-move');
                        const progress = createProgressDialog('Moving', paths.length + ' item(s)');
                        progress.setStatus('Moving...');

                        try {{
                            const waitPromise = waitForTaskCompletion(taskId, progress);
                            const res = await postJson('/bulk-move?task_id=' + encodeURIComponent(taskId), {{
                                paths,
                                destination: destinationPath,
                            }});
                            await waitPromise;
                            progress.setStatus('Completed');
                            progress.setProgress(100);
                            progress.setResult('Moved ' + (res.moved || paths.length) + ' item(s)');
                        }} catch (e) {{
                            progress.setStatus('Failed');
                            progress.setResult(e.message);
                            throw e;
                        }}
                    }}

                    async function executeMove(paths, destinationPath) {{
                        if (paths.length === 1) {{
                            await postJson('/move', {{ path: paths[0], destination: destinationPath }});
                            return;
                        }}
                        await runBulkMove(paths, destinationPath);
                    }}

                    async function openMoveDialog(paths, titleText) {{
                        if (!ensureWriteEnabled()) return;
                        const list = Array.isArray(paths) ? paths : [paths];

                        let tree;
                        try {{
                            const res = await fetch('/folder-tree');
                            if (!res.ok) throw new Error('Failed to load folders');
                            tree = await res.json();
                        }} catch (e) {{
                            showDialog(e.message);
                            return;
                        }}

                        const ui = createDialogContainer('Move To Folder', titleText || (list.length + ' item(s) selected'));

                        const treeWrap = document.createElement('div');
                        treeWrap.className = 'move-tree';
                        ui.content.appendChild(treeWrap);

                        const targetHint = document.createElement('div');
                        targetHint.className = 'dialog-subtitle';
                        targetHint.style.marginTop = '10px';
                        targetHint.style.textAlign = 'left';

                        let selectedDestination = currentPath || tree.path;
                        let selectedRow = null;

                        const updateTargetHint = function(path) {{
                            if (!path) return;
                            selectedDestination = path;
                            targetHint.textContent = 'Target: ' + path;
                        }};

                        const isOpenByDefault = function(path) {{
                            return currentPath === path || currentPath.startsWith(path + '/');
                        }};

                        const renderMoveNode = function(node, depth, mountPoint) {{
                            const hasChildren = Array.isArray(node.children) && node.children.length > 0;

                            const row = document.createElement('div');
                            row.className = 'move-tree-item';
                            row.style.paddingLeft = (10 + (depth * 14)) + 'px';
                            row.dataset.path = node.path;
                            row.title = node.path;

                            const toggle = document.createElement('span');
                            toggle.className = 'move-tree-toggle';
                            toggle.textContent = hasChildren ? '>' : '-';
                            row.appendChild(toggle);

                            const label = document.createElement('span');
                            label.className = 'move-tree-label';
                            label.textContent = node.name + (hasChildren ? ' +' : '');
                            row.appendChild(label);

                            row.addEventListener('mouseenter', () => {{
                                targetHint.textContent = 'Target: ' + node.path;
                            }});

                            row.addEventListener('click', () => {{
                                if (selectedRow) selectedRow.classList.remove('selected');
                                selectedRow = row;
                                selectedRow.classList.add('selected');
                                updateTargetHint(node.path);
                            }});

                            mountPoint.appendChild(row);

                            const childWrap = document.createElement('div');
                            childWrap.className = 'move-tree-children';
                            mountPoint.appendChild(childWrap);

                            if (hasChildren) {{
                                if (isOpenByDefault(node.path)) {{
                                    childWrap.classList.add('open');
                                    toggle.textContent = 'v';
                                }}

                                toggle.addEventListener('click', (event) => {{
                                    event.stopPropagation();
                                    childWrap.classList.toggle('open');
                                    toggle.textContent = childWrap.classList.contains('open') ? 'v' : '>';
                                }});

                                node.children.forEach((child) => renderMoveNode(child, depth + 1, childWrap));
                            }}

                            if (node.path === selectedDestination) {{
                                row.classList.add('selected');
                                selectedRow = row;
                                updateTargetHint(node.path);
                            }}
                        }};

                        renderMoveNode(tree, 0, treeWrap);
                        updateTargetHint(selectedDestination);
                        ui.content.appendChild(targetHint);

                        const actions = document.createElement('div');
                        actions.className = 'dialog-actions';
                        const cancelBtn = document.createElement('button');
                        cancelBtn.className = 'ghost-btn';
                        cancelBtn.textContent = 'Cancel';
                        cancelBtn.onclick = function() {{ ui.dialogDiv.remove(); }};

                        const moveBtn = document.createElement('button');
                        moveBtn.textContent = 'Move';
                        moveBtn.onclick = async function() {{
                            const destinationPath = selectedDestination;
                            if (!destinationPath) {{
                                showDialog('Choose a destination folder.');
                                return;
                            }}
                            try {{
                                await executeMove(list, destinationPath);
                                ui.dialogDiv.remove();
                                clearSelection();
                                await loadFolderContents(currentPath);
                                await loadFolderTree();
                                showToast('Moved successfully');
                            }} catch (e) {{
                                showDialog(e.message);
                            }}
                        }};

                        actions.appendChild(cancelBtn);
                        actions.appendChild(moveBtn);
                        ui.content.appendChild(actions);
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

                    function triggerDownloadLink(filePath, fileName, taskId = null, withHash = false) {{
                        let href = '/download?path=' + encodeURIComponent(filePath);
                        if (taskId) href += '&task_id=' + encodeURIComponent(taskId);
                        if (withHash) href += '&hash=1';

                        const a = document.createElement('a');
                        a.href = href;
                        a.download = fileName;
                        document.body.appendChild(a);
                        a.click();
                        a.remove();
                    }}

                    function delay(ms) {{
                        return new Promise(resolve => setTimeout(resolve, ms));
                    }}

                    function openBulkDownloadDialog(fileItems, folderItems = []) {{
                        const totalFiles = Array.isArray(fileItems) ? fileItems.length : 0;
                        if (totalFiles === 0) {{
                            showDialog('No files selected for individual download.');
                            return;
                        }}

                        const ui = createDialogContainer('Download Selected Files', totalFiles + ' file(s) selected');

                        if (folderItems.length > 0) {{
                            const note = document.createElement('p');
                            note.style.margin = '0 0 12px 0';
                            note.textContent = folderItems.length + ' folder(s) are selected and will be skipped here. Use ZIP for folders.';
                            ui.content.appendChild(note);
                        }}

                        const options = document.createElement('div');
                        options.className = 'dialog-row';
                        const hashLabel = document.createElement('label');
                        const hashCheck = document.createElement('input');
                        hashCheck.type = 'checkbox';
                        hashLabel.appendChild(hashCheck);
                        hashLabel.appendChild(document.createTextNode('Calculate SHA-256 for each file'));
                        options.appendChild(hashLabel);
                        ui.content.appendChild(options);

                        const actions = document.createElement('div');
                        actions.className = 'dialog-actions';
                        const cancelBtn = document.createElement('button');
                        cancelBtn.className = 'ghost-btn';
                        cancelBtn.textContent = 'Cancel';
                        cancelBtn.onclick = function() {{ ui.dialogDiv.remove(); }};
                        const startBtn = document.createElement('button');
                        startBtn.textContent = 'Download Files';
                        startBtn.onclick = async function() {{
                            ui.dialogDiv.remove();
                            await startBulkFileDownloads(fileItems, hashCheck.checked);
                        }};
                        actions.appendChild(cancelBtn);
                        actions.appendChild(startBtn);
                        ui.content.appendChild(actions);
                    }}

                    async function startBulkFileDownloads(fileItems, withHash) {{
                        const total = Array.isArray(fileItems) ? fileItems.length : 0;
                        if (total === 0) return;

                        const progress = createProgressDialog('Downloading Files', total + ' file(s)');
                        let successCount = 0;
                        const failed = [];
                        const hashes = [];

                        for (let i = 0; i < total; i += 1) {{
                            const item = fileItems[i];
                            const step = '(' + (i + 1) + '/' + total + ')';
                            progress.setSpeed('');
                            progress.setStatus('Downloading ' + step + ': ' + item.name);
                            progress.setProgress((i / total) * 100);

                            try {{
                                if (withHash) {{
                                    const taskId = await createTask('download');
                                    triggerDownloadLink(item.path, item.name, taskId, true);
                                    const task = await waitForTaskCompletion(taskId, {{
                                        setProgress: (p) => progress.setProgress(((i + (p / 100)) / total) * 100),
                                        setStatus: (msg) => progress.setStatus('Downloading ' + step + ': ' + item.name + (msg ? ' - ' + msg : '')),
                                        setSpeed: (msg) => progress.setSpeed(msg),
                                    }});
                                    successCount += 1;
                                    if (task.hash_sha256) {{
                                        hashes.push(item.name + ': ' + task.hash_sha256);
                                    }} else {{
                                        hashes.push(item.name + ': Hash unavailable');
                                    }}
                                }} else {{
                                    triggerDownloadLink(item.path, item.name);
                                    successCount += 1;
                                    progress.setProgress(((i + 1) / total) * 100);
                                    await delay(220);
                                }}
                            }} catch (e) {{
                                failed.push(item.name + ': ' + e.message);
                            }}
                        }}

                        progress.setSpeed('');
                        progress.setProgress(100);

                        if (failed.length === 0) {{
                            progress.setStatus('Completed');
                        }} else {{
                            progress.setStatus('Completed with errors');
                        }}

                        let resultText = 'Downloaded ' + successCount + '/' + total + ' file(s).';
                        if (withHash && hashes.length > 0) {{
                            const hashPreview = hashes.slice(0, 2).join(' | ');
                            const moreHashes = hashes.length > 2 ? ' | +' + (hashes.length - 2) + ' more hash(es)' : '';
                            resultText += ' ' + hashPreview + moreHashes;
                        }}
                        if (failed.length > 0) {{
                            const failPreview = failed.slice(0, 2).join(' | ');
                            const moreFails = failed.length > 2 ? ' | +' + (failed.length - 2) + ' more error(s)' : '';
                            resultText += ' ' + failPreview + moreFails;
                        }}
                        progress.setResult(resultText);
                    }}

                    async function startFileDownload(filePath, fileName, withHash) {{
                        const taskId = await createTask('download');
                        triggerDownloadLink(filePath, fileName, taskId, withHash);

                        if (!withHash) return;

                        const progress = createProgressDialog('Downloading', fileName);
                        try {{
                            progress.setStatus('Downloading...');
                            const task = await waitForTaskCompletion(taskId, progress);
                            progress.setStatus('Completed');
                            progress.setProgress(100);
                            progress.setResult(task.hash_sha256 ? 'SHA-256: ' + task.hash_sha256 : 'Hash unavailable');
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
                            const sidebarEl = document.getElementById('sidebar');
                            if (sidebarEl) {{
                                const openPaths = new Set();
                                sidebarEl.querySelectorAll('.tree-item').forEach(item => {{
                                    const childContainer = item.nextElementSibling;
                                    if (
                                        childContainer &&
                                        childContainer.classList.contains('tree-children') &&
                                        childContainer.classList.contains('open') &&
                                        item.dataset.path
                                    ) {{
                                        openPaths.add(item.dataset.path);
                                    }}
                                }});
                                expandedTreePaths = openPaths;
                            }}

                            const res = await fetch('/folder-tree');
                            const tree = await res.json();
                            const sidebarMount = document.getElementById('sidebar');
                            sidebarMount.innerHTML = '';
                            renderTree(tree, sidebarMount);
                        }} catch (e) {{
                            console.error('Error loading folder tree:', e);
                        }}
                    }}
                    
                    function renderTree(node, container, depth = 0) {{
                        const hasChildren = Array.isArray(node.children) && node.children.length > 0;
                        const isCurrentPathOrParent = currentPath === node.path || currentPath.startsWith(node.path + '/');
                        const shouldOpen = hasChildren && (expandedTreePaths.has(node.path) || isCurrentPathOrParent);

                        const div = document.createElement('div');
                        div.className = 'tree-item folder';
                        div.style.marginLeft = (depth * 15) + 'px';
                        
                        let html = '<span class="tree-toggle">' + (shouldOpen ? '- ' : '+ ') + '</span>';
                        html += 'ðŸ“ ' + node.name;
                        
                        div.innerHTML = html;
                        div.dataset.path = node.path;
                        
                        const toggle = div.querySelector('.tree-toggle');
                        const childrenDiv = document.createElement('div');
                        childrenDiv.className = 'tree-children';
                        if (shouldOpen) {{
                            childrenDiv.classList.add('open');
                            expandedTreePaths.add(node.path);
                        }}
                        
                        if (!hasChildren) {{
                            toggle.style.visibility = 'hidden';
                        }}
                        
                        toggle.addEventListener('click', (e) => {{
                            e.stopPropagation();
                            if (!hasChildren) return;
                            childrenDiv.classList.toggle('open');
                            const isOpen = childrenDiv.classList.contains('open');
                            toggle.textContent = isOpen ? '- ' : '+ ';
                            if (isOpen) {{
                                expandedTreePaths.add(node.path);
                            }} else {{
                                expandedTreePaths.delete(node.path);
                            }}
                        }});
                        
                        div.addEventListener('click', () => {{
                            if (hasChildren) expandedTreePaths.add(node.path);
                            loadFolderContents(node.path);
                            updateBreadcrumb(node.path);
                            closeMobileSidebar();
                        }});

                        if (uploadsEnabled) {{
                            div.addEventListener('dragover', (e) => {{
                                if (!isInternalMoveDrag(e)) return;
                                e.preventDefault();
                                e.dataTransfer.dropEffect = 'move';
                                div.classList.add('drop-target');
                            }});

                            div.addEventListener('dragleave', () => {{
                                div.classList.remove('drop-target');
                            }});

                            div.addEventListener('drop', async (e) => {{
                                if (!isInternalMoveDrag(e)) return;
                                e.preventDefault();
                                div.classList.remove('drop-target');
                                const paths = getDraggedInternalPaths(e);
                                if (paths.length === 0) return;
                                try {{
                                    await executeMove(paths, node.path);
                                    clearSelection();
                                    await loadFolderContents(currentPath);
                                    await loadFolderTree();
                                    showToast('Moved successfully');
                                }} catch (err) {{
                                    showDialog(err.message);
                                }}
                            }});
                        }}
                        
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
                            currentFolderItems = Array.isArray(items) ? items : [];
                            applySearchFilter();
                        }} catch (e) {{
                            console.error('Error loading folder contents:', e);
                        }}
                    }}

                    function applySearchFilter() {{
                        const query = (searchInput?.value || '').trim().toLowerCase();
                        searchQuery = query;
                        selectedItems.clear();

                        if (!query) {{
                            renderTable(currentFolderItems);
                            return;
                        }}

                        const filtered = currentFolderItems.filter(item => {{
                            const name = String(item.name || '').toLowerCase();
                            const path = String(item.path || '').toLowerCase();
                            return name.includes(query) || path.includes(query);
                        }});
                        renderTable(filtered);
                    }}

                    function openSearchBar() {{
                        searchWrap.classList.add('show');
                        searchInput.focus();
                        searchInput.select();
                    }}

                    function closeSearchBar() {{
                        searchWrap.classList.remove('show');
                        searchInput.value = '';
                        searchQuery = '';
                        applySearchFilter();
                    }}
                    
                    function renderTable(items) {{
                        const tbody = document.getElementById('file-table');
                        tbody.innerHTML = '';
                        itemMap = new Map();
                        imageFilesInCurrentFolder = items
                            .filter(item => !item.is_dir && (!!item.is_image || isImageFilename(item.name)))
                            .map(item => ({{ path: item.path, name: item.name }}));
                        videoFilesInCurrentFolder = items
                            .filter(item => !item.is_dir && (!!item.is_video || isVideoFilename(item.name)))
                            .map(item => ({{ path: item.path, name: item.name }}));
                        audioFilesInCurrentFolder = items
                            .filter(item => !item.is_dir && (!!item.is_audio || isAudioFilename(item.name)))
                            .map(item => ({{ path: item.path, name: item.name }}));
                        
                        items.forEach(item => {{
                            itemMap.set(item.path, item);
                            const row = document.createElement('tr');
                            const ext = item.name.substring(item.name.lastIndexOf('.')).toLowerCase();
                            const isTextFile = !!item.is_text;
                            const isImageFile = !!item.is_image || isImageFilename(item.name);
                            const isVideoFile = !!item.is_video || isVideoFilename(item.name);
                            const isAudioFile = !!item.is_audio || isAudioFilename(item.name);
                            const isPdfFile = !!item.is_pdf || isPdfFilename(item.name);
                            
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
                            checkboxCell.dataset.label = 'Select';
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
                            filenameCell.dataset.label = 'Name';
                            filenameCell.textContent = filename;
                            filenameCell.dataset.path = item.path;
                            filenameCell.dataset.isdir = item.is_dir;
                            if (item.is_dir) row.classList.add('folder-row');
                            row.appendChild(filenameCell);
                            
                            const sizeCell = document.createElement('td');
                            sizeCell.className = 'col-size';
                            sizeCell.dataset.label = 'Size';
                            sizeCell.textContent = sizeStr;
                            row.appendChild(sizeCell);
                            
                            const typeCell = document.createElement('td');
                            typeCell.className = 'col-type';
                            typeCell.dataset.label = 'Type';
                            typeCell.textContent = typeStr;
                            row.appendChild(typeCell);
                            
                            const dateCell = document.createElement('td');
                            dateCell.className = 'col-date';
                            dateCell.dataset.label = 'Date';
                            dateCell.textContent = item.date;
                            row.appendChild(dateCell);
                            
                            const actionCell = document.createElement('td');
                            actionCell.className = 'col-action';
                            actionCell.dataset.label = 'Actions';
                            const actionSlot = document.createElement('div');
                            actionSlot.className = 'action-slot';
                            
                            if (downloadsEnabled) {{
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

                                    if (isImageFile) {{
                                        const imageViewBtn = document.createElement('button');
                                        imageViewBtn.className = 'action-btn image-view';
                                        imageViewBtn.textContent = 'VIEW';
                                        imageViewBtn.dataset.file = item.path;
                                        imageViewBtn.dataset.name = item.name;
                                        actionSlot.appendChild(imageViewBtn);
                                    }}

                                    if (isVideoFile) {{
                                        const videoPlayBtn = document.createElement('button');
                                        videoPlayBtn.className = 'action-btn video-play';
                                        videoPlayBtn.textContent = 'PLAY';
                                        videoPlayBtn.dataset.file = item.path;
                                        videoPlayBtn.dataset.name = item.name;
                                        actionSlot.appendChild(videoPlayBtn);
                                    }}

                                    if (isAudioFile) {{
                                        const audioPlayBtn = document.createElement('button');
                                        audioPlayBtn.className = 'action-btn audio-play';
                                        audioPlayBtn.textContent = 'PLAY';
                                        audioPlayBtn.dataset.file = item.path;
                                        audioPlayBtn.dataset.name = item.name;
                                        actionSlot.appendChild(audioPlayBtn);
                                    }}

                                    if (isPdfFile) {{
                                        const pdfViewBtn = document.createElement('button');
                                        pdfViewBtn.className = 'action-btn pdf-view';
                                        pdfViewBtn.textContent = 'VIEW';
                                        pdfViewBtn.dataset.file = item.path;
                                        pdfViewBtn.dataset.name = item.name;
                                        actionSlot.appendChild(pdfViewBtn);
                                    }}
                                }}
                            }}

                            if (uploadsEnabled) {{
                                const renameBtn = document.createElement('button');
                                renameBtn.className = 'action-btn manage-action rename';
                                renameBtn.textContent = 'RENAME';
                                renameBtn.dataset.path = item.path;
                                renameBtn.dataset.name = item.name;
                                actionSlot.appendChild(renameBtn);
                            }}
                            
                            actionCell.appendChild(actionSlot);
                            row.appendChild(actionCell);

                            if (uploadsEnabled) {{
                                row.draggable = true;
                                row.addEventListener('dragstart', (e) => {{
                                    const dragPaths = getSelectedOrSinglePaths(item.path);
                                    e.dataTransfer.setData(INTERNAL_MOVE_MIME, JSON.stringify(dragPaths));
                                    e.dataTransfer.effectAllowed = 'move';
                                }});

                                row.addEventListener('dragend', () => {{
                                    document.querySelectorAll('.drop-target').forEach(el => el.classList.remove('drop-target'));
                                }});
                            }}

                            if (item.is_dir) {{
                                row.addEventListener('click', function(e) {{
                                    if (e.target.closest('button') || e.target.closest('input')) return;
                                    loadFolderContents(item.path);
                                    updateBreadcrumb(item.path);
                                }});

                                if (uploadsEnabled) {{
                                    row.addEventListener('dragover', (e) => {{
                                        if (!isInternalMoveDrag(e)) return;
                                        e.preventDefault();
                                        e.dataTransfer.dropEffect = 'move';
                                        row.classList.add('drop-target');
                                    }});

                                    row.addEventListener('dragleave', () => {{
                                        row.classList.remove('drop-target');
                                    }});

                                    row.addEventListener('drop', async (e) => {{
                                        if (!isInternalMoveDrag(e)) return;
                                        e.preventDefault();
                                        row.classList.remove('drop-target');
                                        const dragPaths = getDraggedInternalPaths(e);
                                        if (dragPaths.length === 0) return;
                                        try {{
                                            await executeMove(dragPaths, item.path);
                                            clearSelection();
                                            await loadFolderContents(currentPath);
                                            await loadFolderTree();
                                            showToast('Moved successfully');
                                        }} catch (err) {{
                                            showDialog(err.message);
                                        }}
                                    }});
                                }}
                            }}

                            tbody.appendChild(row);
                        }});

                        if (items.length === 0) {{
                            const emptyRow = document.createElement('tr');
                            const emptyCell = document.createElement('td');
                            emptyCell.colSpan = 6;
                            emptyCell.style.padding = '18px 12px';
                            emptyCell.style.color = '#a0a0a0';
                            emptyCell.textContent = searchQuery
                                ? 'No results for "' + searchQuery + '" in this folder.'
                                : 'No files found in this folder.';
                            emptyRow.appendChild(emptyCell);
                            tbody.appendChild(emptyRow);
                        }}
                        
                        // Attach event listeners
                        document.querySelectorAll('.filename').forEach(el => {{
                            el.addEventListener('click', function() {{
                                const path = this.dataset.path;
                                const isDir = this.dataset.isdir === 'true' || this.dataset.isdir === true;
                                if (isDir && path) {{
                                    loadFolderContents(path);
                                    updateBreadcrumb(path);
                                    closeMobileSidebar();
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

                        document.querySelectorAll('.image-view').forEach(el => {{
                            el.addEventListener('click', function() {{
                                const filePath = this.dataset.file;
                                const fileName = this.dataset.name;
                                openImageViewer(filePath, fileName);
                            }});
                        }});

                        document.querySelectorAll('.video-play').forEach(el => {{
                            el.addEventListener('click', function() {{
                                const filePath = this.dataset.file;
                                const fileName = this.dataset.name;
                                openVideoPlayer(filePath, fileName);
                            }});
                        }});

                        document.querySelectorAll('.audio-play').forEach(el => {{
                            el.addEventListener('click', function() {{
                                const filePath = this.dataset.file;
                                const fileName = this.dataset.name;
                                openAudioPlayer(filePath, fileName);
                            }});
                        }});

                        document.querySelectorAll('.pdf-view').forEach(el => {{
                            el.addEventListener('click', function() {{
                                const filePath = this.dataset.file;
                                const fileName = this.dataset.name;
                                openPdfViewer(filePath, fileName);
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

                        document.querySelectorAll('.rename').forEach(el => {{
                            el.addEventListener('click', function() {{
                                openRenameDialog(this.dataset.path, this.dataset.name);
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

                    function isImageFilename(name) {{
                        return /\\.(jpg|jpeg|png)$/i.test(name || '');
                    }}

                    function isVideoFilename(name) {{
                        return /\\.(mp4|webm|ogg)$/i.test(name || '');
                    }}

                    function isAudioFilename(name) {{
                        return /\\.(mp3|wav|ogg|aac)$/i.test(name || '');
                    }}

                    function isPdfFilename(name) {{
                        return /\\.pdf$/i.test(name || '');
                    }}

                    function isWordFilename(name) {{
                        return /\\.docx$/i.test(name || '');
                    }}

                    function isSheetFilename(name) {{
                        return /\\.(xlsx|xls|csv)$/i.test(name || '');
                    }}

                    function closeFileViewer() {{
                        modal.classList.remove('show');
                        modalBody.textContent = '';
                        modalBody.innerHTML = '';
                    }}

                    function openModalWithTitle(title) {{
                        modalTitle.textContent = title;
                        modalBody.textContent = '';
                        modalBody.innerHTML = '';
                        modal.classList.add('show');
                    }}

                    function openPdfViewer(filePath, fileName) {{
                        if (!downloadsEnabled) return;
                        openModalWithTitle('PDF Viewer - ' + fileName);
                        const frame = document.createElement('iframe');
                        frame.className = 'doc-preview-frame';
                        frame.src = '/pdf?path=' + encodeURIComponent(filePath);
                        frame.setAttribute('title', 'PDF preview');
                        modalBody.appendChild(frame);
                    }}

                    async function openWordViewer(filePath, fileName) {{
                        if (!downloadsEnabled) return;
                        openModalWithTitle('Word Viewer - ' + fileName);

                        try {{
                            const res = await fetch('/docx?path=' + encodeURIComponent(filePath));
                            if (!res.ok) throw new Error('Preview unavailable');
                            const blob = await res.blob();
                            const sizeText = formatSize(blob.size || 0);

                            const message = document.createElement('div');
                            message.className = 'doc-preview-message';
                            message.textContent = 'Document stream is ready (' + sizeText + '). Rich DOCX rendering will be enabled in the next implementation step.';
                            modalBody.appendChild(message);

                            const actions = document.createElement('div');
                            actions.className = 'doc-preview-actions';
                            const downloadBtn = document.createElement('button');
                            downloadBtn.className = 'action-btn';
                            downloadBtn.textContent = 'DOWNLOAD';
                            downloadBtn.addEventListener('click', function() {{
                                openDownloadDialog(filePath, fileName);
                            }});
                            actions.appendChild(downloadBtn);
                            modalBody.appendChild(actions);
                        }} catch (e) {{
                            showDialog('Error loading document: ' + e.message);
                            closeFileViewer();
                        }}
                    }}

                    function parseCsvLine(line) {{
                        const out = [];
                        let current = '';
                        let inQuotes = false;

                        for (let i = 0; i < line.length; i += 1) {{
                            const ch = line[i];
                            if (ch === '"') {{
                                if (inQuotes && line[i + 1] === '"') {{
                                    current += '"';
                                    i += 1;
                                }} else {{
                                    inQuotes = !inQuotes;
                                }}
                            }} else if (ch === ',' && !inQuotes) {{
                                out.push(current);
                                current = '';
                            }} else {{
                                current += ch;
                            }}
                        }}
                        out.push(current);
                        return out;
                    }}

                    function renderCsvPreview(csvText) {{
                        const lines = (csvText || '').split(/\\r?\\n/).filter(Boolean).slice(0, 200);
                        if (!lines.length) {{
                            modalBody.textContent = 'Empty CSV file.';
                            return;
                        }}

                        const rows = lines.map(parseCsvLine);
                        const maxCols = Math.min(20, Math.max(...rows.map(r => r.length), 0));
                        const table = document.createElement('table');
                        table.className = 'sheet-preview-table';

                        const thead = document.createElement('thead');
                        const headRow = document.createElement('tr');
                        for (let i = 0; i < maxCols; i += 1) {{
                            const th = document.createElement('th');
                            th.textContent = 'Col ' + (i + 1);
                            headRow.appendChild(th);
                        }}
                        thead.appendChild(headRow);
                        table.appendChild(thead);

                        const tbody = document.createElement('tbody');
                        rows.forEach(row => {{
                            const tr = document.createElement('tr');
                            for (let i = 0; i < maxCols; i += 1) {{
                                const td = document.createElement('td');
                                td.textContent = row[i] || '';
                                tr.appendChild(td);
                            }}
                            tbody.appendChild(tr);
                        }});

                        table.appendChild(tbody);
                        modalBody.appendChild(table);
                    }}

                    async function openSheetViewer(filePath, fileName) {{
                        if (!downloadsEnabled) return;
                        openModalWithTitle('Sheet Viewer - ' + fileName);

                        try {{
                            const res = await fetch('/sheet?path=' + encodeURIComponent(filePath));
                            if (!res.ok) throw new Error('Preview unavailable');

                            const contentType = (res.headers.get('Content-Type') || '').toLowerCase();
                            if (contentType.includes('csv') || /\\.csv$/i.test(fileName || '')) {{
                                const csvText = await res.text();
                                renderCsvPreview(csvText);
                                return;
                            }}

                            const blob = await res.blob();
                            const message = document.createElement('div');
                            message.className = 'doc-preview-message';
                            message.textContent = 'Spreadsheet stream is ready (' + formatSize(blob.size || 0) + '). XLSX/XLS grid rendering will be enabled in the next implementation step.';
                            modalBody.appendChild(message);

                            const actions = document.createElement('div');
                            actions.className = 'doc-preview-actions';
                            const downloadBtn = document.createElement('button');
                            downloadBtn.className = 'action-btn';
                            downloadBtn.textContent = 'DOWNLOAD';
                            downloadBtn.addEventListener('click', function() {{
                                openDownloadDialog(filePath, fileName);
                            }});
                            actions.appendChild(downloadBtn);
                            modalBody.appendChild(actions);
                        }} catch (e) {{
                            showDialog('Error loading sheet: ' + e.message);
                            closeFileViewer();
                        }}
                    }}

                    function closeImageViewer() {{
                        imageModal.classList.remove('show');
                        imagePreview.removeAttribute('src');
                        activeImageIndex = -1;
                    }}

                    function renderActiveImage() {{
                        if (activeImageIndex < 0 || activeImageIndex >= imageFilesInCurrentFolder.length) return;
                        const active = imageFilesInCurrentFolder[activeImageIndex];
                        imageModalTitle.textContent = 'ðŸ–¼ ' + active.name;
                        imageCounter.textContent = (activeImageIndex + 1) + ' / ' + imageFilesInCurrentFolder.length;
                        imagePreview.src = '/image?path=' + encodeURIComponent(active.path);
                        imagePrevBtn.disabled = activeImageIndex === 0;
                        imageNextBtn.disabled = activeImageIndex === imageFilesInCurrentFolder.length - 1;
                    }}

                    function openImageViewer(filePath, fileName) {{
                        if (!downloadsEnabled) return;
                        if (!imageFilesInCurrentFolder.length) {{
                            showDialog('No images found in this folder.');
                            return;
                        }}

                        const index = imageFilesInCurrentFolder.findIndex(file => file.path === filePath);
                        if (index >= 0) {{
                            activeImageIndex = index;
                        }} else {{
                            imageFilesInCurrentFolder.push({{ path: filePath, name: fileName }});
                            activeImageIndex = imageFilesInCurrentFolder.length - 1;
                        }}

                        renderActiveImage();
                        imageModal.classList.add('show');
                    }}

                    function navigateImage(delta) {{
                        if (!imageModal.classList.contains('show')) return;
                        const nextIndex = activeImageIndex + delta;
                        if (nextIndex < 0 || nextIndex >= imageFilesInCurrentFolder.length) return;
                        activeImageIndex = nextIndex;
                        renderActiveImage();
                    }}

                    function closeVideoPlayer() {{
                        videoModal.classList.remove('show');
                        videoPreview.pause();
                        videoPreview.removeAttribute('src');
                        videoPreview.load();
                        activeVideoIndex = -1;
                    }}

                    function renderActiveVideo() {{
                        if (activeVideoIndex < 0 || activeVideoIndex >= videoFilesInCurrentFolder.length) return;
                        const active = videoFilesInCurrentFolder[activeVideoIndex];
                        videoModalTitle.textContent = 'â–¶ ' + active.name;
                        videoCounter.textContent = (activeVideoIndex + 1) + ' / ' + videoFilesInCurrentFolder.length;
                        videoPreview.src = '/video?path=' + encodeURIComponent(active.path);
                        videoPrevBtn.disabled = activeVideoIndex === 0;
                        videoNextBtn.disabled = activeVideoIndex === videoFilesInCurrentFolder.length - 1;
                    }}

                    function openVideoPlayer(filePath, fileName) {{
                        if (!downloadsEnabled) return;
                        if (!videoFilesInCurrentFolder.length) {{
                            showDialog('No videos found in this folder.');
                            return;
                        }}

                        const index = videoFilesInCurrentFolder.findIndex(file => file.path === filePath);
                        if (index >= 0) {{
                            activeVideoIndex = index;
                        }} else {{
                            videoFilesInCurrentFolder.push({{ path: filePath, name: fileName }});
                            activeVideoIndex = videoFilesInCurrentFolder.length - 1;
                        }}

                        renderActiveVideo();
                        videoModal.classList.add('show');
                    }}

                    function navigateVideo(delta) {{
                        if (!videoModal.classList.contains('show')) return;
                        const nextIndex = activeVideoIndex + delta;
                        if (nextIndex < 0 || nextIndex >= videoFilesInCurrentFolder.length) return;
                        activeVideoIndex = nextIndex;
                        renderActiveVideo();
                    }}

                    function closeAudioPlayer() {{
                        audioModal.classList.remove('show');
                        audioPreview.pause();
                        audioPreview.removeAttribute('src');
                        audioPreview.load();
                        activeAudioIndex = -1;
                    }}

                    function renderActiveAudio() {{
                        if (activeAudioIndex < 0 || activeAudioIndex >= audioFilesInCurrentFolder.length) return;
                        const active = audioFilesInCurrentFolder[activeAudioIndex];
                        audioModalTitle.textContent = 'â™ª ' + active.name;
                        audioCounter.textContent = (activeAudioIndex + 1) + ' / ' + audioFilesInCurrentFolder.length;
                        audioPreview.src = '/audio?path=' + encodeURIComponent(active.path);
                        audioPrevBtn.disabled = activeAudioIndex === 0;
                        audioNextBtn.disabled = activeAudioIndex === audioFilesInCurrentFolder.length - 1;
                    }}

                    function openAudioPlayer(filePath, fileName) {{
                        if (!downloadsEnabled) return;
                        if (!audioFilesInCurrentFolder.length) {{
                            showDialog('No audio files found in this folder.');
                            return;
                        }}

                        const index = audioFilesInCurrentFolder.findIndex(file => file.path === filePath);
                        if (index >= 0) {{
                            activeAudioIndex = index;
                        }} else {{
                            audioFilesInCurrentFolder.push({{ path: filePath, name: fileName }});
                            activeAudioIndex = audioFilesInCurrentFolder.length - 1;
                        }}

                        renderActiveAudio();
                        audioModal.classList.add('show');
                    }}

                    function navigateAudio(delta) {{
                        if (!audioModal.classList.contains('show')) return;
                        const nextIndex = activeAudioIndex + delta;
                        if (nextIndex < 0 || nextIndex >= audioFilesInCurrentFolder.length) return;
                        activeAudioIndex = nextIndex;
                        renderActiveAudio();
                    }}
                    
                    async function viewFile(filePath, fileName) {{
                        try {{
                            const res = await fetch('/view?path=' + encodeURIComponent(filePath));
                            if (!res.ok) {{
                                const msg = await res.text();
                                throw new Error(msg || 'Preview unavailable');
                            }}
                            const content = await res.text();
                            modalTitle.textContent = 'ðŸ“„ ' + fileName;
                            modalBody.textContent = content;
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
                        if (selectedItems.size > 0 && downloadsEnabled) {{
                            bulkActionsDiv.classList.add('show');
                        }} else {{
                            bulkActionsDiv.classList.remove('show');
                        }}

                        const bulkManagementDiv = document.getElementById('bulk-management');
                        if (selectedItems.size > 0 && uploadsEnabled && manageMode) {{
                            bulkManagementDiv.classList.add('show');
                        }} else {{
                            bulkManagementDiv.classList.remove('show');
                        }}
                    }}
                    
                    document.getElementById('bulk-zip').addEventListener('click', function() {{
                        if (selectedItems.size === 0) return;
                        const selected = Array.from(selectedItems);
                        if (selected.length === 1) {{
                            const one = itemMap.get(selected[0]);
                            if (one) {{
                                const rawName = one.name || 'archive';
                                const baseName = one.is_dir ? rawName : (rawName.replace(/\\.[^/.]+$/, '') || rawName);
                                startZipDownload(selected, baseName + '.zip');
                                return;
                            }}
                        }}
                        startZipDownload(selected, 'selected-items.zip');
                    }});
                    
                    document.getElementById('bulk-download').addEventListener('click', async function() {{
                        if (selectedItems.size === 0) return;
                        const selected = Array.from(selectedItems);
                        const selectedEntries = selected.map(path => itemMap.get(path)).filter(Boolean);
                        if (selectedEntries.length === 0) return;

                        if (selectedEntries.length === 1) {{
                            const one = selectedEntries[0];
                            if (one && !one.is_dir) {{
                                openDownloadDialog(one.path, one.name);
                                return;
                            }}
                            if (one) {{
                                const rawName = one.name || 'archive';
                                const baseName = one.is_dir ? rawName : (rawName.replace(/\\.[^/.]+$/, '') || rawName);
                                startZipDownload(selected, baseName + '.zip');
                                return;
                            }}
                        }}

                        const fileEntries = selectedEntries.filter(entry => !entry.is_dir);
                        const folderEntries = selectedEntries.filter(entry => entry.is_dir);

                        if (fileEntries.length === 0) {{
                            startZipDownload(selected, 'bulk-download.zip');
                            return;
                        }}

                        openBulkDownloadDialog(
                            fileEntries.map(entry => ({{ path: entry.path, name: entry.name }})),
                            folderEntries
                        );
                    }});

                    document.getElementById('upload-btn').addEventListener('click', function() {{
                        openUploadDialog();
                    }});

                    document.getElementById('mkdir-btn').addEventListener('click', function() {{
                        openMkdirDialog();
                    }});

                    document.getElementById('manage-btn').addEventListener('click', function() {{
                        if (!uploadsEnabled) return;
                        setManageMode(!manageMode);
                    }});

                    searchToggleBtn.addEventListener('click', function() {{
                        openSearchBar();
                    }});

                    searchCloseBtn.addEventListener('click', function() {{
                        closeSearchBar();
                    }});

                    searchInput.addEventListener('input', function() {{
                        applySearchFilter();
                    }});

                    searchInput.addEventListener('keydown', function(e) {{
                        if (e.key !== 'Escape') return;
                        e.preventDefault();
                        closeSearchBar();
                    }});

                    document.getElementById('bulk-delete').addEventListener('click', function() {{
                        if (selectedItems.size === 0) return;
                        const paths = Array.from(selectedItems);
                        openDeleteConfirmDialog(paths, paths.length + ' item(s) selected');
                    }});

                    document.getElementById('bulk-move').addEventListener('click', function() {{
                        if (selectedItems.size === 0) return;
                        const paths = Array.from(selectedItems);
                        openMoveDialog(paths, paths.length + ' item(s) selected');
                    }});

                    document.getElementById('file-close-btn').addEventListener('click', function() {{
                        closeFileViewer();
                    }});

                    modal.addEventListener('click', function(e) {{
                        if (e.target === modal) closeFileViewer();
                    }});

                    imagePrevBtn.addEventListener('click', function() {{
                        navigateImage(-1);
                    }});

                    imageNextBtn.addEventListener('click', function() {{
                        navigateImage(1);
                    }});

                    document.getElementById('image-close-btn').addEventListener('click', function() {{
                        closeImageViewer();
                    }});

                    imageModal.addEventListener('click', function(e) {{
                        if (e.target === imageModal) closeImageViewer();
                    }});

                    videoPrevBtn.addEventListener('click', function() {{
                        navigateVideo(-1);
                    }});

                    videoNextBtn.addEventListener('click', function() {{
                        navigateVideo(1);
                    }});

                    document.getElementById('video-close-btn').addEventListener('click', function() {{
                        closeVideoPlayer();
                    }});

                    videoModal.addEventListener('click', function(e) {{
                        if (e.target === videoModal) closeVideoPlayer();
                    }});

                    audioPrevBtn.addEventListener('click', function() {{
                        navigateAudio(-1);
                    }});

                    audioNextBtn.addEventListener('click', function() {{
                        navigateAudio(1);
                    }});

                    document.getElementById('audio-close-btn').addEventListener('click', function() {{
                        closeAudioPlayer();
                    }});

                    audioModal.addEventListener('click', function(e) {{
                        if (e.target === audioModal) closeAudioPlayer();
                    }});

                    document.addEventListener('keydown', function(e) {{
                        if (imageModal.classList.contains('show')) {{
                            if (e.key === 'ArrowLeft') {{
                                e.preventDefault();
                                navigateImage(-1);
                            }} else if (e.key === 'ArrowRight') {{
                                e.preventDefault();
                                navigateImage(1);
                            }} else if (e.key === 'Escape') {{
                                e.preventDefault();
                                closeImageViewer();
                            }}
                            return;
                        }}
                        if (videoModal.classList.contains('show')) {{
                            if (e.key === 'ArrowLeft') {{
                                e.preventDefault();
                                navigateVideo(-1);
                            }} else if (e.key === 'ArrowRight') {{
                                e.preventDefault();
                                navigateVideo(1);
                            }} else if (e.key === 'Escape') {{
                                e.preventDefault();
                                closeVideoPlayer();
                            }}
                            return;
                        }}
                        if (modal.classList.contains('show') && e.key === 'Escape') {{
                            e.preventDefault();
                            closeFileViewer();
                            return;
                        }}
                        if (!audioModal.classList.contains('show')) return;
                        if (e.key === 'ArrowLeft') {{
                            e.preventDefault();
                            navigateAudio(-1);
                        }} else if (e.key === 'ArrowRight') {{
                            e.preventDefault();
                            navigateAudio(1);
                        }} else if (e.key === 'Escape') {{
                            e.preventDefault();
                            closeAudioPlayer();
                        }}
                    }});
                    
                    function updateBreadcrumb(path) {{
                        // Remove the base upload folder path to get relative parts
                        const basePath = path.replace(/\\\\/g, '/');
                        const parts = basePath.split('/').filter(p => p && p !== 'shared_files');
                        
                        const breadcrumbDiv = document.getElementById('breadcrumb');
                        breadcrumbDiv.innerHTML = '';
                        
                        // Root button
                        const rootBtn = document.createElement('button');
                        rootBtn.textContent = 'ðŸŒ²';
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
                        if (isMobileViewport()) {{
                            sidebar.classList.remove('hidden');
                            mainContent.classList.add('fullwidth');
                            sidebar.classList.toggle('mobile-open');
                            if (sidebarBackdrop) {{
                                sidebarBackdrop.classList.toggle('show', sidebar.classList.contains('mobile-open'));
                            }}
                            updateSidebarToggleIcon();
                            return;
                        }}

                        sidebar.classList.toggle('hidden');
                        mainContent.classList.toggle('fullwidth');
                        updateSidebarToggleIcon();
                    }});

                    if (sidebarBackdrop) {{
                        sidebarBackdrop.addEventListener('click', () => {{
                            closeMobileSidebar();
                        }});
                    }}

                    window.addEventListener('resize', () => {{
                        applyResponsiveLayout(false);
                    }});

                    document.addEventListener('dragenter', (e) => {{
                        if (!uploadsEnabled) return;
                        if (!isExternalFilesDrag(e)) return;
                        e.preventDefault();
                        dragCounter += 1;
                        dropOverlay.classList.add('show');
                    }});

                    document.addEventListener('dragover', (e) => {{
                        if (!uploadsEnabled) return;
                        if (!isExternalFilesDrag(e)) return;
                        e.preventDefault();
                    }});

                    document.addEventListener('dragleave', (e) => {{
                        if (!uploadsEnabled) return;
                        if (!isExternalFilesDrag(e)) return;
                        e.preventDefault();
                        dragCounter = Math.max(0, dragCounter - 1);
                        if (dragCounter === 0) dropOverlay.classList.remove('show');
                    }});

                    document.addEventListener('drop', async (e) => {{
                        if (!uploadsEnabled) return;
                        if (!isExternalFilesDrag(e)) return;
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
                        const manageBtn = document.getElementById('manage-btn');
                        const bulkManagement = document.getElementById('bulk-management');
                        uploadBtn.style.display = 'none';
                        mkdirBtn.style.display = 'none';
                        manageBtn.style.display = 'none';
                        bulkManagement.style.display = 'none';
                    }}

                    if (!downloadsEnabled) {{
                        const bulkActions = document.getElementById('bulk-actions');
                        bulkActions.style.display = 'none';
                    }}

                    if (uploadsEnabled) {{
                        setManageMode(false);
                    }}
                    
                    applyResponsiveLayout(true);

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

import hashlib
import json
import mimetypes
import os
import shutil
import tempfile
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, unquote, urlparse
from zipfile import ZipFile



@dataclass
class ServerContext:
    upload_folder: str
    upload_root: str
    allow_uploads: bool
    allow_downloads: bool
    max_upload_bytes: int
    stream_chunk_size: int
    resolve_client_path_fn: callable
    to_web_path_fn: callable
    is_target_allowed_fn: callable
    is_path_visible_fn: callable
    get_folder_contents_fn: callable
    build_folder_tree_fn: callable
    collect_files_for_paths_fn: callable
    allow_new_path_for_session_fn: callable
    remove_allowed_paths_under_fn: callable
    move_allowed_paths_fn: callable
    is_likely_text_file_fn: callable


def send_json(handler: BaseHTTPRequestHandler, status_code, payload):
    handler.send_response(status_code)
    handler.send_header("Content-type", "application/json")
    handler.end_headers()
    handler.wfile.write(json.dumps(payload).encode("utf-8"))


def stream_download(handler: BaseHTTPRequestHandler, file_path, download_name, ctx: ServerContext, task_id=None, hash_requested=False):
    file_size = os.path.getsize(file_path)
    if task_id:
        update_task_progress(task_id, bytes_done=0, total_bytes=file_size, phase="downloading", message="Downloading")

    hasher = hashlib.sha256() if hash_requested else None

    try:
        content_type = mimetypes.guess_type(download_name)[0] or "application/octet-stream"
        handler.send_response(200)
        handler.send_header("Content-Disposition", f"attachment; filename=\"{download_name}\"")
        handler.send_header("Content-type", content_type)
        handler.send_header("Content-Length", str(file_size))
        handler.end_headers()

        bytes_sent = 0
        with open(file_path, "rb") as file_obj:
            while True:
                chunk = file_obj.read(ctx.stream_chunk_size)
                if not chunk:
                    break
                handler.wfile.write(chunk)
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
            handler.send_error(500, f"Error: {e}")


def stream_inline_media(handler: BaseHTTPRequestHandler, file_path, mime_type, chunk_size):
    file_size = os.path.getsize(file_path)
    range_header = handler.headers.get("Range")
    start = 0
    end = max(file_size - 1, 0)
    status_code = 200

    if range_header and range_header.startswith("bytes="):
        try:
            range_spec = range_header.split("=", 1)[1].strip()
            if "," in range_spec:
                raise ValueError("Multiple ranges not supported")

            start_str, end_str = range_spec.split("-", 1)
            if start_str:
                start = int(start_str)
                end = int(end_str) if end_str else end
            else:
                suffix_len = int(end_str)
                if suffix_len <= 0:
                    raise ValueError("Invalid suffix range")
                start = max(file_size - suffix_len, 0)

            if start < 0 or end < start or start >= file_size:
                raise ValueError("Invalid byte range")
            end = min(end, file_size - 1)
            status_code = 206
        except Exception:
            handler.send_response(416)
            handler.send_header("Content-Range", f"bytes */{file_size}")
            handler.send_header("Accept-Ranges", "bytes")
            handler.end_headers()
            return

    content_length = (end - start) + 1 if file_size > 0 else 0

    handler.send_response(status_code)
    handler.send_header("Content-type", mime_type)
    handler.send_header("Accept-Ranges", "bytes")
    handler.send_header("Content-Disposition", f"inline; filename=\"{os.path.basename(file_path)}\"")
    handler.send_header("Content-Length", str(content_length))
    if status_code == 206:
        handler.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
    handler.end_headers()

    with open(file_path, "rb") as file_obj:
        if start:
            file_obj.seek(start)
        remaining = content_length
        while remaining > 0:
            chunk = file_obj.read(min(chunk_size, remaining))
            if not chunk:
                break
            handler.wfile.write(chunk)
            remaining -= len(chunk)


def handle_get_request(handler: BaseHTTPRequestHandler, ctx: ServerContext):
    path = handler.path

    if path == "/folder-tree":
        send_json(handler, 200, ctx.build_folder_tree_fn())
        return True

    if path.startswith("/task/new"):
        parsed = urlparse(path)
        kind = parse_qs(parsed.query).get("kind", ["generic"])[0]
        task_id = create_task(kind, f"{kind.capitalize()} started")
        send_json(handler, 200, {"task_id": task_id})
        return True

    if path.startswith("/progress"):
        parsed = urlparse(path)
        task_id = parse_qs(parsed.query).get("task_id", [""])[0]
        task = get_task(task_id)
        if not task:
            send_json(handler, 404, {"error": "Task not found"})
            return True
        send_json(handler, 200, task)
        return True

    if path.startswith("/files-metadata"):
        parsed = urlparse(path)
        raw_path = parse_qs(parsed.query).get("path", [ctx.upload_folder])[0]
        resolved = ctx.resolve_client_path_fn(unquote(raw_path))
        if not ctx.is_path_visible_fn(resolved):
            send_json(handler, 403, {"error": "Path not allowed in restricted mode"})
            return True
        send_json(handler, 200, ctx.get_folder_contents_fn(resolved))
        return True

    if path.startswith("/view"):
        parsed = urlparse(path)
        raw_path = parse_qs(parsed.query).get("path", [""])[0]
        file_path = ctx.resolve_client_path_fn(unquote(raw_path))

        if file_path and os.path.isfile(file_path):
            if not ctx.is_target_allowed_fn(file_path):
                handler.send_error(403, "Access denied")
                return True
            if not ctx.is_likely_text_file_fn(file_path):
                handler.send_error(415, "Binary file preview is not supported")
                return True
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                handler.send_response(200)
                handler.send_header("Content-type", "text/plain; charset=utf-8")
                handler.end_headers()
                handler.wfile.write(content.encode("utf-8"))
            except Exception as e:
                handler.send_error(500, f"Error: {e}")
            return True

        handler.send_error(404, "File not found")
        return True

    if path.startswith("/image"):
        parsed = urlparse(path)
        raw_path = parse_qs(parsed.query).get("path", [""])[0]
        file_path = ctx.resolve_client_path_fn(unquote(raw_path))

        if not file_path or not os.path.isfile(file_path):
            handler.send_error(404, "File not found")
            return True
        if not ctx.is_target_allowed_fn(file_path):
            handler.send_error(403, "Access denied")
            return True

        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        if not mime_type.startswith("image/"):
            handler.send_error(415, "Image preview is only supported for image files")
            return True

        try:
            file_size = os.path.getsize(file_path)
            handler.send_response(200)
            handler.send_header("Content-type", mime_type)
            handler.send_header("Content-Length", str(file_size))
            handler.send_header("Content-Disposition", f"inline; filename=\"{os.path.basename(file_path)}\"")
            handler.end_headers()

            with open(file_path, "rb") as file_obj:
                while True:
                    chunk = file_obj.read(ctx.stream_chunk_size)
                    if not chunk:
                        break
                    handler.wfile.write(chunk)
        except Exception as e:
            handler.send_error(500, f"Error: {e}")
        return True

    if path.startswith("/video"):
        parsed = urlparse(path)
        raw_path = parse_qs(parsed.query).get("path", [""])[0]
        file_path = ctx.resolve_client_path_fn(unquote(raw_path))

        if not file_path or not os.path.isfile(file_path):
            handler.send_error(404, "File not found")
            return True
        if not ctx.is_target_allowed_fn(file_path):
            handler.send_error(403, "Access denied")
            return True

        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        if not mime_type.startswith("video/"):
            handler.send_error(415, "Video preview is only supported for video files")
            return True

        try:
            stream_inline_media(handler, file_path, mime_type, ctx.stream_chunk_size)
        except Exception as e:
            handler.send_error(500, f"Error: {e}")
        return True

    if path.startswith("/audio"):
        parsed = urlparse(path)
        raw_path = parse_qs(parsed.query).get("path", [""])[0]
        file_path = ctx.resolve_client_path_fn(unquote(raw_path))

        if not file_path or not os.path.isfile(file_path):
            handler.send_error(404, "File not found")
            return True
        if not ctx.is_target_allowed_fn(file_path):
            handler.send_error(403, "Access denied")
            return True

        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        if not mime_type.startswith("audio/"):
            handler.send_error(415, "Audio preview is only supported for audio files")
            return True

        try:
            stream_inline_media(handler, file_path, mime_type, ctx.stream_chunk_size)
        except Exception as e:
            handler.send_error(500, f"Error: {e}")
        return True

    if path.startswith("/pdf"):
        parsed = urlparse(path)
        raw_path = parse_qs(parsed.query).get("path", [""])[0]
        file_path = ctx.resolve_client_path_fn(unquote(raw_path))

        if not file_path or not os.path.isfile(file_path):
            handler.send_error(404, "File not found")
            return True
        if not ctx.is_target_allowed_fn(file_path):
            handler.send_error(403, "Access denied")
            return True

        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        if mime_type != "application/pdf":
            handler.send_error(415, "PDF preview is only supported for PDF files")
            return True

        try:
            stream_inline_media(handler, file_path, mime_type, ctx.stream_chunk_size)
        except Exception as e:
            handler.send_error(500, f"Error: {e}")
        return True

    if path.startswith("/docx"):
        parsed = urlparse(path)
        raw_path = parse_qs(parsed.query).get("path", [""])[0]
        file_path = ctx.resolve_client_path_fn(unquote(raw_path))

        if not file_path or not os.path.isfile(file_path):
            handler.send_error(404, "File not found")
            return True
        if not ctx.is_target_allowed_fn(file_path):
            handler.send_error(403, "Access denied")
            return True

        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        allowed = {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        }
        if mime_type not in allowed:
            handler.send_error(415, "Word preview is only supported for Word document files")
            return True

        try:
            file_size = os.path.getsize(file_path)
            handler.send_response(200)
            handler.send_header("Content-type", mime_type)
            handler.send_header("Content-Length", str(file_size))
            handler.send_header("Content-Disposition", f"inline; filename=\"{os.path.basename(file_path)}\"")
            handler.end_headers()

            with open(file_path, "rb") as file_obj:
                while True:
                    chunk = file_obj.read(ctx.stream_chunk_size)
                    if not chunk:
                        break
                    handler.wfile.write(chunk)
        except Exception as e:
            handler.send_error(500, f"Error: {e}")
        return True

    if path.startswith("/sheet"):
        parsed = urlparse(path)
        raw_path = parse_qs(parsed.query).get("path", [""])[0]
        file_path = ctx.resolve_client_path_fn(unquote(raw_path))

        if not file_path or not os.path.isfile(file_path):
            handler.send_error(404, "File not found")
            return True
        if not ctx.is_target_allowed_fn(file_path):
            handler.send_error(403, "Access denied")
            return True

        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        allowed = {
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
            "text/csv",
            "application/csv",
        }
        if mime_type not in allowed:
            handler.send_error(415, "Spreadsheet preview is only supported for sheet files")
            return True

        try:
            file_size = os.path.getsize(file_path)
            handler.send_response(200)
            handler.send_header("Content-type", mime_type)
            handler.send_header("Content-Length", str(file_size))
            handler.send_header("Content-Disposition", f"inline; filename=\"{os.path.basename(file_path)}\"")
            handler.end_headers()

            with open(file_path, "rb") as file_obj:
                while True:
                    chunk = file_obj.read(ctx.stream_chunk_size)
                    if not chunk:
                        break
                    handler.wfile.write(chunk)
        except Exception as e:
            handler.send_error(500, f"Error: {e}")
        return True

    if path.startswith("/download?"):
        parsed = urlparse(path)
        query = parse_qs(parsed.query)
        raw_path = query.get("path", [""])[0]
        task_id = query.get("task_id", [""])[0] or None
        hash_requested = parse_bool(query.get("hash", ["0"])[0])
        file_path = ctx.resolve_client_path_fn(unquote(raw_path))
        if not os.path.isfile(file_path):
            if task_id:
                fail_task(task_id, "File not found")
            handler.send_error(404, "File not found")
            return True
        if not ctx.is_target_allowed_fn(file_path):
            if task_id:
                fail_task(task_id, "Access denied")
            handler.send_error(403, "Access denied")
            return True
        stream_download(handler, file_path, os.path.basename(file_path), ctx, task_id=task_id, hash_requested=hash_requested)
        return True

    if path.startswith("/download/"):
        file_name = path[len("/download/"):]
        file_path = ctx.resolve_client_path_fn(f"{ctx.upload_folder}/{unquote(file_name)}")
        if os.path.isfile(file_path):
            if not ctx.is_target_allowed_fn(file_path):
                handler.send_error(403, "Access denied")
                return True
            stream_download(handler, file_path, os.path.basename(file_path), ctx, task_id=None, hash_requested=False)
        else:
            handler.send_error(404, "File not found")
        return True

    return False


def handle_post_request(handler: BaseHTTPRequestHandler, ctx: ServerContext):
    parsed = urlparse(handler.path)

    if parsed.path == "/upload-raw":
        if not ctx.allow_uploads:
            send_json(handler, 403, {"error": "Uploads are disabled in this mode"})
            return True
        _handle_upload_raw(handler, parsed, ctx)
        return True

    if parsed.path == "/zip-download":
        _handle_zip_download(handler, parsed, ctx)
        return True

    if parsed.path == "/mkdir":
        if not ctx.allow_uploads:
            send_json(handler, 403, {"error": "Folder creation is disabled because uploads are off"})
            return True
        _handle_mkdir(handler, ctx)
        return True

    if parsed.path == "/rename":
        if not ctx.allow_uploads:
            send_json(handler, 403, {"error": "Rename is disabled because uploads are off"})
            return True
        _handle_rename(handler, ctx)
        return True

    if parsed.path == "/delete":
        if not ctx.allow_uploads:
            send_json(handler, 403, {"error": "Delete is disabled because uploads are off"})
            return True
        _handle_delete(handler, ctx)
        return True

    if parsed.path == "/move":
        if not ctx.allow_uploads:
            send_json(handler, 403, {"error": "Move is disabled because uploads are off"})
            return True
        _handle_move(handler, ctx)
        return True

    if parsed.path == "/bulk-delete":
        if not ctx.allow_uploads:
            send_json(handler, 403, {"error": "Bulk delete is disabled because uploads are off"})
            return True
        _handle_bulk_delete(handler, parsed, ctx)
        return True

    if parsed.path == "/bulk-move":
        if not ctx.allow_uploads:
            send_json(handler, 403, {"error": "Bulk move is disabled because uploads are off"})
            return True
        _handle_bulk_move(handler, parsed, ctx)
        return True

    return False


def _read_json_body(handler: BaseHTTPRequestHandler):
    content_length = int(handler.headers.get("Content-Length", "0"))
    if content_length <= 0:
        return None, "Missing request body"
    try:
        payload = json.loads(handler.rfile.read(content_length).decode("utf-8"))
    except Exception:
        return None, "Invalid JSON body"
    return payload, None


def _resolve_manage_source_path(ctx: ServerContext, raw_path):
    if raw_path is None:
        return None, "Missing path"
    source_path = ctx.resolve_client_path_fn(unquote(str(raw_path)))
    if source_path == ctx.upload_root:
        return None, "Operation on root folder is not allowed"
    if not os.path.exists(source_path):
        return None, "Source path not found"
    return source_path, None


def _resolve_manage_destination_dir(ctx: ServerContext, raw_path):
    if raw_path is None:
        return None, "Missing destination"
    dest_dir = ctx.resolve_client_path_fn(unquote(str(raw_path)))
    if not os.path.isdir(dest_dir):
        return None, "Destination folder not found"
    return dest_dir, None


def _move_single_path(ctx: ServerContext, source_path, destination_dir):
    source_abs = os.path.abspath(source_path)
    dest_abs = os.path.abspath(destination_dir)

    if source_abs == ctx.upload_root:
        raise ValueError("Operation on root folder is not allowed")
    if source_abs == dest_abs:
        raise ValueError("Cannot move an item into itself")

    if os.path.isdir(source_abs) and dest_abs.startswith(source_abs + os.sep):
        raise ValueError("Cannot move a folder into its own subfolder")

    target_name = os.path.basename(source_abs)
    target_candidate = os.path.join(dest_abs, target_name)
    is_dir = os.path.isdir(source_abs)

    if os.path.exists(target_candidate):
        target_candidate = get_unique_target_path(dest_abs, target_name, is_dir)

    shutil.move(source_abs, target_candidate)
    ctx.move_allowed_paths_fn(source_abs, target_candidate)
    ctx.allow_new_path_for_session_fn(target_candidate)
    return target_candidate


def _normalize_bulk_paths(ctx: ServerContext, raw_paths):
    if not isinstance(raw_paths, list):
        return [], "paths must be an array"

    unique = []
    seen = set()
    for raw in raw_paths:
        source_path, error = _resolve_manage_source_path(ctx, raw)
        if error:
            return [], error
        source_abs = os.path.abspath(source_path)
        if source_abs in seen:
            continue
        seen.add(source_abs)
        unique.append(source_abs)

    unique.sort(key=len)
    filtered = []
    for path in unique:
        if any(path.startswith(parent + os.sep) for parent in filtered):
            continue
        filtered.append(path)
    return filtered, None


def _handle_upload_raw(handler: BaseHTTPRequestHandler, parsed_url, ctx: ServerContext):
    query = parse_qs(parsed_url.query)
    target_path = ctx.resolve_client_path_fn(unquote(query.get("path", [ctx.upload_folder])[0]))
    file_name = sanitize_filename(unquote(query.get("filename", ["upload.bin"])[0]))
    task_id = query.get("task_id", [""])[0] or create_task("upload", "Upload started")
    hash_requested = parse_bool(query.get("hash", ["0"])[0])

    if not os.path.isdir(target_path):
        send_json(handler, 400, {"error": "Target folder not found"})
        fail_task(task_id, "Target folder not found")
        return

    content_length = int(handler.headers.get("Content-Length", "0"))
    if content_length <= 0:
        send_json(handler, 400, {"error": "Empty upload payload"})
        fail_task(task_id, "Empty upload payload")
        return

    if content_length > ctx.max_upload_bytes:
        send_json(handler, 413, {"error": "Upload too large"})
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
                read_size = min(ctx.stream_chunk_size, remaining)
                chunk = handler.rfile.read(read_size)
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
        ctx.allow_new_path_for_session_fn(file_path)
        send_json(
            handler,
            200,
            {
                "ok": True,
                "task_id": task_id,
                "name": os.path.basename(file_path),
                "path": ctx.to_web_path_fn(file_path),
                "size": bytes_written,
                "sha256": digest,
            },
        )
    except Exception as e:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        fail_task(task_id, str(e))
        send_json(handler, 500, {"error": str(e), "task_id": task_id})


def _handle_zip_download(handler: BaseHTTPRequestHandler, parsed_url, ctx: ServerContext):
    content_length = int(handler.headers.get("Content-Length", "0"))
    if content_length <= 0:
        send_json(handler, 400, {"error": "Missing request body"})
        return

    try:
        payload = json.loads(handler.rfile.read(content_length).decode("utf-8"))
    except Exception:
        send_json(handler, 400, {"error": "Invalid JSON body"})
        return

    task_id = parse_qs(parsed_url.query).get("task_id", [""])[0] or create_task("zip", "ZIP started")
    paths = payload.get("paths") or []
    archive_name = sanitize_filename(payload.get("archive_name") or "archive.zip")
    if not archive_name.lower().endswith(".zip"):
        archive_name += ".zip"

    files = ctx.collect_files_for_paths_fn(paths)
    if not files:
        fail_task(task_id, "No valid files selected")
        send_json(handler, 400, {"error": "No valid files selected"})
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
        handler.send_response(200)
        handler.send_header("Content-Disposition", f"attachment; filename=\"{archive_name}\"")
        handler.send_header("Content-type", "application/zip")
        handler.send_header("Content-Length", str(zip_size))
        handler.end_headers()

        sent = 0
        with open(temp_zip_path, "rb") as zf:
            while True:
                chunk = zf.read(ctx.stream_chunk_size)
                if not chunk:
                    break
                handler.wfile.write(chunk)
                sent += len(chunk)
                update_task_progress(task_id, bytes_done=sent, total_bytes=zip_size, phase="downloading", message="Downloading ZIP")

        finish_task(task_id, message="ZIP download completed")
    except (BrokenPipeError, ConnectionResetError):
        fail_task(task_id, "Client disconnected")
    except Exception as e:
        fail_task(task_id, str(e))
        if not handler.wfile.closed:
            send_json(handler, 500, {"error": str(e)})
    finally:
        if temp_zip_path and os.path.exists(temp_zip_path):
            try:
                os.remove(temp_zip_path)
            except OSError:
                pass


def _handle_mkdir(handler: BaseHTTPRequestHandler, ctx: ServerContext):
    payload, error = _read_json_body(handler)
    if error:
        send_json(handler, 400, {"error": error})
        return

    target_path = ctx.resolve_client_path_fn(unquote(payload.get("path", ctx.upload_folder)))
    if not os.path.isdir(target_path):
        send_json(handler, 400, {"error": "Target folder not found"})
        return

    folder_name = sanitize_folder_name(payload.get("name", ""))
    if not folder_name:
        send_json(handler, 400, {"error": "Invalid folder name"})
        return

    new_dir = get_unique_dir_path(target_path, folder_name)
    try:
        os.makedirs(new_dir, exist_ok=False)
    except OSError as e:
        send_json(handler, 500, {"error": str(e)})
        return

    ctx.allow_new_path_for_session_fn(new_dir)
    send_json(handler, 200, {"ok": True, "name": os.path.basename(new_dir), "path": ctx.to_web_path_fn(new_dir)})


def _handle_rename(handler: BaseHTTPRequestHandler, ctx: ServerContext):
    payload, error = _read_json_body(handler)
    if error:
        send_json(handler, 400, {"error": error})
        return

    source_path, error = _resolve_manage_source_path(ctx, payload.get("path"))
    if error:
        send_json(handler, 400, {"error": error})
        return

    is_dir = os.path.isdir(source_path)
    new_name = sanitize_entry_name(payload.get("new_name"), is_dir=is_dir)
    if not new_name:
        send_json(handler, 400, {"error": "Invalid new name"})
        return

    source_abs = os.path.abspath(source_path)
    source_parent = os.path.dirname(source_abs)
    target_path = os.path.abspath(os.path.join(source_parent, new_name))

    if target_path == source_abs:
        send_json(handler, 200, {"ok": True, "name": os.path.basename(source_abs), "path": ctx.to_web_path_fn(source_abs)})
        return

    if target_path == ctx.upload_root or not target_path.startswith(ctx.upload_root + os.sep):
        send_json(handler, 400, {"error": "Invalid rename target"})
        return

    if os.path.exists(target_path):
        target_path = get_unique_target_path(source_parent, new_name, is_dir)

    try:
        os.rename(source_abs, target_path)
        ctx.move_allowed_paths_fn(source_abs, target_path)
        ctx.allow_new_path_for_session_fn(target_path)
    except OSError as e:
        send_json(handler, 500, {"error": str(e)})
        return

    send_json(handler, 200, {"ok": True, "name": os.path.basename(target_path), "path": ctx.to_web_path_fn(target_path)})


def _handle_delete(handler: BaseHTTPRequestHandler, ctx: ServerContext):
    payload, error = _read_json_body(handler)
    if error:
        send_json(handler, 400, {"error": error})
        return

    source_path, error = _resolve_manage_source_path(ctx, payload.get("path"))
    if error:
        send_json(handler, 400, {"error": error})
        return

    source_abs = os.path.abspath(source_path)
    try:
        if os.path.isdir(source_abs):
            shutil.rmtree(source_abs)
        else:
            os.remove(source_abs)
        ctx.remove_allowed_paths_under_fn(source_abs)
    except OSError as e:
        send_json(handler, 500, {"error": str(e)})
        return

    send_json(handler, 200, {"ok": True})


def _handle_move(handler: BaseHTTPRequestHandler, ctx: ServerContext):
    payload, error = _read_json_body(handler)
    if error:
        send_json(handler, 400, {"error": error})
        return

    source_path, error = _resolve_manage_source_path(ctx, payload.get("path"))
    if error:
        send_json(handler, 400, {"error": error})
        return

    destination_dir, error = _resolve_manage_destination_dir(ctx, payload.get("destination"))
    if error:
        send_json(handler, 400, {"error": error})
        return

    try:
        target_path = _move_single_path(ctx, source_path, destination_dir)
    except ValueError as e:
        send_json(handler, 400, {"error": str(e)})
        return
    except OSError as e:
        send_json(handler, 500, {"error": str(e)})
        return

    send_json(handler, 200, {"ok": True, "name": os.path.basename(target_path), "path": ctx.to_web_path_fn(target_path)})


def _handle_bulk_delete(handler: BaseHTTPRequestHandler, parsed_url, ctx: ServerContext):
    payload, error = _read_json_body(handler)
    if error:
        send_json(handler, 400, {"error": error})
        return

    paths, error = _normalize_bulk_paths(ctx, payload.get("paths", []))
    if error:
        send_json(handler, 400, {"error": error})
        return
    if not paths:
        send_json(handler, 400, {"error": "No valid paths selected"})
        return

    task_id = parse_qs(parsed_url.query).get("task_id", [""])[0] or create_task("bulk-delete", "Bulk delete started")
    total_units = sum(count_path_units(path) for path in paths)
    total_units = max(total_units, len(paths))
    done_units = 0
    deleted_count = 0

    update_task_progress(task_id, bytes_done=0, total_bytes=total_units, phase="deleting", message="Deleting items")

    try:
        for path in paths:
            units = max(count_path_units(path), 1)
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            ctx.remove_allowed_paths_under_fn(path)
            done_units += units
            deleted_count += 1
            update_task_progress(task_id, bytes_done=done_units, total_bytes=total_units, phase="deleting", message=f"Deleted {deleted_count}/{len(paths)}")
    except OSError as e:
        fail_task(task_id, str(e))
        send_json(handler, 500, {"error": str(e), "task_id": task_id})
        return

    finish_task(task_id, message=f"Deleted {deleted_count} item(s)")
    send_json(handler, 200, {"ok": True, "task_id": task_id, "deleted": deleted_count})


def _handle_bulk_move(handler: BaseHTTPRequestHandler, parsed_url, ctx: ServerContext):
    payload, error = _read_json_body(handler)
    if error:
        send_json(handler, 400, {"error": error})
        return

    paths, error = _normalize_bulk_paths(ctx, payload.get("paths", []))
    if error:
        send_json(handler, 400, {"error": error})
        return
    if not paths:
        send_json(handler, 400, {"error": "No valid paths selected"})
        return

    destination_dir, error = _resolve_manage_destination_dir(ctx, payload.get("destination"))
    if error:
        send_json(handler, 400, {"error": error})
        return

    task_id = parse_qs(parsed_url.query).get("task_id", [""])[0] or create_task("bulk-move", "Bulk move started")
    total_units = sum(count_path_units(path) for path in paths)
    total_units = max(total_units, len(paths))
    done_units = 0
    moved_items = []

    update_task_progress(task_id, bytes_done=0, total_bytes=total_units, phase="moving", message="Moving items")

    try:
        for path in paths:
            units = max(count_path_units(path), 1)
            target_path = _move_single_path(ctx, path, destination_dir)
            moved_items.append({"name": os.path.basename(target_path), "path": ctx.to_web_path_fn(target_path)})
            done_units += units
            update_task_progress(task_id, bytes_done=done_units, total_bytes=total_units, phase="moving", message=f"Moved {len(moved_items)}/{len(paths)}")
    except ValueError as e:
        fail_task(task_id, str(e))
        send_json(handler, 400, {"error": str(e), "task_id": task_id})
        return
    except OSError as e:
        fail_task(task_id, str(e))
        send_json(handler, 500, {"error": str(e), "task_id": task_id})
        return

    finish_task(task_id, message=f"Moved {len(moved_items)} item(s)")
    send_json(handler, 200, {"ok": True, "task_id": task_id, "moved": len(moved_items), "items": moved_items})

import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


UPLOAD_FOLDER = "shared_files"
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(MODULE_DIR, ".."))
WORKSPACE_UPLOAD_ROOT = os.path.abspath(os.path.join(PROJECT_ROOT, UPLOAD_FOLDER))
LEGACY_UPLOAD_ROOT = os.path.abspath(os.path.join(MODULE_DIR, UPLOAD_FOLDER))
UPLOAD_ROOT = WORKSPACE_UPLOAD_ROOT if os.path.isdir(WORKSPACE_UPLOAD_ROOT) else LEGACY_UPLOAD_ROOT
FAVICON_CANDIDATES = [
    os.path.abspath(os.path.join(PROJECT_ROOT, "Images", "favicon.ico")),
    os.path.abspath(os.path.join(MODULE_DIR, "Images", "favicon.ico")),
]
FAVICON_PATH = next((path for path in FAVICON_CANDIDATES if os.path.isfile(path)), None)

os.makedirs(UPLOAD_ROOT, exist_ok=True)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024 * 1024  # 10 GB hard safety cap
STREAM_CHUNK_SIZE = 1024 * 1024  # 1 MB

# Ask permission once at server start
ALLOW_UPLOADS = input("Give uploading permissions (Y/N): ").strip().lower() == 'y'
if ALLOW_UPLOADS:
    ALLOW_DOWNLOADS = input("Do you wanna make your files available for download? (Y/N): ").strip().lower() == 'y'
else:
    ALLOW_DOWNLOADS = True
ALLOWED_PATHS = set()


def allow_new_path_for_session(abs_path):
    """Allow newly created/uploaded items in current restricted upload session."""
    if ALLOW_UPLOADS and (not ALLOW_DOWNLOADS or ALLOWED_PATHS):
        ALLOWED_PATHS.add(os.path.abspath(abs_path))


def remove_allowed_paths_under(abs_path):
    global ALLOWED_PATHS
    if not ALLOWED_PATHS:
        return
    source = os.path.abspath(abs_path)
    prefix = source + os.sep
    ALLOWED_PATHS = {p for p in ALLOWED_PATHS if p != source and not p.startswith(prefix)}


def move_allowed_paths(old_abs_path, new_abs_path):
    global ALLOWED_PATHS
    if not ALLOWED_PATHS:
        return

    old_abs = os.path.abspath(old_abs_path)
    new_abs = os.path.abspath(new_abs_path)
    old_prefix = old_abs + os.sep
    updated = set()

    for allowed in ALLOWED_PATHS:
        if allowed == old_abs:
            updated.add(new_abs)
            continue
        if allowed.startswith(old_prefix):
            rel = os.path.relpath(allowed, old_abs)
            updated.add(os.path.abspath(os.path.join(new_abs, rel)))
            continue
        updated.add(allowed)

    ALLOWED_PATHS = updated


def app_collect_files_for_paths(client_paths):
    return core_access.collect_files_for_paths(
        client_paths=client_paths,
        upload_root=UPLOAD_ROOT,
        resolve_client_path_fn=app_resolve_client_path,
        is_target_allowed_fn=app_is_target_allowed,
    )


def app_is_target_allowed(abs_path):
    return core_access.is_target_allowed(
        abs_path=abs_path,
        allow_uploads=ALLOW_UPLOADS,
        allow_downloads=ALLOW_DOWNLOADS,
        allowed_paths=ALLOWED_PATHS,
    )


def app_is_path_visible(abs_path):
    return core_access.is_path_visible(
        abs_path=abs_path,
        upload_root=UPLOAD_ROOT,
        allow_uploads=ALLOW_UPLOADS,
        allow_downloads=ALLOW_DOWNLOADS,
        allowed_paths=ALLOWED_PATHS,
    )

def app_get_lan_ip():
    return core_access.get_lan_ip()

def app_to_web_path(abs_path):
    return core_access.to_web_path(abs_path, UPLOAD_ROOT, UPLOAD_FOLDER)

def app_resolve_client_path(raw_path=None):
    return core_access.resolve_client_path(raw_path, UPLOAD_ROOT, UPLOAD_FOLDER)


def app_list_shareable_entries():
    return core_access.list_shareable_entries(UPLOAD_ROOT)


def app_get_download_only_allowlist():
    entries = app_list_shareable_entries()
    if not entries:
        return set()
    return cli_access_selector(entries)

def app_build_folder_tree(path=None):
    if path is None:
        path = UPLOAD_ROOT
    return core_access.build_folder_tree(
        path=path,
        upload_root=UPLOAD_ROOT,
        upload_folder=UPLOAD_FOLDER,
        is_path_visible_fn=app_is_path_visible,
    )

def app_get_folder_contents(path=None):
    if path is None:
        path = UPLOAD_ROOT
    return core_access.get_folder_contents(
        path=path,
        upload_root=UPLOAD_ROOT,
        upload_folder=UPLOAD_FOLDER,
        is_path_visible_fn=app_is_path_visible,
        is_likely_text_file_fn=is_likely_text_file,
        is_image_file_fn=is_image_file,
        is_video_file_fn=is_video_file,
        is_audio_file_fn=is_audio_file,
        is_pdf_file_fn=is_pdf_file,
        is_word_file_fn=is_word_file,
        is_sheet_file_fn=is_sheet_file,
    )


SERVER_CTX = ServerContext(
    upload_folder=UPLOAD_FOLDER,
    upload_root=UPLOAD_ROOT,
    allow_uploads=ALLOW_UPLOADS,
    allow_downloads=ALLOW_DOWNLOADS,
    max_upload_bytes=MAX_UPLOAD_BYTES,
    stream_chunk_size=STREAM_CHUNK_SIZE,
    resolve_client_path_fn=app_resolve_client_path,
    to_web_path_fn=app_to_web_path,
    is_target_allowed_fn=app_is_target_allowed,
    is_path_visible_fn=app_is_path_visible,
    get_folder_contents_fn=app_get_folder_contents,
    build_folder_tree_fn=app_build_folder_tree,
    collect_files_for_paths_fn=app_collect_files_for_paths,
    allow_new_path_for_session_fn=allow_new_path_for_session,
    remove_allowed_paths_under_fn=remove_allowed_paths_under,
    move_allowed_paths_fn=move_allowed_paths,
    is_likely_text_file_fn=is_likely_text_file,
)


class CustomHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/favicon.ico"):
            if not FAVICON_PATH:
                self.send_error(404, "Favicon not found")
                return

            try:
                with open(FAVICON_PATH, "rb") as icon_file:
                    icon_bytes = icon_file.read()
                self.send_response(200)
                self.send_header("Content-type", "image/x-icon")
                self.send_header("Content-Length", str(len(icon_bytes)))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                self.wfile.write(icon_bytes)
            except OSError:
                self.send_error(500, "Unable to load favicon")
            return

        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            
            html = render_index_html(
                UPLOAD_FOLDER,
                ALLOW_UPLOADS,
                ALLOW_DOWNLOADS,
                ALLOWED_PATHS,
            )
            self.wfile.write(html.encode("utf-8"))
        else:
            if not handle_get_request(self, SERVER_CTX):
                self.send_error(404, "Not Found")

    def do_POST(self):
        if not handle_post_request(self, SERVER_CTX):
            self.send_error(404, "Not Found")


def main():
    global ALLOWED_PATHS
    print("=== HTTP File Sharing Server ===")
    print(f"[i] Share root: {UPLOAD_ROOT}")

    should_select_downloads = not ALLOW_UPLOADS or (ALLOW_UPLOADS and ALLOW_DOWNLOADS)

    if should_select_downloads:
        if ALLOW_UPLOADS:
            print("[i] Select files/folders clients can download.")
        else:
            print("[i] Download-only mode: select files/folders clients can access.")
        selected = app_get_download_only_allowlist()
        if not selected:
            print("[-] No items selected. Server not started.")
            return
        ALLOWED_PATHS = {os.path.abspath(p) for p in selected}
        print(f"[+] Download access set with {len(ALLOWED_PATHS)} selected items.")
    elif ALLOW_UPLOADS and not ALLOW_DOWNLOADS:
        print("[i] Downloads disabled. Server will start with no files available for download.")

    server_ip = app_get_lan_ip()
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

