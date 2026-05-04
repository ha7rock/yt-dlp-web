#!/usr/bin/env python3
"""Flask LAN web UI for yt-dlp downloads with SSE progress."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import shlex
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Generator
from urllib.parse import quote, unquote, urlparse

from flask import Flask, Response, jsonify, request, send_file, send_from_directory, stream_with_context

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
JOBS: dict[str, "Job"] = {}
JOBS_LOCK = threading.Lock()

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="")


@dataclass
class Job:
    id: str
    url: str
    output_dir: str
    command: list[str]
    status: str = "queued"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    returncode: int | None = None
    log: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    title: str = ""
    thumbnail_url: str = ""
    uploader: str = ""
    quality: str = ""
    format: str = ""
    proc: subprocess.Popen | None = field(default=None, repr=False, compare=False)
    cancel_requested: bool = False
    progress: dict[str, Any] = field(default_factory=lambda: {
        "stage": "queued",
        "percent": 0.0,
        "speed": "",
        "eta": "",
        "label": "等待中",
        "status": "queued",
    })

    def append_log(self, line: str) -> None:
        self.updated_at = time.time()
        self.log.append(line.rstrip())
        if len(self.log) > 500:
            self.log = self.log[-500:]

    def handle_output_line(self, line: str) -> None:
        progress = parse_progress_line(line)
        if progress:
            self.progress.update(progress)
            self.progress["status"] = self.status
            self.updated_at = time.time()
        else:
            self.append_log(line)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.id,
            "url": self.url,
            "output_dir": self.output_dir,
            "command": self.command,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "returncode": self.returncode,
            "log": self.log,
            "files": self.files,
            "title": self.title,
            "thumbnail_url": self.thumbnail_url,
            "uploader": self.uploader,
            "quality": self.quality,
            "format": self.format,
            "progress": self.progress,
        }

    def event_payload(self) -> dict[str, Any]:
        filename = Path(self.files[0]).name if self.files else ""
        data = {
            "task_id": self.id,
            "url": self.url,
            "status": self.status,
            "filename": filename,
            "title": self.title or filename,
            "thumbnail_url": self.thumbnail_url,
            "uploader": self.uploader,
            "quality": self.quality,
            "format": self.format,
            **self.progress,
        }
        data["status"] = self.status
        return data


def safe_job_id() -> str:
    return uuid.uuid4().hex[:12]


_PROGRESS_RE = re.compile(r"^\[(?P<stage>[^\]]+)\]\s+(?P<percent>\d+(?:\.\d+)?)%", re.IGNORECASE)
_SPEED_RE = re.compile(r"\bat\s+(?P<speed>\S+)", re.IGNORECASE)
_ETA_RE = re.compile(r"\bETA\s+(?P<eta>\S+)", re.IGNORECASE)


def parse_progress_line(line: str) -> dict[str, Any] | None:
    text = line.strip().replace("\r", "")
    match = _PROGRESS_RE.search(text)
    if not match:
        return None
    percent = max(0.0, min(100.0, float(match.group("percent"))))
    stage = match.group("stage") or "download"
    speed_match = _SPEED_RE.search(text)
    eta_match = _ETA_RE.search(text)
    speed = speed_match.group("speed") if speed_match else ""
    eta = eta_match.group("eta") if eta_match else ""
    label_parts = [f"{percent:.1f}%"]
    if speed:
        label_parts.append(speed)
    if eta:
        label_parts.append(f"剩余 {eta}")
    return {"stage": stage, "percent": percent, "speed": speed, "eta": eta, "label": " · ".join(label_parts)}


def _downloads_root() -> Path:
    return Path.home() / "Downloads"


def _history_path() -> Path:
    return Path.home() / ".local" / "share" / "yt-dlp-web" / "history.json"


def _load_history() -> list[dict[str, Any]]:
    path = _history_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _save_history(items: list[dict[str, Any]]) -> None:
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def media_token_for(path: str | Path) -> str:
    resolved = Path(path).expanduser().resolve()
    try:
        return str(resolved.relative_to(_downloads_root().resolve()))
    except ValueError as exc:
        raise ValueError("只能访问 Downloads 目录里的文件") from exc


def resolve_media_path(token: str) -> Path:
    token = unquote(token or "").lstrip("/")
    candidate = (_downloads_root() / token).resolve()
    root = _downloads_root().resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("非法文件路径") from exc
    if not candidate.is_file():
        raise FileNotFoundError("文件不存在")
    return candidate


def _history_item_from_file(job: Job, file_path: str | Path) -> dict[str, Any]:
    path = Path(file_path).expanduser().resolve()
    token = quote(media_token_for(path))
    stat = path.stat()
    item_id = uuid.uuid5(uuid.NAMESPACE_URL, str(path)).hex[:16]
    mime, _ = mimetypes.guess_type(path.name)
    suffix = path.suffix.lower().lstrip(".")
    return {
        "id": item_id,
        "job_id": job.id,
        "url": job.url,
        "title": job.title or path.name,
        "filename": path.name,
        "path": str(path),
        "size": stat.st_size,
        "size_human": human_size(stat.st_size),
        "mtime": stat.st_mtime,
        "date": datetime.fromtimestamp(stat.st_mtime).strftime("%Y/%m/%d"),
        "mime": mime or "application/octet-stream",
        "ext": suffix,
        "uploader": job.uploader,
        "thumbnail_url": job.thumbnail_url,
        "previewable": (mime or "").startswith(("video/", "audio/")),
        "download_url": f"/media/{token}?download=1",
        "preview_url": f"/media/{token}",
        "deleted": False,
    }


def record_history_for_job(job: Job) -> list[dict[str, Any]]:
    if job.status != "done":
        return []
    new_items = []
    for file_path in job.files:
        path = Path(file_path)
        if path.is_file():
            new_items.append(_history_item_from_file(job, path))
    if not new_items:
        return []
    items = [i for i in _load_history() if not i.get("deleted")]
    by_id = {i["id"]: i for i in items}
    for item in new_items:
        by_id[item["id"]] = item
    merged = sorted(by_id.values(), key=lambda i: i.get("mtime", 0), reverse=True)
    _save_history(merged)
    return new_items



def backfill_missing_thumbnails() -> None:
    """启动时给缺封面的历史记录补封面。"""
    items = _load_history()
    changed = False
    for item in items:
        if item.get("deleted") or item.get("thumbnail_url"):
            continue
        url = item.get("url", "")
        if not url or url in ("existing-file",):
            continue
        try:
            info = safe_probe_formats(url)
            thumb = info.get("thumbnail_url") or info.get("thumbnail") or ""
            if thumb:
                item["thumbnail_url"] = thumb
                changed = True
        except Exception:
            continue
    if changed:
        _save_history(items)


def list_history(page: int = 1, per_page: int = 10, q: str = "") -> dict[str, Any]:
    page = max(1, int(page or 1))
    per_page = max(1, min(50, int(per_page or 10)))
    needle = (q or "").lower().strip()
    existing = []
    for item in _load_history():
        if item.get("deleted"):
            continue
        path = Path(item.get("path", ""))
        if not path.is_file():
            continue
        if needle:
            haystack = " ".join(str(item.get(k, "")) for k in ("title", "filename", "url")).lower()
            if needle not in haystack:
                continue
        existing.append(item)
    existing.sort(key=lambda i: i.get("mtime", 0), reverse=True)
    start = (page - 1) * per_page
    total = len(existing)
    total_pages = max(1, (total + per_page - 1) // per_page)
    return {"page": page, "limit": per_page, "per_page": per_page, "total": total, "total_pages": total_pages, "items": existing[start:start + per_page]}


def delete_history_item(item_id: str) -> dict[str, Any]:
    items = _load_history()
    for item in items:
        if item.get("id") == item_id and not item.get("deleted"):
            path = resolve_media_path(media_token_for(item["path"]))
            path.unlink(missing_ok=True)
            item["deleted"] = True
            item["deleted_at"] = time.time()
            _save_history(items)
            return {"deleted": True, "id": item_id}
    raise FileNotFoundError("历史项不存在")


def clear_history(delete_files: bool = False) -> dict[str, Any]:
    items = _load_history()
    count = 0
    for item in items:
        if item.get("deleted"):
            continue
        if delete_files and item.get("path"):
            try:
                Path(item["path"]).unlink(missing_ok=True)
            except OSError:
                pass
        item["deleted"] = True
        item["deleted_at"] = time.time()
        count += 1
    _save_history(items)
    return {"deleted": count}


def classify_url(url: str) -> Path:
    host = (urlparse(url).hostname or "").lower()
    downloads = _downloads_root()
    if host in {"x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com", "vxtwitter.com", "fxtwitter.com"}:
        return downloads / "x-videos"
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "music.youtube.com"}:
        return downloads / "youtube-videos"
    if is_bilibili_url(url):
        return downloads / "bilibili-videos"
    return downloads / "yt-dlp-videos"


def is_bilibili_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host.endswith("bilibili.com") or host in {"b23.tv"}


def bilibili_anti_412_args(url: str) -> list[str]:
    return ["--add-header", "Origin:https://www.bilibili.com"] if is_bilibili_url(url) else []


def build_probe_command(url: str) -> list[str]:
    url = _validate_url(url)
    return ["yt-dlp", "-J", "--no-playlist", *bilibili_anti_412_args(url), url]


def normalize_input_url(raw: str) -> str:
    raw = (raw or "").strip()
    match = re.search(r"https?://[^\s\]）】>\"'，。！？；、]+", raw)
    if not match:
        return raw
    return match.group(0).rstrip(".,，。!！?？;；)）]】>")


def _validate_url(url: str) -> str:
    url = normalize_input_url(url)
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("请输入 http/https 视频链接")
    return url


def is_youtube_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "music.youtube.com"}


def ios_compatible_format(quality: str) -> str:
    quality = (quality or "best").strip()
    vres = f"[height<={int(quality)}]" if quality.isdigit() else ""
    return (
        f"bestvideo[vcodec~='^((he|a)vc|h26[45])']{vres}+bestaudio[acodec=aac]/"
        f"bestvideo[vcodec~='^((he|a)vc|h26[45])']{vres}+bestaudio[ext=m4a]/"
        f"bestvideo[ext=mp4]{vres}+bestaudio[ext=m4a]/"
        f"best[ext=mp4]{vres}"
    )


def _quality_format(base_format: str, quality: str) -> str:
    base_format = base_format or "bv*+ba/b"
    quality = (quality or "best").strip()
    if quality == "worst":
        return "worst"
    if base_format not in {"bv*+ba/b", "best", "worst"}:
        return base_format
    if not quality or quality == "best" or base_format in {"best", "worst"}:
        return base_format
    if quality.isdigit():
        q = int(quality)
        return f"bv*[height<={q}]+ba/b[height<={q}]"
    return base_format


def _resolve_output_dir(url: str, options: dict[str, Any]) -> Path:
    raw = str(options.get("output_path") or "").strip()
    if not raw:
        return classify_url(url)
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = _downloads_root() / path
    path = path.resolve()
    # Keep local personal tool constrained to HOME/Downloads-ish paths.
    try:
        path.relative_to(Path.home().resolve())
    except ValueError as exc:
        raise ValueError("保存路径必须在用户 home 目录下") from exc
    return path


def build_yt_dlp_command(options: dict[str, Any]) -> tuple[list[str], Path]:
    url = _validate_url(str(options.get("url", "")))
    output_dir = _resolve_output_dir(url, options)
    output_tpl_value = str(options.get("filename_tmpl") or "").strip() or "%(title).200B [%(id)s].%(ext)s"
    output_tpl = str(output_dir / output_tpl_value)

    cmd = ["yt-dlp", url, "--newline", *bilibili_anti_412_args(url), "-P", str(output_dir), "-o", output_tpl]
    cmd.append("--yes-playlist" if options.get("playlist") else "--no-playlist")

    audio_only = bool(options.get("audio_only"))
    if audio_only:
        cmd.extend(["-x", "--audio-format", str(options.get("audio_format") or "mp3")])
    else:
        raw_format = str(options.get("format") or "bv*+ba/b")
        container_formats = {"mp4", "mkv", "webm", "mov"}
        merge_format = str(options.get("merge_output_format") or "").strip()
        base_format = "bv*+ba/b" if raw_format in container_formats else raw_format
        if not merge_format and raw_format in container_formats:
            merge_format = raw_format
        if (options.get("ios_compatible") or options.get("ios_compat")) and is_youtube_url(url):
            fmt = ios_compatible_format(str(options.get("quality") or "best"))
        else:
            fmt = _quality_format(base_format, str(options.get("quality") or "best"))
        if fmt:
            cmd.extend(["-f", fmt])
        if merge_format:
            cmd.extend(["--merge-output-format", merge_format])

    if options.get("write_subs"):
        cmd.append("--write-subs")
    if options.get("write_auto_subs"):
        cmd.append("--write-auto-subs")
    sub_langs = str(options.get("sub_langs") or "").strip()
    if sub_langs:
        cmd.extend(["--sub-langs", sub_langs])
    if options.get("embed_subs"):
        cmd.append("--embed-subs")
    if options.get("write_thumbnail"):
        cmd.append("--write-thumbnail")
    if options.get("embed_thumbnail"):
        cmd.append("--embed-thumbnail")
    proxy = str(options.get("proxy") or "").strip()
    if proxy:
        cmd.extend(["--proxy", proxy])
    cookies_file = str(options.get("cookies_file") or "").strip()
    if cookies_file:
        cmd.extend(["--cookies", str(Path(cookies_file).expanduser())])
    if options.get("cookies_from_browser"):
        cmd.extend(["--cookies-from-browser", str(options.get("browser") or "chrome")])
    if options.get("embed_metadata"):
        cmd.append("--embed-metadata")
    extra_args = str(options.get("extra_args") or "").strip()
    if extra_args:
        cmd.extend(shlex.split(extra_args))
    return cmd, output_dir


def human_size(n: int | float | None) -> str:
    if not n:
        return ""
    units = ["B", "KB", "MB", "GB", "TB"]
    x = float(n)
    i = 0
    while x >= 1024 and i < len(units) - 1:
        x /= 1024
        i += 1
    return f"{x:.1f} {units[i]}" if i else f"{int(x)} {units[i]}"


def probe_formats(url: str) -> dict[str, Any]:
    url = _validate_url(url)
    proc = subprocess.run(build_probe_command(url), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "yt-dlp 获取信息失败")
    data = json.loads(proc.stdout)
    return info_payload_from_yt_dlp(data)


def info_payload_from_yt_dlp(data: dict[str, Any]) -> dict[str, Any]:
    filesize = data.get("filesize") or data.get("filesize_approx")
    return {
        "title": data.get("title"),
        "thumbnail_url": data.get("thumbnail"),
        "thumbnail": data.get("thumbnail"),
        "uploader": data.get("uploader") or data.get("channel"),
        "upload_date": data.get("upload_date"),
        "filesize_approx": human_size(filesize),
        "filesize": filesize,
        "extractor": data.get("extractor"),
        "duration": data.get("duration"),
    }


def safe_probe_formats(url: str) -> dict[str, Any]:
    try:
        return probe_formats(url)
    except Exception:
        return {}


def video_codec_tag(path: str | Path) -> tuple[str, str] | None:
    path = Path(path)
    if path.suffix.lower() != ".mp4":
        return None
    proc = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,codec_tag_string", "-of", "json", str(path)
    ], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    if proc.returncode != 0:
        return None
    streams = json.loads(proc.stdout or "{}").get("streams") or []
    if not streams:
        return None
    s = streams[0]
    return str(s.get("codec_name") or ""), str(s.get("codec_tag_string") or "")


def needs_bilibili_hvc1_remux(url: str, path: str | Path) -> bool:
    return is_bilibili_url(url) and video_codec_tag(path) == ("hevc", "hev1")


def remux_hev1_to_hvc1(path: str | Path) -> Path:
    path = Path(path)
    tmp = path.with_name(f".{path.stem}.hvc1{path.suffix}")
    proc = subprocess.run(["ffmpeg", "-y", "-i", str(path), "-c:v", "copy", "-c:a", "copy", "-tag:v", "hvc1", str(tmp)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
    if proc.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(proc.stderr.strip() or "ffmpeg hvc1 remux failed")
    tmp.replace(path)
    return path


def postprocess_downloaded_files(job: Job) -> None:
    if not is_bilibili_url(job.url):
        return
    for file_path in list(job.files):
        path = Path(file_path)
        if path.is_file() and needs_bilibili_hvc1_remux(job.url, path):
            job.append_log(f"[postprocess] B站 HEVC hev1 → hvc1: {path.name}")
            remux_hev1_to_hvc1(path)


def _snapshot_files(output_dir: Path) -> set[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    return {p for p in output_dir.glob("*") if p.is_file()}


def run_job(job_id: str) -> None:
    with JOBS_LOCK:
        job = JOBS[job_id]
    output_dir = Path(job.output_dir)
    before = _snapshot_files(output_dir)
    job.status = "running"
    job.updated_at = time.time()
    job.progress.update({"stage": "starting", "percent": 0.0, "label": "准备下载", "status": "running"})
    job.append_log("$ " + " ".join(shlex.quote(x) for x in job.command))
    try:
        proc = subprocess.Popen(job.command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        job.proc = proc
        assert proc.stdout is not None
        for line in proc.stdout:
            job.handle_output_line(line)
        job.returncode = proc.wait()
        after = _snapshot_files(output_dir)
        new_files = sorted(after - before, key=lambda p: p.stat().st_mtime)
        job.files = [str(p) for p in new_files]
        if job.cancel_requested:
            job.status = "cancelled"
            job.progress.update({"stage": "cancelled", "label": "已取消", "status": "cancelled"})
        else:
            job.status = "done" if job.returncode == 0 else "failed"
            if job.status == "done":
                postprocess_downloaded_files(job)
                job.progress.update({"stage": "done", "percent": 100.0, "label": "完成", "status": "done"})
                record_history_for_job(job)
            else:
                job.progress.update({"stage": "failed", "label": "失败", "status": "failed"})
    except Exception as exc:
        job.returncode = -1
        job.status = "failed"
        job.progress.update({"stage": "failed", "label": "失败", "status": "failed"})
        job.append_log(f"ERROR: {exc}")
    finally:
        job.updated_at = time.time()
        job.proc = None


@app.after_request
def no_cache(resp):
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/api/info")
def api_info_get():
    return jsonify(probe_formats(request.args.get("url", "")))


@app.post("/api/info")
def api_info_post():
    payload = request.get_json(silent=True) or {}
    return jsonify(probe_formats(str(payload.get("url", ""))))


@app.post("/api/download")
def api_download():
    payload = request.get_json(silent=True) or {}
    cmd, output_dir = build_yt_dlp_command(payload)
    output_dir.mkdir(parents=True, exist_ok=True)
    url = normalize_input_url(payload.get("url", ""))
    info = safe_probe_formats(url) if not payload.get("title") or not payload.get("thumbnail_url") else {}
    job = Job(
        id=safe_job_id(), url=url, output_dir=str(output_dir), command=cmd,
        title=str(payload.get("title") or info.get("title") or ""),
        thumbnail_url=str(payload.get("thumbnail_url") or info.get("thumbnail_url") or info.get("thumbnail") or ""),
        uploader=str(payload.get("uploader") or info.get("uploader") or ""),
        quality=str(payload.get("quality") or ""), format=str(payload.get("format") or ""),
    )
    with JOBS_LOCK:
        JOBS[job.id] = job
    threading.Thread(target=run_job, args=(job.id,), daemon=True).start()
    return jsonify({"task_id": job.id, "job": job.to_dict()}), 202


@app.get("/api/jobs")
def api_jobs():
    with JOBS_LOCK:
        jobs = [j.to_dict() for j in sorted(JOBS.values(), key=lambda x: x.created_at, reverse=True)]
    return jsonify({"jobs": jobs})


@app.get("/api/progress/<task_id>")
def api_progress(task_id: str):
    def stream() -> Generator[str, None, None]:
        while True:
            with JOBS_LOCK:
                job = JOBS.get(task_id)
                data = job.event_payload() if job else {"task_id": task_id, "status": "missing", "percent": 0}
            yield "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"
            if data.get("status") in {"done", "failed", "cancelled", "missing"}:
                break
            time.sleep(0.25)
    return Response(stream_with_context(stream()), mimetype="text/event-stream")


@app.delete("/api/download/<task_id>")
def api_cancel(task_id: str):
    with JOBS_LOCK:
        job = JOBS.get(task_id)
    if not job:
        return jsonify({"error": "任务不存在"}), 404
    job.cancel_requested = True
    if job.proc and job.proc.poll() is None:
        job.proc.terminate()
    job.status = "cancelled"
    job.progress.update({"status": "cancelled", "label": "已取消"})
    job.updated_at = time.time()
    return jsonify({"cancelled": True, "task_id": task_id})


@app.get("/api/history")
def api_history():
    page = int(request.args.get("page", "1"))
    limit = int(request.args.get("limit") or request.args.get("per_page") or "7")
    q = request.args.get("q", "")
    return jsonify(list_history(page=page, per_page=limit, q=q))


@app.delete("/api/history/<item_id>")
def api_history_delete(item_id: str):
    return jsonify(delete_history_item(item_id))


@app.delete("/api/history")
def api_history_clear():
    return jsonify(clear_history(delete_files=False))


@app.post("/api/history/delete")
def api_history_delete_legacy():
    payload = request.get_json(silent=True) or {}
    return jsonify(delete_history_item(str(payload.get("id", ""))))


@app.get("/media/<path:token>")
def media(token: str):
    path = resolve_media_path(token)
    return send_file(path, as_attachment=request.args.get("download") == "1", download_name=path.name)


@app.errorhandler(Exception)
def handle_error(exc: Exception):
    code = getattr(exc, "code", 400)
    return jsonify({"error": str(exc)}), code


def main() -> None:
    parser = argparse.ArgumentParser(description="Flask LAN yt-dlp web UI")
    parser.add_argument("--host", default=os.environ.get("YTDLP_WEB_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("YTDLP_WEB_PORT", "8765")))
    args = parser.parse_args()
    threading.Thread(target=backfill_missing_thumbnails, daemon=True).start()
    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
