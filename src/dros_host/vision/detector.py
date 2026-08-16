from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np


@dataclass(frozen=True, slots=True)
class FaceDetection:
    """One face found by a FaceDetector.

    All coordinates are normalized to [0, 1] relative to the image dimensions
    so that detections are resolution-independent and transport-safe.

    Attributes:
        confidence: Detector score, range [0, 1].
        nose: (x, y) of the nose tip, normalized [0, 1].
        bbox: (x, y, w, h) of the bounding box, normalized [0, 1].
    """

    confidence: float
    nose: tuple[float, float]
    bbox: tuple[float, float, float, float]


@runtime_checkable
class FaceDetector(Protocol):
    """Detects all faces in an image.

    The detector only reports what it found — it does not pick a face or
    compute offsets. Selection and offset math belong to the consuming node.
    """

    def detect(self, image: np.ndarray) -> list[FaceDetection]:
        """Return all faces found in ``image`` (BGR ``np.ndarray``)."""
        ...
