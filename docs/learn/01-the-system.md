# 1. The system

## What it is

A food photo goes in and the name of the food comes out, with 101 possible foods. The classifier is deliberately ordinary. The point of the repository is everything around it: how the model was chosen, how it is packaged, how it reaches the cloud, how it is watched and what it costs.

## The parts

| Part | What it is | Why it exists |
|---|---|---|
| Training | Lightning, timm and Hydra, on a local GPU | Produces weights. Runs once, and needs PyTorch and a GPU |
| Evaluation | `fruity compare` and `fruity finalize` | Decides which weights are good enough, and records why |
| Release | `model.onnx` and `labels.json` on GitHub, with checksums | Keeps weights out of git, and pins exactly which model runs |
| API | FastAPI and ONNX Runtime in a container | Answers requests. Holds the model |
| Demo page | Streamlit in a container | Lets a person try it. Holds no model and only calls the API |
| Infrastructure | Terraform for Azure Container Apps | Makes the cloud setup reviewable and repeatable |
| CI and deploy | GitHub Actions | Checks every change, and builds and deploys on request |
| Monitoring | Azure metrics, alerts and a dashboard | Says what the running service is doing |
| Load test | Locust | Measures what the service does as traffic grows |

Training and serving are separated on purpose. They have opposite needs: training wants a GPU and many large libraries for a few hours, while serving wants to start fast, stay small and run for free when idle. The ONNX file is the handover between them.

## One request, start to finish

1. The browser uploads a photo to the demo page.
2. The demo page posts it to the API at `/batch/classification`.
3. Azure's ingress checks the caller's address against the allowed list. If no API replica is running, it starts one.
4. The API's middleware counts the request against the rate limit and checks the body size.
5. `read_image` checks the file type, size and pixel count, then decodes it. Wrong type gives 415, too large gives 413, and something that only claims to be an image gives 422. Each is a clear answer rather than a crash.
6. `prepare_image` resizes the short side to 256 pixels, crops the center 224 and normalizes the colors, exactly as was done when the model was measured.
7. ONNX Runtime turns those pixels into 101 numbers, called logits.
8. `classify` turns the logits into probabilities with softmax and returns the top 3.
9. The demo page shows the photo with the answers.

## The design choices that shape everything

- **The model loads at startup, not per request**, so no request pays for loading it. `/health` says "not ready" until it has loaded, so the platform sends traffic only to replicas that can answer.
- **Model endpoints are plain functions, not `async`.** FastAPI runs them in a thread pool, so `/health` still answers while a slow classification runs. An `async` function doing heavy work would block every other request in that process.
- **The rate limit counts per replica and for everyone together.** Its job is to cap cost, and per-visitor limits are easy to fake.
- **Config lives in YAML files that mirror the code's folders**, checked by Pydantic when the module loads, so a typo fails immediately instead of on some later request.

## In this repo

- [cli.py](../../src/fruity/cli.py): every command, and the place to start reading.
- [api.py](../../src/fruity/lib/serving/api.py) and [limits.py](../../src/fruity/lib/serving/limits.py): the request path.
- [inference.py](../../src/fruity/lib/serving/inference.py) and [preprocess.py](../../src/fruity/lib/shared/preprocess.py): from pixels to answers.
- [frontend/app.py](../../src/fruity/lib/frontend/app.py): the demo page.
