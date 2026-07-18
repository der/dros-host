"""ASR node for Marvin speech project.

Ported from ROS2 to socket.io. Subscribes to audio_stream room and publishes
transcriptions to text_stream room using pywhispercpp.
"""

import argparse
import asyncio
import contextlib
import logging
import os
import threading
import time
from queue import Empty, Queue

import numpy as np
from dros import Bus, SourceNode, DrosLogger
from dros_host.messages.audio import AudioMessage
from pywhispercpp.model import Model

logger = DrosLogger("asr_node")


class ASRNode(SourceNode):
    def __init__(
        self,
        bus: Bus,
        topic: str = "/audio_stream",
        output_topic: str = "/text_stream",
        model_name: str = "large-v3-turbo-q5_0",
    ):
        super().__init__(bus=bus)
        self.topic = topic
        self.output_topic = output_topic
        self.model_name = model_name

        # Audio state
        self.sample_rate = 16000
        self.channels = 1
        self.chunk_size = 512
        self.format: str = ""

        # Buffer for accumulating audio
        self.buffer: np.ndarray= np.zeros(30 * self.sample_rate, dtype=np.float32)
        self.buffer_index = 0
        self.buffer_lock = threading.Lock()
        self.buffer_ready_event = threading.Event()

    def startup(self):
        super().startup()
        logger.info(f'Loading Whisper model "{self.model_name}"...')
        self.model: Model = Model(self.model_name)
        logger.info(f'Whisper model "{self.model_name}" loaded successfully')
        self.subscribe_stream(self.topic, self.audio_chunk_callback)

    def reset_buffer(self):
        with self.buffer_lock:
            self.buffer = np.zeros(30 * self.sample_rate, dtype=np.float32)
            self.buffer_index = 0

    def append_to_buffer(self, audio_data):
        with self.buffer_lock:
            if self.buffer_index + len(audio_data) > len(self.buffer):
                return False
            self.buffer[self.buffer_index : self.buffer_index + len(audio_data)] = audio_data
            self.buffer_index += len(audio_data)
            return True

    def run(self):
        """Await complete utterances and transcribe them."""
        logger.info("ASR node is running and awaiting audio chunks...")
        while  self._source_running.is_set():
            self.buffer_ready_event.wait()
            self.buffer_ready_event.clear()
            with self.buffer_lock:
                if self.buffer_index == 0:
                    continue
                buffer = self.buffer[: self.buffer_index].copy()
            self.reset_buffer()

            def segment_callback(segment):
                text = segment.text
                logger.info(f"Transcribed segment: {text}")
                self.publish(self.output_topic, {"message": text})
                self.publish("/events", {"type": "asr", "message": text})

            self.model.transcribe(buffer, new_segment_callback=segment_callback)

    def audio_chunk_callback(self, message: dict):
        """Handle incoming audio chunk messages."""
        msg = AudioMessage(**message)
        
        fmt = msg.info.format
        if fmt != self.format:
            logger.info(
                f"Audio format set to: {fmt}, "
                f"{msg.info.sample_rate}Hz, {msg.info.num_channels}ch, "
                f"{msg.info.chunk_size} samples/chunk"
            )
            self.format = fmt
            self.sample_rate = msg.info.sample_rate
            self.channels = msg.info.num_channels
            self.chunk_size = msg.info.chunk_size

        # Convert to numpy array
        if not msg.data.int16_data:
            return
        audio_data = np.array(msg.data.int16_data, dtype=np.int16).astype(np.float32) / 32768.0

        if msg.event == "start_utterance":
            logger.info("Start of utterance detected")
            self.reset_buffer()
            self.append_to_buffer(audio_data)
        elif msg.event == "end_utterance":
            logger.info("End of utterance detected")
            self.append_to_buffer(audio_data)
            self.buffer_ready_event.set()
        else:
            if not self.append_to_buffer(audio_data):
                logger.warning("Audio buffer overflow, processing current buffer")
                self.buffer_ready_event.set()
