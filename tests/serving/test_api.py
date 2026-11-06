"""The API, through real HTTP requests to the app."""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from fruity.lib.serving import api
from tests.serving.conftest import IMAGE_SIZE, LABELS


def _image(mode: str = "RGB", size: tuple[int, int] = (80, 60), image_format: str = "PNG") -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, size).save(buffer, format=image_format)
    return buffer.getvalue()


@pytest.fixture
def client(saved_model: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    model, labels = saved_model
    config = api.ApiConfig(model_path=model, labels_path=labels, image_size=IMAGE_SIZE, top_k=2, threads=1)
    monkeypatch.setattr(api, "CONFIG", config)
    with TestClient(api.app) as test_client:
        yield test_client


def _limit(monkeypatch: pytest.MonkeyPatch, **changes: int) -> None:
    monkeypatch.setattr(api, "LIMITS", api.LIMITS.model_copy(update=changes))


class TestHealth:
    def test_it_is_ok_once_the_model_is_loaded(self, client: TestClient) -> None:
        response = client.get("/health")
        assert (response.status_code, response.json()) == (200, {"status": "ok"})

    def test_it_is_not_ok_before_the_model_is_loaded(self, client: TestClient) -> None:
        api.app.state.classifier = None
        assert client.get("/health").status_code == 503

    def test_it_is_never_rate_limited(self, client: TestClient) -> None:
        api.app.state.rate_limiter.per_minute = 0
        assert client.get("/health").status_code == 200


class TestClassifyImage:
    @pytest.mark.parametrize(
        ("mode", "image_format", "content_type"),
        [("RGB", "PNG", "image/png"), ("RGBA", "PNG", "image/png"), ("L", "JPEG", "image/jpeg")],
    )
    def test_it_answers_for_a_real_image(
        self,
        client: TestClient,
        mode: str,
        image_format: str,
        content_type: str,
    ) -> None:
        upload = {"file": ("food", _image(mode, image_format=image_format), content_type)}
        response = client.post("/image/classification", files=upload)
        assert response.status_code == 200
        assert len(response.json()) == 2
        assert {answer["label"] for answer in response.json()} <= set(LABELS.values())

    def test_a_wrong_file_type_is_415_and_not_a_crash(self, client: TestClient) -> None:
        response = client.post("/image/classification", files={"file": ("notes.txt", b"hello", "text/plain")})
        assert response.status_code == 415

    def test_a_file_that_only_claims_to_be_an_image_is_422(self, client: TestClient) -> None:
        response = client.post("/image/classification", files={"file": ("fake.png", b"not an image", "image/png")})
        assert response.status_code == 422

    def test_a_truncated_image_is_422(self, client: TestClient) -> None:
        cut = _image(size=(400, 400), image_format="JPEG")[:200]
        response = client.post("/image/classification", files={"file": ("cut.jpg", cut, "image/jpeg")})
        assert response.status_code == 422

    def test_too_many_bytes_is_413(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        _limit(monkeypatch, max_upload_bytes=10)
        response = client.post("/image/classification", files={"file": ("big.png", _image(), "image/png")})
        assert response.status_code == 413

    def test_too_many_pixels_is_413(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        _limit(monkeypatch, max_image_pixels=100)
        response = client.post("/image/classification", files={"file": ("big.png", _image(), "image/png")})
        assert response.status_code == 413

    def test_a_body_over_the_limit_is_refused_before_it_is_read(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _limit(monkeypatch, max_upload_bytes=1, max_batch_files=1)
        response = client.post("/image/classification", files={"file": ("big.png", _image(), "image/png")})
        assert response.json()["detail"] == "The request is too large."

    def test_too_many_requests_is_429(self, client: TestClient) -> None:
        api.app.state.rate_limiter.per_minute = 0
        upload = {"file": ("food.png", _image(), "image/png")}
        assert client.post("/image/classification", files=upload).status_code == 429


class TestClassifyBatch:
    def test_each_file_gets_its_own_answers_in_order(self, client: TestClient) -> None:
        files = [("files", (name, _image(), "image/png")) for name in ("a.png", "b.png")]
        response = client.post("/batch/classification", files=files)
        assert response.status_code == 200
        assert [result["filename"] for result in response.json()] == ["a.png", "b.png"]
        assert all(len(result["predictions"]) == 2 for result in response.json())

    def test_too_many_files_is_413(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        _limit(monkeypatch, max_batch_files=1)
        files = [("files", (name, _image(), "image/png")) for name in ("a.png", "b.png")]
        assert client.post("/batch/classification", files=files).status_code == 413

    def test_one_bad_file_names_itself(self, client: TestClient) -> None:
        files = [("files", ("good.png", _image(), "image/png")), ("files", ("bad.txt", b"hello", "text/plain"))]
        response = client.post("/batch/classification", files=files)
        assert response.status_code == 415
        assert "bad.txt" in response.json()["detail"]
