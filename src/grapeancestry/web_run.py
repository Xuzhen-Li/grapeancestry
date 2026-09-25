"""Write a temp samples YAML and invoke the v1 CLI."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import yaml

from grapeancestry.report.build_report import REPORT_V2_SUFFIX

PCA_COLORS = ("Grp", "CON", "GEO", "Uti")
ADMIX_MODES = ("auto", "lookup", "nnls", "official")
FASTP_POLY_G = ("auto", "on", "off")
AR3_ADAPTER_SEL = ("auto", "manual", "undefined", "none")
AR3_QUAL_TRIM = ("mott", "window", "per-base", "none")
AR3_POLYX = ("auto", "off")
_ADAPTER_DNA = re.compile(r"^[ACGTN]*$", re.I)

SNAKE_KEYS = (
    "threads",
    "fastp_min_length",
    "fastp_qualified_quality",
    "fastp_unqualified_percent",
    "fastp_n_base_limit",
    "fastp_poly_g",
    "fastp_cut_tail",
    "fastp_cut_mean_quality",
    "fastp_detect_adapter_pe",
    "adna_min_length",
    "adna_adapter_selection",
    "adna_adapter1",
    "adna_quality_trimming",
    "adna_trim_min_quality",
    "adna_trim_mott_rate",
    "adna_min_overlap",
    "adna_mismatch_rate",
    "adna_pre_trim_polyx",
    "adna_min_mean_quality",
    "bwa_mem_seed",
    "bwa_mem_min_score",
    "bwa_aln_l",
    "bwa_aln_n",
    "bwa_aln_max_gap",
    "min_mq",
    "min_bq",
    "max_depth",
    "adjust_mq",
    "min_dp",
)


@dataclass
class PipelineOptions:
    """UI / CLI knobs. Defaults match config/default.yaml and the tool --help."""

    paired: bool = False
    as_query: bool = True
    threads: int = 4
    force_query_vcf: bool = False
    snakemake_force: bool = False
    pca_color: str = "Grp"
    admix_mode: str = "auto"
    admix_all_k: bool = True
    source_sample: str = ""
    fastp_min_length: int = 15
    fastp_qualified_quality: int = 15
    fastp_unqualified_percent: int = 40
    fastp_n_base_limit: int = 5
    fastp_poly_g: str = "auto"
    fastp_cut_tail: bool = False
    fastp_cut_mean_quality: int = 20
    fastp_detect_adapter_pe: bool = True
    adna_min_length: int = 25
    adna_adapter_selection: str = "auto"
    adna_adapter1: str = ""
    adna_quality_trimming: str = "mott"
    adna_trim_min_quality: int = 2
    adna_trim_mott_rate: float = 0.05
    adna_min_overlap: int = 1
    adna_mismatch_rate: float = 0.1667
    adna_pre_trim_polyx: str = "auto"
    adna_min_mean_quality: int = 0
    bwa_mem_seed: int = 19
    bwa_mem_min_score: int = 30
    bwa_aln_l: int = 1024
    bwa_aln_n: float = 0.01
    bwa_aln_max_gap: int = 1
    min_mq: int = 0
    min_bq: int = 13
    max_depth: int = 250
    adjust_mq: int = 0
    min_dp: int = 0

    def __post_init__(self) -> None:
        self.paired = bool(self.paired)
        self.as_query = bool(self.as_query)
        self.force_query_vcf = bool(self.force_query_vcf)
        self.snakemake_force = bool(self.snakemake_force)
        self.admix_all_k = bool(self.admix_all_k)
        self.fastp_cut_tail = bool(self.fastp_cut_tail)
        self.fastp_detect_adapter_pe = bool(self.fastp_detect_adapter_pe)
        self.threads = int(self.threads)
        self.fastp_min_length = int(self.fastp_min_length)
        self.fastp_qualified_quality = int(self.fastp_qualified_quality)
        self.fastp_unqualified_percent = int(self.fastp_unqualified_percent)
        self.fastp_n_base_limit = int(self.fastp_n_base_limit)
        self.fastp_cut_mean_quality = int(self.fastp_cut_mean_quality)
        self.adna_min_length = int(self.adna_min_length)
        self.adna_trim_min_quality = int(self.adna_trim_min_quality)
        self.adna_min_overlap = int(self.adna_min_overlap)
        self.adna_min_mean_quality = int(self.adna_min_mean_quality)
        self.bwa_mem_seed = int(self.bwa_mem_seed)
        self.bwa_mem_min_score = int(self.bwa_mem_min_score)
        self.bwa_aln_l = int(self.bwa_aln_l)
        self.bwa_aln_max_gap = int(self.bwa_aln_max_gap)
        self.min_mq = int(self.min_mq)
        self.min_bq = int(self.min_bq)
        self.max_depth = int(self.max_depth)
        self.adjust_mq = int(self.adjust_mq)
        self.min_dp = int(self.min_dp)
        self.bwa_aln_n = float(self.bwa_aln_n)
        self.adna_trim_mott_rate = float(self.adna_trim_mott_rate)
        self.adna_mismatch_rate = float(self.adna_mismatch_rate)
        self.source_sample = str(self.source_sample or "").strip()
        self.adna_adapter1 = str(self.adna_adapter1 or "").strip().upper()
        self.pca_color = str(self.pca_color)
        self.admix_mode = str(self.admix_mode)
        self.fastp_poly_g = str(self.fastp_poly_g)
        self.adna_adapter_selection = str(self.adna_adapter_selection)
        self.adna_quality_trimming = str(self.adna_quality_trimming)
        self.adna_pre_trim_polyx = str(self.adna_pre_trim_polyx)
        if self.pca_color not in PCA_COLORS:
            raise ValueError(f"pca_color must be one of {PCA_COLORS}")
        if self.admix_mode not in ADMIX_MODES:
            raise ValueError(f"admix_mode must be one of {ADMIX_MODES}")
        if self.fastp_poly_g not in FASTP_POLY_G:
            raise ValueError(f"fastp_poly_g must be one of {FASTP_POLY_G}")
        if self.adna_adapter_selection not in AR3_ADAPTER_SEL:
            raise ValueError(f"adna_adapter_selection must be one of {AR3_ADAPTER_SEL}")
        if self.adna_quality_trimming not in AR3_QUAL_TRIM:
            raise ValueError(f"adna_quality_trimming must be one of {AR3_QUAL_TRIM}")
        if self.adna_pre_trim_polyx not in AR3_POLYX:
            raise ValueError(f"adna_pre_trim_polyx must be one of {AR3_POLYX}")
        if self.adna_adapter1 and not _ADAPTER_DNA.match(self.adna_adapter1):
            raise ValueError("adna_adapter1 must be ACGTN only")

    def as_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> PipelineOptions:
        if not data:
            return cls()
        allowed = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in allowed})


def write_run_config(dest: Path, root: Path, options: PipelineOptions) -> Path:
    cfg = yaml.safe_load((root / "config" / "default.yaml").read_text()) or {}
    for key in SNAKE_KEYS:
        cfg[key] = getattr(options, key)
    dest.write_text(yaml.safe_dump(cfg, sort_keys=False))
    return dest


def _analyze_flags(options: PipelineOptions, *, with_source: bool = False) -> list[str]:
    cmd: list[str] = []
    if options.as_query:
        cmd.append("--as-query")
    else:
        cmd.append("--in-panel")
    if options.force_query_vcf:
        cmd.append("--force-query-vcf")
    cmd.extend(["--pca-color", options.pca_color])
    cmd.extend(["--admix-mode", options.admix_mode])
    cmd.append("--admix-all-k" if options.admix_all_k else "--admix-k8-only")
    if with_source and options.source_sample:
        cmd.extend(["--source-sample", options.source_sample])
    return cmd


def write_samples_yaml(
    dest: Path,
    sample: str,
    kind: str,
    files: dict[str, str],
    *,
    paired: bool = False,
) -> Path:
    rec: dict = {"type": kind}
    rec.update(files)
    if kind == "bam":
        rec["paired"] = bool(paired)
    dest.write_text(yaml.safe_dump({"samples": {sample: rec}}, sort_keys=False))
    return dest


def v2_names(sample: str) -> tuple[str, str]:
    html = f"{sample}{REPORT_V2_SUFFIX}"
    sidecar = html.replace(".html", ".data.json")
    return html, sidecar


def report_id_for(sample: str, kind: str, as_query: bool) -> str:
    sid = sample.strip()
    if as_query and not sid.endswith("_query"):
        return f"{sid}_query"
    return sid


def pipeline_command(
    root: Path,
    sample: str,
    kind: str,
    files: dict[str, str],
    *,
    paired: bool = False,
    as_query: bool = True,
    threads: int = 4,
    options: PipelineOptions | None = None,
) -> list[str]:
    opt = options or PipelineOptions(paired=paired, as_query=as_query, threads=threads)
    flags = _analyze_flags(opt, with_source=(kind == "vcf"))
    if kind == "vcf":
        cmd = [
            sys.executable,
            "-m",
            "grapeancestry.cli",
            "analyze",
            "--sample",
            sample,
            "--vcf",
            str(files["vcf"]),
        ]
        cmd.extend(flags)
        return cmd
    yaml_path = Path(tempfile.mkstemp(suffix=".yaml", prefix="ga-samples-")[1])
    write_samples_yaml(yaml_path, sample, kind, files, paired=opt.paired)
    cfg_path = Path(tempfile.mkstemp(suffix=".yaml", prefix="ga-config-")[1])
    write_run_config(cfg_path, root, opt)
    cmd = [
        sys.executable,
        "-m",
        "grapeancestry.cli",
        "run",
        "--config",
        str(cfg_path),
        "--samples",
        str(yaml_path),
        "--sample",
        sample,
        "-j",
        str(opt.threads),
        "--mapping",
        "full",
    ]
    cmd.extend(flags)
    if opt.snakemake_force:
        cmd.append("--forceall")
    return cmd


def iter_pipeline(
    root: Path,
    sample: str,
    kind: str,
    files: dict[str, str],
    *,
    paired: bool = False,
    as_query: bool = True,
    threads: int = 4,
    extra_env: dict[str, str] | None = None,
    options: PipelineOptions | None = None,
) -> Iterator[tuple[str | None, int | None]]:
    """Yield (log_line, None) then (None, returncode)."""
    cmd = pipeline_command(
        root,
        sample,
        kind,
        files,
        paired=paired,
        as_query=as_query,
        threads=threads,
        options=options,
    )
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    proc = subprocess.Popen(
        cmd,
        cwd=root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        yield line, None
    yield None, int(proc.wait())


def run_pipeline(
    root: Path,
    sample: str,
    kind: str,
    files: dict[str, str],
    *,
    paired: bool = False,
    as_query: bool = True,
    threads: int = 4,
    extra_env: dict[str, str] | None = None,
    options: PipelineOptions | None = None,
) -> subprocess.CompletedProcess[str]:
    chunks: list[str] = []
    code = 1
    for line, rc in iter_pipeline(
        root,
        sample,
        kind,
        files,
        paired=paired,
        as_query=as_query,
        threads=threads,
        extra_env=extra_env,
        options=options,
    ):
        if line is not None:
            chunks.append(line)
        if rc is not None:
            code = rc
    return subprocess.CompletedProcess(
        args=["grapeancestry"],
        returncode=code,
        stdout="".join(chunks),
        stderr="",
    )
