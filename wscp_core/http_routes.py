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

from wscp_core.fs_utils import (
    count_path_units,
    get_unique_dir_path,
    get_unique_file_path,
    get_unique_target_path,
    parse_bool,
    sanitize_entry_name,
    sanitize_filename,
    sanitize_folder_name,
)
from wscp_core.tasks import (
    create_task,
    fail_task,
    finish_task,
    get_task,
    update_task_progress,
)


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
