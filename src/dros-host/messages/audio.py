"""Audio message models matching the ROS2 audio_msg definitions."""

from pydantic import BaseModel


class AudioInfo(BaseModel):
    """Audio stream info header. Matches audio_msg/AudioInfo.msg."""

    num_channels: int = 1
    sample_rate: int = 16000
    chunk_size: int = 512
    format: str = "16kmono"


class AudioData(BaseModel):
    """Audio payload data. Matches audio_msg/AudioData.msg."""

    float32_data: list[float] = []
    int16_data: list[int] = []


class AudioMessage(BaseModel):
    """Complete audio message. Matches audio_msg/Audio.msg."""

    info: AudioInfo = AudioInfo()
    data: AudioData = AudioData()
    event: str = ""
