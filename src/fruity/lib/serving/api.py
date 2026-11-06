"""The HTTP API that classifies food images.

The model loads when the service starts, not when the module is imported, so importing this file needs no weights.
The endpoints that run the model are plain functions, so FastAPI runs them in a thread and `/health` still answers while
a slow request is busy.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict

from fruity.lib.serving.inference import Classifier, Prediction, classify, load_classifier
from fruity.lib.serving.limits import LIMITS, RateLimiter
from fruity.lib.shared.settings import config_for

IMAGE_TYPES = {"image/png", "image/jpeg"}
HEALTH_PATH = "/health"


class ApiConfig(BaseModel):
    """What the API serves."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_path: Path
    labels_path: Path
    image_size: int
    top_k: int
    threads: int


class FileResult(BaseModel):
    """The answers for one file of a batch."""

    filename: str
    predictions: list[Prediction]


CONFIG = config_for(__name__, ApiConfig)


def read_image(file: UploadFile) -> Image.Image:
    """Turn an upload into an image, or say exactly what is wrong with it.

    Raises:
        HTTPException: 413 if it is too large, 415 if it is not a PNG or JPEG, 422 if it cannot be read as one.
    """
    if file.content_type not in IMAGE_TYPES:
        raise HTTPException(415, f"{file.filename}: must be a PNG or JPEG image.")
    if file.size is not None and file.size > LIMITS.max_upload_bytes:
        raise HTTPException(413, f"{file.filename}: larger than {LIMITS.max_upload_bytes} bytes.")
    try:
        image = Image.open(file.file)
        if image.width * image.height > LIMITS.max_image_pixels:
            raise HTTPException(413, f"{file.filename}: more than {LIMITS.max_image_pixels} pixels.")
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise HTTPException(422, f"{file.filename}: could not be read as an image.") from error
    return image


def loaded_classifier(request: Request) -> Classifier:
    """Return the model, or 503 if the service is still starting."""
    classifier: Classifier | None = getattr(request.app.state, "classifier", None)
    if classifier is None:
        raise HTTPException(503, "The model is not loaded yet.")
    return classifier


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load the model once, when the service starts, and start counting requests."""
    app.state.rate_limiter = RateLimiter(LIMITS.requests_per_minute)
    app.state.classifier = load_classifier(CONFIG.model_path, CONFIG.labels_path, CONFIG.image_size, CONFIG.threads)
    yield
    app.state.classifier = None


app = FastAPI(title="fruity", lifespan=lifespan)


@app.middleware("http")
async def enforce_limits(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Turn away too many requests or too large a body before any work is done on them."""
    if request.url.path == HEALTH_PATH:
        return await call_next(request)
    if not request.app.state.rate_limiter.allow():
        return JSONResponse({"detail": "Too many requests. Try again in a minute."}, status_code=429)
    size_limit = LIMITS.max_upload_bytes * LIMITS.max_batch_files
    if int(request.headers.get("content-length", 0)) > size_limit:
        return JSONResponse({"detail": "The request is too large."}, status_code=413)
    return await call_next(request)


@app.get("/", include_in_schema=False)
def redirect_to_docs() -> RedirectResponse:
    """Send a visitor to the API documentation."""
    return RedirectResponse(url="/docs")


@app.get(HEALTH_PATH)
def health(request: Request) -> dict[str, str]:
    """Say whether the model is loaded, so the platform only sends traffic to a replica that can answer."""
    loaded_classifier(request)
    return {"status": "ok"}


@app.post("/image/classification")
def classify_image(request: Request, file: Annotated[UploadFile, File()]) -> list[Prediction]:
    """Name the most likely foods in one image."""
    return classify(loaded_classifier(request), read_image(file), CONFIG.top_k)


@app.post("/batch/classification")
def classify_batch(request: Request, files: Annotated[list[UploadFile], File()]) -> list[FileResult]:
    """Name the most likely foods in each of several images."""
    if len(files) > LIMITS.max_batch_files:
        raise HTTPException(413, f"At most {LIMITS.max_batch_files} files at a time.")
    classifier = loaded_classifier(request)
    return [
        FileResult(filename=str(file.filename), predictions=classify(classifier, read_image(file), CONFIG.top_k))
        for file in files
    ]
