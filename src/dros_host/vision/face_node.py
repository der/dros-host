from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np
from dros import DrosLogger, Node
from pydantic import ValidationError

from dros_host.messages.events import EventPublisherMixin
from dros_host.messages.face import FaceDetectMessage
from dros_host.messages.image import ImageMessage
from dros_host.vision.detector import FaceDetection, FaceDetector
from dros_host.vision.yunet import YuNetDetector

if TYPE_CHECKING:
    from dros import Bus

logger = DrosLogger("face_node")

_CAMERA_TOPIC = "/marvin/camera"
_FACE_TOPIC = "/face_detect"
_INTERVAL = 0.2
_CONFIDENCE_THRESHOLD = 0.5
_FACE_TYPE = "face"
_FACE_DETECTED = "Face detected"
_FACE_LOST = "Face lost"


class FaceNode(EventPublisherMixin, Node):
    """Periodically samples the camera, detects faces, and publishes state.

    Runs a ``FaceDetector`` on the latest camera frame each tick. Publishes
    the strongest face's nose offset / size / confidence to the ``face_topic``
    state topic, and fires "Face detected" / "Face lost" edge events on
    ``/events`` when presence transitions.
    """

    def __init__(
        self,
        bus: Bus,
        *,
        camera_topic: str = _CAMERA_TOPIC,
        face_topic: str = _FACE_TOPIC,
        interval: float = _INTERVAL,
        confidence_threshold: float = _CONFIDENCE_THRESHOLD,
        detector: FaceDetector | None = None,
    ) -> None:
        super().__init__(bus, interval=interval)
        self.camera_topic = camera_topic
        self.face_topic = face_topic
        self.confidence_threshold = confidence_threshold
        self.detector = detector
        self._present = False

    def startup(self) -> None:
        self.bus.state_topic(self.face_topic, history=4)
        if self.detector is None:
            self.detector = YuNetDetector()

    def tick(self) -> None:
        detector = self.detector
        if detector is None:
            return
        frame = self._latest_frame()
        if frame is None:
            return
        reading = self._reading(detector.detect(frame))
        self.publish(self.face_topic, reading.model_dump())
        self._emit_edges(reading)

    def _latest_frame(self) -> np.ndarray | None:
        msg = self.bus.topic(self.camera_topic).current()
        if msg is None:
            return None
        try:
            image = ImageMessage.model_validate(msg)
        except ValidationError:
            logger.warning("Invalid camera message on %s", self.camera_topic)
            return None
        if image.data is None:
            logger.warning("Camera message on %s had no data", self.camera_topic)
            return None
        frame = cv2.imdecode(np.frombuffer(image.data, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            logger.warning("Failed to decode camera image on %s", self.camera_topic)
            return None
        return frame

    def _reading(self, faces: list[FaceDetection]) -> FaceDetectMessage:
        strongest = max(faces, key=lambda f: f.confidence) if faces else None
        if strongest is None or strongest.confidence < self.confidence_threshold:
            return FaceDetectMessage()
        nx, ny = strongest.nose
        bx, by, bw, bh = strongest.bbox
        return FaceDetectMessage(
            present=True,
            x=2.0 * nx - 1.0,
            y=2.0 * ny - 1.0,
            size=bw * bh,
            confidence=strongest.confidence,
            bbox=(bx, by, bw, bh),
        )

    def _emit_edges(self, reading: FaceDetectMessage) -> None:
        present = reading.present
        if present and not self._present:
            self.publish_event(f"Face detected at {reading.x}, {reading.y}: confidence {reading.confidence}", _FACE_TYPE)
        elif not present and self._present:
            self.publish_event(_FACE_LOST, _FACE_TYPE)
        self._present = present
