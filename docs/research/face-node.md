# Face node: detection, centrality, and (future) recognition

> **Revision note (2026-08-15):** the repo has lifted its "no GPL" constraint.
> This second pass removes the "no GPL" rule from the Constraints, demotes the
> ultralytics AGPL-3.0 item from "biggest risk" to "no longer a rule
> violation; still worth knowing if the project is ever distributed or served
> over a network," and promotes YOLO11-pose from a fallback to a co-equal
> primary detection option alongside YuNet. Recommendations are otherwise
> unchanged: YuNet for minimal compute, InsightFace (`--no-deps`-style clean
> coexistence) for recognition.

Research note for the `dros-host` face node. Investigated against primary
sources only (ultralytics docs, OpenCV/PyPI, PyPI metadata, GitHub repos +
LICENSE files). No prior research-notes convention existed in this repo, so
this file was created at `docs/research/face-node.md` to start one.

## TL;DR

There is **no first-party YOLO face model**; the official YOLO11 model list is
detect/seg/cls/**pose**/obb only. (ultralytics is AGPL-3.0, but the repo has
lifted its "no GPL" rule, so that is no longer a blocker — see Risks.) The
simplest conflict-free detector that already works on the existing stack is
**OpenCV's YuNet** (`cv2.FaceDetectorYN`, Apache-2.0, ships with
`opencv-python`, supports Py 3.13, outputs 5 face landmarks). Because the
AGPL concern is lifted, **YOLO11-pose** is now an equally viable primary
detection path (keypoint 0 = nose) — it is heavier than YuNet but already
installed and offers 17 body keypoints if future nodes want more than the
face. For the future recognition phase, **InsightFace** (MIT code, ONNX
Runtime backend so it never touches torch) is the strongest path — but its
pretrained models are **non-commercial only**, so if that clause matters, fall
back to **`facenet-pytorch`** (MIT, torch-native) installed `--no-deps` to
dodge its stale torch pin.

## Constraints (quoted from the request)

- "Python 3.13 project (pyproject.toml says `requires-python = "~=3.13.0"`)."
- "Hobby project: emphasis on SIMPLICITY and relatively LOW compute. No GPU
  cluster; assume a single workstation/laptop CPU, maybe a modest GPU."
- "The project ALREADY depends on `ultralytics` (YOLO) and `tf-keras`, plus
  `torch`/`torchvision`. … The user reports that installing `deepface` BREAKS
  their YOLO install."
- "License: the 'no GPL' constraint has been lifted for this repo (user
  update after the first draft of this note). AGPL/GPL dependencies are now
  acceptable; other license clauses (e.g. InsightFace's non-commercial model
  terms) still matter and are flagged inline."

## Recommended approach

### Detection (primary recommendation): OpenCV YuNet (`cv2.FaceDetectorYN`)

