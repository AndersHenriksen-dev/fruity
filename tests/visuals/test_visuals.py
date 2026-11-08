"""The photos and graphics, on made-up photos, a made-up Food-101 folder and an untrained model."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import onnx
import pytest
import timm
from PIL import Image

from fruity import cli
from fruity.lib.evaluation import compare
from fruity.lib.evaluation.onnx_model import export_onnx
from fruity.lib.training.data import Food101DataModule
from fruity.lib.visuals import draw, photos
from fruity.lib.visuals.model_parts import Network, feature_name

DISHES = ["apple_pie", "pizza", "sushi", "waffles"]
IMAGE_SIZE = 64


def _random_photo(path: Path, seed: int) -> None:
    pixels = np.random.default_rng(seed).integers(0, 255, (80, 120, 3), dtype=np.uint8)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(pixels).save(path)


@pytest.fixture(scope="module")
def model(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Export an untrained model with one output per dish."""
    folder = tmp_path_factory.mktemp("model")
    net = timm.create_model("resnet18", pretrained=False, num_classes=len(DISHES))
    export_onnx(net, IMAGE_SIZE, folder / "model.onnx")
    (folder / "labels.json").write_text(json.dumps(dict(enumerate(DISHES))), encoding="utf-8")
    return folder


@pytest.fixture
def workspace(tmp_path: Path, model: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the graphics at made-up photos, made-up validation data and the untrained model."""
    for index, dish in enumerate(DISHES):
        _random_photo(tmp_path / "photos" / f"{dish}.jpg", index)
    meta = tmp_path / "data" / "food-101" / "meta"
    meta.mkdir(parents=True)
    names = {dish: [f"{dish}/{number}" for number in range(8)] for dish in DISHES}
    for split in ("train", "test"):
        (meta / f"{split}.json").write_text(json.dumps(names), encoding="utf-8")
    for files in names.values():
        for number, file in enumerate(files):
            _random_photo(tmp_path / "data" / "food-101" / "images" / f"{file}.jpg", 100 + number)
    datamodule = Food101DataModule(str(tmp_path / "data"), IMAGE_SIZE, 0.5, 42, 4, 0)
    datamodule.setup()
    monkeypatch.setattr(compare, "load_datamodule", lambda: datamodule)
    monkeypatch.setattr(photos.CONFIG, "photo_dir", tmp_path / "photos")
    overrides = {
        "model_path": model / "model.onnx",
        "labels_path": model / "labels.json",
        "image_size": IMAGE_SIZE,
        "gallery_every": 1,
        "gallery_columns": 2,
        "occlusion_dishes": ["pizza"],
        "occlusion_patch": 16,
        "occlusion_stride": 16,
        "map_columns": 2,
        "map_rows": 2,
        "map_perplexity": 2,
        "features_cache": tmp_path / "features.npz",
        "results_path": tmp_path / "real_photos.json",
        "report_path": tmp_path / "PHOTOS.md",
        "image_dir": tmp_path / "visuals",
    }
    for name, value in overrides.items():
        monkeypatch.setattr(draw.CONFIG, name, value)
    monkeypatch.setattr("sys.argv", ["fruity", "visuals"])
    return tmp_path


def test_every_graphic_and_the_report_are_written(workspace: Path) -> None:
    cli.main()
    results = json.loads((workspace / "real_photos.json").read_text(encoding="utf-8"))
    assert [result["dish"] for result in results] == DISHES
    assert all(len(result["predictions"]) == len(DISHES) for result in results)
    report = (workspace / "PHOTOS.md").read_text(encoding="utf-8")
    assert f"of {len(DISHES)}" in report
    for name in ("gallery.jpg", "where_it_looks.jpg", "dish_map.jpg"):
        assert Image.open(workspace / "visuals" / name).size[0] > 0
    assert len(np.load(workspace / "features.npz")["labels"]) == len(DISHES) * 4


def test_the_features_are_what_the_final_layer_reads(model: Path) -> None:
    graph = onnx.load(str(model / "model.onnx"))
    final = next(node for node in graph.graph.node if graph.graph.output[0].name in node.output)
    assert feature_name(graph) in final.input
    batch = np.zeros((2, 3, IMAGE_SIZE, IMAGE_SIZE), dtype=np.float32)
    logits, features = Network(model / "model.onnx").run(batch)
    assert logits.shape == (2, len(DISHES))
    assert features.shape == (2, 512)


def test_every_point_gets_its_own_cell_and_neighbours_stay_close() -> None:
    points = np.array([[0.0, 0.0], [0.1, 0.0], [10.0, 10.0], [9.9, 10.0]])
    cells = draw.place_on_grid(points, 2, 2)
    assert len(set(cells)) == len(points)
    assert cells[0][1] == cells[1][1]
    assert cells[2][1] == cells[3][1]


def test_more_points_than_cells_is_refused() -> None:
    with pytest.raises(ValueError, match="do not fit"):
        draw.place_on_grid(np.zeros((5, 2)), 2, 2)


@pytest.mark.parametrize(
    ("licence", "allowed"),
    [
        ("CC0", True),
        ("Public domain", True),
        ("CC BY 2.0", True),
        ("CC BY 4.0", True),
        ("CC BY-SA 4.0", False),
        ("CC BY-NC 2.0", False),
        ("CC BY-ND 3.0", False),
        ("GFDL", False),
    ],
)
def test_only_licences_that_allow_cropping_with_a_credit_are_taken(licence: str, allowed: bool) -> None:
    assert photos.licence_allowed(licence) is allowed


def test_a_pinned_file_is_used_and_credited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def __init__(self, payload: object = None, content: bytes = b"") -> None:
            self.payload, self.content = payload, content

        def raise_for_status(self) -> None:
            """Every made-up request succeeds."""

        def json(self) -> object:
            return self.payload

    meta = {
        "LicenseShortName": {"value": "CC BY 2.0"},
        "Artist": {"value": '<a href="x">Jane Doe</a>'},
        "LicenseUrl": {"value": "https://creativecommons.org/licenses/by/2.0"},
    }
    info = {
        "width": 800,
        "descriptionurl": "https://commons.example/pizza",
        "thumburl": "https://upload.example/p.jpg",
        "extmetadata": meta,
    }
    page = {"title": "File:Pizza.jpg", "imageinfo": [info]}

    def get(_: object, url: str, params: dict[str, object] | None = None, timeout: int = 0) -> Response:
        if params is not None:
            assert params["titles"] == "File:Pizza.jpg"
            return Response({"query": {"pages": {"1": page}}})
        return Response(content=b"jpeg bytes")

    monkeypatch.setattr(photos.requests.Session, "get", get)
    monkeypatch.setattr(photos.CONFIG, "pinned", {"pizza": "File:Pizza.jpg"})
    monkeypatch.setattr(photos.CONFIG, "request_pause_seconds", 0.0)
    for name in ("photo_dir", "credits_path", "manifest_path"):
        monkeypatch.setattr(
            photos.CONFIG,
            name,
            tmp_path / {"photo_dir": "photos", "credits_path": "CREDITS.md", "manifest_path": "photos.json"}[name],
        )
    found = photos.fetch(["pizza"])
    assert found[0].author == "Jane Doe"
    assert (tmp_path / "photos" / "pizza.jpg").read_bytes() == b"jpeg bytes"
    assert "| pizza | [Pizza.jpg](https://commons.example/pizza) | Jane Doe |" in (tmp_path / "CREDITS.md").read_text(
        encoding="utf-8",
    )
