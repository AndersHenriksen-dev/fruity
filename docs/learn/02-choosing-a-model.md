# 2. Choosing a model

## Three sets of data, three jobs

Food-101 has 75,750 training images and 25,250 test images. This repo also holds back 10% of the training images, chosen by a fixed seed, as validation.

| Set | Images | Job | How often it is read |
|---|---:|---|---|
| Training | 68,175 | The model learns from it | Constantly |
| Validation | 7,575 | Every choice: which model, which settings, which form | As often as needed |
| Test | 25,250 | One honest final number | Once |

Every time a score influences a decision, that score becomes slightly optimistic, because you kept what happened to do well on those images. Trying many things on validation is fine, as long as a set exists that no decision has touched. That is why the test set is read once, at the end.

## Set the rule before seeing the results

It is easy to justify any choice after the fact. So the rule was committed to git before any comparison ran:

> Deploy the smallest model whose validation top-1 accuracy is within 3 percentage points of the best, unless its CPU latency at 1 vCPU has a p95 above 1 second. If it does, take the next smallest.

The git history proves the order. It also expresses a real trade-off: accuracy matters, but a model 7 times smaller that starts faster and costs less is worth 2 points.

## What the accuracy is compared with

A number like 88% means little alone. Many readers assume 50% is the floor, because that is chance with two classes. With 101 classes, guessing is right about 1% of the time. So the useful comparisons are methods that do not use deep learning, scored on the same validation images:

| Method | Top-1 |
|---|---:|
| Guessing | 0.99% |
| Always the most common class | 0.81% |
| Colour histogram, logistic regression | 7.97% |
| Colour, shape and texture, chi-squared kernel | 12.84% |
| Best published without deep learning, on test | 50.76% |
| `convnext_tiny` | 88.13% |

Hand-made features such as colour, edge directions (HOG) and texture (LBP) describe a whole image, and food of one kind looks different from photo to photo. The published method did far better by finding small, telling parts of each dish, and the pretrained network does better again, because it learned what to look for from millions of images. The table and its sources are in [evals/BASELINES.md](../../evals/BASELINES.md).

## Transfer learning

Each model starts from weights already trained on ImageNet, with only its final layer replaced for 101 classes. Everything before that final layer already knows edges, textures and shapes, so ten epochs is enough.

A full learning rate from the first step can wreck those weights, because the new final layer is still random and produces large errors. So training uses a warmup and then a cosine decay. The comparison showed why this matters: `convnext_tiny` at a rate of 3e-4 reached 15.5% after one epoch, and 80.7% at 5e-5. That is also why each model gets its own rate from a one-epoch probe: one shared rate would compare the setting as much as the models.

## Top-1, top-5 and worst classes

- **Top-1:** the first answer is right.
- **Top-5:** the right answer is among the first five. The gap between them says how often the model is close but not sure.
- **Worst classes:** an average hides things. Steak is the weakest class, because a steak looks a lot like filet mignon. That is a fact about the task as much as the model, and a reader should know it.

## The sweep

A sweep tries settings automatically. This one ran 6 runs, with Weights & Biases choosing each next try by Bayesian optimization. That means it builds a rough model of which settings look promising and tries there next, which suits runs that take 20 minutes each. It searched the learning rate on a log scale, because the difference between 3e-5 and 6e-5 matters as much as between 1e-4 and 2e-4.

The best run reached 88.16% against 88.05% from the comparison run. **That gain is not evidence of a better model.** Sampling alone can move a score on 7,575 images by about 0.73 points, and this gain is 0.11 points, or about 8 images. The rule still took the better score, because it was set in advance, but the honest finding is different: learning rates above 1e-4 score lower.

## Why the test score is higher than validation

Final numbers: 91.66% on test and 88.13% on validation. Test scores are usually at or below validation, so a gap like this should make you suspect a leak. Two checks were run before believing it:

- The train and test lists share no file names, and only 2 of the 25,250 test images match a training file exactly, by checksum. So nothing leaked.
- The dataset's authors reviewed the test images by hand, and left noise, including some wrong labels, in the training images on purpose. Validation comes from those training images.

So validation is scored on messier data. The likely conclusion, not proven, is that a noisy label costs points even when the model is right. Real uploads may be messier than the test set too, so 91.66% is not a promise about photos from a phone.

## In this repo

- [decisions.md](../decisions.md): entries 1 to 6, the choices above with their reasons.
- [evals/RESULTS.md](../../evals/RESULTS.md) and [evals/FINAL.md](../../evals/FINAL.md): the results, generated from saved measurements.
- [selection.py](../../src/fruity/lib/evaluation/selection.py): the rule as code.
- [finalize.py](../../src/fruity/lib/evaluation/finalize.py): how the test set is guarded. `evals/final.json` is the lock.
- [sweep.yml](../../src/fruity/config/training/sweep.yml): the sweep.
