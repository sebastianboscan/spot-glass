"""Spot body-camera source, read through the robot's authenticated image service.

The body cameras are not RTSP. Each frame is a get_image() request, so this
source holds an authenticated robot connection and polls at a fixed rate.
"""

import getpass
import os
import sys

import cv2
import numpy as np

import bosdyn.client
import bosdyn.client.util
from bosdyn.api import image_pb2
from bosdyn.client.image import ImageClient, build_image_request

from .config import env_bool, env_int, env_str
from .imaging import crop_rotated, rotate_expand, stitch

# Correction angles from the SDK examples. They undo the ~90° CCW mount and
# the outward splay of the front pair.
ROTATION_ANGLE = {
    "frontleft_fisheye_image": -78,
    "frontright_fisheye_image": -102,
    "back_fisheye_image": 0,
    "left_fisheye_image": 0,
    "right_fisheye_image": 180,
}

# Each list is the left-to-right stitch order. The front cameras are named for
# where they are mounted and point across each other, so frontright (which sees
# the robot's left) comes first. Reversing it mirrors the panorama.
CAMERAS = {
    "front": ["frontright_fisheye_image", "frontleft_fisheye_image"],
    "frontleft": ["frontleft_fisheye_image"],
    "frontright": ["frontright_fisheye_image"],
    "back": ["back_fisheye_image"],
    "left": ["left_fisheye_image"],
    "right": ["right_fisheye_image"],
}

CREDENTIAL_VARS = ("BOSDYN_CLIENT_USERNAME", "BOSDYN_CLIENT_PASSWORD")


def prompt_for_credentials():
    """Ask for any missing robot credentials when running interactively."""
    if not sys.stdin.isatty():
        return
    if not os.environ.get("BOSDYN_CLIENT_USERNAME"):
        os.environ["BOSDYN_CLIENT_USERNAME"] = input("Spot username: ")
    if not os.environ.get("BOSDYN_CLIENT_PASSWORD"):
        os.environ["BOSDYN_CLIENT_PASSWORD"] = getpass.getpass("Spot password: ")


class SpotSource:
    label = "Spot"

    def __init__(self, hostname, camera, capture_fps, jpeg_quality, crop):
        if camera not in CAMERAS:
            raise SystemExit(f"SPOT_CAMERA={camera!r} unknown; expected one of {sorted(CAMERAS)}")
        self.hostname = hostname
        self.camera = camera
        self.sources = CAMERAS[camera]
        self.crop = crop
        # The body cameras run at ~15 Hz; polling faster only re-fetches frames.
        self.poll_interval = 1.0 / max(capture_fps, 1)
        # Have the robot JPEG-encode: Wi-Fi bandwidth is the bottleneck.
        self._requests = [
            build_image_request(
                src, quality_percent=jpeg_quality, image_format=image_pb2.Image.FORMAT_JPEG
            )
            for src in self.sources
        ]
        self._client = None

    @classmethod
    def from_env(cls):
        return cls(
            hostname=env_str("SPOT_HOSTNAME", "192.168.80.3"),
            camera=env_str("SPOT_CAMERA", "front"),
            capture_fps=env_int("CAPTURE_FPS", 10),
            jpeg_quality=env_int("JPEG_QUALITY", 60),
            crop=env_bool("CROP", True),
        )

    def connect(self):
        # Without these, authenticate() would block on a stdin prompt.
        missing = [name for name in CREDENTIAL_VARS if not os.environ.get(name)]
        if missing:
            raise RuntimeError(f"{' and '.join(missing)} must be set")
        sdk = bosdyn.client.create_standard_sdk("SpotGlass")
        robot = sdk.create_robot(self.hostname)
        bosdyn.client.util.authenticate(robot)
        robot.time_sync.wait_for_sync()
        self._client = robot.ensure_client(ImageClient.default_service_name)

    def read(self):
        responses = self._client.get_image(self._requests)
        # Response order isn't guaranteed; walk the stitch order explicitly.
        by_name = {r.source.name: r for r in responses}
        frames = [self._decode(by_name[s]) for s in self.sources if s in by_name]
        frames = [f for f in frames if f is not None]
        # Publish complete sets only, so the panorama never changes width.
        if len(frames) != len(self.sources):
            return None
        return stitch(frames)

    def close(self):
        self._client = None

    def info(self):
        return {"source": "spot", "hostname": self.hostname, "camera": self.camera}

    def _decode(self, response):
        buf = np.frombuffer(response.shot.image.data, dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if img is None:
            return None
        angle = ROTATION_ANGLE.get(response.source.name, 0)
        if angle:
            img = rotate_expand(img, angle)
            if self.crop:
                img = crop_rotated(img, angle)
        return img
