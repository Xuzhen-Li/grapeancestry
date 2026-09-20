"""Precomputed ADMIXTURE Q for the Italian 2449 panel (stat_vcf_from_3527).

Background (3k / chip project):
  9000+ WGS design cohort → 167K panel → QC on ~3527 chip samples →
  keep-list subset used for structure = **2449** IDs (older notes sometimes
  say **2448**; suite MANIFEST measured 2449). ADMIXTURE K=2..8 + pophelper
  plots live in ``stat_vcf_from_3527/ADMIXTURE/`` (k{K}.Q aligned to
  id_only.txt; metadata in 2449.info: CON/Wild/GEO/Uti/Grp).

This module loads precomputed Q (Science archive and/or ``panel167k_nogwas``)
and can project new samples with official ``admixture -P``. Prefer the
167k-minus-GWAS family when its Q+P exist. NNLS is only a fallback.
Do not mix ``grape.chip.subset.{K}.P`` (167,433 rows) with
``panel167k_nogwas.{K}.P`` (153,483 rows).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

import numpy as np

from grapeancestry.adna.grp_order import DEFAULT_GRP_ORDER, load_grp_order
from grapeancestry.adna.manual_qp import apply_q_dict_edits, projection_p_for_sample
from grapeancestry.adna.panel167k_nogwas import (
    ID_FILE_NAME,
    MANIFEST_NAME,
    REPORT_METHODS_PANEL167K,
    PANEL167K_NOGWAS_FAMILY,
    panel167k_assets_complete,
    p_path as panel167k_p_path,
    q_path as panel167k_q_path,
)


@dataclass
class AdmixtureContrast:
    sample: str
    meta: dict[str, str]
    q_by_k: dict[int, dict[str, float]]  # precomputed (in-panel) or empty
    grp_mean_by_k: dict[int, dict[str, float]]
    panel_mean_by_k: dict[int, dict[str, float]]
    n_panel: int
    n_grp: int
    grp_key: str
    grp_value: str
    projected_by_k: dict[int, dict[str, float]] = field(default_factory=dict)
    source: str = "lookup"  # lookup | projected | mixed
    grp_order: list[str] = field(default_factory=lambda: list(DEFAULT_GRP_ORDER))
    run_family: str = "legacy_chip"
    projection_status: str = "not_requested"
    projection_source: str = ""
    chip_projected_by_k: dict[int, dict[str, float]] = field(default_factory=dict)


# Science-style K=8 ancestry colors (Grp/Syl hex from Figure 1).
# These constants retain the short group aliases for API compatibility; the
# machine-readable manifest also stores full display labels and provenance.
SCIENCE_K8_COLORS: list[str] = [
    "#4470b7",
    "#dc1f26",
    "#981b1e",
    "#f7922c",
    "#835ca6",
    "#0b5475",
    "#fbee61",
    "#f6a3b1",
]
SCIENCE_K8_LABELS: list[str] = [
    "WWE1",
    "CG1",
    "CG6",
    "CG4",
    "CG3",
    "CG2",
    "CG5",
    "WWE2",
]
SCIENCE_K8_LEGEND_LABELS: list[str] = [
    "Syl-W1 (WWE1)",
    "Syl-E1 (WEE1) / CG1",
    "CG6",
    "CG4",
    "CG3",
    "Syl-E2 (WEE2) / CG2",
    "CG5",
    "Syl-W2 (WWE2)",
]
# Paper Fig. 1D uses one colour for WEE1 and CG1 (and WEE2/CG2). That combined
# legend name is for one colour, not two ADMIXTURE columns. Name a column by
# the owner groups that actually share that colour.
SCIENCE_GROUP_DISPLAY_LABEL: dict[str, str] = {
    "WWE1": "Syl-W1 (WWE1)",
    "WEE1": "Syl-E1 (WEE1)",
    "CG1": "CG1",
    "CG6": "CG6",
    "CG4": "CG4",
    "CG3": "CG3",
    "WEE2": "Syl-E2 (WEE2)",
    "CG2": "CG2",
    "CG5": "CG5",
    "WWE2": "Syl-W2 (WWE2)",
}
# Fig. 1D / fig. S8 plot K=2–8 as one series and name colours at K=8
# (Dong et al. 2023, https://doi.org/10.1126/science.add8655).
# ADMIXTURE column ids are independently labelled at every K (label switching):
# raw k1 at K=2 is not raw k1 at K=4. Alignment is always to the Science K=8
# *named* ancestries, never to ADMIXTURE's k1..kK integers.
SCIENCE_K_INHERITS_K8: dict[int, list[int]] = {
    2: [0, 1],
    3: [0, 1, 2],
    4: [0, 1, 2, 3],
    5: [0, 1, 2, 3, 4],
    6: [0, 1, 2, 3, 4, 5],
    7: [0, 1, 2, 3, 4, 5, 7],
    8: [0, 1, 2, 3, 4, 5, 6, 7],
}
# Report bars use paper-canonical order (existing Science components left to
# right as K1, K2, …). A manual Excel alignment is one worked example of
# the same identity mapping, not a plot permutation to copy.
SCIENCE_K8_GROUP_ANCHORS: list[tuple[str, int]] = [
    ("WWE1", 0),  # K1 Syl-W1 94.7%
    ("WEE1", 1),  # K2 Syl-E1 84.3%
    ("CG6", 2),  # K3 68.4%
    ("CG4", 3),  # K4 69.9%
    ("CG3", 4),  # K5 87.7%
    ("WEE2", 5),  # K6 Syl-E2 72.7%
    ("CG5", 6),  # K7 68.8%
    ("WWE2", 7),  # K8 Syl-W2 69.8%
]
SCIENCE_RUN_FAMILY = "science_core_ld_sort"
SCIENCE_MANIFEST_NAME = "science_manifest.json"

# Map a named Grp onto Dong et al. 2023 Fig. 1D K=8 colour index.
# WEE1 and CG1 share K2; WEE2 and CG2 share K6.
SCIENCE_GROUP_TO_K8: dict[str, int] = {
    "WWE1": 0,
    "WEE1": 1,
    "CG1": 1,
    "CG6": 2,
    "CG4": 3,
    "CG3": 4,
    "WEE2": 5,
    "CG2": 5,
    "CG5": 6,
    "WWE2": 7,
}
SCIENCE_K8_EXTRA_COLORS: list[str] = ["#00c853", "#00b0ff"]
# C1…C10 paint. C1/C2 kept; C3–C5/C8 from Dong 2023 Fig. 1D
# (doi:10.1126/science.add8655). C6 pink, C7 yellow unchanged.
COMPONENT_COLORS: list[str] = [
    "#4470b7",  # C1 west (unchanged)
    "#dc1f26",  # C2 east (unchanged)
    "#981b1e",  # C3 CG6
    "#835ca6",  # C4 CG3
    "#f7922c",  # C5 CG4
    "#f6a3b1",  # C6 pink (unchanged)
    "#fbee61",  # C7 yellow (unchanged)
    "#0b5475",  # C8 CG2
    "#00c853",  # C9 green
    "#00b0ff",  # C10 cyan
]


def unique_component_colors(k: int) -> list[str]:
    """C1…CK each get a different colour. Colour i is stable across K."""
    if k < 1 or k > len(COMPONENT_COLORS):
        raise ValueError(f"need 1..{len(COMPONENT_COLORS)} colours, got K={k}")
    colors = COMPONENT_COLORS[:k]
    if len({c.lower() for c in colors}) != k:
        raise ValueError(f"COMPONENT_COLORS[:{k}] are not unique")
    return list(colors)


def stack_newest_on_top(q: np.ndarray, colors: list[str]) -> tuple[np.ndarray, list[str], list[int]]:
    """Draw CK at the top (origin='upper'), C1 at the bottom."""
    k = q.shape[1]
    order = list(range(k - 1, -1, -1))
    return q[:, order], [colors[i] for i in order], order
# Layer-2 Pearson cores: 10 Dong source groups. Not C-Ad / W-Ad / ITA / OUT.
# Spec: 00_array/admixture-qp-and-projection/q-column-alignment-schemes.md
SCIENCE_K8_GROUPS: tuple[str, ...] = (
    "WWE1",
    "WWE2",
    "WEE1",
    "WEE2",
    "CG1",
    "CG2",
    "CG3",
    "CG4",
    "CG5",
    "CG6",
)
_SCIENCE_CONFLICT_PRIORITY: list[str] = [
    "WWE1",
    "WEE1",
    "WWE2",
    "WEE2",
    "CG1",
    "CG2",
    "CG3",
    "CG4",
    "CG5",
    "CG6",
]


def owner_groups_for_science_paint(label: str) -> list[str]:
    """Purest-owner groups for Science colour. Mean-only leftovers are extra."""
    if not label or label == "—" or "(mean" in label:
        return []
    groups: list[str] = []
    for part in label.split("+"):
        name = part.split(":")[0].strip()
        if name:
            groups.append(name)
    return groups


def science_extra_color(k: int, extra_i: int = 0) -> str:
    """Leftover colour: first new at K=9, second new at K=10."""
    i = max(int(k) - 9, 0) + int(extra_i)
    return SCIENCE_K8_EXTRA_COLORS[min(i, len(SCIENCE_K8_EXTRA_COLORS) - 1)]


def science_index_for_groups(groups: list[str]) -> int | None:
    """Science K=8 colour index for a column's owner groups, or None if extra."""
    names = [g for g in groups if g in SCIENCE_GROUP_TO_K8]
    if not names:
        return None
    if "WWE1" in names:
        return 0
    if "WWE2" in names and "WWE1" not in names:
        return 7
    for g in _SCIENCE_CONFLICT_PRIORITY:
        if g in names:
            return SCIENCE_GROUP_TO_K8[g]
    return SCIENCE_GROUP_TO_K8[names[0]]


