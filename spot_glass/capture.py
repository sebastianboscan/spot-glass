"""Background capture: pull frames from a source, keep only the newest JPEG."""

import threading
import time

import cv2

RECONNECT_MIN_S = 1.0
RECONNECT_MAX_S = 30.0


class FrameBuffer:
    """Latest encoded frame, written by the capture thread and read by requests."""

    def __init__(self):
        self._lock = threading.Lock()
        self._jpeg = None
        self._timestamp = 0.0

    def publish(self, jpeg):
        with self._lock:
            self._jpeg = jpeg
            self._timestamp = time.time()

    def latest(self):
        """Return (jpeg bytes or None, unix time it was published)."""
        with self._lock:
            return self._jpeg, self._timestamp


def encode(frame, max_width, quality):
    h, w = frame.shape[:2]
    if w > max_width:
        frame = cv2.resize(frame, (max_width, int(h * max_width / w)))
    ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return jpeg.tobytes() if ok else None


def run_capture(source, buffer, settings):
    """Loop forever, reconnecting with exponential backoff on any failure.

    A source provides connect(), read() and close(). read() returns a BGR
    frame, returns None when there is nothing complete to publish, or raises
    when the connection is lost.
    """
    backoff = RECONNECT_MIN_S
    connected = False

    def fail(what, exc):
        nonlocal backoff, connected
        print(f"[capture] {what}, retrying in {backoff:.0f}s: {exc}", flush=True)
        source.close()
        connected = False
        time.sleep(backoff)
        backoff = min(backoff * 2, RECONNECT_MAX_S)

    while True:
        if not connected:
            try:
                source.connect()
                connected = True
                print(f"[capture] connected to {source.label}", flush=True)
            except Exception as exc:
                fail("connect failed", exc)
                continue

        start = time.monotonic()
        try:
            frame = source.read()
        except Exception as exc:
            fail("read failed", exc)
            continue

        if backoff != RECONNECT_MIN_S:
            print("[capture] stream recovered", flush=True)
            backoff = RECONNECT_MIN_S

        if frame is not None:
            jpeg = encode(frame, settings.max_width, settings.jpeg_quality)
            if jpeg:
                buffer.publish(jpeg)

        remaining = source.poll_interval - (time.monotonic() - start)
        if remaining > 0:
            time.sleep(remaining)


def start_capture(source, buffer, settings):
    thread = threading.Thread(
        target=run_capture, args=(source, buffer, settings), daemon=True
    )
    thread.start()
    return thread
