"""Write customer files into ./input and sniff FASTQ / BAM / VCF."""

from __future__ import annotations

import gzip
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from grapeancestry.core.ingest_bam import contig_mismatch_message, load_fai_contigs

VS1_FAI = Path("data/ref/VS1.final.fa.fai")

# Orlando 2026 NC submitted BAM for library V5 (filename *Ages*; ENA sample_alias V57).
# Lab wget: http://ftp.sra.ebi.ac.uk/vol1/run/ERR166/ERR16654874/V5xL1xP2_Ages_3_5070.12Xv2.realigned.bam
# ENA filereport ERR16654874 / PRJEB94459 (https://www.ebi.ac.uk/ena/portal/api/filereport?accession=ERR16654874&result=read_run)
ORLANDO_V5_AGES_URL = (
    "https://ftp.sra.ebi.ac.uk/vol1/run/ERR166/ERR16654874/"
    "V5xL1xP2_Ages_3_5070.12Xv2.realigned.bam"
)
ORLANDO_V5_AGES_RUN = "ERR16654874"
ORLANDO_V5_AGES_STUDY = "PRJEB94459"

_FASTQ_EXT = (".fq", ".fastq", ".fq.gz", ".fastq.gz")
_VCF_EXT = (".vcf", ".vcf.gz")


@dataclass
class IntakeReport:
    path: str
    name: str
    kind: str
    ok: bool
    size: int
    messages: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def safe_input_name(name: str) -> str:
    base = Path(name).name.replace("\x00", "")
    if not base or base in {".", ".."} or "/" in base or "\\" in base:
        raise ValueError("invalid file name")
    if ".." in base:
        raise ValueError("invalid file name")
    return base


def guess_kind(name: str) -> str:
    n = name.lower()
    if n.endswith(".bam"):
        return "bam"
    if any(n.endswith(ext) for ext in _VCF_EXT):
        return "vcf"
    if any(n.endswith(ext) for ext in _FASTQ_EXT):
        return "fastq"
    return "unknown"


def ensure_input_dir(dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    return dest_dir


def write_bytes(dest_dir: Path, name: str, data: bytes) -> Path:
    dest_dir = ensure_input_dir(dest_dir)
    dest = dest_dir / safe_input_name(name)
    dest.write_bytes(data)
    return dest


def copy_into_input(src: Path, dest_dir: Path) -> Path:
    if not src.is_file() or src.stat().st_size == 0:
        raise ValueError(f"missing or empty: {src}")
    dest_dir = ensure_input_dir(dest_dir)
    dest = dest_dir / safe_input_name(src.name)
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    return dest


def fetch_url(url: str, dest_dir: Path, *, timeout: float | None = None) -> Path:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("only http(s) URLs")
    name = safe_input_name(Path(parsed.path).name or "download.bin")
    dest_dir = ensure_input_dir(dest_dir)
    dest = dest_dir / name
    req = Request(url.strip(), headers={"User-Agent": "GrapeAncestry/1.0"})
    wrote = 0
    with urlopen(req, timeout=timeout) as resp, dest.open("wb") as out:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
            wrote += len(chunk)
    if wrote == 0:
        dest.unlink(missing_ok=True)
        raise ValueError("empty download")
    return dest


def _text_head(path: Path, n: int = 4096) -> str:
    with path.open("rb") as raw:
        magic = raw.read(2)
        raw.seek(0)
        if magic == b"\x1f\x8b":
            with gzip.GzipFile(fileobj=raw, mode="rb") as gz:
                return gz.read(n).decode("utf-8", "replace")
        return raw.read(n).decode("utf-8", "replace")


def _is_gzip(path: Path) -> bool:
    with path.open("rb") as raw:
        return raw.read(2) == b"\x1f\x8b"


def inspect_input(path: Path, *, root: Path | None = None) -> IntakeReport:
    name = path.name
    kind = guess_kind(name)
    size = path.stat().st_size if path.is_file() else 0
    messages: list[str] = []
    ok = True
    if not path.is_file() or size == 0:
        return IntakeReport(str(path), name, kind, False, size, ["empty or missing file"])
    if kind == "unknown":
        return IntakeReport(str(path), name, kind, False, size, ["need FASTQ, BAM, or VCF"])
    try:
        if kind == "fastq":
            if name.lower().endswith(".gz") and not _is_gzip(path):
                ok = False
                messages.append("name is .gz but bytes are not gzip")
            else:
                head = _text_head(path)
                if not head.lstrip().startswith("@"):
                    ok = False
                    messages.append("FASTQ should start with @")
                else:
                    messages.append("FASTQ header ok")
        elif kind == "vcf":
            if name.lower().endswith(".gz") and not _is_gzip(path):
                ok = False
                messages.append("name is .gz but bytes are not gzip")
            else:
                head = _text_head(path, n=512_000)
                if "##fileformat=VCF" not in head:
                    ok = False
                    messages.append("VCF missing ##fileformat=VCF")
                elif "#CHROM" not in head:
                    ok = False
                    messages.append("VCF missing #CHROM header")
                else:
                    messages.append("VCF header ok")
        elif kind == "bam":
            if not _is_gzip(path):
                ok = False
                messages.append("BAM should be BGZF (gzip magic)")
            else:
                messages.append("BAM BGZF magic ok")
            fai = (root / VS1_FAI) if root is not None else None
            if ok and fai is not None and fai.is_file() and shutil.which("samtools"):
                from grapeancestry.core.ingest_bam import bam_sq_names

                try:
                    msg = contig_mismatch_message(load_fai_contigs(fai), bam_sq_names(path))
                except (OSError, subprocess.CalledProcessError) as exc:
                    ok = False
                    messages.append(f"samtools header failed: {exc}")
                else:
                    if msg:
                        ok = False
                        messages.append(msg)
                    else:
                        messages.append("BAM @SQ overlaps VS-1")
            elif ok:
                messages.append("VS-1 contig check skipped (no samtools or fai)")
    except OSError as exc:
        ok = False
        messages.append(str(exc))
    return IntakeReport(str(path), name, kind, ok, size, messages)
