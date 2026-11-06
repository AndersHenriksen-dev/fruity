"""The entry point: reads the command line and hands over."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    """Run one of the commands. Each imports what it needs, so a serving image never loads the training stack."""
    parser = argparse.ArgumentParser(prog="fruity", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "train",
        help="train a model; Hydra overrides follow, such as experiment=convnext",
        add_help=False,
    )
    serve = commands.add_parser("serve", help="serve the model over HTTP")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    predict = commands.add_parser("predict", help="name the food in an image file")
    predict.add_argument("image", type=Path)

    commands.add_parser("compare", help="measure the trained models, choose one and write the results")

    args, rest = parser.parse_known_args()
    if args.command == "train":
        from fruity.lib.training.train import main as train

        sys.argv = ["fruity train", *rest]
        train()
    elif args.command == "compare":
        from fruity.lib.evaluation.compare import main as compare

        compare()
    elif args.command == "predict":
        from PIL import Image

        from fruity.lib.serving.api import CONFIG
        from fruity.lib.serving.inference import classify, load_classifier

        classifier = load_classifier(CONFIG.model_name, CONFIG.weights_path, CONFIG.labels_path, CONFIG.image_size)
        for answer in classify(classifier, Image.open(args.image), CONFIG.top_k):
            print(f"{answer.label}: {answer.probability:.1%}")
    else:
        import uvicorn

        uvicorn.run("fruity.lib.serving.api:app", host=args.host, port=args.port)
