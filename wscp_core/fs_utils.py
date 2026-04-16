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
