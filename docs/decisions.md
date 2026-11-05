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