def owner_groups_for_colour(groups: list[str], science_index: int) -> list[str]:
    """Owner groups that paint to this Fig. 1D colour (Dong et al. 2023)."""
    return [g for g in groups if SCIENCE_GROUP_TO_K8.get(g) == science_index]


def display_label_for_owner_groups(groups: list[str], fallback: str = "") -> str:
    """Unique names for this column. Shared colour does not force a shared name."""
    ordered = [g for g in _SCIENCE_CONFLICT_PRIORITY if g in groups]
    for g in groups:
        if g not in ordered and g in SCIENCE_GROUP_DISPLAY_LABEL:
            ordered.append(g)
    seen: list[str] = []
    for g in ordered:
        lab = SCIENCE_GROUP_DISPLAY_LABEL.get(g, g)
        if lab not in seen:
            seen.append(lab)
    return " / ".join(seen) if seen else fallback


def load_science_manifest(admix_dir: Path) -> dict:
    """Load the portable Science ADMIXTURE manifest."""
    path = admix_dir / SCIENCE_MANIFEST_NAME
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _science_asset(admix_dir: Path, k: int) -> dict:
    manifest = load_science_manifest(admix_dir)
    assets = manifest.get("assets") or {}
    asset = assets.get(f"science_k{k}_raw.Q")
    if isinstance(asset, dict):
        return asset
    per_k = manifest.get("per_k") or {}
    asset = per_k.get(str(k))
    return asset if isinstance(asset, dict) else {}


def _science_assets_complete(admix_dir: Path, k_min: int, k_max: int) -> bool:
    manifest = load_science_manifest(admix_dir)
    if manifest.get("run_family") != SCIENCE_RUN_FAMILY:
        return False
    return all(
        (admix_dir / f"science_k{k}_raw.Q").exists()
        and _science_asset(admix_dir, k).get("run_family") == SCIENCE_RUN_FAMILY
        for k in range(k_min, k_max + 1)
    )


def resolve_admixture_run_family(
    admix_dir: Path,
    k_min: int = 2,
    k_max: int = 8,
) -> str:
    """Return one coherent run family for the requested K range."""
    if panel167k_assets_complete(admix_dir, k_min, k_max):
        return PANEL167K_NOGWAS_FAMILY
    if _science_assets_complete(admix_dir, k_min, k_max):
        return SCIENCE_RUN_FAMILY
    return "legacy_chip"


def display_run_family(
    admix_dir: Path,
    contrast: AdmixtureContrast | None = None,
    k_min: int = 2,
    k_max: int = 8,
) -> str:
    """Q/colors for the 2449 strip.

    Chip-P projection is a different coordinate system. Painting it with
    Science names/colours (or replacing the strip with ``k{K}.Q``) makes the
    figure unreadable against Dong et al. 2023 Fig. 1D.
    """
    if contrast and contrast.run_family == PANEL167K_NOGWAS_FAMILY:
        if panel167k_assets_complete(admix_dir, k_min, k_max):
            return PANEL167K_NOGWAS_FAMILY
    if _science_assets_complete(admix_dir, k_min, k_max):
        return SCIENCE_RUN_FAMILY
    if contrast and contrast.run_family:
        return contrast.run_family
    return resolve_admixture_run_family(admix_dir, k_min, k_max)


def _normalise_run_family(admix_dir: Path, run_family: str | None, k: int) -> str:
    requested = (run_family or "auto").lower()
    if requested in {"science", SCIENCE_RUN_FAMILY}:
        return SCIENCE_RUN_FAMILY
    if requested in {"legacy", "legacy_chip", "chip"}:
        return "legacy_chip"
    if requested in {"panel167k", "nogwas", PANEL167K_NOGWAS_FAMILY}:
        return PANEL167K_NOGWAS_FAMILY
    return resolve_admixture_run_family(admix_dir, k, k)


def load_panel167k_manifest(admix_dir: Path) -> dict:
    path = admix_dir / MANIFEST_NAME
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _panel167k_asset(admix_dir: Path, k: int) -> dict:
    manifest = load_panel167k_manifest(admix_dir)
    assets = manifest.get("assets") or {}
    asset = assets.get(f"panel167k_nogwas.{k}.Q") or assets.get(str(k))
    if isinstance(asset, dict) and asset.get("component_permutation"):
        return asset
    return {}


def component_metadata(
    admix_dir: Path,
    k: int,
    *,
    run_family: str | None = None,
) -> dict:
    """Return manifest component metadata for one K, or a legacy fallback."""
    family = _normalise_run_family(admix_dir, run_family, k)
    if family == SCIENCE_RUN_FAMILY:
        return _science_asset(admix_dir, k)
    if family == PANEL167K_NOGWAS_FAMILY:
        live = live_panel167k_metadata(admix_dir, k)
        if live:
            return live
        cached = _panel167k_asset(admix_dir, k)
        if cached:
            return cached
    return {
        "run_family": "legacy_chip",
        "component_permutation": list(range(k)),
        "components": [
            {
                "id": f"K{i}",
                "raw_component_id": f"raw_col_{i}",
                "raw_column_index": i - 1,
                "label": f"A{i}",
                "display_label": f"A{i}",
                "aliases": [f"A{i}"],
                "color": "",
            }
            for i in range(1, k + 1)
        ],
        "projection_available": (admix_dir / f"grape.chip.subset.{k}.P").exists()
        or (admix_dir / "duan" / f"grape.chip.subset.{k}.P").exists(),
        "projection_status": "chip_P_available",
    }


