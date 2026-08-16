import math
from pathlib import Path

import cv2
import numpy as np

from dros_host.vision.detector import FaceDetection, FaceDetector
from dros_host.vision.yunet import YuNetDetector

FIXTURE = Path(__file__).parent / "fixtures" / "vision" / "synthetic_face.png"


def load_fixture() -> np.ndarray:
    img = cv2.imread(str(FIXTURE))
    assert img is not None, f"could not read fixture {FIXTURE}"
    return img


class TestYuNetDetector:
    def test_implements_protocol(self) -> None:
        detector = YuNetDetector()
        assert isinstance(detector, FaceDetector)

    def test_detect_returns_list_of_face_detection(self) -> None:
        detector = YuNetDetector()
        img = load_fixture()
        faces = detector.detect(img)
        assert isinstance(faces, list)
        for f in faces:
            assert isinstance(f, FaceDetection)

    def test_finds_face_in_fixture(self) -> None:
        detector = YuNetDetector()
        img = load_fixture()
        faces = detector.detect(img)
        assert len(faces) >= 1, "expected at least one face in synthetic fixture"

    def test_nose_normalized_to_unit_interval(self) -> None:
        detector = YuNetDetector()
        img = load_fixture()
        faces = detector.detect(img)
        for f in faces:
            nx, ny = f.nose
            assert 0.0 <= nx <= 1.0, f"nose x {nx} out of [0,1]"
            assert 0.0 <= ny <= 1.0, f"nose y {ny} out of [0,1]"

    def test_bbox_normalized_to_unit_interval(self) -> None:
        detector = YuNetDetector()
        img = load_fixture()
        faces = detector.detect(img)
        for f in faces:
            x, y, w, h = f.bbox
            assert 0.0 <= x <= 1.0, f"bbox x {x} out of [0,1]"
            assert 0.0 <= y <= 1.0, f"bbox y {y} out of [0,1]"
            assert 0.0 <= w <= 1.0, f"bbox w {w} out of [0,1]"
            assert 0.0 <= h <= 1.0, f"bbox h {h} out of [0,1]"

    def test_strongest_face_nose_near_centre(self) -> None:
        """The synthetic face is roughly centred in a 320x320 image."""
        detector = YuNetDetector()
        img = load_fixture()
        faces = detector.detect(img)
        strongest = max(faces, key=lambda f: f.confidence)
        nx, ny = strongest.nose
        assert math.isclose(nx, 0.5, abs_tol=0.15), f"nose x {nx} not near 0.5"
        assert math.isclose(ny, 0.5, abs_tol=0.15), f"nose y {ny} not near 0.5"

    def test_blank_image_yields_only_low_confidence_noise(self) -> None:
        """With score_threshold=0.0 YuNet returns noise on a blank image;
        the node's confidence_threshold is the real filter. All detections
        here should be well below the default 0.5 threshold."""
        detector = YuNetDetector()
        img = np.zeros((320, 320, 3), dtype=np.uint8)
        faces = detector.detect(img)
        for f in faces:
            assert f.confidence < 0.5, f"noise detection {f.confidence} >= 0.5"
