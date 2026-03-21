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
