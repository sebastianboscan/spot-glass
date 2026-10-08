"""Flask app serving a FrameBuffer as MJPEG, snapshots, a viewer and a health check."""

import time
from pathlib import Path

from flask import Flask, Response, jsonify

# Re-send the last frame this often during a stall so the connection, and the
# tunnel buffering it, never goes silent.
KEEPALIVE_S = 2.0
FRESH_S = 10.0

_VIEWER = (Path(__file__).parent / "viewer.html").read_text(encoding="utf-8")


def mjpeg_stream(buffer, fps):
    interval = 1.0 / fps
    last_sent, last_sent_at = None, 0.0
    while True:
        start = time.time()
        jpeg, _ = buffer.latest()
        if jpeg is not None and (jpeg is not last_sent or start - last_sent_at >= KEEPALIVE_S):
            last_sent, last_sent_at = jpeg, start
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
        remaining = interval - (time.time() - start)
        if remaining > 0:
            time.sleep(remaining)


def create_app(source, buffer, settings):
    app = Flask(__name__)
    viewer = (
        _VIEWER.replace("{{label}}", source.label)
        .replace("{{interval}}", str(1000 // settings.target_fps))
    )

    def stream():
        return Response(
            mjpeg_stream(buffer, settings.target_fps),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    def snapshot():
        jpeg, _ = buffer.latest()
        if jpeg is None:
            return Response("no frame yet", status=503, mimetype="text/plain")
        return Response(
            jpeg,
            mimetype="image/jpeg",
            headers={"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"},
        )

    def healthz():
        _, timestamp = buffer.latest()
        age = time.time() - timestamp if timestamp else None
        fresh = age is not None and age < FRESH_S
        body = {
            "stream_fresh": fresh,
            "last_frame_age_s": round(age, 2) if age is not None else None,
            **source.info(),
        }
        return jsonify(body), (200 if fresh else 503)

    def view():
        return viewer

    # cloudflared forwards the path prefix unchanged, so every route is served
    # both bare (local testing) and under the prefix (behind the tunnel).
    for rule, handler in [
        ("/stream", stream),
        ("/snapshot", snapshot),
        ("/healthz", healthz),
        ("/view", view),
    ]:
        app.add_url_rule(rule, handler.__name__, handler)
        if settings.url_prefix:
            app.add_url_rule(
                settings.url_prefix + rule, f"prefixed_{handler.__name__}", handler
            )

    return app
