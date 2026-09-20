"""Machine-readable provenance records for breeding pipeline steps.

Schema (plan §7.1): step, timestamp, git_sha, python/numpy/scipy/torch,
inputs, parameters, counts, methods, outputs, caveats.

Ref keys in ``methods[].ref_keys`` must exist in ``docs/REFERENCES.bib``.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STEPS = (
    "phenotype_etl",
    "gwas",
    "gs_train",
    "gs_predict",
    "cross_recommend",
)


@dataclass
class FileRef:
    path: str
    sha256: str
    n_rows: int | None = None
    note: str = ""


@dataclass
class MethodRef:
    name: str
    ref_keys: list[str] = field(default_factory=list)


@dataclass
class Provenance:
    step: str
    timestamp: str
    git_sha: str
    python: str
    numpy: str
    scipy: str
    torch: str | None
    inputs: list[dict[str, Any]]
    parameters: dict[str, Any]
    counts: dict[str, Any]
    methods: list[dict[str, Any]]
    outputs: list[dict[str, Any]]
    caveats: list[str]


def sha256_file(path: Path, *, max_bytes: int = 64 * 1024 * 1024) -> str:
    """SHA256 of file; files larger than max_bytes hash the prefix plus size."""
    h = hashlib.sha256()
    n = 0
    if not path.exists() or not path.is_file():
        return ""
    with path.open("rb") as fh:
        while n < max_bytes:
            chunk = fh.read(min(1 << 20, max_bytes - n))
            if not chunk:
                break
            h.update(chunk)
            n += len(chunk)
    size = path.stat().st_size
    if size > max_bytes:
        h.update(f"|size={size}".encode())
    return h.hexdigest()


def git_sha(cwd: Path | None = None) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(cwd) if cwd else None,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return "unknown"


def package_versions() -> dict[str, str | None]:
    out: dict[str, str | None] = {
        "python": sys.version.split()[0],
        "numpy": None,
        "scipy": None,
        "torch": None,
    }
    try:
        import numpy as np

        out["numpy"] = np.__version__
    except ImportError:
        pass
    try:
        import scipy

        out["scipy"] = scipy.__version__
    except ImportError:
        pass
    try:
        import torch

        out["torch"] = torch.__version__
    except ImportError:
        pass
    return out


def file_ref(path: Path, *, n_rows: int | None = None, note: str = "") -> dict[str, Any]:
    return asdict(
        FileRef(
            path=str(path),
            sha256=sha256_file(path) if path.exists() and path.is_file() else "",
            n_rows=n_rows,
            note=note,
        )
    )


def write_provenance(
    out_dir: Path,
    *,
    step: str,
    inputs: list[dict[str, Any]],
    parameters: dict[str, Any],
    counts: dict[str, Any],
    methods: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
    caveats: list[str],
    git_cwd: Path | None = None,
    filename: str | None = None,
) -> Path:
    """Write ``results/provenance/{step}.json`` (or ``filename``)."""
    if step not in STEPS:
        raise ValueError(f"unknown provenance step {step!r}; expected one of {STEPS}")
    vers = package_versions()
    rec = Provenance(
        step=step,
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        git_sha=git_sha(git_cwd),
        python=str(vers["python"]),
        numpy=str(vers["numpy"] or ""),
        scipy=str(vers["scipy"] or ""),
        torch=vers["torch"],
        inputs=inputs,
        parameters=parameters,
        counts=counts,
        methods=methods,
        outputs=outputs,
        caveats=caveats,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / (filename or f"{step}.json")
    dest.write_text(json.dumps(asdict(rec), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return dest


def load_provenance(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def collect_ref_keys(records: list[dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for rec in records:
        for m in rec.get("methods") or []:
            for k in m.get("ref_keys") or []:
                keys.add(str(k))
    return keys
