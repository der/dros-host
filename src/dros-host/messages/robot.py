# Messages for interacting with Marvin

from pydantic import BaseModel

class EyeMessage(BaseModel):
    """Message format for eye control commands."""
    open: bool = True
    wide: bool = False
    x: float = 0.0

class NeckControlMessage(BaseModel):
    """Message format for neck control commands."""
    pan: float = 0.0
    tilt: float = 0.0
    speed: int = 2000