def load_admixture_matrix(
    admix_dir: Path,
    k: int,
    *,
    run_family: str | None = None,
) -> np.ndarray:
    """Load one Q matrix in its declared canonical component order.

    Science assets remain raw on disk. panel167k files are written already
    aligned when ``on_disk_aligned`` is set; otherwise the manifest
    permutation (canonical → HPC raw) is applied in memory.
    """
    family = _normalise_run_family(admix_dir, run_family, k)
    q_file = _q_path(admix_dir, k, run_family=family)
    if not q_file.exists():
        raise FileNotFoundError(q_file)
    q = np.loadtxt(q_file)
    if q.ndim == 1:
        q = q.reshape(1, -1)
    if q.ndim != 2 or q.shape[1] != k:
        raise ValueError(f"{q_file} has shape {q.shape}; expected (*, {k})")
    metadata = component_metadata(admix_dir, k, run_family=family)
    permutation = metadata.get("component_permutation") or list(range(k))
    return apply_column_order(q, permutation)


def load_admixture_p(
    admix_dir: Path,
    k: int,
    *,
    run_family: str | None = None,
) -> np.ndarray:
    """Load P with the same column permutation as ``load_admixture_matrix``."""
    p_file = _p_path(admix_dir, k, run_family=run_family)
    if not p_file.exists():
        raise FileNotFoundError(p_file)
    p = np.loadtxt(p_file)
    if p.ndim != 2 or p.shape[1] != k:
        raise ValueError(f"{p_file} has shape {p.shape}; expected (*, {k})")
    metadata = component_metadata(admix_dir, k, run_family=run_family)
    permutation = metadata.get("component_permutation") or list(range(k))
    return apply_column_order(p, permutation)


def component_labels_colors(
    admix_dir: Path,
    k: int,
    *,
    run_family: str | None = None,
) -> tuple[list[str], list[str], list[list[str]]]:
    """Return display labels, colors, and aliases in canonical component order."""
    metadata = component_metadata(admix_dir, k, run_family=run_family)
    components = metadata.get("components") or []
    labels = [str(c.get("display_label") or c.get("label") or f"A{i + 1}") for i, c in enumerate(components)]
    colors = [str(c.get("color") or "") for c in components]
    aliases = [list(c.get("aliases") or []) for c in components]
    return labels, colors, aliases


def plot_order_indices(
    admix_dir: Path,
    k: int,
    *,
    run_family: str | None = None,
) -> list[int]:
    """Draw bars in paper-canonical order (Science K1, K2, … that exist at this K)."""
    metadata = component_metadata(admix_dir, k, run_family=run_family)
    order = metadata.get("plot_order")
    if isinstance(order, list) and sorted(order) == list(range(k)):
        return [int(i) for i in order]
    return list(range(k))


def science_k8_active(admix_dir: Path) -> bool:
    return _science_assets_complete(admix_dir, 8, 8) or (admix_dir / "k8_science.Q").exists()


def _q_path(admix_dir: Path, k: int, *, run_family: str | None = None) -> Path:
    """Resolve a Q path without silently mixing run families."""
    family = _normalise_run_family(admix_dir, run_family, k)
    if family == PANEL167K_NOGWAS_FAMILY:
        return panel167k_q_path(admix_dir, k)
    if family == SCIENCE_RUN_FAMILY:
        return admix_dir / f"science_k{k}_raw.Q"
    if k == 8:
        sci = admix_dir / "k8_science.Q"
        if sci.exists():
            return sci
    return admix_dir / f"k{k}.Q"


def id_path_for_family(admix_dir: Path, run_family: str | None = None) -> Path:
    family = _normalise_run_family(admix_dir, run_family, 8)
    if family == PANEL167K_NOGWAS_FAMILY:
        path = admix_dir / ID_FILE_NAME
        if path.exists():
            return path
    return admix_dir / "id_only.txt"


def _read_ids(admix_dir: Path, run_family: str | None = None) -> list[str]:
    path = id_path_for_family(admix_dir, run_family)
    if not path.exists():
        return []
    return [ln.strip() for ln in path.read_text().splitlines() if ln.strip()]


def _read_meta(info_path: Path) -> dict[str, dict[str, str]]:
    meta: dict[str, dict[str, str]] = {}
    if not info_path.exists():
        return meta
    with info_path.open() as fh:
        hdr = fh.readline().rstrip().split("\t")
        for line in fh:
            p = line.rstrip().split("\t")
            row = dict(zip(hdr, p))
            if "ID" in row:
                meta[row["ID"]] = row
    return meta


def group_k8_score(
    q: np.ndarray,
    idx: list[int],
    score: str = "mean",
) -> np.ndarray:
    """One length-K score vector for a group's rows.

    mean: all members (ingest default).
    max: per-column max Q among members.
    purest: the single member with the highest max(Q); use that row.
    """
    if not idx:
        raise ValueError("empty group for K=8 score")
    qi = np.asarray(q, float)[idx]
    if qi.ndim == 1:
        qi = qi.reshape(1, -1)
    if score == "mean":
        return qi.mean(axis=0)
    if score == "max":
        return qi.max(axis=0)
    if score == "purest":
        return qi[int(np.argmax(qi.max(axis=1)))]
    raise ValueError(f"unknown K=8 group score {score!r}")


def infer_science_k8_permutation(
    q: np.ndarray,
    ids: list[str],
    grp_of: dict[str, str],
    *,
    score: str = "mean",
) -> list[int]:
    """Assign raw K=8 columns to Science K1–K8 using published group majorities.

    ADMIXTURE's column integers are arbitrary each run. The paper names
    components by the group that carries them (WWE1→K1, …, WWE2→K8).
    Returns canonical_to_raw permutation.

    ``score`` is how a group votes: ``mean`` (default), ``max`` (highest Q
    on each column), or ``purest`` (one member with the highest single
    component). Greedy unique assignment is still in paper-anchor order.
    """
    if q.ndim != 2 or q.shape[1] != 8:
        raise ValueError(f"expected (*, 8) Q, got {q.shape}")
    scores: dict[str, np.ndarray] = {}
    for grp, paper_i in SCIENCE_K8_GROUP_ANCHORS:
        idx = [i for i, sid in enumerate(ids) if grp_of.get(sid) == grp]
        if not idx:
            raise ValueError(f"no samples with Grp={grp} to anchor Science K{paper_i + 1}")
        scores[grp] = group_k8_score(q, idx, score)
    used: set[int] = set()
    perm: list[int] = [0] * 8
    for grp, paper_i in SCIENCE_K8_GROUP_ANCHORS:
        m = scores[grp]
        raw = max((j for j in range(8) if j not in used), key=lambda j: float(m[j]))
        perm[paper_i] = raw
        used.add(raw)
    if sorted(perm) != list(range(8)):
        raise ValueError(f"Science K=8 assignment is not a permutation: {perm}")
    return perm


def match_q_columns(q_from: np.ndarray, q_to: np.ndarray) -> list[int]:
    """Map each column of ``q_from`` to a unique column of ``q_to``, or -1.

    Greedy Pearson matching (Alexander 2009 label switching: column ids are
    arbitrary each K). Extra columns when ``q_from`` is wider stay -1.
    """
    if q_from.ndim != 2 or q_to.ndim != 2 or q_from.shape[0] != q_to.shape[0]:
        raise ValueError(f"shape mismatch from={q_from.shape} to={q_to.shape}")
    kf = q_from.shape[1]
    kt = q_to.shape[1]
    a = q_from - q_from.mean(axis=0)
    b = q_to - q_to.mean(axis=0)
    an = np.sqrt((a**2).sum(axis=0))
    bn = np.sqrt((b**2).sum(axis=0))
    corr = (a.T @ b) / np.clip(an[:, None] * bn[None, :], 1e-12, None)
    pairs = sorted(
        ((float(corr[i, j]), i, j) for i in range(kf) for j in range(kt)),
        reverse=True,
    )
    assigned = [-1] * kf
    used_from: set[int] = set()
    used_to: set[int] = set()
    for _r, i, j in pairs:
        if i in used_from or j in used_to:
            continue
        assigned[i] = j
        used_from.add(i)
        used_to.add(j)
        if len(used_to) == kt or len(used_from) == kf:
            break
    return assigned


