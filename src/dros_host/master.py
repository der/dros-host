import readline

from dros_host.audio_base.asr_node import ASRNode
from dros_host.audio_base.tts_node import TTSNode
from dros_host.audio_base.player_node import AudioPlayerNode
from dros import Bus, DrosLogger, Node, ServerTransport
from dros_host.llm_support.llm_node import LLMNode
from dros_host.messages.events import EVENT_TOPIC, EventMessage, EventPublisherMixin
from dros_host.messages.image import ImageMessage

logger = DrosLogger("events")
logger.setLevel("DEBUG")

class EventLogNode(EventPublisherMixin, Node):
    def __init__(self, bus):
        super().__init__(bus)
        self.subscribe_event(EVENT_TOPIC)
    
    def process(self, message):
        try:
            event = EventMessage.model_validate(message)
            logger.info(f"Event {event.type}: {event.message}")
        except Exception:
            logger.info(f"Event channel received: {message}")

class CameraNode(Node):
    def __init__(self, bus, topic="/marvin/camera"):
        super().__init__(bus)
        self.topic = topic
        self.bus.state_topic(self.topic, history=4)
        self.subscribe_event(self.topic)

    def process(self, message):
        # image = ImageMessage.model_validate(message)
        # logger.info(f"Camera image received: {len(image.data)} bytes") 
        pass

class EchoEyeNode(Node):
    def __init__(self, bus, topic="/marvin/eyes"):
        super().__init__(bus)
        self.topic = topic
        self.bus.state_topic(self.topic, history=1)
        self.subscribe_event(self.topic)

    def process(self, message):
        # logger.info(f"Echo eye reading: {message}")
        pass

class DistanceSensorNode(Node):
    def __init__(self, bus, topic="/marvin/dist_heading"):
        super().__init__(bus)
        self.topic = topic
        self.bus.state_topic(self.topic, history=4)

    def startup(self):
        self.subscribe_event(self.topic)
        pass

    def process(self, message):
        # logger.info(f"Distance sensor reading: {message}")
        pass

def main():
    bus = Bus(transport=ServerTransport(port=5000, static_dir="src/dros_host/static"))
#    bus = Bus(transport=ServerTransport(port=5000))
    EventLogNode(bus)
    CameraNode(bus, topic="/marvin/camera")
    ASRNode(bus, topic="/audio_stream", output_topic="/text_stream", model_name="large-v3-turbo-q5_0")
    LLMNode(bus, text_topic="/text_stream", response_topic="/llm_response", camera_topic="/marvin/camera", model_name="gemma4:26b")
    TTSNode(bus, input_topic="/llm_response", output_topic="/speech_stream")
#    AudioPlayerNode(bus, topic="/speech_stream", device_index=-1)
    DistanceSensorNode(bus, topic="/marvin/dist_heading")
    EchoEyeNode(bus, topic="/marvin/eyes")
    bus.run()

if __name__ == "__main__":
    main()
