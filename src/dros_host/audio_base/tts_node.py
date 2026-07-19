"""TTS node for Marvin speech project.

Ported to DROS. Subscribes to text_stream room and publishes
synthesised audio chunks to speech_stream using pocket-tts in streaming mode.
"""

import os
import threading
from queue import Empty, Queue

import numpy as np
from pocket_tts import TTSModel
from scipy.signal import resample_poly

from dros import Bus, Node, DrosLogger
from dros_host.messages.events import EVENT_TOPIC, EventMessage, EventPublisherMixin
from dros_host.messages.audio import AudioMessage, AudioData, AudioInfo

logger = DrosLogger("tts_node")

# Sentinel value to signal end of synthesis
_SENTINEL = object()


class TTSNode(EventPublisherMixin, Node):
    def __init__(
        self,
        bus: Bus,
        input_topic: str = "/text_stream",
        output_topic: str = "/speech_stream",
        voice: str = "alba",
    ):
        super().__init__(bus=bus)
        self.input_topic = input_topic
        self.output_topic = output_topic
        self.voice_path = voice

        # TTS model settings
        self.tts_sample_rate = 24000
        self.output_sample_rate = 16000
        self.chunk_size = 1280  # 80ms at 16kHz
        self.voice_state = None
        self.is_running = False
        self.stop = False

    def startup(self):
        super().startup()

        logger.info("Loading pocket_tts model...")
        self.tts_model = TTSModel.load_model()
        self.tts_sample_rate = self.tts_model.sample_rate
        logger.info(f"pocket_tts model loaded (sample_rate={self.tts_sample_rate})")

        # Load voice
        logger.info(f"Loading voice: {self.voice_path}")
        self.voice_state = self.tts_model.get_state_for_audio_prompt(self.voice_path)
        logger.info("Voice loaded")

        self.subscribe_event(EVENT_TOPIC, self.event_callback)
        self.subscribe_stream(self.input_topic, self.text_callback)
        logger.info(f"TTS node initialized: {self.input_topic} -> {self.output_topic}")

    def text_callback(self, message: dict):
        """Queue incoming text for synthesis."""
        text = message.get("message", "")
        text = text.strip()
        if text:
            logger.info(f"Received text for synthesis: {text}")
            self.stop = False
            self._synthesize(text)  # Running in thread on stream queue

    def event_callback(self, message: dict):
        msg = EventMessage.model_validate(message)
        if msg.message in ("interrupt", "stop"):
            logger.info("Interrupt event received, stopping synthesis")
            if self.is_running:
                self.stop = True
            # TODO clear input text message queue - needs framework extension

    def _synthesize(self, text: str):
        """Chunked generation of audio messages from the TTS model."""
        chunk_index = 0
        self.is_running = True
        for audio_tensor in self.tts_model.generate_audio_stream(
            self.voice_state, text
        ):
            if self.stop:
                chunk_samples = self.chunk_size
                audio_buffer = np.zeros(chunk_samples, dtype=np.int16)
            else:
                # Resample 24kHz -> 16kHz (ratio 2/3)
                audio_f32 = audio_tensor.numpy().astype(np.float32)
                audio_16k = resample_poly(audio_f32, 2, 3).astype(np.float32)

                # Convert float32 [-1, 1] to int16
                audio_buffer = np.clip(audio_16k, -1.0, 1.0)
                audio_buffer = (audio_buffer * 32767).astype(np.int16)
                chunk_samples = len(audio_buffer)

            msg = AudioMessage(
                info=AudioInfo(
                    num_channels=1,
                    sample_rate=self.output_sample_rate,
                    chunk_size=chunk_samples,
                    format=f"16kmono-{chunk_samples}",
                ),
                data=AudioData(int16_data=audio_buffer.tolist()),
                event="break" if self.stop else "",
            )
            self.publish(self.output_topic, msg.model_dump())
            chunk_index += 1

            if self.stop:
                logger.info("TTS synthesis stopped mid-stream")
                self.is_running = False
                break

        self.is_running = False
        logger.info(f"Synthesis complete: {chunk_index} chunks generated")
