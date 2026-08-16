import time
from collections.abc import Callable

import cv2
import numpy as np
import pytest
from dros import Bus

from dros_host.messages.events import EVENT_TOPIC
from dros_host.messages.face import FaceDetectMessage
from dros_host.vision.detector import FaceDetection
from dros_host.vision.face_node import FaceNode
from dros_host.vision.yunet import YuNetDetector

CAMERA_TOPIC = "/marvin/camera"
FACE_TOPIC = "/face_detect"


class FakeDetector:
    def __init__(self, faces: list[FaceDetection] | None = None) -> None:
        self.faces: list[FaceDetection] = faces or []
        self.calls: list[np.ndarray] = []

    def detect(self, image: np.ndarray) -> list[FaceDetection]:
        self.calls.append(image)
        return self.faces


def face(
    confidence: float = 0.9,
    nose: tuple[float, float] = (0.5, 0.5),
    bbox: tuple[float, float, float, float] = (0.25, 0.25, 0.5, 0.5),
) -> FaceDetection:
    return FaceDetection(confidence=confidence, nose=nose, bbox=bbox)


def jpeg_frame(width: int = 320, height: int = 320) -> dict[str, object]:
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", arr)
    assert ok
    return {"format": "image/jpeg", "data": buf.tobytes()}


