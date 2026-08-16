# dros-host

The host process for Dave's ROS (dros) robot: a single in-process bus of
publish/subscribe topics, populated by long-lived Node subclasses that bridge
hardware (camera, audio, distance sensor) and services (LLM) to the bus.

Note: This context node was generated while developing face related processing
and is incomplete with respect to other features such as audio and LLM.

## Language

### Topics

**/marvin/camera**:
State topic carrying the most recent camera frame. Source for any vision node.
_Avoid_: `/marvin_camera` (research-note typo).

**/face_detect**:
State topic (`history=4`) carrying the current face reading published by the
face node. Schema: `{present, x, y, size, confidence}` (see fields below).

**/events**:
Event topic carrying notifications from any node. Payload is `EventMessage`.

### Events

**EventMessage.type**:
The *source namespace* of the event (e.g. `face`, `asr`, `llm`), not the
action verb. Multiple event kinds from one source share a `type` and differ
in `message`. _Avoid_: action verbs like `detected`, `stop` as `type`
(existing `stop` outlier in `llm_node.py` is a known inconsistency).

**Face detected**:
Edge event on `/events` (`type="face"`, `message="Face detected"`) fired on
the no-face → face transition.

**Face lost**:
Edge event on `/events` (`type="face"`, `message="Face lost"`) fired on the
face → no-face transition.

### Face node

**FaceNode**:
The dros `Node` (tick-driven, 5 Hz) that subscribes to `/marvin/camera`, runs a
`FaceDetector`, picks the strongest face, computes the offset/size, and
publishes `/face_detect` plus edge events on `/events`. Face *recognition* is a
future step and is expected to live in this same node (with a `Recognizer`
seam alongside `FaceDetector`); split only if experience shows that's a bad
idea. _Avoid_: FaceDetectNode (premature — recognition may merge in here).

**FaceDetector**:
A swappable protocol whose `detect(image: np.ndarray) -> list[FaceDetection]`
returns all faces found in a frame. Implementations: YuNet (primary, model
vendored under `src/dros_host/vision/models/`). Future: YOLO11-pose,
InsightFace. The detector does *not* pick a face or compute offsets — it only
reports what it found.

**FaceDetection**:
Detector output for one face: `confidence: float`, `nose: tuple[float, float]`
(normalized [0,1] image coords), `bbox: tuple[float, float, float, float]`
(normalized x, y, w, h). _Avoid_: FaceReading, detection result.

### /face_detect schema fields

**present**:
`bool` — whether a face was selected this tick.

**x, y**:
Signed offset of the nose tip from frame centre, normalized to half-frame:
`(nose - W/2) / (W/2)`, range [-1, 1]. Computed by the face node, not the
detector. _Avoid_: raw nose coordinates, pixel coords (not transport-safe
across resolution changes).

**size**:
Normalized face bbox area `bbox_area / (W * H)`, range [0, 1].

**confidence**:
The selected face's detector score, range [0, 1].

### Behaviour

**Strongest face**:
When the detector returns multiple faces, the face node publishes the one with
the highest `confidence`. _Avoid_: largest, nearest-centre, all-faces.

**Edge-triggered**:
"Face detected" / "Face lost" events fire only on the `present` boolean's
transitions, not on every tick. Initial state is `present=false`; a face in
the first processed frame counts as a transition and emits "Face detected".
