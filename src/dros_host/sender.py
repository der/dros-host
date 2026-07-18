import ast
import re
import readline

from dros import Bus, ClientTransport, SourceNode


class KeyboardEchoNode(SourceNode):
    def __init__(self, bus, topic="/events"):
        super().__init__(bus)
        self._topic = topic

    def _parse_payload(self, command: str) -> dict:
        try:
            payload = ast.literal_eval(command)
            if isinstance(payload, dict) and all(
                isinstance(k, str) for k in payload
            ) and all(isinstance(v, str | int | float | bool) for v in payload.values()):
                return payload
        except (SyntaxError, ValueError):
            pass
        return {"message": command}

    def _parse_topic_and_command(self, command: str) -> tuple[str, str]:
        match = re.match(r"^\s*topic\s*=(\S+)(?:\s+(.*))?$", command)
        if match:
            topic = match.group(1)
            remaining_command = match.group(2) or ""
            return topic, remaining_command
        return "/events", command

    def run(self):
        """
        Wait for keyboard input and echo it back as a message
        Can prefix with "topic=<topic>" to specify a topic, otherwise defaults to "/events"
        Can send a dictionary as a string to specify a payload, otherwise defaults to {"message": "<input>"}
        """
        command = input("Enter command: ")
        topic, payload_command = self._parse_topic_and_command(command)
        self.publish(topic or self._topic, self._parse_payload(payload_command)) 

    def shutdown(self):
        print("Shutting down KeyboardEchoNode...")
        self.bus.unsubscribe(self._topic, self.process)
        super().shutdown()

def main():
    bus = Bus(transport=ClientTransport("http://localhost:5000"))
    KeyboardEchoNode(bus)
    bus.run()


if __name__ == "__main__":
    main()
