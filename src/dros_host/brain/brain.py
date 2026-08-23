from enum import Enum
from time import time

from dros import Bus, DrosLogger, Node

from dros_host.messages.events import EVENT_TOPIC, EventPublisherMixin
from dros_host.messages.face import FaceDetectMessage
from dros_host.messages.robot import EyeMessage, NeckControlMessage, NeckPositionMessage

logger = DrosLogger("brain_node")
logger.setLevel("DEBUG")

class BrainMode(Enum):
    ASLEEP = "asleep"
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    WORKING = "working"

CAMERA_TOPIC = "/marvin/camera"
HEADING_TOPIC = "/marvin/dist_heading"
NECK_CONTROL_TOPIC = "/marvin/neck"
NECK_POSITION_TOPIC = "/marvin/neck_position"
FACE_TOPIC = "/face_detect"
EYE_TOPIC = "/marvin/eyes"

class BrainNode(EventPublisherMixin, Node):
    def __init__(
        self,
        bus: Bus,
        tick_interval: float = 0.2,
    ):
        super().__init__(bus=bus, interval=tick_interval)
        self.user_speaking = False
        self.robot_speaking = False
        self.robot_thinking = False
        self.robot_moving = False
        self.mode = BrainMode.ASLEEP
        self.mode_change = time()
        self.tick_actions = []

    def startup(self) -> None:
        """Initialize the BrainNode."""
        self.camera = self.bus.topic(CAMERA_TOPIC)
        self.heading = self.bus.topic(HEADING_TOPIC)
        self.face = self.bus.topic(FACE_TOPIC)
        self.subscribe_event(EVENT_TOPIC, self.event_callback)
        self.subscribe_event(NECK_POSITION_TOPIC, self.neck_callback)
        self.neck_position_topic = self.bus.state_topic(NECK_POSITION_TOPIC, history=1)
        self.publish(NECK_CONTROL_TOPIC, NeckControlMessage(pan=0.0, tilt=0.0).model_dump())
        # Debug
        print(f"face topic = {self.face.name}: {self.face.topic_type} ({self.face.history_limit})")
        logger.info(f"BrainNode started in mode: {self.mode.value}")

    def event_callback(self, message: dict) -> None:
        """Use events to detect changes in state"""
        event_type = message.get("type", "generic")
        event_message = message.get("message", "")

        # Voice detection events
        if event_type == 'vad':
            if event_message == 'voice start':
                self.user_speaking = True
            elif event_message == 'voice end':
                self.user_speaking = False
            logger.info(f"User speaking state updated: {self.user_speaking}") 

        # TTS events
        if event_type == 'tts':
            if event_message == 'synthesis start':
                self.robot_speaking = True
            elif event_message == 'synthesis end':
                self.robot_speaking = False
            logger.info(f"Robot speaking state updated: {self.robot_speaking}")

        # LLM events
        if event_type == 'llm':
            if event_message == 'thinking start':
                self.robot_thinking = True
            elif event_message == 'thinking end':
                self.robot_thinking = False
            logger.info(f"Robot thinking state updated: {self.robot_thinking}")

        # Motor events
        if event_type == 'motor':
            if event_message == 'motor start':
                self.robot_moving = True
            elif event_message == 'motor stop':
                self.robot_moving = False
            logger.info(f"Robot moving state updated: {self.robot_moving}")

    def neck_callback(self, message: dict) -> None:
        """Update the neck position based on reported position. NOOP since it's a state topic."""
        pass

    def set_mode(self, new_mode: BrainMode) -> None:
        """Set the brain mode and publish an event if it changes."""
        if new_mode != self.mode:
            self.mode = new_mode
            self.mode_change = time()
            self.publish_event(self.mode.value, event_type="brain_mode")
            logger.info(f"Brain mode changed to {self.mode.value}")

    def tick(self) -> None:
        """Main loop for the BrainNode."""
        mode_was = self.mode
        self._default_mode_transitions()
        if mode_was != self.mode:  # noqa: SIM102
            if self.mode == BrainMode.LISTENING and self._action_turn_to_face not in self.tick_actions:
                logger.info("Starting turn to face")
                self.tick_actions.append(self._action_turn_to_face)
        for action in self.tick_actions:
            action()

    def _default_mode_transitions(self) -> None:
        """Default mode transitions based on time and events."""
        if self.mode != BrainMode.WORKING:
            if self.mode in [BrainMode.ASLEEP, BrainMode.IDLE] and self.user_speaking:
                self.set_mode(BrainMode.LISTENING)                
            elif self.mode == BrainMode.LISTENING and not self.user_speaking:
                self.set_mode(BrainMode.IDLE)

            if self.mode != BrainMode.SPEAKING and self.robot_speaking:
                self.set_mode(BrainMode.SPEAKING)
            elif self.mode == BrainMode.SPEAKING and not self.robot_speaking:
                self.set_mode(BrainMode.IDLE)

            if self.mode != BrainMode.THINKING and self.robot_thinking:
                self.set_mode(BrainMode.THINKING)
            elif self.mode == BrainMode.THINKING and not self.robot_thinking:
                self.set_mode(BrainMode.IDLE)

            if self.mode == BrainMode.IDLE and time() - self.mode_change > 15:
                self.set_mode(BrainMode.ASLEEP)
                self.tick_actions.clear()
                self.publish(EYE_TOPIC, EyeMessage(open=False).model_dump())

    FACE_HYSTERESIS = 0.1  # Minimum change in face position to trigger neck movement

    def _action_turn_to_face(self) -> None:
        """Turn the robot's head to face the detected face."""
        face_msg = self.face.current()
        if face_msg:
            face = FaceDetectMessage.model_validate(face_msg)
            if face.present:
                x = face.x
                y = face.y
                if abs(x) > self.FACE_HYSTERESIS or abs(y) > self.FACE_HYSTERESIS:
                    neck_msg = self.neck_position_topic.current()
                    if neck_msg is not None:
                        neck = NeckPositionMessage.model_validate(neck_msg)
                        pan = neck.pan + x * 40
                        tilt = neck.tilt - y * 40
                        self.publish(NECK_CONTROL_TOPIC, NeckControlMessage(pan=pan, tilt=tilt, speed=1200).model_dump())
                        return
            else:
                logger.info("Lost face detection probably while moving, wait to reappear")
                return
        logger.info("Exiting turn to face action")
        self.tick_actions.remove(self._action_turn_to_face)
