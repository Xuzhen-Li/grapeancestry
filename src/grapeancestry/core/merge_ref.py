"""Merge user sample VCF(s) with the 2449-sample reference panel.

Strategy:
- Align user sites to panel site set (missing → ./.)
- Harmonize REF/ALT against panel
- bcftools merge → merged.vcf.gz with n_samples = 2449 + N
"""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path


def write_query_vcf(
    user_vcf: Path,
    out_vcf: Path,
    *,
    new_id: str | None = None,
) -> str:
    """Copy a single-sample VCF and rename the ID to ``{id}_query``.

    Used when an independently called VCF reuses a panel accession name
    (e.g. HUN89) and must be treated as a stranger sample, not in-panel lookup.
    """
    samples = subprocess.check_output(["bcftools", "query", "-l", str(user_vcf)], text=True).splitlines()
    if not samples:
        raise ValueError(f"no samples in {user_vcf}")
    if len(samples) != 1:
        raise ValueError(
            f"{user_vcf} must be a single-sample VCF; found {len(samples)} samples"
        )
    if new_id is None:
        new_id = samples[0] if samples[0].endswith("_query") else f"{samples[0]}_query"
    out_vcf.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ga_query_") as td:
        rename_map = Path(td) / "rename.txt"
        with rename_map.open("w") as fh:
            for s in samples:
                fh.write(f"{s}\t{new_id if len(samples) == 1 else (s if s.endswith('_query') else f'{s}_query')}\n")
        tmp = Path(td) / "renamed.vcf.gz"
        subprocess.check_call(["bcftools", "reheader", "-s", str(rename_map), "-o", str(tmp), str(user_vcf)])
        subprocess.check_call(["bcftools", "index", "-t", str(tmp)])
        subprocess.check_call(["bcftools", "view", "-Oz", "-o", str(out_vcf), str(tmp)])
        subprocess.check_call(["bcftools", "index", "-t", "-f", str(out_vcf)])
    out_ids = subprocess.check_output(["bcftools", "query", "-l", str(out_vcf)], text=True).splitlines()
    return out_ids[0] if out_ids else new_id


def merge_ref(user_vcfs: list[Path], panel_vcf: Path, out_vcf: Path) -> None:
    out_vcf.parent.mkdir(parents=True, exist_ok=True)
    panel_samples = set(
        subprocess.check_output(["bcftools", "query", "-l", str(panel_vcf)], text=True).splitlines()
    )
    with tempfile.TemporaryDirectory(prefix="ga_merge_") as td:
        td_path = Path(td)
        normed: list[Path] = []
        for i, uv in enumerate(user_vcfs):
            samples = subprocess.check_output(["bcftools", "query", "-l", str(uv)], text=True).splitlines()
            rename_map = td_path / f"rename_{i}.txt"
            with rename_map.open("w") as fh:
                for s in samples:
                    new = f"{s}_query" if s in panel_samples else s
                    if new != s:
                        fh.write(f"{s}\t{new}\n")
            tgt = td_path / f"user_{i}.vcf.gz"
            lean = td_path / f"user_{i}.lean.vcf.gz"
            # GT-only to avoid INFO/FORMAT type clashes with panel
            subprocess.check_call(
                ["bcftools", "annotate", "-x", "INFO,^FORMAT/GT", "-Oz", "-o", str(lean), str(uv)]
            )
            subprocess.check_call(["bcftools", "index", "-t", str(lean)])
            if rename_map.stat().st_size > 0:
                subprocess.check_call(
                    [
                        "bcftools",
                        "reheader",
                        "-s",
                        str(rename_map),
                        "-o",
                        str(tgt),
                        str(lean),
                    ]
                )
                subprocess.check_call(["bcftools", "index", "-t", str(tgt)])
            else:
                lean.rename(tgt)
                # index already on lean path name — reindex
                subprocess.check_call(["bcftools", "index", "-t", str(tgt)])
            normed.append(tgt)

        if not Path(str(panel_vcf) + ".tbi").exists() and not Path(str(panel_vcf) + ".csi").exists():
            subprocess.check_call(["bcftools", "index", "-t", str(panel_vcf)])

        merge_list = [str(panel_vcf)] + [str(p) for p in normed]
        cmd = [
            "bcftools",
            "merge",
            "-m",
            "none",
            "-Oz",
            "-o",
            str(out_vcf),
            *merge_list,
        ]
        subprocess.check_call(cmd)
        subprocess.check_call(["bcftools", "index", "-t", str(out_vcf)])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--user-vcf", type=Path, action="append", required=True)
    p.add_argument("--panel-vcf", type=Path, required=True)
    p.add_argument("--out-vcf", type=Path, required=True)
    args = p.parse_args(argv)
    merge_ref(args.user_vcf, args.panel_vcf, args.out_vcf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
