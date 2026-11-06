"""A demo page: upload food photos and see what the API calls them."""

from __future__ import annotations

import os

import requests
import streamlit as st
from pydantic import BaseModel, ConfigDict

from fruity.lib.shared.settings import config_for


class FrontendConfig(BaseModel):
    """Where the API is."""

    model_config = ConfigDict(extra="forbid")

    api_endpoint: str
    timeout_seconds: int


# `streamlit run` makes this file `__main__`, so its name has to be spelled out to find its config.
CONFIG = config_for("fruity.lib.frontend.app", FrontendConfig)
# Where the API is depends on the deployment, not on this code, so the platform can override the config file.
API_ENDPOINT = os.environ.get("FRUITY_API_ENDPOINT", CONFIG.api_endpoint)


def main() -> None:
    """Show the page."""
    st.title("What food is this?")
    uploads = st.file_uploader("Food photos", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
    if not (uploads and st.button("Classify")):
        return
    files = [("files", (upload.name, upload.getvalue(), upload.type)) for upload in uploads]
    response = requests.post(API_ENDPOINT, files=files, timeout=CONFIG.timeout_seconds)
    if not response.ok:
        st.error(response.json().get("detail", "The classifier could not answer."))
        return
    for upload, result in zip(uploads, response.json(), strict=True):
        answers = ", ".join(
            f"{prediction['label'].replace('_', ' ')} ({prediction['probability']:.0%})"
            for prediction in result["predictions"]
        )
        st.image(upload, caption=answers)


main()
