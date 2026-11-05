"""The HTTP API that classifies food images.

The model loads when the service starts, not when the module is imported, so importing this file needs no weights.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import timm
import torch
from fastapi import FastAPI, File, UploadFile
from PIL import Image
from pydantic import BaseModel, ConfigDict
from starlette.responses import RedirectResponse
from torchvision import transforms

from fruity.lib.shared.settings import config_for


class ApiConfig(BaseModel):
    """What the API serves."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_name: str
    weights_path: Path
    labels_path: Path
    num_classes: int
    image_size: int


@dataclass(frozen=True)
class Classifier:
    """A loaded model with what it takes to use it."""

    net: torch.nn.Module
    labels: dict[int, str]
    preprocess: transforms.Compose


CONFIG = config_for(__name__, ApiConfig)
_loaded: dict[str, Classifier] = {}


def load_classifier(config: ApiConfig) -> Classifier:
    """Load the weights and labels named in the config."""
    net = timm.create_model(config.model_name, pretrained=False, in_chans=3, num_classes=config.num_classes)
    net.load_state_dict(torch.load(config.weights_path, map_location="cpu"))
    net.eval()
    labels = {int(index): label for index, label in json.loads(config.labels_path.read_text(encoding="utf-8")).items()}
    preprocess = transforms.Compose(
        [
            transforms.Resize((config.image_size, config.image_size)),
            transforms.ToTensor(),
            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
        ],
    )
    return Classifier(net, labels, preprocess)


def classify(classifier: Classifier, image: Image.Image) -> str:
    """Name the food in one image."""
    with torch.no_grad():
        logits = classifier.net(classifier.preprocess(image).unsqueeze(0))
    return classifier.labels.get(int(logits.argmax()), "Unknown")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Load the model once, when the service starts."""
    _loaded["classifier"] = load_classifier(CONFIG)
    yield
    _loaded.clear()


app = FastAPI(title="fruity", lifespan=lifespan)


@app.get("/", include_in_schema=False)
async def redirect_to_docs() -> RedirectResponse:
    """Send a visitor to the API documentation."""
    return RedirectResponse(url="/docs")


@app.post("/image/classification")
async def classify_image(file: Annotated[UploadFile, File()]) -> dict[str, str]:
    """Classify a single food image."""
    return {"result": classify(_loaded["classifier"], Image.open(file.file))}


@app.post("/batch/classification")
async def classify_batch(files: Annotated[list[UploadFile], File()]) -> dict[str, str]:
    """Classify several food images, returning the result for each file name."""
    return {str(file.filename): classify(_loaded["classifier"], Image.open(file.file)) for file in files}
