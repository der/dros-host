from dros import Bus, ClientTransport, Node


class LoggerNode(Node):
    def __init__(self, bus):
        super().__init__(bus)
        self.subscribe_event("messages")
    
    def process(self, message):
        print("Received message:", message)

def main():
    bus = Bus(transport=ClientTransport("http://localhost:5000"))
    LoggerNode(bus)
    bus.run()

if __name__ == "__main__":
    main()
