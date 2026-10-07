from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from anyio import CancelScope
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.types import Receive, Scope, Send
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DOWNLOAD_DIR = Path(os.getenv("YTDLP_DOWNLOAD_DIR", BASE_DIR / "downloads"))

DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Youtube Downloader")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class DownloadFileResponse(FileResponse):
    def __init__(self, path: Path, directory: Path, **kwargs: Any) -> None:
        super().__init__(path, **kwargs)
        self.directory = directory

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            with CancelScope(shield=True):
                await run_in_threadpool(shutil.rmtree, self.directory, ignore_errors=True)


YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}


def validate_youtube_url(url: str) -> str:
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or host not in YOUTUBE_HOSTS:
        raise HTTPException(status_code=400, detail="Enter a valid YouTube URL.")
    return url.strip()


def ydl_base_options() -> dict[str, Any]:
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 30,
    }


def ydl_info_options() -> dict[str, Any]:
    return {
        **ydl_base_options(),
        "format": "all",
        "skip_download": True,
        "ignore_no_formats_error": True,
    }


def extract_info(url: str) -> dict[str, Any]:
    try:
        with YoutubeDL(ydl_info_options()) as ydl:
            return ydl.extract_info(url, download=False)
    except DownloadError as exc:
        raise HTTPException(status_code=422, detail=f"Could not retrieve video information: {exc}") from exc


def format_size(fmt: dict[str, Any]) -> str:
    size = fmt.get("filesize") or fmt.get("filesize_approx")
    if not size:
        return "unknown size"
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024
    return "unknown size"


def format_label(fmt: dict[str, Any], kind: str) -> str:
    ext = fmt.get("ext", "file")
    size = format_size(fmt)
    if kind == "audio":
        abr = fmt.get("abr")
        quality = f"{abr:.0f} kbps" if isinstance(abr, (int, float)) else "audio"
        return f"{quality} · {ext} · {size}"

    height = fmt.get("height")
    fps = fmt.get("fps")
    resolution = f"{height}p" if height else fmt.get("resolution") or "video"
    if fps and fps > 30:
        resolution = f"{resolution}{int(fps)}"
    return f"{resolution} · {ext} · {size}"


def build_format_options(info: dict[str, Any]) -> list[dict[str, Any]]:
    formats = info.get("formats") or []
    options: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    video_by_height: dict[int, dict[str, Any]] = {}
    for fmt in formats:
        if fmt.get("vcodec") == "none" or not fmt.get("height") or not fmt.get("format_id"):
            continue
        height = int(fmt.get("height") or 0)
        current = video_by_height.get(height)
        if current is None or video_rank(fmt) > video_rank(current):
            video_by_height[height] = fmt

    video_formats = [
        video_by_height[height]
        for height in sorted(video_by_height, reverse=True)
    ]

    combined_video_formats = [
        fmt for fmt in video_formats
        if fmt.get("acodec") != "none"
    ]
    video_only_formats = [
        fmt for fmt in video_formats
        if fmt.get("vcodec") != "none" and fmt.get("height") and fmt.get("format_id")
    ]

    for fmt in [*video_only_formats, *combined_video_formats]:
        format_id = str(fmt["format_id"])
        has_audio = fmt.get("acodec") != "none"
        download_format = format_id if has_audio else f"{format_id}+bestaudio[ext=m4a]/bestaudio/best"
        key = ("video", download_format)
        if key in seen:
            continue
        seen.add(key)
        options.append(
            {
                "kind": "video",
                "format_id": format_id,
                "download_format": download_format,
                "label": format_label(fmt, "video") + ("" if has_audio else " · + audio"),
                "ext": "mp4" if not has_audio else fmt.get("ext", "mp4"),
                "height": fmt.get("height"),
                "has_audio": has_audio,
            }
        )

    audio_formats = [
        fmt for fmt in formats
        if fmt.get("acodec") != "none" and fmt.get("vcodec") == "none" and fmt.get("format_id")
    ]
    audio_formats.sort(key=lambda fmt: int(fmt.get("abr") or fmt.get("tbr") or 0), reverse=True)

    for fmt in audio_formats[:8]:
        format_id = str(fmt["format_id"])
        key = ("audio", format_id)
        if key in seen:
            continue
        seen.add(key)
        options.append(
            {
                "kind": "audio",
                "format_id": format_id,
                "download_format": format_id,
                "label": format_label(fmt, "audio"),
                "ext": fmt.get("ext", "m4a"),
            }
        )

    if not options:
        options.append(
            {
                "kind": "video",
                "format_id": "best",
                "download_format": "best",
                "label": "Best available quality",
                "ext": "mp4",
                "has_audio": True,
            }
        )

    return options


def video_rank(fmt: dict[str, Any]) -> tuple[int, int, int, int]:
    ext_score = 3 if fmt.get("ext") == "mp4" else 1
    codec = str(fmt.get("vcodec") or "")
    codec_score = 3 if codec.startswith("avc1") else 2 if codec.startswith("av01") else 1
    audio_score = 2 if fmt.get("acodec") != "none" else 1
    bitrate = int(fmt.get("tbr") or 0)
    return ext_score, codec_score, audio_score, bitrate


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/info")
def info(url: str = Form(...)) -> dict[str, Any]:
    checked_url = validate_youtube_url(url)
    video_info = extract_info(checked_url)
    return {
        "title": video_info.get("title") or "YouTube video",
        "duration": video_info.get("duration"),
        "thumbnail": video_info.get("thumbnail"),
        "webpage_url": video_info.get("webpage_url") or checked_url,
        "options": build_format_options(video_info),
    }


@app.post("/api/download")
def download(
    url: str = Form(...),
    download_format: str = Form(...),
    kind: str = Form("video"),
) -> FileResponse:
    checked_url = validate_youtube_url(url)
    if kind not in {"video", "audio"}:
        raise HTTPException(status_code=400, detail="Invalid download type.")

    temp_dir = Path(tempfile.mkdtemp(prefix="ytdlp-", dir=DOWNLOAD_DIR))
    output_template = str(temp_dir / "%(title).120B.%(ext)s")

    options: dict[str, Any] = {
        **ydl_base_options(),
        "format": download_format,
        "outtmpl": output_template,
        "noplaylist": True,
        "merge_output_format": "mp4",
    }

    if kind == "audio":
        options["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]

    try:
        with YoutubeDL(options) as ydl:
            ydl.extract_info(checked_url, download=True)

        files = [path for path in temp_dir.iterdir() if path.is_file() and not path.name.endswith(".part")]
        if not files:
            raise HTTPException(status_code=500, detail="No file was created.")

        result = max(files, key=lambda path: path.stat().st_size)
        if kind == "audio" and result.suffix.lower() != ".mp3":
            renamed = result.with_suffix(".mp3")
            result.rename(renamed)
            result = renamed

        media_type = "audio/mpeg" if kind == "audio" else "application/octet-stream"
        return DownloadFileResponse(
            result,
            directory=temp_dir,
            filename=result.name,
            media_type=media_type,
        )
    except DownloadError as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=422, detail=f"Could not download the file: {exc}") from exc
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


app.mount("/", StaticFiles(directory=STATIC_DIR), name="assets")
