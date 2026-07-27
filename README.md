# DROS-based Marvin host

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

## Dashboard

Web dashboard served as a static file from `src/dros_host/static/dashboard.html` which uses socket.io to directly show camera, event stream and heading info.

Go to http://localhost:5000/dashboard
