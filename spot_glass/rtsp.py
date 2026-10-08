"""RTSP camera source (the thermal payload camera)."""

import os

import cv2

from .config import env_str

# Cap FFmpeg's socket timeout so reconnects to a dead host take 5s, not ~30s.
# FFmpeg <5 calls the option "stimeout" and >=5 calls it "timeout"; each
# version ignores the key it doesn't know.
os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "rtsp_transport;tcp|timeout;5000000|stimeout;5000000",
)


class RtspSource:
    label = "thermal camera"
    # Read as fast as the camera delivers so FFmpeg never builds a backlog;
    # the HTTP side caps the output rate.
    poll_interval = 0.0

    def __init__(self, url):
        self.url = url
        self._cap = None

    @classmethod
    def from_env(cls):
        return cls(env_str("RTSP_URL", "rtsp://192.168.80.102/avc"))

    def connect(self):
        cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            cap.release()
            raise ConnectionError(f"cannot open {self.url}")
        self._cap = cap

    def read(self):
        ok, frame = self._cap.read()
        if not ok:
            raise ConnectionError(f"no frame from {self.url}")
        return frame

    def close(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def info(self):
        return {"source": "rtsp", "url": self.url}
