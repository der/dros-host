import readline

from dros_host.audio_base.asr_node import ASRNode
from dros_host.audio_base.tts_node import TTSNode
from dros_host.audio_base.player_node import AudioPlayerNode
from dros import Bus, DrosLogger, Node, ServerTransport
from dros_host.llm_support.llm_node import LLMNode
from dros_host.messages.events import EventMessage

logger = DrosLogger("events")

class EventLogNode(Node):
    def __init__(self, bus):
        super().__init__(bus)
        self.subscribe_event("/events")
    
    def process(self, message):
        try:
            event = EventMessage.model_validate(message)
            logger.info(f"Event {event.type}: {event.message}")
        except Exception:
            logger.info(f"Event channel received: {message}")

def main():
    bus = Bus(transport=ServerTransport(port=5000))  
    EventLogNode(bus)
#    ASRNode(bus, topic="/audio_stream", output_topic="/text_stream")
#    LLMNode(bus, text_topic="/text_stream", response_topic="/llm_response", model_name="gemma4:26b")
    TTSNode(bus, input_topic="/text_stream", output_topic="/speech_stream")
    AudioPlayerNode(bus, topic="/speech_stream", device_index=-1)
    bus.run()

if __name__ == "__main__":
    main()
