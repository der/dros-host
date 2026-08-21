from enum import Enum
from time import time

from dros import Bus, DrosLogger, Node
from dros_host.messages.events import EVENT_TOPIC, EventPublisherMixin
from dros_host.messages.robot import EyeMessage

logger = DrosLogger("brain_node")

class BrainMode(Enum):
    ASLEEP = "asleep"
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    WORKING = "working"

class BrainNode(EventPublisherMixin, Node):
    def __init__(
        self,
        bus: Bus,
        camera_topic: str = "/marvin/camera",
        heading_topic: str = "/marvin/dist_heading",
        neck_topic: str = "/marvin/neck",
        face_topic: str = "/face_detect",
        tick_interval: float = 0.2,
    ):
        super().__init__(bus=bus, interval=tick_interval)
        self.camera = bus.topic(camera_topic)
        self.heading = bus.topic(heading_topic)
        self.neck = bus.topic(neck_topic)
        self.face = bus.topic(face_topic)
        self.subscribe_event(EVENT_TOPIC, self.event_callback)
        self.user_speaking = False
        self.robot_speaking = False
        self.robot_thinking = False
        self.mode = BrainMode.ASLEEP
        self.mode_change = time()

    def startup(self) -> None:
        """Initialize the BrainNode."""
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

    def set_mode(self, new_mode: BrainMode) -> None:
        """Set the brain mode and publish an event if it changes."""
        if new_mode != self.mode:
            self.mode = new_mode
            self.mode_change = time()
            self.publish_event(self.mode.value, event_type="brain_mode")
            logger.info(f"Brain mode changed to {self.mode.value}")

    def tick(self) -> None:
        """Main loop for the BrainNode."""
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
                self.publish("/marvin/eyes", EyeMessage(open=False).model_dump())
