"""A demo page: upload food photos and see what the API calls them."""

from __future__ import annotations

import requests
import streamlit as st
from pydantic import BaseModel, ConfigDict

from fruity.lib.shared.settings import config_for


class FrontendConfig(BaseModel):
    """Where the API is."""

    model_config = ConfigDict(extra="forbid")

    api_endpoint: str


CONFIG = config_for(__name__, FrontendConfig)


def main() -> None:
    """Show the page."""
    st.title("What food is this?")
    uploads = st.file_uploader("Food photos", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
    if uploads and st.button("Classify"):
        files = [("files", (upload.name, upload.getvalue(), upload.type)) for upload in uploads]
        response = requests.post(CONFIG.api_endpoint, files=files, timeout=120)
        response.raise_for_status()
        results = response.json()
        for upload in uploads:
            st.image(upload, caption=results.get(upload.name, "Unknown"))


main()
