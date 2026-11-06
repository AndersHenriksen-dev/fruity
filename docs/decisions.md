# Design decisions

One entry per choice, with the reason. Newest last.

## 1. The rule for choosing a model is set before training

A small model is cheaper and starts faster, so a little accuracy is worth giving up for it, but it is easy to justify any choice after seeing the results. So the rule is fixed first, and this entry was committed before any comparison run:

**Deploy the smallest model whose validation top-1 accuracy is within 3 percentage points of the best, unless its CPU latency at 1 vCPU has a p95 above 1 second. If it does, take the next smallest.**

Accuracy for the choice comes from validation data. The test set is used once, on the chosen model, for the final number.

## 2. The official Food-101 split

The hand-in used a custom split at 100x100 pixels, so its 76% cannot be compared with the numbers here. This repo uses the official split of 75,750 training and 25,250 test images at 224 pixels, so results can be compared with published work. Validation is 10% of the training images, chosen by a fixed seed.

## 3. Each model gets its own learning rate, chosen on validation data

One shared rate would compare the setting as much as the models. `convnext_tiny` at a rate of 3e-4 reached 15.5% validation accuracy after one epoch, and 80.7% at 5e-5. So each model gets a one-epoch probe of two rates, on validation data, and keeps the better one. The probes are saved in `evals/lr_probe.json`. A warmup and a cosine decay apply to all of them, because a full rate from the first step can wreck pretrained weights while the new final layer is still random.

## 4. The rule picks `convnext_tiny`

The best validation accuracy is 90.05%, from `convnext_large`, so the floor is 87.05%. The two models under 20 MB reach 83.23% and 82.20%, which is below it. `convnext_tiny` reaches 88.05% and is the smallest model above it, with a p95 of 98 ms on one core against a limit of 1 second. Giving up 2 points of accuracy makes the model 7 times smaller and about 6 times faster than `convnext_large`. The numbers are in `evals/RESULTS.md`.

## 5. The service runs plain ONNX, not quantized ONNX

Plain ONNX scores the same 88.05% as PyTorch at about the same speed, and needs ONNX Runtime instead of PyTorch in the serving image. Quantized ONNX is 4 times smaller and twice as fast, but scores 85.76%. That is below the 87.05% floor from entry 4, so the rule that excludes the smaller models excludes it too.

Quantizing only `Conv`, `MatMul` and `Gemm` layers is deliberate. Quantizing every layer took `convnext_tiny` to about 20%, as `evals/quantization_settings.json` shows for 1,500 validation images. Even with this setting, quantization costs some models far more than others: `efficientnet_b0` falls to 29.83% and `mobilenetv3_large_100` to 63.87%, as `evals/comparison.json` shows. So a quantized model always needs its accuracy measured before use.

## 6. The final weights come from the sweep's best run, and the gain is within noise

A Weights & Biases sweep of 6 runs tried learning rates from 3e-5 to 3e-4 and weight decay from 0 to 0.1. Its best run reached 88.16% on validation against 88.05% from the comparison run. The rule was set before the sweep: the best validation score wins, so the sweep's run is the final model. The 0.11 point gain is about 8 images and well inside what sampling alone can move, so it is not evidence of a better model. The clearer finding is that rates above 1e-4 score lower. The numbers are in `evals/FINAL.md`.

The test set is read by `fruity finalize` only, after the run and the form are fixed and the ONNX file has matched PyTorch on validation. `evals/final.json` is the lock: while it exists, the command rewrites the report and does not read the test set.
