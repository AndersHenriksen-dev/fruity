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
    commands.add_parser("finalize", help="fix the final model and score it on the test set, once")
    commands.add_parser("fetch", help="download the published model and verify its checksums")

    loadtest = commands.add_parser("loadtest", help="measure this project's own service under load")
    loadtest.add_argument("--host", required=True, help="the service's URL")
    loadtest.add_argument("--output", type=Path, required=True, help="the folder for the results")
    loadtest.add_argument("--azure-resource-id", help="the API's resource ID, to read replica counts from Azure")
    loadtest.add_argument("--cold-starts", action="store_true", help="measure cold starts instead of load")
    loadtest.add_argument("--soak", action="store_true", help="hold a steady load for most of the deployment")

    cloud = commands.add_parser("cloud-report", help="write the report on the service's run on Azure")
    cloud.add_argument("--folder", type=Path, default=Path("evals"), help="where the saved Azure data is")
    cloud.add_argument("--fetch", action="store_true", help="first save the metrics from Azure, while the apps exist")

    args, rest = parser.parse_known_args()
    if args.command == "train":
        from fruity.lib.training.train import main as train

        sys.argv = ["fruity train", *rest]
        train()
    elif args.command == "compare":
        from fruity.lib.evaluation.compare import main as compare

        compare()
    elif args.command == "finalize":
        from fruity.lib.evaluation.finalize import main as finalize

        finalize()
    elif args.command == "fetch":
        from fruity.lib.serving.fetch import main as fetch

        fetch()
    elif args.command == "loadtest":
        from fruity.lib.loadtest.run import measure_cold_starts, measure_soak, measure_stages

        if args.cold_starts:
            measure_cold_starts(args.host, args.output)
        elif args.soak:
            measure_soak(args.host, args.output, args.azure_resource_id)
        else:
            measure_stages(args.host, args.output, args.azure_resource_id)
    elif args.command == "cloud-report":
        from fruity.lib.loadtest.cloud import fetch as save_metrics
        from fruity.lib.loadtest.cloud import write_report

        if args.fetch:
            save_metrics(args.folder)
        write_report(args.folder)
    elif args.command == "predict":
        from PIL import Image

        from fruity.lib.serving.api import CONFIG
        from fruity.lib.serving.inference import classify, load_classifier

        classifier = load_classifier(CONFIG.model_path, CONFIG.labels_path, CONFIG.image_size, CONFIG.threads)
        for answer in classify(classifier, Image.open(args.image), CONFIG.top_k):
            print(f"{answer.label}: {answer.probability:.1%}")
    else:
        import uvicorn

        uvicorn.run("fruity.lib.serving.api:app", host=args.host, port=args.port)
