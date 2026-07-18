from pydantic import BaseModel

class EventMessage(BaseModel):
    """Message format for general events."""
    type: str = "generic"
    message: str
