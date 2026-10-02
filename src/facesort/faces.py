"""Head crops: find the face with OpenCV's YuNet detector and cut a square around it.

Used for the face-crop condition, which removes the setting (backdrops, logos,
other people) so a model can only group by the person. The crop keeps the hair:
it is part of how a person looks, and Jenkins' viewers saw it too.

Every crop returns a record (faces found, which one was used, box, source size)
so a crop can be checked and reproduced. Photos with more than one face are not
resolved here: the largest face is used and `n_faces` flags them for a look.
"""

import hashlib
from pathlib import Path

import cv2
import numpy as np
import requests
from PIL import Image, ImageOps

from facesort.cache import CACHE_ROOT

MODEL_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx"
)
MODEL_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
MODEL_PATH = CACHE_ROOT / "models" / "face_detection_yunet_2023mar.onnx"

# Detect on a downscaled copy, trying smaller sizes if nothing is found: YuNet misses faces
# that fill most of the frame (close-ups) at large sizes but finds them once the photo is smaller.
DETECT_SIDES = (1600, 800, 400)
SCORE_THRESHOLD = 0.8

_detector = None


def _model_path() -> Path:
    if not MODEL_PATH.exists():
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(MODEL_URL, timeout=60)
        r.raise_for_status()
        MODEL_PATH.write_bytes(r.content)
    got = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()
    if got != MODEL_SHA256:
        raise RuntimeError(f"YuNet model hash mismatch ({got}); delete {MODEL_PATH} and retry")
    return MODEL_PATH


def _get_detector():
    global _detector
    if _detector is None:
        _detector = cv2.FaceDetectorYN.create(str(_model_path()), "", (320, 320), SCORE_THRESHOLD)
    return _detector


def load_upright(path: Path) -> Image.Image:
    return ImageOps.exif_transpose(Image.open(path)).convert("RGB")


def _detect_at(img: Image.Image, max_side: int) -> list[dict]:
    scale = min(1.0, max_side / max(img.size))
    small = img.resize((round(img.width * scale), round(img.height * scale))) if scale < 1 else img
    bgr = cv2.cvtColor(np.asarray(small), cv2.COLOR_RGB2BGR)

    det = _get_detector()
    det.setInputSize((bgr.shape[1], bgr.shape[0]))
    _, found = det.detect(bgr)
    if found is None:
        return []
    return [
        {"x": f[0] / scale, "y": f[1] / scale, "w": f[2] / scale, "h": f[3] / scale,
         "score": float(f[-1]), "detect_side": max_side}
        for f in found
    ]


def detect(img: Image.Image) -> list[dict]:
    """Faces in `img` as dicts with x, y, w, h (in `img` pixels), score and the detection size used, largest first."""
    for max_side in DETECT_SIDES:
        faces = _detect_at(img, max_side)
        if faces:
            return sorted(faces, key=lambda f: f["w"] * f["h"], reverse=True)
    return []


def head_box(face: dict, width: int, height: int, scale: float = 1.8, lift: float = 0.15) -> tuple[int, int, int, int]:
    """Square (left, top, right, bottom) around a face, `scale` times its size, moved up by
    `lift` of the face height to take in the hair. Shrunk if needed so it stays square inside the photo."""
    side = scale * max(face["w"], face["h"])
    cx = face["x"] + face["w"] / 2
    cy = face["y"] + face["h"] / 2 - lift * face["h"]

    side = min(side, width, height)
    left = min(max(cx - side / 2, 0), width - side)
    top = min(max(cy - side / 2, 0), height - side)
    return round(left), round(top), round(left + side), round(top + side)


def crop_head(src: Path, dest: Path, size: int = 384, scale: float = 1.8, face_index: int = 0) -> dict:
    """Write a `size`x`size` head crop of one face in `src` to `dest` (JPEG q85, no EXIF).

    Faces are ordered largest first; `face_index` picks another one when the largest is the wrong person.

    Raises if no face is found, so a photo can never silently drop out of a condition.
    """
    img = load_upright(src)
    faces = detect(img)
    if not faces:
        raise RuntimeError(f"no face found in {src}")

    if face_index >= len(faces):
        raise RuntimeError(f"face_index {face_index} but only {len(faces)} faces in {src}")
    face = faces[face_index]
    box = head_box(face, img.width, img.height, scale=scale)
    crop = img.crop(box).resize((size, size), Image.Resampling.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    crop.save(dest, "JPEG", quality=85)

    return {
        "crop_path": str(dest),
        "n_faces": len(faces),
        "face_index": face_index,
        "face_score": round(face["score"], 3),
        "detect_side": face["detect_side"],
        "box": box,
        "source_px": box[2] - box[0],  # side of the crop in the original photo; small means upscaled and soft
    }