def _q_column_corr(q_from: np.ndarray, q_to: np.ndarray) -> np.ndarray:
    a = q_from - q_from.mean(axis=0)
    b = q_to - q_to.mean(axis=0)
    an = np.sqrt((a**2).sum(axis=0))
    bn = np.sqrt((b**2).sum(axis=0))
    return (a.T @ b) / np.clip(an[:, None] * bn[None, :], 1e-12, None)


def sequential_column_orders(
    q_by_k: dict[int, np.ndarray],
    order_k2: list[int],
    *,
    k_min: int = 2,
    k_max: int | None = None,
    allow_merge: bool = False,
    merge_min_r: float = 0.45,
    orphan_max_r: float = 0.30,
) -> dict[int, list[int]]:
    """Raw-column order at each K so colours inherit from K-1.

    ``order_k2`` is canonical-column → raw-column at K=2.
    ``allow_merge`` is display-only: if a K-1 column is forced onto a
    weakly correlated child while it still tracks an already-matched
    column (WWE1+WWE2 collapsing at K=7), retire that parent and treat
    the freed child as a new split at the end. Default False so frozen
    Q/P permutations stay greedy 1-to-1.
    """
    if k_min != 2:
        raise ValueError("sequential paint starts at K=2")
    if sorted(order_k2) != [0, 1]:
        raise ValueError(f"K=2 order must be a permutation of 0,1: {order_k2}")
    k_max = k_max if k_max is not None else max(q_by_k)
    orders: dict[int, list[int]] = {2: list(order_k2)}
    q_prev = q_by_k[2][:, np.asarray(order_k2, int)]
    for k in range(3, k_max + 1):
        if k not in q_by_k:
            raise KeyError(k)
        qk = q_by_k[k]
        assigned = match_q_columns(qk, q_prev)
        leftovers = [i for i, a in enumerate(assigned) if a < 0]
        prev_to_new = {a: i for i, a in enumerate(assigned) if a >= 0}
        missing = [j for j in range(q_prev.shape[1]) if j not in prev_to_new]
        if missing:
            raise ValueError(f"K={k} failed to match K={k-1} columns {missing}: {assigned}")
        retired: set[int] = set()
        if allow_merge:
            corr = _q_column_corr(q_prev, qk)
            for prev_i, new_j in prev_to_new.items():
                r_ass = float(corr[prev_i, new_j])
                j_best = int(np.argmax(corr[prev_i]))
                r_best = float(corr[prev_i, j_best])
                if r_ass < orphan_max_r and r_best >= merge_min_r and j_best != new_j:
                    retired.add(prev_i)
        order = [prev_to_new[j] for j in range(q_prev.shape[1]) if j not in retired]
        used = set(order)
        extra = leftovers + [i for i in range(k) if i not in used and i not in leftovers]
        order = order + extra
        if sorted(order) != list(range(k)):
            raise ValueError(f"K={k} plot order is not a permutation: {order}")
        orders[k] = order
        q_prev = qk[:, np.asarray(order, int)]
    return orders


def core_match_mask(
    q_prev: np.ndarray,
    q_new: np.ndarray,
    ids: list[str],
    grp_of: dict[str, str],
    *,
    keep: list[int] | None = None,
    qmax_cut: float = 0.75,
) -> np.ndarray:
    """Layer-2 matching people: 10 Dong groups, Qmax>cut at both K and K+1.

    If a group has no such person, keep that group's single purest at the
    previous K. Drops OUT, C-Ad, W-Ad. Same rule as c_align.py
    (00_italy_2center/Final_ana_3057_adna/c_align/c_align.py).
    Spec: 00_array/admixture-qp-and-projection/q-column-alignment-schemes.md
    """
    n = len(ids)
    if q_prev.shape[0] != n or q_new.shape[0] != n:
        raise ValueError(
            f"Q rows must match ids: prev={q_prev.shape[0]} new={q_new.shape[0]} n={n}"
        )
    keep_set = None if keep is None else set(keep)
    mask = np.zeros(n, dtype=bool)
    qmax_p = np.asarray(q_prev, float).max(axis=1)
    qmax_n = np.asarray(q_new, float).max(axis=1)
    for g in SCIENCE_K8_GROUPS:
        idx = [
            i
            for i, sid in enumerate(ids)
            if grp_of.get(sid) == g
            and (keep_set is None or i in keep_set)
            and grp_of.get(sid) != "OUT"
        ]
        if not idx:
            continue
        both = [i for i in idx if qmax_p[i] > qmax_cut and qmax_n[i] > qmax_cut]
        if both:
            for i in both:
                mask[i] = True
        else:
            mask[idx[int(np.argmax(qmax_p[idx]))]] = True
    if not mask.any():
        raise ValueError("empty core match mask")
    return mask


def match_next_columns(q_prev: np.ndarray, q_new: np.ndarray, mask: np.ndarray) -> list[int]:
    """Greedy 1-to-1 Pearson by C order; leftover column last.

    Same algorithm as 00_italy_2center/.../c_align.py match_next.
    q_prev is already in C1..CK order. q_new is raw ADMIXTURE order.
    """
    n_old = q_prev.shape[1]
    n_new = q_new.shape[1]
    used: set[int] = set()
    order: list[int] = []
    rows = np.flatnonzero(mask)
    if rows.size == 0:
        raise ValueError("no core rows for K→K+1 Pearson")
    a = q_prev[rows]
    b = q_new[rows]
    for i in range(n_old):
        best_j, best_r = -1, -2.0
        for j in range(n_new):
            if j in used:
                continue
            r = _pearson_1d(a[:, i], b[:, j])
            if r > best_r:
                best_r, best_j = r, j
        if best_j < 0:
            raise ValueError("could not match a parent column")
        used.add(best_j)
        order.append(best_j)
    leftover = [j for j in range(n_new) if j not in used]
    return order + leftover


def _pearson_1d(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, float) - float(np.mean(a))
    b = np.asarray(b, float) - float(np.mean(b))
    d = float(np.sqrt(np.dot(a, a) * np.dot(b, b)))
    return float(np.dot(a, b) / d) if d else 0.0


def sequential_column_orders_core(
    q_by_k: dict[int, np.ndarray],
    ids: list[str],
    grp_of: dict[str, str],
    *,
    keep: list[int] | None = None,
    k_max: int = 10,
    qmax_cut: float = 0.75,
) -> dict[int, list[int]]:
    """Layer-2 column names: core Pearson, leftover at the right. Display-only.

    Does not change frozen .Q/.P. Do not use this to rewrite ingest orders.
    """
    if 2 not in q_by_k:
        raise ValueError("need K=2")
    orders: dict[int, list[int]] = {
        2: k2_order_from_purest_wwe1(q_by_k[2], ids, grp_of, keep=keep)
    }
    q_prev = q_by_k[2][:, np.asarray(orders[2], int)]
    for k in range(3, k_max + 1):
        if k not in q_by_k:
            break
        qk = q_by_k[k]
        mask = core_match_mask(q_prev, qk, ids, grp_of, keep=keep, qmax_cut=qmax_cut)
        order = match_next_columns(q_prev, qk, mask)
        if sorted(order) != list(range(k)):
            raise ValueError(f"K={k} core order is not a permutation: {order}")
        orders[k] = order
        q_prev = qk[:, np.asarray(order, int)]
    return orders


