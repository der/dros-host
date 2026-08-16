from pydantic import BaseModel


class FaceDetectMessage(BaseModel):
    """State message published to /face_detect.

    ``x``/``y`` are the signed offset of the nose tip from frame centre,
    normalized to half-frame (range [-1, 1]). ``size`` is the normalized face
    bounding-box area (range [0, 1]). ``bbox`` is the selected face's
    normalized (x, y, w, h) bounding box with top-left origin. When no face is
    present all numeric fields are zero.
    """

    present: bool = False
    x: float = 0.0
    y: float = 0.0
    size: float = 0.0
    confidence: float = 0.0
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