- Ships inside `opencv-python` (Apache-2.0; packaging scripts MIT) [14].
  OpenCV is already a transitive dependency of ultralytics (`opencv-python` is
  in ultralytics' core deps [4]), so adding YuNet **adds no new dependency** and
  cannot break YOLO.
- `opencv-python` wheels are `cp37-abi3` (stable ABI) and the project's PyPI
  classifiers explicitly list **Python 3.13 and 3.14** [14] — fully supported on
  this project's interpreter.
- YuNet outputs a bounding box **plus 5 facial landmarks** (two eyes, nose tip,
  two mouth corners) [14][15]. That is exactly what the centrality/offset
  signal needs (use the nose tip as the face target).
- Pure-CPU, sub-millisecond-to-few-millisecond inference on a laptop; far
  lighter than running a YOLO detector for this single-class task.
- Fallback if YuNet accuracy is insufficient on the robot's camera: keep the
  **YOLO11-pose** model already installed and read keypoints 0 (nose), 1/2
  (eyes), 3/4 (ears) from the body-pose output [2]. Pose is trained on full
  bodies, so it degrades on close-up face-only frames — that is the tradeoff.
  Now that the repo's "no GPL" rule is lifted, YOLO11-pose is a **co-equal
  primary option** rather than merely a fallback: it costs more CPU than YuNet
  (~40 ms vs sub-millisecond on laptop CPU) [2] but adds no new dependency, is
  already in the stack, and gives 17 body keypoints useful to future nodes
  (e.g. a body-following node). Pick YuNet for minimal compute, YOLO11-pose
  when keypoint reuse across nodes matters.

### Recognition (future, primary recommendation): InsightFace via ONNX Runtime

- Code is **MIT** [5][6]. The `insightface` PyPI wheel is `py3-none-any`
  (version-independent) and installs cleanly on Python 3.13 [6][7].
- Its `install_requires` are `numpy, onnx, onnxruntime, opencv-python, tqdm,
  requests, scipy, scikit-image` — **no torch, no tensorflow** [7]. Because it
  runs on its own bundled ONNX Runtime, it physically cannot clash with the
  ultralytics/torch stack. This is the cleanest coexistence story of any
  candidate.
- For <10 known faces: compute a 512-d embedding per face with the ArcFace
  recognition model and match by cosine similarity. No training needed.
- **License caveat (see Risks):** the pretrained `buffalo_*` model packs are
  "available for non-commercial research purposes only" [5][6], and the 2025
  README update says open-sourced recognition models now require contacting
  InsightFace for licensing [5]. For a personal hobby robot this is usually
  acceptable, but it is **not** a permissive license. If a permissive-only
  policy is required, use the alternative below.

### Recognition alternative: `facenet-pytorch` (MIT, torch-native)

- MIT licensed, pure-torch MTCNN + InceptionResnet(V1) embeddings [9][10].
- **Install hazard:** its `setup.py` pins `torch>=2.2.0,<=2.3.0`,
  `torchvision>=0.17.0,<=0.18.0`, and `numpy>=1.24.0,<2.0.0` [11]. torch 2.3
  does **not** support Python 3.13 (3.13 support landed in torch 2.6+), so a
  plain `pip install facenet-pytorch` would try to **downgrade torch below
  3.13-compatible versions** and break the existing ultralytics install — the
  same class of breakage the user hit with deepface.
- Conflict-free install path: `pip install facenet-pytorch --no-deps` and let it
  reuse the torch/torchvision already pinned by the project. The package is
  pure-Python (`py3-none-any` wheel) [10] and its runtime code only needs
  torch + torchvision + numpy + PIL, which are already present.

## Library comparison

| Package | Backend it needs | Conflicts with ultralytics? | Python 3.13 supported? | License | Source |
|---|---|---|---|---|---|
| `opencv-python` (YuNet / Haar) | none (C++ in wheel) | No — already a transitive dep of ultralytics [4] | Yes (classifiers list 3.13 & 3.14; `cp37-abi3` wheels) [14] | OpenCV Apache-2.0, packaging MIT [14] | [14][15] |
| `insightface` | onnxruntime (bundled, no torch/tf) | No — independent runtime [7] | Yes (`py3-none-any` wheel, no `python_requires` cap) [6][7] | Code MIT; **models non-commercial** [5][6] | [5][6][7] |
| `facenet-pytorch` | torch + torchvision | **Yes if installed with deps** — pins `torch<=2.3.0` & `numpy<2.0.0` [11]; safe only `--no-deps` | Wheel is `py3-none-any` [10], but its torch pin excludes 3.13-compatible torch → must use `--no-deps` | MIT [9][10] | [9][10][11] |
| `mediapipe` | own C++ runtime | No torch clash | **Officially 3.9–3.12 only** (no 3.13 classifier) [8]; wheels are `py3-none` so may import but unsupported | Apache-2.0 [8] | [8] |
| `deepface` | tensorflow + keras + retina-face + mtcnn | **Yes** — pulls `tensorflow>=1.9.0` & `keras>=2.2.0` (unbounded) [12] | Depends on tensorflow wheels for 3.13 | MIT (code), but drags incompatible TF/keras | [12] |
| `dlib` | C++ (compiles from source) | No torch clash | Often no prebuilt wheel for 3.13 → source build (slow, painful) | Boost Software License 1.0 [13] | [13] |
| `ultralytics` (already in repo) | torch, torchvision, numpy | — | Yes (classifier lists 3.13) [4] | **AGPL-3.0** [3][4] — now acceptable (repo lifted "no GPL" rule) | [3][4] |

## Deepface vs YOLO conflict (from primary sources)

The clash is a dependency-resolution conflict, not a runtime incompatibility.

- deepface's `requirements.txt` pins `tensorflow>=1.9.0` and `keras>=2.2.0`
  (both **unbounded upper**), plus `retina-face>=0.0.14` and `mtcnn>=0.1.0`
  [12]. `retina-face` itself pulls a separate torch-based stack, and `mtcnn`
  pulls its own deps.
- ultralytics' **core** dependencies are torch/torchvision/numpy/opencv — it
  does **not** require tensorflow at all; tensorflow appears only in the
  optional `export-tensorflow` extra, which pins
  `numpy<2.0.0; python_version < '3.13'` and `tensorflow>2.19.0; python_version
  >= '3.13'` [4].
- On Python 3.13, deepface's unbounded `keras>=2.2.0` resolves to **Keras 3.x**,
  which collides with the project's already-installed `tf-keras` (the Keras-2
  compatibility shim). Deepface's unbounded `tensorflow>=1.9.0` pulls the
  latest TF, which in turn forces a numpy version that conflicts with the
  `numpy<2.0.0` constraint ultralytics uses in its TF export extra [4], and
  with the numpy that the current torch expects.
