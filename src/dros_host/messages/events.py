from pydantic import BaseModel

EVENT_TOPIC = "/events"

class EventMessage(BaseModel):
    """Message format for general events."""
    type: str = "generic"
    message: str


class EventPublisherMixin:
    """Mixin to add event publishing capability to Node subclasses."""

    def publish_event(self, message: str, event_type: str = "generic") -> None:
        """Publish an event to the EVENT_TOPIC.

        Args:
            message: The event message text.
            event_type: The type of event (default: "generic").
        """
        self.publish(EVENT_TOPIC, {"type": event_type, "message": message}) # type: ignore
