# 3. ONNX and serving

## What ONNX is

PyTorch is a framework for building and training models, so it carries far more than running one needs. ONNX is a file format that describes only the finished calculation: which operations, in which order, with which numbers. ONNX Runtime is a small engine that runs such a file.

Why it matters here:

| | With PyTorch | With ONNX Runtime |
|---|---|---|
| Serving dependencies | PyTorch, torchvision, timm | ONNX Runtime, NumPy, Pillow |
| Exact same scores | Yes | Proven, see below |

A service that scales to zero starts from nothing often, so the first visitor pays for every extra second and megabyte.

## Proving it is the same model

An export can silently change behavior, so three checks stand between "exported" and "trusted":

1. **Before the test set is opened**, `fruity finalize` scores both forms on all validation images. If they differ by more than 0.1 points, it stops, and the test set stays closed.
2. **The preprocessing had to change too**, since the old code used torchvision. A test compares the new NumPy function with the torchvision pipeline, pixel for pixel, on 9 image shapes, including thin and tiny ones. It requires exact equality, not "close".
3. **The whole serving path was run** on all 7,575 validation images and got 6,676 right, the same 88.13% as before.

Training and evaluation now call the same NumPy function, so they cannot drift apart. And a test fails if importing the API ever pulls PyTorch in.

## Quantization, and why it is not used

Quantizing stores a model's numbers as 8-bit integers instead of 32-bit floats. That makes the file about 4 times smaller and calculation faster, because integer arithmetic is cheaper. The cost is rounding, and rounding hurts more where the numbers are sensitive.

| Form | Size (MB) | Top-1 | p95 (ms) |
|---|---:|---:|---:|
| ONNX | 112.1 | 88.05% | 90 |
| Quantized ONNX | 28.5 | 85.76% | 46 |

These are from the comparison run. It looks tempting, but 85.76% is below the 87.05% floor that excluded the smaller models, so the same rule excludes it too. Letting it in would mean bending the rule because the number looked nice.

Two more lessons came from getting it this far:

- **Rounding every layer took the model to about 20%.** ConvNeXt relies on layer normalization and additions, where rounding does real damage. Quantizing only `Conv`, `MatMul` and `Gemm` is what makes it usable at all.
- **Effects differ hugely by model.** `efficientnet_b0` fell to 29.83% and `mobilenetv3_large_100` to 63.87% with the same settings. So a quantized model always needs measuring. "Should be about the same" is not safe.

The rounding is fitted on calibration images from the training set, never on images it will be scored on.

## Threads in a container

ONNX Runtime asks the machine how many cores it has and starts that many threads. In a container limited to half a core on a host with many cores, those threads fight over a small share of CPU, and things get slower, not faster. So `threads: 1` is set in `api.yaml`. Software often cannot see its container's real limits, so this kind of setting is worth checking in any containerized service.

## Pinning the model

The image build runs `fruity fetch`, which downloads the release and fails if a file's SHA-256 differs from the checksum in config. The checksum of `model.onnx` is the one recorded in `evals/final.json`. So the model in a running container traces back to the exact file that was scored. Weights do not live in git because git keeps every version forever, and 112 MB per version would make every clone slow.

## In this repo

- [inference.py](../../src/fruity/lib/serving/inference.py): serving, without PyTorch.
- [onnx_model.py](../../src/fruity/lib/evaluation/onnx_model.py): export and quantization.
- [test_preprocess.py](../../tests/shared/test_preprocess.py) and [test_inference.py](../../tests/serving/test_inference.py): the proofs above.
- [fetch.py](../../src/fruity/lib/serving/fetch.py): the checksum check.
- [quantization_settings.json](../../evals/quantization_settings.json): the rounding experiment.
- [decisions.md](../decisions.md): entry 5.
