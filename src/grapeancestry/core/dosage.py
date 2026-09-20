"""Load allele dosages from panel / sample VCFs (MBP-safe streaming).

Dosage coding: 0=HOM_REF, 1=HET, 2=HOM_ALT, -1=missing.
Default: subsample every Nth site to ~n_sites for local demo.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import numpy as np


def list_samples(vcf: Path) -> list[str]:
    return subprocess.check_output(["bcftools", "query", "-l", str(vcf)], text=True).splitlines()


def _gt_to_dose(gt: str) -> int:
    if not gt or gt in {".", "./.", ".|."}:
        return -1
    gt = gt.split(":")[0].replace("|", "/")
    parts = gt.split("/")
    if len(parts) != 2 or "." in parts:
        return -1
    try:
        return int(parts[0]) + int(parts[1])
    except ValueError:
        return -1


def load_dosage_matrix(
    vcf: Path,
    *,
    every_nth: int = 30,
    max_sites: int = 5000,
    samples: list[str] | None = None,
) -> tuple[np.ndarray, list[str], list[str]]:
    """Return (n_samples, n_sites) int8 matrix, sample ids, site keys chrom:pos.

    every_nth: keep site i if i % every_nth == 0 (after filtering to max_sites).
    """
    all_samples = list_samples(vcf)
    if samples is None:
        samples = all_samples
    else:
        missing = [s for s in samples if s not in all_samples]
        if missing:
            raise ValueError(f"samples not in VCF: {missing[:5]}")

    # Stream GT for selected samples
    sample_arg = ",".join(samples)
    fmt = "%CHROM:%POS[\t%GT]\\n"
    proc = subprocess.Popen(
        ["bcftools", "query", "-s", sample_arg, "-f", fmt, str(vcf)],
        stdout=subprocess.PIPE,
        text=True,
        bufsize=1 << 20,
    )
    assert proc.stdout is not None

    site_keys: list[str] = []
    cols: list[list[int]] = []
    kept = 0
    seen = 0
    for line in proc.stdout:
        line = line.rstrip("\n")
        if not line:
            continue
        parts = line.split("\t")
        key = parts[0]
        if seen % every_nth == 0:
            doses = [_gt_to_dose(g) for g in parts[1:]]
            if len(doses) != len(samples):
                raise RuntimeError(f"GT width mismatch at {key}")
            site_keys.append(key)
            cols.append(doses)
            kept += 1
            if kept >= max_sites:
                break
        seen += 1
    proc.stdout.close()
    # drain/kill if early break
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    if not cols:
        raise RuntimeError(f"no sites loaded from {vcf}")

    # cols is list of length n_sites, each len n_samples → stack to (n_samples, n_sites)
    mat = np.asarray(cols, dtype=np.int8).T
    return mat, samples, site_keys


def load_sample_dosage(
    vcf: Path,
    sample: str,
    site_keys: list[str],
) -> np.ndarray:
    """Load one sample's dosages aligned to site_keys (missing=-1 if absent)."""
    want = {k: i for i, k in enumerate(site_keys)}
    out = np.full(len(site_keys), -1, dtype=np.int8)
    fmt = "%CHROM:%POS[\t%GT]\\n"
    raw = subprocess.check_output(
        ["bcftools", "query", "-s", sample, "-f", fmt, str(vcf)],
        text=True,
    )
    for line in raw.splitlines():
        if not line.strip():
            continue
        key, gt = line.split("\t", 1)
        idx = want.get(key)
        if idx is not None:
            out[idx] = _gt_to_dose(gt)
    return out


def save_cache(path: Path, mat: np.ndarray, samples: list[str], sites: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        mat=mat,
        samples=np.array(samples, dtype=object),
        sites=np.array(sites, dtype=object),
    )


CACHE_167K = Path("results/cache/panel_dosage_167k.npz")
CACHE_5K = Path("results/cache/panel_dosage_5k.npz")


def resolve_cache(root: Path) -> Path:
    """Prefer 167k analysis matrix; fall back to 5k smoke cache."""
    full = root / CACHE_167K
    if full.exists():
        return full
    return root / CACHE_5K


def load_cache(path: Path) -> tuple[np.ndarray, list[str], list[str]]:
    z = np.load(path, allow_pickle=True)
    return z["mat"], list(z["samples"]), list(z["sites"])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--panel-vcf", type=Path, required=True)
    p.add_argument("--out-npz", type=Path, required=True)
    p.add_argument("--every-nth", type=int, default=30)
    p.add_argument("--max-sites", type=int, default=5000)
    p.add_argument("--full", action="store_true", help="Keep all sites (167k; every-nth=1)")
    args = p.parse_args(argv)
    if args.full:
        args.every_nth = 1
        args.max_sites = 200_000
    mat, samples, sites = load_dosage_matrix(
        args.panel_vcf, every_nth=args.every_nth, max_sites=args.max_sites
    )
    save_cache(args.out_npz, mat, samples, sites)
    print(f"wrote {args.out_npz} shape={mat.shape} sites={len(sites)} samples={len(samples)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
