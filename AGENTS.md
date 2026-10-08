# AGENTS.md

Guidance for AI coding agents working in this repository.

## Overview

The `spot_glass` package relays Boston Dynamics Spot camera feeds as MJPEG, optionally through a Cloudflare tunnel, for viewing on the Meta Ray-Ban Display (600×600). There are two sources: `spot` (body cameras via the bosdyn image gRPC service) and `thermal` (an RTSP payload camera). The README covers usage, config and endpoints.

There is no test suite, linter or build system. The dev environment is `.venv` (Python 3.10, deps pinned in `requirements.txt`).

## Commands

```bash
.venv/Scripts/python -m spot_glass spot             # http://localhost:21001/spot/view
.venv/Scripts/python -m spot_glass thermal          # http://localhost:5000/view
.venv/Scripts/python -m spot_glass spot --tunnel    # also runs cloudflared ($CLOUDFLARE_TUNNEL)
cd spot-extension && ./build_spx.sh                 # CORE I/O .spx (Docker buildx, arm64)
```

Settings load from `.env` (gitignored, which keeps the real public hostname out of the repo); existing env vars take priority. **Don't run `--tunnel` while testing.** The local `.env` names a real tunnel, so the command exposes the relay publicly. Override `LISTEN_PORT` when smoke-testing so you don't collide with a running relay.

## Architecture

- **Sources** (`spot.py`, `rtsp.py`) implement `label`, `poll_interval`, `connect()`, `read()`, `close()` and `info()`. `read()` returns a BGR frame, returns `None` when there's nothing complete to publish, or raises when the connection is lost. `__main__.py` maps the CLI name to a source and its default port and prefix.
- **`capture.py`** runs one daemon thread per process. It calls the source, handles reconnect backoff (1s doubling to 30s), downscales and JPEG-encodes, and publishes only the newest frame into `FrameBuffer`. Because of this, never run the app under a multi-worker WSGI server: each worker would open its own robot or camera connection.
- **`server.py`** builds the Flask app. The MJPEG generator re-sends the last frame every 2s during stalls to keep the tunnel alive. Every route is registered both bare and under `URL_PREFIX`, because cloudflared doesn't strip path prefixes. `viewer.html` must keep its *relative* URLs (`stream`, `snapshot`) so it works under either path.
- **The Extension** (`spot-extension/`) runs `python3 -m spot_glass thermal` on Debian's apt Flask and OpenCV. bosdyn is not installed there, so `spot.py`, which imports bosdyn at module level, must only be imported lazily, as `__main__.build_source` does. `build_spx.sh` copies `../spot_glass` into the build context.

## Spot imaging (easy to break)

- `CAMERAS["front"]` lists **frontright first**. That list is the left-to-right stitch order, and frontright sees the robot's left. Responses are re-keyed by source name because `get_image()` order isn't guaranteed. A frame publishes only when every source decoded.
- `imaging.rotate_expand` grows the canvas for the non-90° SDK angles (−78°/−102°). `crop_rotated`/`inscribed_rect` are closed-form on purpose, because a pixel search took about 100ms per frame. Output was verified pixel-identical to the original single-file implementation. Re-verify with synthetic JPEGs if you touch this code.
- `viewer.html`: the display is additive, so black renders as transparent. Use no dark UI chrome, only bright text. MJPEG support on the glasses is undocumented, hence the snapshot-polling fallback.

Nothing here has been tested yet against a physical robot or the glasses.
