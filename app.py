#!/usr/bin/env python3
"""Small LAN web UI for yt-dlp downloads.

No external web framework needed: stdlib HTTP server + yt-dlp subprocess.
"""

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
from dataclasses import dataclass, field, asdict
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
JOBS: dict[str, "Job"] = {}
JOBS_LOCK = threading.Lock()


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
    progress: dict[str, Any] = field(default_factory=lambda: {
        "stage": "queued",
        "percent": 0.0,
        "speed": "",
        "eta": "",
        "label": "等待中",
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
            self.updated_at = time.time()
        else:
            self.append_log(line)


def safe_job_id() -> str:
    return uuid.uuid4().hex[:12]


_PROGRESS_RE = re.compile(r"^\[(?P<stage>[^\]]+)\]\s+(?P<percent>\d+(?:\.\d+)?)%", re.IGNORECASE)
_SPEED_RE = re.compile(r"\bat\s+(?P<speed>\S+)", re.IGNORECASE)
_ETA_RE = re.compile(r"\bETA\s+(?P<eta>\S+)", re.IGNORECASE)


def parse_progress_line(line: str) -> dict[str, Any] | None:
    text = line.strip()
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
    return {
        "stage": stage,
        "percent": percent,
        "speed": speed,
        "eta": eta,
        "label": " · ".join(label_parts),
    }


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
    is_video = (mime or "").startswith("video/")
    is_audio = (mime or "").startswith("audio/")
    return {
        "id": item_id,
        "job_id": job.id,
        "url": job.url,
        "title": path.name,
        "path": str(path),
        "size": stat.st_size,
        "mtime": stat.st_mtime,
        "mime": mime or "application/octet-stream",
        "previewable": is_video or is_audio,
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


def list_history(page: int = 1, per_page: int = 10) -> dict[str, Any]:
    page = max(1, int(page or 1))
    per_page = max(1, min(50, int(per_page or 10)))
    existing = []
    for item in _load_history():
        if item.get("deleted"):
            continue
        path = Path(item.get("path", ""))
        if path.is_file():
            existing.append(item)
    existing.sort(key=lambda i: i.get("mtime", 0), reverse=True)
    start = (page - 1) * per_page
    return {
        "page": page,
        "per_page": per_page,
        "total": len(existing),
        "total_pages": (len(existing) + per_page - 1) // per_page,
        "items": existing[start:start + per_page],
    }


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
    if not is_bilibili_url(url):
        return []
    # BiliBili's playurl API currently returns HTTP 412 unless Origin is present.
    # Referer is already set by yt-dlp's BiliBili extractor; Origin is not.
    return ["--add-header", "Origin:https://www.bilibili.com"]


def build_probe_command(url: str) -> list[str]:
    url = _validate_url(url)
    return ["yt-dlp", "-J", "--no-playlist", *bilibili_anti_412_args(url), url]


def _validate_url(url: str) -> str:
    url = normalize_input_url(url)
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("请输入 http/https 视频链接")
    return url


def normalize_input_url(raw: str) -> str:
    raw = (raw or "").strip()
    match = re.search(r"https?://[^\s\]）】>\"'，。！？；、]+", raw)
    if not match:
        return raw
    return match.group(0).rstrip(".,，。!！?？;；)）]】>")


def _quality_format(base_format: str, quality: str) -> str:
    base_format = base_format or "bv*+ba/b"
    quality = (quality or "best").strip()
    # If the user chose an exact source format from yt-dlp -J, do not rewrite it.
    # Quality caps only apply to the generic best-video/best-audio presets.
    if base_format not in {"bv*+ba/b", "best", "worst"}:
        return base_format
    if not quality or quality == "best" or base_format in {"best", "worst"}:
        return base_format
    if quality.isdigit():
        q = int(quality)
        return f"bv*[height<={q}]+ba/b[height<={q}]"
    return base_format


def build_yt_dlp_command(options: dict[str, Any]) -> tuple[list[str], Path]:
    url = _validate_url(str(options.get("url", "")))
    output_dir = classify_url(url)
    output_tpl = str(output_dir / "%(title).200B [%(id)s].%(ext)s")

    cmd = ["yt-dlp", url, *bilibili_anti_412_args(url), "-P", str(output_dir), "-o", output_tpl]

    if options.get("playlist"):
        cmd.append("--yes-playlist")
    else:
        cmd.append("--no-playlist")

    if options.get("audio_only"):
        cmd.extend(["-x", "--audio-format", str(options.get("audio_format") or "mp3")])
    else:
        fmt = _quality_format(str(options.get("format") or "bv*+ba/b"), str(options.get("quality") or "best"))
        if fmt:
            cmd.extend(["-f", fmt])
        merge_format = str(options.get("merge_output_format") or "").strip()
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
    if options.get("embed_metadata"):
        cmd.append("--embed-metadata")
    if options.get("write_thumbnail"):
        cmd.append("--write-thumbnail")
    if options.get("embed_thumbnail"):
        cmd.append("--embed-thumbnail")
    if options.get("cookies_from_browser"):
        browser = str(options.get("browser") or "chrome").strip()
        cmd.extend(["--cookies-from-browser", browser])

    rate_limit = str(options.get("rate_limit") or "").strip()
    if rate_limit:
        cmd.extend(["--limit-rate", rate_limit])
    retries = str(options.get("retries") or "").strip()
    if retries:
        cmd.extend(["--retries", retries])

    extra_args = str(options.get("extra_args") or "").strip()
    if extra_args:
        cmd.extend(shlex.split(extra_args))

    return cmd, output_dir


def probe_formats(url: str) -> dict[str, Any]:
    url = _validate_url(url)
    proc = subprocess.run(
        build_probe_command(url),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=90,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "yt-dlp 获取信息失败")
    data = json.loads(proc.stdout)
    formats = []
    seen = set()
    for f in data.get("formats") or []:
        fid = f.get("format_id")
        if not fid or fid in seen:
            continue
        seen.add(fid)
        formats.append({
            "format_id": fid,
            "ext": f.get("ext"),
            "resolution": f.get("resolution") or (f"{f.get('width')}x{f.get('height')}" if f.get("height") else "audio"),
            "height": f.get("height"),
            "fps": f.get("fps"),
            "vcodec": f.get("vcodec"),
            "acodec": f.get("acodec"),
            "filesize": f.get("filesize") or f.get("filesize_approx"),
            "note": f.get("format_note"),
        })
    formats.sort(key=lambda x: ((x.get("height") or 0), str(x.get("format_id"))), reverse=True)
    return {
        "title": data.get("title"),
        "extractor": data.get("extractor"),
        "duration": data.get("duration"),
        "thumbnail": data.get("thumbnail"),
        "formats": formats,
    }


def _snapshot_files(output_dir: Path) -> set[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    return {p for p in output_dir.glob("*") if p.is_file()}


def video_codec_tag(path: str | Path) -> tuple[str, str] | None:
    path = Path(path)
    if path.suffix.lower() != ".mp4":
        return None
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,codec_tag_string",
            "-of", "json",
            str(path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    if proc.returncode != 0:
        return None
    streams = json.loads(proc.stdout or "{}").get("streams") or []
    if not streams:
        return None
    stream = streams[0]
    return str(stream.get("codec_name") or ""), str(stream.get("codec_tag_string") or "")


def needs_bilibili_hvc1_remux(url: str, path: str | Path) -> bool:
    if not is_bilibili_url(url):
        return False
    tag = video_codec_tag(path)
    return tag == ("hevc", "hev1")


def remux_hev1_to_hvc1(path: str | Path) -> Path:
    path = Path(path)
    tmp = path.with_name(f".{path.stem}.hvc1{path.suffix}")
    proc = subprocess.run(
        ["ffmpeg", "-y", "-i", str(path), "-c:v", "copy", "-c:a", "copy", "-tag:v", "hvc1", str(tmp)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=300,
    )
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
        if not path.is_file():
            continue
        if needs_bilibili_hvc1_remux(job.url, path):
            job.append_log(f"[postprocess] B站 HEVC hev1 → hvc1: {path.name}")
            remux_hev1_to_hvc1(path)


def run_job(job_id: str) -> None:
    with JOBS_LOCK:
        job = JOBS[job_id]
    output_dir = Path(job.output_dir)
    before = _snapshot_files(output_dir)
    job.status = "running"
    job.progress.update({"stage": "starting", "percent": 0.0, "label": "准备下载"})
    job.append_log("$ " + " ".join(shlex.quote(x) for x in job.command))
    try:
        proc = subprocess.Popen(
            job.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            job.handle_output_line(line)
        job.returncode = proc.wait()
        after = _snapshot_files(output_dir)
        new_files = sorted(after - before, key=lambda p: p.stat().st_mtime)
        job.files = [str(p) for p in new_files]
        job.status = "done" if job.returncode == 0 else "failed"
        if job.status == "done":
            postprocess_downloaded_files(job)
            job.progress.update({"stage": "done", "percent": 100.0, "label": "完成"})
            record_history_for_job(job)
        else:
            job.progress.update({"stage": "failed", "label": "失败"})
    except Exception as exc:  # pragma: no cover - defensive runtime path
        job.returncode = -1
        job.status = "failed"
        job.progress.update({"stage": "failed", "label": "失败"})
        job.append_log(f"ERROR: {exc}")
    finally:
        job.updated_at = time.time()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, fmt: str, *args: Any) -> None:
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def _json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        return json.loads(raw or "{}")

    def _send_file(self, path: Path, download: bool = False) -> None:
        mime, _ = mimetypes.guess_type(path.name)
        body_len = path.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", str(body_len))
        if download:
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(path.name)}")
        self.end_headers()
        with path.open("rb") as f:
            while chunk := f.read(1024 * 512):
                self.wfile.write(chunk)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/jobs"):
            with JOBS_LOCK:
                jobs = [asdict(j) for j in sorted(JOBS.values(), key=lambda x: x.created_at, reverse=True)]
            return self._json({"jobs": jobs})
        if parsed.path.startswith("/api/history"):
            qs = parse_qs(parsed.query)
            page = int(qs.get("page", ["1"])[0])
            per_page = int(qs.get("per_page", ["10"])[0])
            return self._json(list_history(page=page, per_page=per_page))
        if parsed.path.startswith("/media/"):
            token = parsed.path[len("/media/"):]
            try:
                path = resolve_media_path(token)
                qs = parse_qs(parsed.query)
                return self._send_file(path, download=qs.get("download", [""])[0] == "1")
            except Exception as exc:
                return self._json({"error": str(exc)}, 404)
        return super().do_GET()

    def do_POST(self) -> None:
        try:
            if self.path == "/api/info":
                payload = self._read_json()
                return self._json(probe_formats(str(payload.get("url", ""))))
            if self.path == "/api/download":
                payload = self._read_json()
                cmd, output_dir = build_yt_dlp_command(payload)
                output_dir.mkdir(parents=True, exist_ok=True)
                job = Job(id=safe_job_id(), url=payload["url"], output_dir=str(output_dir), command=cmd)
                with JOBS_LOCK:
                    JOBS[job.id] = job
                threading.Thread(target=run_job, args=(job.id,), daemon=True).start()
                return self._json({"job": asdict(job)}, HTTPStatus.ACCEPTED)
            if self.path == "/api/history/delete":
                payload = self._read_json()
                return self._json(delete_history_item(str(payload.get("id", ""))))
            return self._json({"error": "not found"}, 404)
        except Exception as exc:
            return self._json({"error": str(exc)}, 400)


def main() -> None:
    parser = argparse.ArgumentParser(description="LAN yt-dlp web UI")
    parser.add_argument("--host", default=os.environ.get("YTDLP_WEB_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("YTDLP_WEB_PORT", "8765")))
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"yt-dlp web listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
