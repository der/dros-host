from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from dros_host.vision.detector import FaceDetection

_MODEL_PATH = (
    Path(__file__).parent / "models" / "face_detection_yunet_2023mar.onnx"
)
_INITIAL_SIZE = (320, 320)
_SCORE_THRESHOLD = 0.0
_NMS_THRESHOLD = 0.3
_TOP_K = 50


class YuNetDetector:
    """FaceDetector backed by OpenCV's YuNet (``cv2.FaceDetectorYN``).

    The model ONNX is vendored under ``vision/models/``. YuNet's internal
    ``score_threshold`` is 0.0 so every candidate is returned; the consuming
    node applies its own confidence threshold.
    """

    def __init__(self) -> None:
        self._detector = cv2.FaceDetectorYN.create(
            str(_MODEL_PATH),
            "",
            _INITIAL_SIZE,
            score_threshold=_SCORE_THRESHOLD,
            nms_threshold=_NMS_THRESHOLD,
            top_k=_TOP_K,
        )

    def detect(self, image: np.ndarray) -> list[FaceDetection]:
        h, w = image.shape[:2]
        self._detector.setInputSize((w, h))
        _, faces = self._detector.detect(image)
        if faces is None:
            return []

        detections: list[FaceDetection] = []
        for row in faces:
            detections.append(_row_to_detection(row, w, h))
        return detections


def _row_to_detection(
    row: np.ndarray, w: int, h: int
) -> FaceDetection:
    """Convert a YuNet output row (15 floats) to a normalized FaceDetection.

    YuNet row layout:
        0-3: bbox x, y, w, h (pixels)
        8-9: nose tip x, y (pixels)
        14: face score
    """
    bx, by, bw, bh = float(row[0]), float(row[1]), float(row[2]), float(row[3])
    nx, ny = float(row[8]), float(row[9])
    score = float(row[14])
    return FaceDetection(
        confidence=score,
        nose=(nx / w, ny / h),
        bbox=(bx / w, by / h, bw / w, bh / h),
    )