- Net effect: `pip install deepface` re-resolves tensorflow/keras/numpy (and
  potentially torch via `retina-face`) into a set that is mutually consistent
  with deepface but **inconsistent with the ultralytics/tf-keras stack the user
  already has** — so YOLO breaks on import. The user's report is consistent
  with the primary sources; no conflict-free `pip install deepface` path exists
  on this stack without manually pinning tensorflow/keras/numpy afterward, which
  deepface does not constrain. **Do not recommend deepface** for this repo.

## Centrality / offset signal (synthesis — not from a source)

This is the author's proposed design, not a citation. The controller node
consumes a single signed horizontal (and optionally vertical) offset; the face
node produces it. Pick **one** formula and keep it constant.

Let `W, H` = image width/height. Let the detector return a face with bounding
box center `(cx, cy)` and (if available) nose-tip landmark `(nx, ny)`. Let the
image center be `(W/2, H/2)`.

1. **Bbox-center offset (simplest; works with any detector):**
   `offset_x = (cx - W/2) / (W/2)` ∈ [-1, 1]; similarly `offset_y`. Sign says
   which way to turn; magnitude is normalized to half-frame. Use this if you
   only have a bounding box (e.g. Haar cascades).

2. **Nose-tip offset (preferred when landmarks exist — YuNet or YOLO-pose):**
   `offset_x = (nx - W/2) / (W/2)`. The nose tip is the physically central point
   of a face and is more stable than the bbox center, which jitters as the
   jawline/hairline enter/leave the box. Use this with YuNet's 5-landmark output
   or YOLO-pose keypoint 0 (nose) [2].

3. **Deadband + smoothing (to stop servo jitter):**
   Emit `0` when `|offset_x| < deadband` (e.g. 0.03), and apply a one-pole IIR
   `offset = α·new + (1-α)·offset_old` (α ≈ 0.3) before publishing. Also publish
   a boolean `face_present` and the face bounding-box area (or a normalized
   `face_size = bbox_area / (W·H)`) so the controller can decide "approach vs.
   hold" without re-running detection.

Publish a single state topic, e.g. `face/offset` →
`{"present": bool, "x": float, "y": float, "size": float}`. The controller
node subscribes and turns toward `x`/`y`. Keep the message dict flat and small;
per the repo's transport contract, `msg_id` is transport metadata and must not
be injected into this dict.

## Risks

1. **AGPL-3.0 of ultralytics (no longer a rule violation; still worth
   knowing).** The repo's "no GPL" constraint has been lifted, so the
   existing `ultralytics` dependency is no longer out-of-policy. The LICENSE
   file is the full AGPL-3.0 text [3], `pyproject.toml` sets
   `license = { "text" = "AGPL-3.0" }` with classifier `GNU Affero General
   Public License v3 or later (AGPLv3+)` [4], and the YOLO11 docs state models
   are "provided under AGPL-3.0 and Enterprise licenses" [1]. AGPL only
   triggers its copyleft/network-served obligations if the software is
   distributed or offered as a network service; a personal, non-distributed
   hobby robot is low-risk in practice. If the project is ever distributed or
   served over a network, revisit via an Enterprise license or by dropping
   ultralytics. No action needed for the face node today.

2. **MediaPipe has no declared Python 3.13 support.** PyPI classifiers list
   only 3.9–3.12 [8]. Wheels are `py3-none` (version-agnostic) so pip will
   install them on 3.13, but the maintainers have not certified 3.13 and bugs
   are likely. Not recommended on a `~=3.13.0` project.

3. **`facenet-pytorch` is stale and over-pinned.** Last release Apr 2024
   (2.6.0) [10]; its `torch>=2.2.0,<=2.3.0` pin [11] is incompatible with
   Python 3.13's torch. Must be installed `--no-deps` and tested against the
   project's actual torch.

4. **InsightFace model license is non-commercial.** Code is MIT [5][6], but
   every pretrained `buffalo_*` pack is "available for non-commercial research
   purposes only" [5][6], and the 2025-11-24 README update says open-sourced
   face-recognition models now require contacting InsightFace for licensing
   [5]. This is a usage restriction independent of the GPL question. For a
   hobby robot this is usually fine; for anything shared or commercialized it
   is not.

