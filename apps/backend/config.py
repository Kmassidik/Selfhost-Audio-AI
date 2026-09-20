"""Every setting the platform has, read from the environment once.

Nothing here is hardcoded to this box: the same code runs on a laptop, on the
box, or in a container behind a domain. See apps/docker/.env.example.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    root: str                 # the project root (models, runs, engines live here)
    data_dir: str             # where the platform keeps its own database and media
    runs_dir: str             # the lab console's job folder, imported once
    host: str
    port: int
    public_url: str           # e.g. https://music.example.com, used for share links
    owner_password: str       # empty: owner routes only from a private address
    enable_video: bool
    mp3_bitrate: str
    page_size: int
    max_page_size: int
    serve_media: bool         # true in development; in production Caddy serves media
    cover_source: str         # picsum | loremflickr | gradient
    cover_size: int
    music_only: bool          # hide the speech models: this is a music platform


def _clean(value: str) -> str:
    """Drop an inline comment and surrounding space.

    systemd's EnvironmentFile keeps everything after the '=', comment and all,
    so SERVE_MEDIA=1 # dev arrived as the string "1 # dev" and read as false.
    """
    return value.split("#", 1)[0].strip().strip('"').strip("'")


def _env(name: str, default: str = "") -> str:
    return _clean(os.environ.get(name, default))


def _flag(name: str, default: str = "0") -> bool:
    return _env(name, default).lower() in ("1", "true", "yes", "on")


def settings() -> Settings:
    root = _env("SELFHOSTAUDIO_ROOT", "/root/Desktop/selfhostaudioai")
    return Settings(
        root=root,
        data_dir=_env("DATA_DIR", os.path.join(root, "data", "studio")),
        runs_dir=_env("RUNS_DIR", os.path.join(root, "runs", "studio")),
        host=_env("APP_HOST", "0.0.0.0"),
        port=int(_env("APP_PORT", "8095")),
        public_url=_env("PUBLIC_URL").rstrip("/"),
        owner_password=_env("OWNER_PASSWORD"),
        enable_video=_flag("ENABLE_VIDEO", "1"),
        mp3_bitrate=_env("MP3_BITRATE", "128k"),
        page_size=int(_env("LIBRARY_PAGE_SIZE", "50")),
        max_page_size=int(_env("LIBRARY_MAX_PAGE_SIZE", "100")),
        serve_media=_flag("SERVE_MEDIA", "1"),
        cover_source=_env("COVER_SOURCE", "picsum"),
        cover_size=int(_env("COVER_SIZE", "640")),
        music_only=_flag("MUSIC_ONLY", "1"),
    )


def media_dirs(s: Settings) -> dict:
    """The four folders under data/. Created on demand, never in git."""
    d = {k: os.path.join(s.data_dir, k) for k in ("audio", "mp3", "covers", "video")}
    for p in d.values():
        os.makedirs(p, exist_ok=True)
    return d
