import readline

from audio_base.asr_node import ASRNode
from dros import Bus, Node, ServerTransport
from messages.events import EventMessage


class EventLogNode(Node):
    def __init__(self, bus):
        super().__init__(bus)
        self.subscribe_event("/events")
    
    def process(self, message):
        try:
            event = EventMessage.model_validate(message)
            print(f"Event {event.type}: {event.message}")
        except Exception:
            print("Event channel received:", message)

def main():
    bus = Bus(transport=ServerTransport(port=5000))  
    EventLogNode(bus)
    ASRNode(bus, topic="/audio_stream", output_topic="/text_stream")
    bus.run()

if __name__ == "__main__":
    main()
