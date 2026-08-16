# EventMessage.type is a source namespace, not an action verb

`EventMessage.type` (defined in `src/dros_host/messages/events.py`) denotes the
*source node* of an event (e.g. `face`, `asr`, `llm`), not the action that
occurred. The action lives in the human-readable `message` field. Multiple
event kinds from one source share a `type` and differ in `message`: the face
node publishes `type="face"` with `message="Face detected"` on the no-face →
face transition and `message="Face lost"` on the reverse transition; a future
recognition step will publish `type="face"` with `message="Face recognized:
Dave"` rather than a new `type="face_recognized"`.

We picked source-namespace over action-verb so a single source can emit
multiple event kinds without `type` proliferation, and so dashboard styling
keyed on `type` (e.g. `dashboard.html:207`'s `:class="evt.type"`) groups all
events from one source under one look.

The existing `llm_node.py:146` `publish_event("stop", "llm-in")` call uses
`type="stop"` (an action verb) — this is a known inconsistency and the
outlier that motivated recording this convention. New code should follow the
source-namespace rule; reconciling `stop` is left for a separate cleanup.
