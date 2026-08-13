from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"


@dataclass
class AnatomyResult:
    regions: dict[str, dict[str, Any]]
    landmarks: list[dict[str, float]]
    detector: str
    confidence: float
    diagnostics: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "detector": self.detector,
            "confidence": round(float(self.confidence), 3),
            "regions": self.regions,
            "landmarks": self.landmarks,
            "diagnostics": self.diagnostics,
        }


class AnatomyLocator:
    """Optional body-landmark detector with a zero-dependency fallback.

    V0.9 intentionally does not make MediaPipe mandatory. If `mediapipe` and a
    Pose Landmarker task file are present, named body regions become detector
    driven. Otherwise callers keep the V0.8 pose-anchor / bounding-box fallback.
    """

    # MediaPipe Pose Landmarker indexes (33-point pose topology).
    NOSE = 0
    LEFT_EYE = 2
    RIGHT_EYE = 5
    LEFT_EAR = 7
    RIGHT_EAR = 8
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_PINKY = 17
    RIGHT_PINKY = 18
    LEFT_INDEX = 19
    RIGHT_INDEX = 20
    LEFT_THUMB = 21
    RIGHT_THUMB = 22
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_HEEL = 29
    RIGHT_HEEL = 30
    LEFT_FOOT = 31
    RIGHT_FOOT = 32

    CONNECTIONS = [
        (11, 12), (11, 13), (13, 15), (15, 17), (15, 19), (15, 21),
        (12, 14), (14, 16), (16, 18), (16, 20), (16, 22),
        (11, 23), (12, 24), (23, 24), (23, 25), (25, 27), (27, 29), (29, 31),
        (24, 26), (26, 28), (28, 30), (30, 32),
    ]

    def __init__(self):
        self._landmarker = None
        self._loaded_model: Optional[Path] = None
        self._last_error: Optional[str] = None

    def _model_path(self) -> Optional[Path]:
        configured = os.environ.get("CORVO_POSE_LANDMARKER_MODEL", "").strip()
        candidates = []
        if configured:
            candidates.append(Path(configured))
        candidates.extend([
            MODELS_DIR / "pose_landmarker.task",
            MODELS_DIR / "pose_landmarker_lite.task",
            MODELS_DIR / "pose_landmarker_full.task",
        ])
        for path in candidates:
            if path.exists() and path.is_file():
                return path.resolve()
        return None

    def status(self) -> dict[str, Any]:
        model = self._model_path()
        try:
            import mediapipe  # noqa: F401
            installed = True
        except Exception:
            installed = False
        return {
            "mediapipe_installed": installed,
            "model_path": str(model) if model else None,
            "ready": bool(installed and model),
            "loaded": self._landmarker is not None,
            "last_error": self._last_error,
            "fallback": "pose_anchors_and_character_box",
        }

    def _load(self):
        model = self._model_path()
        if not model:
            raise RuntimeError("Arquivo Pose Landmarker não encontrado em models/pose_landmarker.task.")
        if self._landmarker is not None and self._loaded_model == model:
            return self._landmarker
        try:
            import mediapipe as mp
            BaseOptions = mp.tasks.BaseOptions
            PoseLandmarker = mp.tasks.vision.PoseLandmarker
            PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
            RunningMode = mp.tasks.vision.RunningMode
            options = PoseLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(model)),
                running_mode=RunningMode.IMAGE,
                num_poses=1,
                min_pose_detection_confidence=0.45,
                min_pose_presence_confidence=0.45,
            )
            self._landmarker = PoseLandmarker.create_from_options(options)
            self._loaded_model = model
            self._last_error = None
            return self._landmarker
        except Exception as exc:
            self._last_error = str(exc)
            raise RuntimeError(f"Não foi possível carregar MediaPipe Pose Landmarker: {exc}") from exc

    @staticmethod
    def _point(lms: list[dict[str, float]], idx: int, width: int, height: int) -> tuple[float, float, float]:
        lm = lms[idx]
        return lm["x"] * width, lm["y"] * height, min(float(lm.get("visibility", 1.0)), float(lm.get("presence", 1.0)))

    @staticmethod
    def _box_from_points(points: list[tuple[float, float, float]], width: int, height: int,
                         pad_x: float = 0.20, pad_y: float = 0.20) -> Optional[dict[str, Any]]:
        visible = [(x, y, c) for x, y, c in points if c >= 0.25]
        if not visible:
            return None
        xs = [x for x, _, _ in visible]
        ys = [y for _, y, _ in visible]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        span_x = max(12.0, x1 - x0)
        span_y = max(12.0, y1 - y0)
        x0 -= span_x * pad_x
        x1 += span_x * pad_x
        y0 -= span_y * pad_y
        y1 += span_y * pad_y
        x0 = max(0, min(width - 1, int(round(x0))))
        y0 = max(0, min(height - 1, int(round(y0))))
        x1 = max(x0 + 1, min(width, int(round(x1))))
        y1 = max(y0 + 1, min(height, int(round(y1))))
        confidence = sum(c for _, _, c in visible) / len(visible)
        return {"box": [x0, y0, x1 - x0, y1 - y0], "confidence": round(confidence, 3)}

    def detect(self, image: Image.Image) -> Optional[AnatomyResult]:
        diagnostics: list[str] = []
        try:
            landmarker = self._load()
            import mediapipe as mp
            import numpy as np
            rgb = image.convert("RGB")
            array = np.asarray(rgb)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=array)
            result = landmarker.detect(mp_image)
            poses = result.pose_landmarks or []
            if not poses:
                return AnatomyResult({}, [], "mediapipe_pose_landmarker", 0.0, ["Nenhuma pose detectada."])
            raw = poses[0]
            lms = []
            for lm in raw:
                lms.append({
                    "x": float(lm.x), "y": float(lm.y), "z": float(lm.z),
                    "visibility": float(getattr(lm, "visibility", 1.0) or 0.0),
                    "presence": float(getattr(lm, "presence", 1.0) or 0.0),
                })
            w, h = rgb.size
            p = lambda i: self._point(lms, i, w, h)
            groups = {
                "head": ([self.NOSE, self.LEFT_EYE, self.RIGHT_EYE, self.LEFT_EAR, self.RIGHT_EAR], 0.55, 0.85),
                "face": ([self.NOSE, self.LEFT_EYE, self.RIGHT_EYE, self.LEFT_EAR, self.RIGHT_EAR], 0.35, 0.45),
                "left_hand": ([self.LEFT_WRIST, self.LEFT_PINKY, self.LEFT_INDEX, self.LEFT_THUMB], 0.65, 0.75),
                "right_hand": ([self.RIGHT_WRIST, self.RIGHT_PINKY, self.RIGHT_INDEX, self.RIGHT_THUMB], 0.65, 0.75),
                "left_arm": ([self.LEFT_SHOULDER, self.LEFT_ELBOW, self.LEFT_WRIST], 0.28, 0.28),
                "right_arm": ([self.RIGHT_SHOULDER, self.RIGHT_ELBOW, self.RIGHT_WRIST], 0.28, 0.28),
                "torso": ([self.LEFT_SHOULDER, self.RIGHT_SHOULDER, self.LEFT_HIP, self.RIGHT_HIP], 0.15, 0.12),
                "left_leg": ([self.LEFT_HIP, self.LEFT_KNEE, self.LEFT_ANKLE, self.LEFT_FOOT], 0.25, 0.18),
                "right_leg": ([self.RIGHT_HIP, self.RIGHT_KNEE, self.RIGHT_ANKLE, self.RIGHT_FOOT], 0.25, 0.18),
                "character": (list(range(11, 33)) + [0, 7, 8], 0.08, 0.06),
                "body": (list(range(11, 33)) + [0, 7, 8], 0.08, 0.06),
            }
            regions: dict[str, dict[str, Any]] = {}
            for name, (idxs, padx, pady) in groups.items():
                box = self._box_from_points([p(i) for i in idxs], w, h, padx, pady)
                if box:
                    box["source"] = "mediapipe_pose_landmarker"
                    regions[name] = box
            if not regions:
                diagnostics.append("Landmarks detectados, mas sem confiança suficiente para formar regiões.")
            avg = sum(min(x["visibility"], x["presence"]) for x in lms) / max(1, len(lms))
            return AnatomyResult(regions, lms, "mediapipe_pose_landmarker", avg, diagnostics)
        except Exception as exc:
            self._last_error = str(exc)
            return None

    def render_pose_control(self, image: Image.Image, *, target_size: Optional[tuple[int, int]] = None) -> tuple[Optional[Image.Image], dict[str, Any]]:
        """Create a simple OpenPose-like skeleton hint from detected pose landmarks."""
        detected = self.detect(image)
        if not detected or not detected.landmarks:
            return None, {"generated": False, "reason": self._last_error or "pose_not_detected"}
        w, h = target_size or image.size
        canvas = Image.new("RGB", (w, h), (0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        scale = max(2, int(round(min(w, h) / 180)))
        lms = detected.landmarks
        def pt(i: int):
            lm = lms[i]
            return int(round(lm["x"] * w)), int(round(lm["y"] * h)), min(lm["visibility"], lm["presence"])
        for a, b in self.CONNECTIONS:
            ax, ay, ac = pt(a); bx, by, bc = pt(b)
            if min(ac, bc) >= 0.25:
                draw.line((ax, ay, bx, by), fill=(255, 255, 255), width=scale)
        for idx in set(x for pair in self.CONNECTIONS for x in pair):
            x, y, c = pt(idx)
            if c >= 0.25:
                r = max(2, scale + 1)
                draw.ellipse((x-r, y-r, x+r, y+r), fill=(255, 255, 255))
        return canvas, {
            "generated": True,
            "detector": detected.detector,
            "confidence": round(detected.confidence, 3),
            "regions": detected.regions,
        }


anatomy_locator = AnatomyLocator()
