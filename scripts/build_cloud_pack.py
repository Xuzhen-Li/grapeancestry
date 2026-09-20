#!/usr/bin/env python3
"""Build data/cloud/ for Streamlit Cloud. Same as python -m grapeancestry.cloud.pack."""

from grapeancestry.cloud.pack import build_cloud_pack, suite_root

if __name__ == "__main__":
    print(build_cloud_pack(suite_root()))
