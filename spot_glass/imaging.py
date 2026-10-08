"""Rotation, cropping and stitching for Spot's tilted fisheye cameras."""

import math

import cv2
import numpy as np


def rotate_expand(img, angle_deg):
    """Rotate about the center, growing the canvas so no corners are clipped."""
    h, w = img.shape[:2]
    center = (w / 2, h / 2)
    matrix = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
    cos, sin = abs(matrix[0, 0]), abs(matrix[0, 1])
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)
    matrix[0, 2] += new_w / 2 - center[0]
    matrix[1, 2] += new_h / 2 - center[1]
    return cv2.warpAffine(img, matrix, (new_w, new_h))


def inscribed_rect(w, h, angle_deg):
    """Largest axis-aligned rectangle inside a w x h rectangle rotated by angle.

    Closed form, because a pixel search costs ~100ms per frame.
    """
    if w <= 0 or h <= 0:
        return 0, 0
    angle = math.radians(abs(angle_deg) % 180)
    if angle > math.pi / 2:
        angle = math.pi - angle
    sin_a, cos_a = abs(math.sin(angle)), abs(math.cos(angle))
    long_side, short_side = (w, h) if w >= h else (h, w)

    if short_side <= 2 * sin_a * cos_a * long_side or abs(sin_a - cos_a) < 1e-10:
        x = 0.5 * short_side
        wr, hr = (x / sin_a, x / cos_a) if w >= h else (x / cos_a, x / sin_a)
    else:
        cos_2a = cos_a * cos_a - sin_a * sin_a
        wr = (w * cos_a - h * sin_a) / cos_2a
        hr = (h * cos_a - w * sin_a) / cos_2a
    return max(int(wr), 0), max(int(hr), 0)


def crop_rotated(img, angle_deg):
    """Trim the black corners that rotate_expand() left around the content."""
    h, w = img.shape[:2]
    # Invert the canvas growth to recover the original frame size.
    a = math.radians(abs(angle_deg) % 180)
    sin_a, cos_a = abs(math.sin(a)), abs(math.cos(a))
    denom = cos_a * cos_a - sin_a * sin_a
    if abs(denom) < 1e-6:
        return img
    orig_w = (w * cos_a - h * sin_a) / denom
    orig_h = (h * cos_a - w * sin_a) / denom
    if orig_w <= 0 or orig_h <= 0:
        return img

    cw, ch = inscribed_rect(orig_w, orig_h, angle_deg)
    if cw <= 0 or ch <= 0:
        return img
    x0 = max(w // 2 - cw // 2, 0)
    y0 = max(h // 2 - ch // 2, 0)
    cropped = img[y0 : y0 + ch, x0 : x0 + cw]
    return cropped if cropped.size else img


def stitch(frames):
    """Join frames left to right, padding to a common height."""
    if len(frames) == 1:
        return frames[0]
    target_h = max(f.shape[0] for f in frames)
    padded = []
    for f in frames:
        pad = target_h - f.shape[0]
        if pad:
            f = cv2.copyMakeBorder(
                f, pad // 2, pad - pad // 2, 0, 0, cv2.BORDER_CONSTANT, value=(0, 0, 0)
            )
        padded.append(f)
    return np.hstack(padded)
