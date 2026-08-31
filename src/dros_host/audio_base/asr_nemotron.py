from dros_host.audio_base.asr_base_node import ASRBaseNode
from transformers import pipeline

class ASRNemotron(ASRBaseNode):
    def __init__(self, bus, topic="/audio_stream", output_topic="/text_stream", model="nvidia/nemotron-speech-streaming-en-0.6b"):
        super().__init__(bus, topic, output_topic)
        self.model = model

    def startup(self):
        self.pipe = pipeline("automatic-speech-recognition", model=self.model, max_new_tokens=64)
        super().startup()

    def transcribe_buffer(self, buffer) -> str:
        out = self.pipe(buffer, max_new_tokens=64)
        return out["text"]