"""The entry point: reads the command line and hands over."""

from __future__ import annotations

import argparse
import sys


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

    args, rest = parser.parse_known_args()
    if args.command == "train":
        from fruity.lib.training.train import main as train

        sys.argv = ["fruity train", *rest]
        train()
    else:
        import uvicorn

        uvicorn.run("fruity.lib.serving.api:app", host=args.host, port=args.port)
