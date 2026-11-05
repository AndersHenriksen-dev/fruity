# fruity

A food image classifier, trained, deployed and measured as a small production service.

This is a fork of [wdmdev/fruity](https://github.com/wdmdev/fruity), my group project for the DTU course 02476 Machine Learning Operations, by William Diedrichsen Marstrand, Karl Byberg Ulbæk, August Semrau Andersen and me. The project as we handed it in is tagged [`dtu-2024`](https://github.com/AndersHenriksen-dev/fruity/tree/dtu-2024).

## Try it

You need [uv](https://docs.astral.sh/uv/getting-started/installation/), which also installs Python 3.12.

```bash
uv sync --all-extras
uv run pytest
uv run fruity train experiment=convnext
uv run fruity serve
```

The code is MIT licensed.