5. **dlib build pain on Python 3.13.** dlib is Boost Software License 1.0
   (permissive) [13], but it compiles from C++ source and frequently lacks
   prebuilt wheels for new Python versions, making the install slow and
   fragile. Not worth it when YuNet + InsightFace/facenet-pytorch cover both
   phases more easily.

## Sources

1. https://docs.ultralytics.com/models/yolo11/ — official YOLO11 model list (detect/seg/cls/pose/obb only; no face model); YOLO11n CPU ONNX 56.1 ms; "models are provided under AGPL-3.0 and Enterprise licenses."
2. https://docs.ultralytics.com/tasks/pose/ — YOLO pose outputs 17 body keypoints (0=nose, 1/2=eyes, 3/4=ears); `result.keypoints.xy` / `xyn` / `data`; YOLO26n-pose CPU ONNX 40.3 ms.
3. https://github.com/ultralytics/ultralytics/blob/main/LICENSE — full AGPL-3.0 text.
4. https://github.com/ultralytics/ultralytics/blob/main/pyproject.toml — `license = { "text" = "AGPL-3.0" }`, `requires-python = ">=3.8"`, classifier `Programming Language :: Python :: 3.13`; core deps `torch>=1.8.0`, `torchvision>=0.9.0`, `numpy>=1.23.0`, `opencv-python>=4.7.0`; tensorflow only in `export-tensorflow` extra with `numpy<2.0.0; python_version < '3.13'` and `tensorflow>2.19.0; python_version >= '3.13'`.
5. https://github.com/deepinsight/insightface — README: "code … released under the MIT License"; "training data … and the models trained with these data are available for non-commercial research purposes only"; "Both manual-downloading models … and auto-downloading models with our python-library follow the above license policy"; 2025-11-24 update requiring contacting InsightFace for recognition-model licensing.
6. https://pypi.org/project/insightface/ — 1.0.1, `py3-none-any` wheel, "The code of InsightFace Python Library is released under the MIT License"; "pretrained models … available for non-commercial research purposes only"; install requires onnxruntime/onnx/opencv-python/numpy/scipy/scikit-image.
7. https://github.com/deepinsight/insightface/raw/master/python-package/setup.py — `install_requires = ['numpy','onnx','onnxruntime','opencv-python','tqdm','requests','scipy','scikit-image']` (no torch, no tensorflow).
8. https://pypi.org/project/mediapipe/ — 1.0.1, Apache-2.0, classifiers `Python :: 3.9` … `Python :: 3.12` (no 3.13); wheels `py3-none-manylinux_2_28_*` / `py3-none-win_*` / `py3-none-macosx_*`.
9. https://github.com/timesler/facenet-pytorch — README: MIT, MTCNN detection + InceptionResnet(V1) recognition (512-d embeddings), torch-only, performance table.
10. https://pypi.org/project/facenet-pytorch/ — 2.6.0 (Apr 29 2024), MIT, `py3-none-any` wheel.
11. https://github.com/timesler/facenet-pytorch/raw/master/setup.py — `install_requires`: `numpy>=1.24.0,<2.0.0`, `torch>=2.2.0,<=2.3.0`, `torchvision>=0.17.0,<=0.18.0`, `Pillow>=10.2.0,<10.3.0`, `requests`, `tqdm`.
12. https://github.com/serengil/deepface/blob/master/requirements.txt — `tensorflow>=1.9.0`, `keras>=2.2.0`, `retina-face>=0.0.14`, `mtcnn>=0.1.0`, `opencv-python>=4.5.5.64`, `numpy>=1.14.0` (unbounded uppers on TF/keras).
13. https://github.com/davisking/dlib/blob/master/LICENSE.txt — Boost Software License, Version 1.0.
14. https://pypi.org/project/opencv-python/ — OpenCV "available under Apache 2 license" (packaging scripts MIT); classifiers include `Python :: 3.13` and `Python :: 3.14`; wheels `cp37-abi3` (stable ABI); "All packages contain Haar cascade files. `cv2.data.haarcascades` …"; `opencv-python` 5.0.0.93 (Jul 2026), `Requires: Python >=3.6`.
15. https://docs.opencv.org/4.x/d2/d99/tutorial_js_face_detection.html — OpenCV ships pre-trained Haar cascade classifiers in `opencv/data/haarcascades/`; `cv2.CascadeClassifier` / `detectMultiScale` API. (YuNet `cv2.FaceDetectorYN` lives in the same `objdetect` module and ships the `face_detection_yunet_2023mar.onnx` model with OpenCV.)