def science_paint_order(
    q: np.ndarray,
    owner_labels: list[str],
) -> tuple[np.ndarray, list[str], list[str], list[int]]:
    """Layer-3 stack: leftover columns on top, then Fig. 1D so same hex is one block.

    matplotlib origin='upper' draws index 0 at the top of the bar. That matches
    c_align.draw_allk leftover-on-top (Science stack drawn from the bottom).
    Two red columns (WEE1 and CG1) sit together; they need not be adjacent C slots.
    """
    k = q.shape[1]
    hexes: list[str] = []
    leftover_i: list[int] = []
    extra_i = 0
    for j in range(k):
        names = owner_groups_for_science_paint(owner_labels[j])
        slot = science_index_for_groups(names)
        if slot is None:
            leftover_i.append(j)
            hexes.append(science_extra_color(k, extra_i))
            extra_i += 1
        else:
            hexes.append(SCIENCE_K8_COLORS[slot])
    order = list(leftover_i)
    leftover_set = set(leftover_i)
    for h in SCIENCE_K8_COLORS:
        for c, hx in enumerate(hexes):
            if c in leftover_set:
                continue
            if hx.lower() == h.lower():
                order.append(c)
    for c in range(k):
        if c not in order:
            order.append(c)
    return q[:, order], [hexes[j] for j in order], [owner_labels[j] for j in order], order


def swap_canonical_columns(order: list[int], i: int, j: int) -> list[int]:
    """Swap 0-based canonical positions; no-op if K is too small."""
    if max(i, j) >= len(order):
        return list(order)
    out = list(order)
    out[i], out[j] = out[j], out[i]
    return out


def k2_order_from_purest_wwe1(
    q2: np.ndarray,
    ids: list[str],
    grp_of: dict[str, str],
    keep: list[int] | None = None,
) -> list[int]:
    """K=2: put the WWE1-purest column first (west), the other second."""
    keep_set = None if keep is None else set(keep)
    idx = [
        i
        for i, sid in enumerate(ids)
        if grp_of.get(sid) == "WWE1" and (keep_set is None or i in keep_set)
    ]
    if not idx:
        raise ValueError("no WWE1 samples to seed K=2")
    pur = q2[idx].max(axis=1)
    best = idx[int(np.argmax(pur))]
    west = int(np.argmax(q2[best]))
    return [west, 1 - west]


PANEL167K_OWNER_GRPS: list[str] = [
    "CG1",
    "CG2",
    "CG3",
    "CG4",
    "CG5",
    "CG6",
    "WEE1",
    "WEE2",
    "WWE1",
    "WWE2",
]


def keep_non_out_indices(ids: list[str], grp_of: dict[str, str]) -> list[int]:
    return [i for i, sid in enumerate(ids) if grp_of.get(sid) != "OUT"]


def apply_column_order(mat: np.ndarray, order: list[int]) -> np.ndarray:
    """Permute columns of Q (n×K) or P (sites×K) with the same order."""
    arr = np.asarray(mat, float)
    if arr.ndim != 2:
        raise ValueError(f"expected 2-d matrix, got {arr.shape}")
    perm = [int(i) for i in order]
    if sorted(perm) != list(range(arr.shape[1])):
        raise ValueError(f"column order is not a permutation of 0..{arr.shape[1] - 1}: {order}")
    return arr[:, np.asarray(perm, dtype=int)]


def sequential_orders_from_q(
    q_by_k: dict[int, np.ndarray],
    ids: list[str],
    grp_of: dict[str, str],
    *,
    k_max: int,
) -> dict[int, list[int]]:
    """Canonical C1…CK from WWE1-purest K=2, then Pearson K→K+1 (drop OUT)."""
    keep = keep_non_out_indices(ids, grp_of)
    if 2 not in q_by_k:
        raise KeyError(2)
    order2 = k2_order_from_purest_wwe1(q_by_k[2], ids, grp_of, keep=keep)
    q_match = {k: q_by_k[k][keep] for k in range(2, k_max + 1)}
    return sequential_column_orders(q_match, order2, k_max=k_max)


def column_owner_labels(
    q: np.ndarray,
    ids: list[str],
    grp_of: dict[str, str],
    keep: list[int] | None = None,
) -> list[str]:
    """Label each column by the purest member of each Grp (keep excludes OUT)."""
    keep_idx = keep_non_out_indices(ids, grp_of) if keep is None else list(keep)
    keep_set = set(keep_idx)
    owners: list[list[str]] = [[] for _ in range(q.shape[1])]
    for g in PANEL167K_OWNER_GRPS:
        idx = [i for i, sid in enumerate(ids) if grp_of.get(sid) == g and i in keep_set]
        if not idx:
            continue
        sub = np.asarray(idx, int)
        pi = int(sub[int(np.argmax(q[sub].max(axis=1)))])
        owners[int(np.argmax(q[pi]))].append(f"{g}:{ids[pi]}")
    labels = ["+".join(x) if x else "" for x in owners]
    for j, lab in enumerate(labels):
        if lab:
            continue
        scored: list[tuple[float, str]] = []
        for g in PANEL167K_OWNER_GRPS:
            idx = [i for i, sid in enumerate(ids) if grp_of.get(sid) == g and i in keep_set]
            if idx:
                scored.append((float(q[idx, j].mean()), g))
        if scored:
            v, g = max(scored)
            labels[j] = f"{g}(mean {v:.2f})"
        else:
            labels[j] = "—"
    return labels


def science_stack_order(owner_labels: list[str]) -> list[int]:
    """Bar stack: leftover extras first, then Science K=8 slots."""
    k = len(owner_labels)
    sci = [science_index_for_groups(owner_groups_for_science_paint(lab)) for lab in owner_labels]
    extras = [j for j in range(k) if sci[j] is None]
    mapped = sorted((sci[j], j) for j in range(k) if sci[j] is not None)
    return extras + [j for _slot, j in mapped]


def _greedy_k_to_k8(qk: np.ndarray, q8: np.ndarray) -> list[int]:
    """Each Qk column → canonical K=8 index, or -1 if unmatched (k>8 leftover)."""
    if q8.ndim != 2 or q8.shape[1] != 8:
        raise ValueError(f"expected to-K=8 Q, got {q8.shape}")
    return match_q_columns(qk, q8)


def assign_qk_columns_to_k8(qk: np.ndarray, q8: np.ndarray) -> list[int]:
    """Public wrapper: K>8 columns that do not win a K=8 name stay -1."""
    return _greedy_k_to_k8(qk, q8)


def infer_k_to_k8_assignment(qk: np.ndarray, q8: np.ndarray) -> list[int]:
    """Match each column of Qk to one Science K=8 component by Pearson correlation.

    Unique greedy assignment so two K columns cannot claim the same K=8 name.
    Unsplit ancestors keep the K=8 colour of the descendant they correlate with
    most (the ADMIXTURE split story; CG5 appears only at K=8).
    """
    assigned = _greedy_k_to_k8(qk, q8)
    if any(v < 0 for v in assigned):
        raise ValueError(f"incomplete K→K8 assignment: {assigned}")
    return assigned


def k_plot_order_from_k8(assigned: list[int]) -> list[int]:
    """Raw-column order: Science K1–K8, then unmatched extra columns (K>8)."""
    k8_to_raw = {k8i: raw for raw, k8i in enumerate(assigned) if k8i >= 0}
    leftovers = [raw for raw, k8i in enumerate(assigned) if k8i < 0]
    named = [k8_to_raw[i] for i in range(8) if i in k8_to_raw]
    return named + leftovers


def science_k8_anchors_unique(
    q: np.ndarray,
    ids: list[str],
    grp_of: dict[str, str],
) -> tuple[bool, str]:
    """Fail ingest if each Science group does not uniquely own a raw column."""
    if q.ndim != 2 or q.shape[1] != 8:
        return False, f"expected (*, 8) Q, got {q.shape}"
    argmax: list[int] = []
    for grp, paper_i in SCIENCE_K8_GROUP_ANCHORS:
        idx = [i for i, sid in enumerate(ids) if grp_of.get(sid) == grp]
        if not idx:
            return False, f"no samples with Grp={grp} to anchor Science K{paper_i + 1}"
        argmax.append(int(np.argmax(q[idx].mean(axis=0))))
    if len(set(argmax)) != 8:
        return False, f"non-unique K=8 group argmax columns {argmax}"
    return True, "unique"