def wait_for(pred: Callable[[], bool], timeout: float = 2.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pred():
            return True
        time.sleep(0.005)
    return bool(pred())


@pytest.fixture
def bus():
    b = Bus()
    b.state_topic(CAMERA_TOPIC, history=4)
    yield b
    b.stop()


@pytest.fixture
def events(bus: Bus):
    received: list[dict[str, object]] = []
    bus.subscribe(EVENT_TOPIC, lambda m: received.append(m), mode="event")
    return received


def reading(bus: Bus) -> FaceDetectMessage:
    msg = bus.topic(FACE_TOPIC).current()
    assert msg is not None
    return FaceDetectMessage.model_validate(msg)


class TestFaceTopic:
    def test_face_topic_is_state_topic_with_history_4(self, bus: Bus) -> None:
        node = FaceNode(bus, detector=FakeDetector())
        node.startup()
        topic = bus.topic(FACE_TOPIC)
        assert topic.topic_type == "state"
        assert topic.history_limit == 4


class TestTick:
    def test_skip_when_no_frame(self, bus: Bus, events: list[dict[str, object]]) -> None:
        node = FaceNode(bus, detector=FakeDetector())
        node.startup()
        node.tick()
        assert bus.topic(FACE_TOPIC).current() is None
        assert events == []

    def test_centred_face_zero_offset(self, bus: Bus, events: list[dict[str, object]]) -> None:
        node = FaceNode(bus, detector=FakeDetector([face()]))
        node.startup()
        bus.publish(CAMERA_TOPIC, jpeg_frame())
        node.tick()
        msg = reading(bus)
        assert msg.present is True
        assert msg.x == 0.0
        assert msg.y == 0.0
        assert msg.size == 0.25
        assert msg.confidence == 0.9
        assert msg.bbox == (0.25, 0.25, 0.5, 0.5)

    def test_offset_to_edges(self, bus: Bus, events: list[dict[str, object]]) -> None:
        node = FaceNode(
            bus,
            detector=FakeDetector(
                [face(confidence=0.9, nose=(1.0, 0.0), bbox=(0.0, 0.0, 1.0, 1.0))]
            ),
        )
        node.startup()
        bus.publish(CAMERA_TOPIC, jpeg_frame())
        node.tick()
        msg = reading(bus)
        assert msg.x == pytest.approx(1.0)
        assert msg.y == pytest.approx(-1.0)
        assert msg.size == pytest.approx(1.0)
        assert msg.bbox == (0.0, 0.0, 1.0, 1.0)

    def test_selects_strongest_face(self, bus: Bus, events: list[dict[str, object]]) -> None:
        low = face(confidence=0.3, nose=(0.1, 0.5))
        high = face(confidence=0.8, nose=(0.9, 0.5))
        node = FaceNode(bus, detector=FakeDetector([low, high]))
        node.startup()
        bus.publish(CAMERA_TOPIC, jpeg_frame())
        node.tick()
        msg = reading(bus)
        assert msg.confidence == 0.8
        assert msg.x == pytest.approx(0.8)
        assert msg.bbox == (0.25, 0.25, 0.5, 0.5)

    def test_below_threshold_is_no_face(self, bus: Bus, events: list[dict[str, object]]) -> None:
        node = FaceNode(bus, detector=FakeDetector([face(confidence=0.4)]))
        node.startup()
        bus.publish(CAMERA_TOPIC, jpeg_frame())
        node.tick()
        msg = reading(bus)
        assert msg.present is False
        assert msg.x == 0.0
        assert msg.confidence == 0.0
        assert msg.bbox == (0.0, 0.0, 0.0, 0.0)

    def test_no_faces_yields_zero_message(self, bus: Bus, events: list[dict[str, object]]) -> None:
        node = FaceNode(bus, detector=FakeDetector([]))
        node.startup()
        bus.publish(CAMERA_TOPIC, jpeg_frame())
        node.tick()
        msg = reading(bus)
        assert msg == FaceDetectMessage()

    def test_detector_receives_decoded_frame(self, bus: Bus, events: list[dict[str, object]]) -> None:
        detector = FakeDetector([])
        node = FaceNode(bus, detector=detector)
        node.startup()
        bus.publish(CAMERA_TOPIC, jpeg_frame())
        node.tick()
        assert len(detector.calls) == 1
        assert detector.calls[0].shape == (320, 320, 3)


class TestEdgeEvents:
    def test_first_face_fires_detected(self, bus: Bus, events: list[dict[str, object]]) -> None:
        node = FaceNode(bus, detector=FakeDetector([face()]))
        node.startup()
        bus.publish(CAMERA_TOPIC, jpeg_frame())
        node.tick()
        assert wait_for(lambda: len(events) == 1)
        assert events[0] == {"type": "face", "message": "Face detected at 0.0, 0.0: confidence 0.9"}

    def test_fire_once_per_transition(self, bus: Bus, events: list[dict[str, object]]) -> None:
        detector = FakeDetector([])
        node = FaceNode(bus, detector=detector)
        node.startup()
        frame = jpeg_frame()

        bus.publish(CAMERA_TOPIC, frame)
        node.tick()

        detector.faces = [face()]
        bus.publish(CAMERA_TOPIC, frame)
        node.tick()
        node.tick()

        detector.faces = []
        bus.publish(CAMERA_TOPIC, frame)
        node.tick()

        assert wait_for(lambda: len(events) == 2)
        assert [e["message"] for e in events] == [
            "Face detected at 0.0, 0.0: confidence 0.9",
            "Face lost",
        ]
        assert all(e["type"] == "face" for e in events)

    def test_no_event_on_steady_face(self, bus: Bus, events: list[dict[str, object]]) -> None:
        node = FaceNode(bus, detector=FakeDetector([face()]))
        node.startup()
        frame = jpeg_frame()
        bus.publish(CAMERA_TOPIC, frame)
        node.tick()
        node.tick()
        node.tick()
        assert wait_for(lambda: len(events) == 1)
        assert len(events) == 1


class TestBadFrames:
    def test_invalid_message_skips(self, bus: Bus, events: list[dict[str, object]]) -> None:
        node = FaceNode(bus, detector=FakeDetector([face()]))
        node.startup()
        bus.publish(CAMERA_TOPIC, {"data": 123})
        node.tick()
        assert bus.topic(FACE_TOPIC).current() is None
        assert events == []

    def test_undecodable_data_skips(self, bus: Bus, events: list[dict[str, object]]) -> None:
        node = FaceNode(bus, detector=FakeDetector([face()]))
        node.startup()
        bus.publish(CAMERA_TOPIC, {"format": "image/jpeg", "data": b"not an image"})
        node.tick()
        assert bus.topic(FACE_TOPIC).current() is None
        assert events == []

    def test_last_good_reading_retained_after_bad_frame(
        self, bus: Bus, events: list[dict[str, object]]
    ) -> None:
        node = FaceNode(bus, detector=FakeDetector([face()]))
        node.startup()
        bus.publish(CAMERA_TOPIC, jpeg_frame())
        node.tick()
        before = reading(bus)
        bus.publish(CAMERA_TOPIC, {"data": 123})
        node.tick()
        assert reading(bus) == before


class TestLazyDetector:
    def test_default_detector_constructed_in_startup(self, bus: Bus) -> None:
        node = FaceNode(bus)
        assert node.detector is None
        node.startup()
        assert isinstance(node.detector, YuNetDetector)
