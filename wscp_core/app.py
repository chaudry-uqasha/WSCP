import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from wscp_core.fs_utils import (
    is_audio_file,
    is_image_file,
    is_likely_text_file,
    is_pdf_file,
    is_sheet_file,
    is_video_file,
    is_word_file,
)
from wscp_core import access as core_access
from wscp_core.selector import cli_access_selector
from wscp_core.http_routes import ServerContext, handle_get_request, handle_post_request
from wscp_core.web_ui import render_index_html

UPLOAD_FOLDER = "shared_files"
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(MODULE_DIR, ".."))
WORKSPACE_UPLOAD_ROOT = os.path.abspath(os.path.join(PROJECT_ROOT, UPLOAD_FOLDER))
LEGACY_UPLOAD_ROOT = os.path.abspath(os.path.join(MODULE_DIR, UPLOAD_FOLDER))
UPLOAD_ROOT = WORKSPACE_UPLOAD_ROOT if os.path.isdir(WORKSPACE_UPLOAD_ROOT) else LEGACY_UPLOAD_ROOT

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


def collect_files_for_paths(client_paths):
    return core_access.collect_files_for_paths(
        client_paths=client_paths,
        upload_root=UPLOAD_ROOT,
        resolve_client_path_fn=resolve_client_path,
        is_target_allowed_fn=is_target_allowed,
    )


def is_target_allowed(abs_path):
    return core_access.is_target_allowed(
        abs_path=abs_path,
        allow_uploads=ALLOW_UPLOADS,
        allow_downloads=ALLOW_DOWNLOADS,
        allowed_paths=ALLOWED_PATHS,
    )


def is_path_visible(abs_path):
    return core_access.is_path_visible(
        abs_path=abs_path,
        upload_root=UPLOAD_ROOT,
        allow_uploads=ALLOW_UPLOADS,
        allow_downloads=ALLOW_DOWNLOADS,
        allowed_paths=ALLOWED_PATHS,
    )

def get_lan_ip():
    return core_access.get_lan_ip()

def to_web_path(abs_path):
    return core_access.to_web_path(abs_path, UPLOAD_ROOT, UPLOAD_FOLDER)

def resolve_client_path(raw_path=None):
    return core_access.resolve_client_path(raw_path, UPLOAD_ROOT, UPLOAD_FOLDER)


def list_shareable_entries():
    return core_access.list_shareable_entries(UPLOAD_ROOT)


def get_download_only_allowlist():
    entries = list_shareable_entries()
    if not entries:
        return set()
    return cli_access_selector(entries)

def build_folder_tree(path=None):
    if path is None:
        path = UPLOAD_ROOT
    return core_access.build_folder_tree(
        path=path,
        upload_root=UPLOAD_ROOT,
        upload_folder=UPLOAD_FOLDER,
        is_path_visible_fn=is_path_visible,
    )

def get_folder_contents(path=None):
    if path is None:
        path = UPLOAD_ROOT
    return core_access.get_folder_contents(
        path=path,
        upload_root=UPLOAD_ROOT,
        upload_folder=UPLOAD_FOLDER,
        is_path_visible_fn=is_path_visible,
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
    resolve_client_path_fn=resolve_client_path,
    to_web_path_fn=to_web_path,
    is_target_allowed_fn=is_target_allowed,
    is_path_visible_fn=is_path_visible,
    get_folder_contents_fn=get_folder_contents,
    build_folder_tree_fn=build_folder_tree,
    collect_files_for_paths_fn=collect_files_for_paths,
    allow_new_path_for_session_fn=allow_new_path_for_session,
    remove_allowed_paths_under_fn=remove_allowed_paths_under,
    move_allowed_paths_fn=move_allowed_paths,
    is_likely_text_file_fn=is_likely_text_file,
)


class CustomHandler(BaseHTTPRequestHandler):
    def do_GET(self):
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
    print("=== 🎉 HTTP File Sharing Server ===")
    print(f"[i] Share root: {UPLOAD_ROOT}")

    should_select_downloads = not ALLOW_UPLOADS or (ALLOW_UPLOADS and ALLOW_DOWNLOADS)

    if should_select_downloads:
        if ALLOW_UPLOADS:
            print("[i] Select files/folders clients can download.")
        else:
            print("[i] Download-only mode: select files/folders clients can access.")
        selected = get_download_only_allowlist()
        if not selected:
            print("[-] No items selected. Server not started.")
            return
        ALLOWED_PATHS = {os.path.abspath(p) for p in selected}
        print(f"[+] Download access set with {len(ALLOWED_PATHS)} selected items.")
    elif ALLOW_UPLOADS and not ALLOW_DOWNLOADS:
        print("[i] Downloads disabled. Server will start with no files available for download.")

    server_ip = get_lan_ip()
    port = 8000

    httpd = ThreadingHTTPServer(("0.0.0.0", port), CustomHandler)
    print(f"[+] Server running at http://{server_ip}:{port}")
    print("[+] Share this link with others in your LAN.")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[-] Server stopped.")

