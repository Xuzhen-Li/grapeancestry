"""v1 paths: customer output, asset publish, VCF staging."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def customer_output_root(root: Path) -> Path:
    env = os.environ.get("GRAPEANCESTRY_OUTPUT")
    if env:
        return Path(env)
    docker = Path("/output")
    if docker.is_dir() and os.access(docker, os.W_OK):
        return docker
    local = root / "output"
    if local.is_dir():
        return local
    return root / "results"


def customer_input_root(root: Path) -> Path:
    env = os.environ.get("GRAPEANCESTRY_INPUT")
    if env:
        return Path(env)
    docker = Path("/input")
    if docker.is_dir():
        return docker
    return root / "input"


def settings_root(root: Path) -> Path:
    env = os.environ.get("GRAPEANCESTRY_SETTINGS")
    if env:
        return Path(env)
    docker = Path("/settings")
    if docker.is_dir() and os.access(docker, os.W_OK):
        return docker
    local = root / "settings"
    local.mkdir(parents=True, exist_ok=True)
    return local


def sync_assets(root: Path, dest_parent: Path) -> Path:
    src = root / "assets"
    dest = dest_parent / "assets"
    if not src.is_dir():
        return dest
    dest.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dest / item.name
        if item.is_file():
            shutil.copy2(item, target)
    return dest


def publish_v2_report(root: Path, html_path: Path) -> Path:
    """Copy V2 HTML/JSON into output/results so ../assets resolves."""
    out_root = customer_output_root(root)
    reports = out_root / "results"
    reports.mkdir(parents=True, exist_ok=True)
    sync_assets(root, out_root)
    dest = reports / html_path.name
    if html_path.resolve() != dest.resolve():
        shutil.copy2(html_path, dest)
        sidecar = html_path.with_suffix(".data.json")
        # write_dashboard_html uses out_html.with_suffix(".data.json")
        # which turns .report.html into .report.data.json? with_suffix replaces last suffix only
        # .sample-first-v2.report.html -> .sample-first-v2.report.data.json if they used
        # Path.with_suffix(".data.json") on .html → .sample-first-v2.report.data.json
        alt = html_path.with_name(html_path.name.replace(".html", ".data.json"))
        if sidecar.exists():
            shutil.copy2(sidecar, dest.with_suffix(".data.json"))
        elif alt.exists():
            shutil.copy2(alt, reports / alt.name)
    return dest


def stage_vcf(src: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = Path(src)
    dest = Path(dest)
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    tbi = Path(str(src) + ".tbi")
    dest_tbi = Path(str(dest) + ".tbi")
    if tbi.exists() and src.resolve() != dest.resolve():
        shutil.copy2(tbi, dest_tbi)
    elif not dest_tbi.exists():
        subprocess.check_call(["bcftools", "index", "-t", str(dest)])
    return dest