def permutation_from_k8_assignment(assigned: list[int], k: int) -> list[int]:
    """canonical_i → raw column so inherited K=8 names stay in paper order."""
    want = SCIENCE_K_INHERITS_K8[k]
    k8_to_raw = {k8i: raw for raw, k8i in enumerate(assigned)}
    missing = [k8i for k8i in want if k8i not in k8_to_raw]
    if missing:
        # Fall back to sorting assigned K=8 indices (still a permutation of raw cols).
        order = sorted(range(k), key=lambda raw: assigned[raw])
        return order
    return [k8_to_raw[k8i] for k8i in want]


def _grp_of_from_info(admix_dir: Path) -> dict[str, str]:
    info = None
    for cand in (admix_dir / "2449.info", admix_dir.parent / "2449.info"):
        if cand.exists():
            info = cand
            break
    meta = _read_meta(info) if info else {}
    return {sid: row.get("Grp", "") for sid, row in meta.items()}


def live_panel167k_metadata(admix_dir: Path, k: int) -> dict:
    """C1…CK unique COMPONENT_COLORS; newest column drawn on top."""
    ids = _read_ids(admix_dir, PANEL167K_NOGWAS_FAMILY)
    if not ids:
        return {}
    q_by_k: dict[int, np.ndarray] = {}
    for kk in range(2, k + 1):
        qk_file = panel167k_q_path(admix_dir, kk)
        if not qk_file.exists():
            return {}
        qk = np.loadtxt(qk_file)
        if qk.ndim == 1:
            qk = qk.reshape(1, -1)
        if qk.shape[0] != len(ids) or qk.shape[1] != kk:
            return {}
        q_by_k[kk] = qk
    grp_of = _grp_of_from_info(admix_dir)
    man = load_panel167k_manifest(admix_dir)
    on_disk = bool(man.get("on_disk_aligned"))
    raw_from_man = (man.get("canonical_to_raw") or {}).get(str(k))
    if on_disk:
        perm = list(range(k))
    else:
        try:
            orders = sequential_orders_from_q(q_by_k, ids, grp_of, k_max=k)
        except (ValueError, KeyError):
            return {}
        perm = orders[k]
    if isinstance(raw_from_man, list) and len(raw_from_man) == k:
        hpc_raw = [int(x) for x in raw_from_man]
    else:
        hpc_raw = list(perm)
    q_can = apply_column_order(q_by_k[k], perm)
    keep = keep_non_out_indices(ids, grp_of)
    owners = column_owner_labels(q_can, ids, grp_of, keep)
    colors_k = unique_component_colors(k)
    components = []
    for i, lab in enumerate(owners):
        groups = owner_groups_for_science_paint(lab)
        s = science_index_for_groups(groups)
        raw = hpc_raw[i]
        color = colors_k[i]
        if s is None:
            label = lab or f"C{i + 1}"
            display = lab or f"C{i + 1}"
        else:
            same = owner_groups_for_colour(groups, s)
            display = display_label_for_owner_groups(
                same, SCIENCE_K8_LEGEND_LABELS[s]
            )
            label = " / ".join(
                g for g in _SCIENCE_CONFLICT_PRIORITY if g in same
            ) or SCIENCE_K8_LABELS[s]
        components.append(
            {
                "id": f"K{i + 1}",
                "raw_component_id": f"hpc_col_{raw}",
                "raw_column_index": int(raw),
                "label": label,
                "display_label": display,
                "owner": lab,
                "aliases": [x for x in (lab, label) if x],
                "color": color,
                "inherits_k8_index": s,
            }
        )
    return {
        "run_family": PANEL167K_NOGWAS_FAMILY,
        "component_permutation": list(perm),
        "plot_order": list(range(k - 1, -1, -1)),
        "components": components,
        "projection_available": panel167k_p_path(admix_dir, k).exists(),
        "projection_status": (
            "panel167k_P_available"
            if panel167k_p_path(admix_dir, k).exists()
            else "no_P"
        ),
    }


def _canonicalize_q_values(
    admix_dir: Path,
    k: int,
    q_raw: dict[str, float],
    *,
    run_family: str | None = None,
) -> dict[str, float]:
    """Map a raw-column Q dict onto canonical K1..Kk."""
    metadata = component_metadata(admix_dir, k, run_family=run_family)
    perm = metadata.get("component_permutation") or list(range(k))
    raw = [float(q_raw.get(f"K{j + 1}", float("nan"))) for j in range(k)]
    return {f"K{i + 1}": raw[int(perm[i])] for i in range(k)}


def load_admixture_q(
    sample: str,
    admix_dir: Path,
    k: int = 5,
    *,
    run_family: str | None = None,
) -> dict[str, float] | None:
    """Return {K1: frac, ...} for one K, or None if sample not in panel."""
    ids = _read_ids(admix_dir, run_family)
    if not ids:
        return None
    try:
        idx = ids.index(sample)
    except ValueError:
        return None
    try:
        q = load_admixture_matrix(admix_dir, k, run_family=run_family)
    except (FileNotFoundError, ValueError):
        return None
    if idx >= q.shape[0]:
        return None
    return {f"K{j + 1}": float(v) for j, v in enumerate(q[idx])}


def _p_path(admix_dir: Path, k: int, *, run_family: str | None = None) -> Path:
    """P matrix for the selected family. Do not mix 167,433-row chip P with 153k P."""
    family = _normalise_run_family(admix_dir, run_family, k)
    if family == PANEL167K_NOGWAS_FAMILY:
        return panel167k_p_path(admix_dir, k)
    direct = admix_dir / f"grape.chip.subset.{k}.P"
    if direct.exists():
        return direct
    return admix_dir / "duan" / f"grape.chip.subset.{k}.P"


def load_panel_site_index(locus_annot: Path) -> list[str]:
    """Site keys in panel / P-matrix row order (chrom:pos)."""
    sites: list[str] = []
    with locus_annot.open() as fh:
        next(fh)
        for line in fh:
            chrom, pos, *_ = line.split("\t")
            sites.append(f"{chrom}:{pos}")
    return sites


def _find_admixture() -> str | None:
    import shutil

    here = Path(__file__).resolve().parents[3] / "bin" / "admixture"
    if here.exists():
        return str(here)
    return shutil.which("admixture")


def _alleles_for_sites(annot: Path, sites: list[str]) -> dict[str, tuple[str, str]]:
    want = set(sites)
    out: dict[str, tuple[str, str]] = {}
    with annot.open() as fh:
        next(fh)
        for line in fh:
            chrom, pos, ref, alt, *_ = line.rstrip("\n").split("\t")
            key = f"{chrom}:{pos}"
            if key in want:
                out[key] = (ref or "A", (alt.split(",")[0] if alt else "T") or "T")
    return out


def called_loci(
    dosage: np.ndarray,
    sites: list[str],
    P: np.ndarray,
    *,
    min_called: int = 50,
) -> tuple[np.ndarray, list[str], np.ndarray] | None:
    """Drop loci with missing dosage.

    ADMIXTURE 1.3.0 ``-P`` aborts if any SNP is all-missing
    (``Error: detected that all genotypes are missing for a SNP locus``).
    A one-sample query therefore cannot keep 0/0 sites.
    """
    keep = np.asarray(dosage, float) >= 0
    if int(keep.sum()) < min_called:
        return None
    idx = np.flatnonzero(keep)
    return np.asarray(dosage, float)[idx], [sites[int(i)] for i in idx], P[idx]


