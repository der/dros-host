# DROS-based Marvin host

A set of ROS-like nodes to act at the base station for Marvin the robot.

Builds on DROS (Dave's ROS) which provides the event bus and framework.

## Initial install

```
uv sync --all-extras --dev
. .venv/bin/activate
pip install -e ../dros
pip install .

# To use pywhispercpp GPU support via vulkan (assumes specific vulkan install)
. ~/Tools/vulkan/1.4.341.1/setup-env.sh 
GGML_VULKAN=1 pip install git+https://github.com/absadiki/pywhispercpp
```

## Running

Run master - starts bus and all local nodes

```
master
```

Run sender program for interactively sending messages:

```
sender
```

Example messages:

```
This is an event
topic=/marvin/eyes {"x": 0.0}
topic=/marvin/motor {"speed": 50, "dir": "f"}
topic=/marvin/neck {"pan": 20, "tilt": 50}
```

## Nodes in this master

| Node | Default Input | Default output | What |
|---|---|---|---|
| `ASRNode` | `/audio_stream` | `/text_stream` | Transcribe audio stream (from remote robot) to a text stream |
| `LLMNode` | `/text_stream` `/marvin/camera` | `llm_response` | Take transcribed audio input from robot, plus robot state, and act on it. Generating both actions and response back to user |
| `TTSNode` | `/llm_response` | `/speech_stream` | Convert text response to spoken audio for playing |
| `AudioPlayerNode` | `/speech_stream` | | Optional local play of speech output when robot not in use | 
| `DistanceSensorNode` | `/marvin/dist_heading` | | Capture copy of heading and front ranging information from robot |
| `CameraNode` | `/marvin/camera` | | Capture copy of image stream from robot |
| `EchoEyeNode` | `/marvin/eyes` | | Copy copy of eye state information from robot |
| `EventLogNode` | `/events` | | Log event information which includes input and output speech and robot actions |

## Nodes on the robot

| Node | Default Input | Default output | What |
|---|---|---|---|
| `EyeServer` | `/marvin/eyes` `/events` | `/events` | Set eye state, publishes changes to /events, reacts to voice detection events by waking up |
| `DistanceHeaderServer` | | `/marvin/dist_heading` | Publishes heading the front ranging information |
| `MotorServer` | `/marvin/motor` `/events` | | Controls motors, also stops if sees `stop` event |
| `NeckServer` | `/marvin/neck` | `/events` | Sets neck rotation and pitch, publishes changes to /events |
| `CameraServer` | | `/marvin/camera` | Publishes camera images |
| `VADCapture` | | `/audio_stream` `/events` | Detects voice and publishes voiced audio stream, publishes voice start and end to `/events`  |
| `AudioPlayer` | `/speech_stream` | | Plays audio stream to speaker |


## Dashboard

Web dashboard served as a static file from `src/dros_host/static/dashboard.html` which uses socket.io to directly show camera, event stream and heading info.

Go to http://localhost:5000/dashboard
