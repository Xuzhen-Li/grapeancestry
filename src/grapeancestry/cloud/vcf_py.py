"""Parse panel-site VCF / VCF.gz with the stdlib (no bcftools).

Dosage coding matches ``grapeancestry.core.dosage``: 0/1/2, −1 missing.
Strip a leading ``chr`` so VS-1 numeric contigs match the 167K site list.
"""

from __future__ import annotations

import gzip
import io
from dataclasses import dataclass, field
from pathlib import Path

from grapeancestry.core.dosage import _gt_to_dose

MAX_UPLOAD_BYTES = 80 * 1024 * 1024
MAX_SAMPLES = 20
_GZIP_MAGIC = b"\x1f\x8b"


def _norm_chrom(chrom: str) -> str:
    c = chrom.strip()
    if c.lower().startswith("chr"):
        c = c[3:]
    return c


def _gt_index(fmt: str) -> int:
    parts = fmt.split(":")
    try:
        return parts.index("GT")
    except ValueError:
        return 0


def _open_text(data: bytes) -> io.TextIOBase:
    if data.startswith(_GZIP_MAGIC):
        return io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(data)), encoding="utf-8")
    return io.StringIO(data.decode("utf-8", errors="replace"))


@dataclass
class ParsedVcf:
    samples: list[str]
    dosages: dict[str, dict[str, int]]  # sample → site → dosage
    n_records: int = 0
    filename: str = ""
    extra: dict = field(default_factory=dict)


def parse_vcf_bytes(
    data: bytes,
    *,
    filename: str = "query.vcf",
    panel_sites: set[str] | None = None,
    max_bytes: int = MAX_UPLOAD_BYTES,
    max_samples: int = MAX_SAMPLES,
) -> ParsedVcf:
    if len(data) > max_bytes:
        raise ValueError(f"VCF larger than {max_bytes} bytes")
    samples: list[str] = []
    dosages: dict[str, dict[str, int]] = {}
    n_records = 0
    with _open_text(data) as fh:
        for line in fh:
            if not line or line.startswith("##"):
                continue
            if line.startswith("#CHROM"):
                cols = line.rstrip("\n").split("\t")
                samples = cols[9:]
                if len(samples) > max_samples:
                    raise ValueError(f"too many samples ({len(samples)} > {max_samples})")
                dosages = {s: {} for s in samples}
                continue
            if not samples:
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 10:
                continue
            site = f"{_norm_chrom(cols[0])}:{cols[1]}"
            n_records += 1
            if panel_sites is not None and site not in panel_sites:
                continue
            gi = _gt_index(cols[8])
            for sid, cell in zip(samples, cols[9:]):
                gt = cell.split(":")[gi] if cell else "."
                dosages[sid][site] = _gt_to_dose(gt)
    if not samples:
        raise ValueError("no VCF sample columns (missing #CHROM header)")
    return ParsedVcf(samples=samples, dosages=dosages, n_records=n_records, filename=filename)


def parse_vcf_path(path: Path, **kwargs) -> ParsedVcf:
    return parse_vcf_bytes(path.read_bytes(), filename=path.name, **kwargs)


def align_dosage(site_map: dict[str, int], sites: list[str]) -> list[int]:
    return [int(site_map.get(s, -1)) for s in sites]
