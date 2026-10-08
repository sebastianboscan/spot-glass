"""Settings from environment variables, optionally seeded from a .env file."""

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path=".env"):
    """Load KEY=VALUE lines into os.environ. Variables already set win."""
    file = Path(path)
    if not file.is_file():
        return
    for line in file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        value = value.strip("'\"")
        if value and not os.environ.get(key):
            os.environ[key] = value


def env_str(name, default):
    return os.environ.get(name, default)


def env_int(name, default):
    """Fall back to the default on blank or invalid values instead of crashing."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"[config] {name}={raw!r} is not an integer; using {default}", flush=True)
        return default


def env_bool(name, default):
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw not in ("0", "false", "no", "off")


@dataclass(frozen=True)
class ServerSettings:
    listen_host: str
    listen_port: int
    url_prefix: str
    target_fps: int
    jpeg_quality: int
    max_width: int

    @classmethod
    def from_env(cls, default_port, default_prefix=""):
        return cls(
            listen_host=env_str("LISTEN_HOST", "127.0.0.1"),
            listen_port=env_int("LISTEN_PORT", default_port),
            url_prefix=env_str("URL_PREFIX", default_prefix).rstrip("/"),
            target_fps=max(env_int("TARGET_FPS", 10), 1),
            jpeg_quality=env_int("JPEG_QUALITY", 60),
            max_width=env_int("MAX_WIDTH", 480),
        )
