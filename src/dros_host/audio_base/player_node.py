"""Audio player node for Marvin speech project.

Ported to DROS. Subscribes to audio room and plays through
default speaker using PyAudio.
"""

import os

import numpy as np
import pyaudio
from queue import Empty, Queue

from dros import Bus, Node, DrosLogger
from dros_host.messages.audio import AudioMessage

logger = DrosLogger("player_node")

class AudioPlayerNode(Node):
    def __init__(
        self,
        bus: Bus,
        topic: str = "/audio_stream",
        device_index: int = 0,
        buffer_size: int = 64,
    ):
        super().__init__(bus=bus)
        self.topic = topic
        self.device_index = device_index
        self.buffer_size = buffer_size

        # Audio state
        self.sample_rate = 16000
        self.channels = 1
        self.chunk_size = 512
        self.format: str = ""
        self.config_received = False

        # PyAudio
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.is_playing = False

        # Buffering
        self.audio_queue: Queue = Queue(maxsize=self.buffer_size)
        self.chunks_received = 0
        self.chunks_played = 0
        self.buffer_underruns = 0

    def startup(self):
        super().startup()
        self.subscribe_stream(self.topic, self.audio_chunk_callback)
        logger.info(f"Audio player node initialized for topic {self.topic}")

    def audio_chunk_callback(self, message: dict):
        """Handle incoming audio chunk messages."""
        self.chunks_received += 1
        amsg = AudioMessage.model_validate(message)

        fmt = amsg.info.format
        if fmt != self.format:
            logger.info(
                f"Audio format set to: {fmt}, "
                f"{amsg.info.sample_rate}Hz, {amsg.info.num_channels}ch, "
                f"{amsg.info.chunk_size} samples/chunk"
            )
            self.format = fmt
            self.sample_rate = amsg.info.sample_rate
            self.channels = amsg.info.num_channels
            self.chunk_size = amsg.info.chunk_size

            # Reinitialize audio stream with new format
            if self.stream is not None:
                self._cleanup_stream()
            self._init_audio_stream()
            self.config_received = True

        # Convert to numpy
        int16_list = amsg.data.int16_data
        if not int16_list:
            return
        audio_data = np.array(int16_list, dtype=np.int16, copy=True)

        # Test for events
        if amsg.event:
            logger.info(f"Received audio event: {amsg.event}")

        # Try to add to queue
        try:
            self.audio_queue.put_nowait(audio_data.tobytes())
        except Exception:
            # Queue is full, drop the oldest chunk
            try:
                self.audio_queue.get_nowait()
                self.audio_queue.put_nowait(audio_data.tobytes())
                self.buffer_underruns += 1
            except Empty:
                pass

    def _init_audio_stream(self):
        """Initialize the audio output stream."""
        try:
            device_index = self.device_index if self.device_index >= 0 else None

            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                output=True,
                frames_per_buffer=self.chunk_size,
                output_device_index=device_index,
                stream_callback=self._audio_callback,
            )

            self.stream.start_stream()
            self.is_playing = True
            logger.info("Audio output stream started successfully")

        except Exception as e:
            logger.error(f"Failed to initialize audio stream: {e}")
            self.is_playing = False

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback function for playing audio chunks."""
        if status:
            logger.warning(f"Audio stream status: {status}")

        try:
            audio_data = self.audio_queue.get_nowait()
            self.chunks_played += 1
            return (audio_data, pyaudio.paContinue)
        except Empty:
            # No audio data available, return silence
            silence = b"\x00" * (frame_count * self.channels * 2)
            return (silence, pyaudio.paContinue)

    def _cleanup_stream(self):
        """Clean up the audio stream."""
        if self.stream is not None:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
            self.is_playing = False
    
    def shutdown(self):
        """Shutdown the audio player node."""
        self._cleanup_stream()
        if self.audio is not None:
            self.audio.terminate()
        logger.info("Audio player node shutdown complete")

    def _log_status(self):
        """Log periodic status information."""
        queue_size = self.audio_queue.qsize()
        status = "playing" if self.is_playing else "stopped"
        logger.info(
            f"Audio player status: {status}, "
            f"queue: {queue_size}/{self.buffer_size}, "
            f"received: {self.chunks_received}, "
            f"played: {self.chunks_played}, "
            f"underruns: {self.buffer_underruns}"
        )