def project_q_nnls(
    dosage: np.ndarray,
    P: np.ndarray,
    *,
    counted_allele: str = "ALT",
) -> np.ndarray:
    """Fallback: Non-Negative Least Squares onto P (not official ADMIXTURE).

    ``dosage`` is VCF ALT count (0=HOM_REF). ``counted_allele='REF'`` for
    panel167k dest P; chip P stays ALT.
    """
    d = dosage.astype(float)
    ok = d >= 0
    if ok.sum() < max(20, P.shape[1] * 5):
        return np.full(P.shape[1], np.nan)
    y = d[ok] / 2.0
    if counted_allele.upper() == "REF":
        y = 1.0 - y
    A = P[ok]
    try:
        from scipy.optimize import nnls

        q, _ = nnls(A, y)
    except Exception:
        q, *_ = np.linalg.lstsq(A, y, rcond=None)
        q = np.clip(q, 0, None)
    s = float(q.sum())
    if s <= 0:
        return np.full(P.shape[1], np.nan)
    return q / s


def project_sample_q_admixture(
    dosage: np.ndarray,
    sites: list[str],
    P: np.ndarray,
    alleles: dict[str, tuple[str, str]],
    workdir: Path,
    k: int,
    sample: str = "QUERY",
    *,
    counted_allele: str = "REF",
) -> dict[str, float] | None:
    """Official projection: write BED, align P to BIM, ``admixture -P``.

    Manual §2.14 (v1.3). Requires plink + admixture on PATH / suite ``bin/``.
    ``plink --make-bed`` genomic-sorts SNPs; P.in is rewritten to that order.
    """
    import shutil
    import subprocess

    admix = _find_admixture()
    plink = shutil.which("plink")
    if not admix or not plink:
        return None
    if P.shape[0] != len(sites) or P.shape[1] != k:
        return None
    called = called_loci(dosage, sites, P)
    if called is None:
        return None
    dosage, sites, P = called

    workdir.mkdir(parents=True, exist_ok=True)
    prefix = workdir / f"proj_k{k}"
    # PED (A/C/G/T) + MAP
    with prefix.with_suffix(".map").open("w") as fh:
        for s in sites:
            chrom, _, pos = s.partition(":")
            ref, alt = alleles.get(s, ("A", "T"))
            fh.write(f"{chrom}\t{chrom}:{pos}:{ref}:{alt}\t0\t{pos}\n")
    with prefix.with_suffix(".ped").open("w") as fh:
        row = [sample, sample, "0", "0", "0", "-9"]
        for j, s in enumerate(sites):
            ref, alt = alleles.get(s, ("A", "T"))
            d = int(dosage[j])
            if d < 0:
                a1, a2 = "0", "0"
            elif d == 0:
                a1, a2 = ref, ref
            elif d == 1:
                a1, a2 = ref, alt
            else:
                a1, a2 = alt, alt
            row.extend([a1, a2])
        fh.write(" ".join(row) + "\n")

    a1_path = prefix.with_suffix(".a1")
    target = "REF" if counted_allele.upper() == "REF" else "ALT"
    with a1_path.open("w") as fh:
        for s in sites:
            ref, alt = alleles.get(s, ("A", "T"))
            chrom, _, pos = s.partition(":")
            allele = ref if target == "REF" else alt
            fh.write(f"{chrom}:{pos}:{ref}:{alt} {allele}\n")
    subprocess.run(
        [
            plink,
            "--file",
            str(prefix),
            "--make-bed",
            "--out",
            str(prefix),
            "--allow-extra-chr",
            "--keep-allele-order",
            "--a1-allele",
            str(a1_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    from grapeancestry.adna.panel167k_nogwas import align_p_to_study_bim

    bim = Path(f"{prefix}.bim")
    P_use = align_p_to_study_bim(P, sites, bim, alleles, counted_allele=counted_allele)
    pin = Path(f"{prefix}.{k}.P.in")
    np.savetxt(pin, P_use, fmt="%.6f")
    subprocess.run(
        [admix, "-P", f"{prefix}.bed", str(k)],
        check=True,
        capture_output=True,
        text=True,
        cwd=str(workdir),
    )
    # output lands in cwd = workdir as proj_k{k}.{k}.Q
    q_path = workdir / f"{prefix.name}.{k}.Q"
    if not q_path.exists():
        # sometimes written next to bed with full path stem
        q_path = Path(f"{prefix}.{k}.Q")
    if not q_path.exists():
        return None
    vals = [float(x) for x in q_path.read_text().split()]
    if len(vals) != k:
        return None
    return {f"K{j+1}": v for j, v in enumerate(vals)}


def project_sample_q(
    dosage: np.ndarray,
    cache_sites: list[str],
    panel_sites: list[str],
    admix_dir: Path,
    k: int,
    *,
    workdir: Path | None = None,
    allele_annot: Path | None = None,
    sample: str = "QUERY",
    method: str = "nnls",
    run_family: str | None = None,
) -> dict[str, float] | None:
    """Project dosages onto this family's P (raw columns; caller canonicalizes).

    ``method``: ``nnls`` (fast), ``official`` (``admixture -P`` then NNLS
    fallback), or ``auto`` (official then NNLS).
    panel167k_nogwas: align to **all** P rows (missing → 0/0). Chip P still
    subsets to overlapping sites (5k cache vs 167k P).
    """
    from grapeancestry.adna.panel167k_nogwas import align_dosage_to_sites, p_counted_allele

    family = _normalise_run_family(admix_dir, run_family, k)
    counted = p_counted_allele(admix_dir) if family == PANEL167K_NOGWAS_FAMILY else "ALT"
    try:
        P_full = load_admixture_p(admix_dir, k, run_family=family)
    except (FileNotFoundError, ValueError):
        return None
    if P_full.shape[0] != len(panel_sites):
        return None

    full_align = family == PANEL167K_NOGWAS_FAMILY
    if full_align:
        dos_a = align_dosage_to_sites(dosage, cache_sites, panel_sites)
        if int((dos_a >= 0).sum()) < 50:
            return None
        P = P_full
        sites_aln = list(panel_sites)
    else:
        index = {s: i for i, s in enumerate(panel_sites)}
        rows = []
        sites_aln = []
        dos = []
        for j, s in enumerate(cache_sites):
            i = index.get(s)
            if i is None:
                continue
            rows.append(i)
            sites_aln.append(s)
            dos.append(dosage[j])
        if len(rows) < 50:
            return None
        P = P_full[np.asarray(rows)]
        dos_a = np.asarray(dos, float)

    P = projection_p_for_sample(P, k, sample)

    annot = allele_annot
    if annot is None:
        cand = Path(__file__).resolve().parents[3] / "data" / "panel" / "locus_annot.tsv"
        annot = cand if cand.exists() else None
    wd = workdir or (
        Path(__file__).resolve().parents[3] / "results" / "admixture_proj" / sample / f"k{k}"
    )
    use_official = method in {"official", "auto"}
    if use_official and annot and annot.exists() and _find_admixture():
        alleles = _alleles_for_sites(annot, sites_aln)
        try:
            q = project_sample_q_admixture(
                dos_a,
                sites_aln,
                P,
                alleles,
                wd,
                k,
                sample=sample,
                counted_allele=counted,
            )
            if q:
                return q
        except Exception:
            pass
    qv = project_q_nnls(dos_a, P, counted_allele=counted)
    if not np.all(np.isfinite(qv)):
        return None
    return {f"K{j+1}": float(v) for j, v in enumerate(qv)}


def load_saved_chip_projection(root: Path, sample: str) -> dict[int, dict[str, float]]:
    """Read official ``admixture -P`` Q already written under results/admixture_proj."""
    out: dict[int, dict[str, float]] = {}
    base = root / "results" / "admixture_proj" / sample
    for k in range(2, 9):
        q_path = base / f"k{k}" / f"proj_k{k}.{k}.Q"
        if not q_path.exists():
            continue
        vals = [float(x) for x in q_path.read_text().split()]
        if len(vals) != k:
            continue
        out[k] = {f"K{j + 1}": v for j, v in enumerate(vals)}
    return out


def load_admixture_k_range(
    sample: str,
    admix_dir: Path,
    k_min: int = 2,
    k_max: int = 8,
    info_path: Path | None = None,
    *,
    dosage: np.ndarray | None = None,
    cache_sites: list[str] | None = None,
    panel_sites: list[str] | None = None,
    mode: str = "auto",
    all_k: bool = False,
    run_family: str | None = None,
) -> AdmixtureContrast | None:
    """Load K=k_min..k_max: in-panel lookup and/or P-matrix projection.

    Modes (customer default ``auto``):
      - in-panel → **lookup only** (no projection)
      - new sample on ``panel167k_nogwas`` → ``admixture -P`` (NNLS fallback)
        for **K=2–8** (unless ``all_k`` is False)
      - Science family → projection disabled (no matching Science P)
      - ``mode=nnls`` / ``official`` → project onto that family's P (chip P
        only when panel167k assets are absent)
    """
    mode = (mode or "auto").lower()
    if run_family and run_family.lower() != "auto":
        selected_family = _normalise_run_family(admix_dir, run_family, k_min)
    elif mode in {"nnls", "official"}:
        if panel167k_assets_complete(admix_dir, k_min, k_max):
            selected_family = PANEL167K_NOGWAS_FAMILY
        else:
            selected_family = "legacy_chip"
    else:
        selected_family = resolve_admixture_run_family(admix_dir, k_min, k_max)

    ids = _read_ids(admix_dir, selected_family)
    in_panel = sample in ids
    idx = ids.index(sample) if in_panel else -1

    info = info_path
    if info is None:
        for cand in (admix_dir / "2449.info", admix_dir.parent / "2449.info"):
            if cand.exists():
                info = cand
                break
    meta_all = _read_meta(info) if info else {}
    meta = meta_all.get(sample, {})
    grp_key = "Grp"
    grp_value = meta.get(grp_key, "")
    grp_idx = [
        i
        for i, s in enumerate(ids)
        if meta_all.get(s, {}).get(grp_key) == grp_value and grp_value
    ]
    grp_order = load_grp_order(admix_dir)

    q_by_k: dict[int, dict[str, float]] = {}
    grp_mean_by_k: dict[int, dict[str, float]] = {}
    panel_mean_by_k: dict[int, dict[str, float]] = {}
    projected_by_k: dict[int, dict[str, float]] = {}
    chip_projected_by_k: dict[int, dict[str, float]] = {}

    # Decide whether / how to project.  Science Q has no matching Science P;
    # automatic projection is therefore disabled for that run family.
    do_project = False
    proj_method = "nnls"
    if mode == "lookup":
        do_project = False
    elif mode == "nnls":
        do_project = dosage is not None and cache_sites is not None and panel_sites is not None
        proj_method = "nnls"
    elif mode == "official":
        do_project = dosage is not None and cache_sites is not None and panel_sites is not None
        proj_method = "official"
    else:  # auto
        if in_panel:
            do_project = False
        else:
            do_project = (
                selected_family != SCIENCE_RUN_FAMILY
                and dosage is not None
                and cache_sites is not None
                and panel_sites is not None
            )
            proj_method = "official" if selected_family == PANEL167K_NOGWAS_FAMILY else "nnls"

    project_all = all_k or (
        selected_family == PANEL167K_NOGWAS_FAMILY and mode == "auto" and not in_panel
    )
    if do_project and project_all:
        proj_ks = list(range(k_min, k_max + 1))
    elif do_project:
        proj_ks = [8] if k_min <= 8 <= k_max else [k_max]
    else:
        proj_ks = []
    # Science K=8 Q has no matching P in-suite — do not project into chip P
    # space under the automatic/selected Science run.
    if selected_family == SCIENCE_RUN_FAMILY:
        proj_ks = []
    do_project = bool(proj_ks)

    chip_projection_status = ""
    if selected_family == SCIENCE_RUN_FAMILY and not in_panel and not proj_ks:
        projection_status = "disabled_no_matching_science_P"
    elif in_panel and mode in {"auto", "lookup"}:
        projection_status = "not_applicable_in_panel_lookup"
    elif do_project and selected_family == PANEL167K_NOGWAS_FAMILY:
        projection_status = "panel167k_P_projection"
    elif do_project and selected_family == SCIENCE_RUN_FAMILY:
        chip_projection_status = "chip_P_projection_not_comparable"
        projection_status = chip_projection_status
    elif do_project:
        projection_status = "chip_P_projection"
    else:
        projection_status = "not_requested"

    for k in range(k_min, k_max + 1):
        try:
            Q = load_admixture_matrix(admix_dir, k, run_family=selected_family)
        except (FileNotFoundError, ValueError):
            Q = None
        if Q is not None:
            if Q.shape[0] == len(ids):
                panel_mean_by_k[k] = {
                    f"K{j+1}": float(v) for j, v in enumerate(Q.mean(axis=0))
                }
                if grp_idx:
                    gm = Q[grp_idx].mean(axis=0)
                    grp_mean_by_k[k] = {f"K{j+1}": float(v) for j, v in enumerate(gm)}
                if in_panel:
                    row = Q[idx]
                    q_by_k[k] = {f"K{j+1}": float(v) for j, v in enumerate(row)}

        if k in proj_ks:
            pq = project_sample_q(
                dosage,  # type: ignore[arg-type]
                cache_sites,  # type: ignore[arg-type]
                panel_sites,  # type: ignore[arg-type]
                admix_dir,
                k,
                sample=sample,
                method=proj_method,
                run_family=selected_family,
            )
            if pq:
                pq = apply_q_dict_edits(pq, k, sample, grp=str(grp_value or ""))
                projected_by_k[k] = pq
                root = admix_dir.parents[2]
                if (root / "src" / "grapeancestry").is_dir():
                    try:
                        from grapeancestry.adna.admix_project import persist_sample_q

                        labels, _, _ = component_labels_colors(
                            admix_dir, k, run_family=selected_family
                        )
                        persist_sample_q(root, sample, k, pq, labels)
                    except OSError:
                        pass
                if selected_family != PANEL167K_NOGWAS_FAMILY:
                    chip_projected_by_k[k] = pq

    if not q_by_k and not projected_by_k and not panel_mean_by_k:
        return None

    if q_by_k and projected_by_k:
        source = "mixed"
    elif q_by_k:
        source = "lookup_science_k8" if selected_family == SCIENCE_RUN_FAMILY else "lookup"
    elif projected_by_k:
        if selected_family == PANEL167K_NOGWAS_FAMILY:
            source = "projected_panel167k_p"
        elif do_project:
            source = "projected_chip_p"
        else:
            source = "projected"
    else:
        source = "panel_only"

    return AdmixtureContrast(
        sample=sample,
        meta=meta,
        q_by_k=q_by_k,
        grp_mean_by_k=grp_mean_by_k,
        panel_mean_by_k=panel_mean_by_k,
        n_panel=len(ids),
        n_grp=len(grp_idx),
        grp_key=grp_key,
        grp_value=grp_value,
        projected_by_k=projected_by_k,
        source=source,
        grp_order=grp_order,
        run_family=selected_family,
        projection_status=projection_status,
        projection_source=(
            "panel167k_nogwas P (lookup in-panel; -P for new samples)"
            if selected_family == PANEL167K_NOGWAS_FAMILY
            else (
                "chip-P projection; not directly comparable to Science Q"
                if chip_projected_by_k
                else (
                    "Science P unavailable"
                    if selected_family == SCIENCE_RUN_FAMILY
                    else ""
                )
            )
        ),
        chip_projected_by_k=chip_projected_by_k,
    )


def admixture_methods_text(run_family: str) -> str:
    """One paragraph covering the K=2–8 series for the report methods card."""
    if run_family == PANEL167K_NOGWAS_FAMILY:
        return REPORT_METHODS_PANEL167K
    return (
        "ADMIXTURE K=2–8 is one Science-named series "
        "(Dong et al. 2023 https://doi.org/10.1126/science.add8655 Fig. 1D / fig. S8). "
        "In-panel samples use lookup. New-sample projection onto the archived "
        "Science fit is not available."
    )
