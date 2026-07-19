"""LLM node for Marvin speech project.

Ported to DROS. Subscribes to text_stream room and responds
on llm_response room using pydantic_ai with Ollama.
"""

import re
from datetime import datetime

from dros import Bus, DrosLogger, Node
from dros_host.messages.events import EVENT_TOPIC, EventMessage, EventPublisherMixin
from pydantic_ai import Agent, BinaryContent, SystemPromptPart
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles import ModelProfile
from pydantic_ai.providers.ollama import OllamaProvider

logger = DrosLogger("llm_node")

# Matches the position just after sentence-ending punctuation followed by whitespace
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

# Tools for use by the agent, extract to separate file if this grows
def get_time() -> str:
    """Get the current date and time.
       If asked the time always call this fresh, don't rely on your previous answer, since time is always changing."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class LLMNode(EventPublisherMixin, Node):
    def __init__(
        self,
        bus: Bus,
        text_topic: str = "text_stream",
        response_topic: str = "llm_response",
        model_name: str = "gemma4:26b",
    ):
        super().__init__(bus=bus)
        self.text_topic = text_topic
        self.response_topic = response_topic
        self.model_name = model_name
        self.messages: list[ModelMessage] | None = None

        self.is_running = False
        self.stop = False

    def startup(self):
        """Initialize the LLM agent."""
        self.subscribe_event(EVENT_TOPIC)
        self.subscribe_stream(self.text_topic, self.message_callback)
        if self.model_name.startswith("gemma4"):
            ollama_model = OpenAIChatModel(
                model_name=self.model_name,
                provider=OllamaProvider(base_url="http://localhost:11434/v1"),
                profile=ModelProfile(
                    supports_thinking=True,
                    thinking_tags=("<|channel>thought", "<channel|>"),
                ),
            )
        else:
            ollama_model = OpenAIChatModel(
                model_name=self.model_name,
                provider=OllamaProvider(base_url="http://localhost:11434/v1"),
            )

        def move_neck(pan: int, tilt: int) -> None:
            """Move your robot neck to the specified pan and tilt positions.
            These are values between -100 and 100 representing the percentage 
            of the full range of motion in each direction. 
            Positive tilts are up, negative are down."""
            logger.info(f"Moving neck to pan: {pan}, tilt: {tilt}")
            self.publish("/marvin/neck", {"pan": pan, "tilt": tilt, "speed": 1000})
            return None
        
        def move_robot(speed: int = 50, dir: str = 'f', dist: int | None = 50) -> None:
            """Move your robot at the specified speed and direction for an optional distance.
            Speed is a percentage from 0 to 100. Direction can be 'f' for forward, 'b' for backward, 
            'sl'/'sr' for slide left/right, 'rl'/'rr' for rotate left/right, 'tr'/'tl' for turn right/left while moving forward, or 's' for stop.
            Distance is how far to move in centimeters, for rotations use a small value like 20."""
            logger.info(f"Moving motor with speed: {speed}, direction: {dir}, distance: {dist}")
            self.publish("/marvin/motor", {"speed": speed, "dir": dir, "dist": dist})
            return None
        
        # async def get_view() -> BinaryContent | str:
        #     """Get a description of what you see through your camera."""
        #     logger.info("Getting view from camera")
        #     image_data = self.call("/marvin/camera-rpc", {"resolution": "full"})
        #     if image_data is None:
        #         logger.error("No response from camera server")
        #         return "I couldn't get a view from the camera."
        #     elif "error" in image_data and image_data["error"]:
        #         logger.error(f"Camera server error: {image_data['error']}")
        #         return "I couldn't get a view from the camera."
        #     elif "data" in image_data and image_data["data"]:
        #         logger.info("Received image data from camera")
        #         format = image_data.get("format", "image/jpeg")
        #         return BinaryContent(data=image_data["data"], media_type=format)
        #     else:
        #         logger.error(f"Unexpected camera response: {image_data}")
        #         return "I couldn't get a view from the camera."

        
        self.agent = Agent(
            ollama_model,
            output_type=str,
            system_prompt=(
                "You are small droid called Marvin with speech, vision and movement capabilities."
                "Respond to questions VERY BRIEFLY in plain text that the droid can speak aloud."
                'If the user just says "Marvin" then respond with "Hi"'
            ),
#            tools=[get_time, move_neck, move_robot, get_view],
            tools=[get_time, move_neck, move_robot],
            model_settings={"thinking": False},
        )

    def event_callback(self, message: dict):
        msg = EventMessage.model_validate(message)
        if msg.message in ("interrupt", "stop"):
            logger.info("Interrupt event received, stopping current LLM response")
            self.stop = True

    def message_callback(self, message: dict):
        logger.info(f"Received message on {self.text_topic}: {message}")
        text = message.get("message", "").strip()
        if not text:
            logger.info("Received empty message, ignoring")
            return
        logger.info(f"Processing message: {text}")

        if re.match(r"^stop[\.!?]*$", text, re.IGNORECASE):
            if self.is_running:
                logger.info("Stop command received, stopping current LLM response")
                self.stop = True
            self.publish_event("stop", "llm-in")
            return

        self._stream_agent(text)

    def _publish(self, text: str):
        text = text.strip()
        if text:
            logger.info(f"LLM response: {text}")
            self.publish(self.response_topic, {"message": text})
            self.publish_event(text, "llm")

    def _stream_agent(self, text: str):
        self.is_running = True
        self.stop = False
        buffer = ""
        try:
            with self.agent.run_stream_sync(text, message_history = self.messages) as response:
                for chunk in response.stream_text(delta=True):
                    if self.stop:
                        logger.info("LLM response streaming stopped")
                        self.stop = False
                        return
                    buffer += chunk
                    # Publish any complete sentences found in the buffer
                    parts = _SENTENCE_SPLIT_RE.split(buffer)
                    # The last element may be an incomplete sentence — keep it in the buffer
                    for sentence in parts[:-1]:
                        self._publish(sentence)
                    buffer = parts[-1]
                if self.messages is None:
                    self.messages = response.all_messages()
                else:
                    self.messages += response.new_messages()
            # Publish any remaining text after streaming completes
            self._publish(buffer)
        finally:
            self.is_running = False
            
    # Legacy to review not used currently, keeping all of history for a run
    async def keep_recent_messages(self, messages: list[ModelMessage]) -> list[ModelMessage]:
        """
        Keep only recent messages while preserving AI model message ordering rules.

        Most AI models require proper sequencing of:
        - Tool/function calls and their corresponding returns
        - User messages and model responses
        - Multi-turn conversations with proper context

        This means we cannot cut conversation history in a way that:
        - Leaves tool calls without their corresponding returns
        - Separates paired messages inappropriately
        - Breaks the logical flow of multi-turn interactions

        Reference: https://github.com/pydantic/pydantic-ai/issues/2050
        """
        message_window = 15

        if len(messages) <= message_window:
            return messages

        # Find system prompt if it exists
        system_prompt = None
        system_prompt_index = None
        for i, msg in enumerate(messages):
            if isinstance(msg, ModelRequest) and any(isinstance(part, SystemPromptPart) for part in msg.parts):
                system_prompt = msg
                system_prompt_index = i
                break

        # Start at target cut point and search backward (upstream) for a safe cut
        target_cut = len(messages) - message_window

        for cut_index in range(target_cut, -1, -1):
            first_message = messages[cut_index]

            # Skip if first message has tool returns (orphaned without calls)
            if any(isinstance(part, ToolReturnPart) for part in first_message.parts):
                continue

            # Skip if first message has tool calls (violates AI model ordering rules)
            if isinstance(first_message, ModelResponse) and any(
                isinstance(part, ToolCallPart) for part in first_message.parts
            ):
                continue

            # Found a safe cut point
            result = messages[cut_index:]

            # If we cut off the system prompt, prepend it back
            if system_prompt is not None and system_prompt_index is not None and cut_index > system_prompt_index:
                result = [system_prompt] + result

            return result

        # No safe cut point found, keep all messages
        return messages
