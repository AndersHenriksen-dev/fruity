# Design decisions

One entry per choice, with the reason. Newest last.

## 1. The rule for choosing a model is set before training

A small model is cheaper and starts faster, so a little accuracy is worth giving up for it, but it is easy to justify any choice after seeing the results. So the rule is fixed first, and this entry was committed before any comparison run:

**Deploy the smallest model whose validation top-1 accuracy is within 3 percentage points of the best, unless its CPU latency at 1 vCPU has a p95 above 1 second. If it does, take the next smallest.**

Accuracy for the choice comes from validation data. The test set is used once, on the chosen model, for the final number.

## 2. The official Food-101 split

The hand-in used a custom split at 100x100 pixels, so its 76% cannot be compared with the numbers here. This repo uses the official split of 75,750 training and 25,250 test images at 224 pixels, so results can be compared with published work. Validation is 10% of the training images, chosen by a fixed seed.
