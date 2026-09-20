"""Exploratory f3/f4 contrasts of a query vs 2449.info Grp means.

The query is one genotype, not a target population. Missing sites are excluded
per contrast; this is not a formal qp3Pop/qpDstat/qpAdm/qpGraph workflow.
"""

from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np

from grapeancestry.adna.fstats import chrom_blocks, f3_per_site, f4_per_site, jackknife_mean


_SKIP = {"", "ND", "nan"}


def fstat_pop_labels(meta: dict[str, dict[str, str]], ids: list[str]) -> list[str]:
    """Return 2449.info ``Grp`` labels for f3/f4; OUT stays OUT."""
    out: list[str] = []
    for sid in ids:
        row = meta.get(sid, {})
        grp = str(row.get("Grp") or "").strip()
        if grp == "OUT":
            out.append("OUT")
        elif grp in _SKIP:
            out.append("")
        else:
            out.append(grp)
    return out


def grp_allele_means(
    mat: np.ndarray,
    ref_ids: list[str],
    groups: list[str],
) -> dict[str, np.ndarray]:
    """Mean dosage per Grp (missing → nanmean)."""
    buckets: dict[str, list[np.ndarray]] = defaultdict(list)
    for i, g in enumerate(groups):
        if not g:
            continue
        buckets[g].append(mat[i].astype(float))
    out: dict[str, np.ndarray] = {}
    for g, rows in buckets.items():
        X = np.vstack(rows)
        X = X.astype(float)
        X[X < 0] = np.nan
        if not np.any(np.isfinite(X)):
            continue
        with np.errstate(all="ignore"):
            count = np.isfinite(X).sum(axis=0)
            m = np.divide(
                np.nansum(X, axis=0),
                count,
                out=np.full(count.shape, np.nan, dtype=float),
                where=count > 0,
            )
        if not np.any(count > 0):
            continue
        out[g] = m
    return out


def fstats_for_query(
    query: np.ndarray,
    mat: np.ndarray,
    ref_ids: list[str],
    groups: list[str],
    *,
    outgroup: str = "OUT",
    sites: list[str] | None = None,
    min_n: int = 2,
    n_pairwise: int = 6,
) -> dict:
    """f3 / f4 of a query vs population-mean allele frequencies.

    Pairwise ``f3(Q; A, B)`` is a descriptive three-population statistic.
    ``f3(OUT; Q, G)`` is outgroup-f3 (higher = more shared drift with G).
    ``f4(Q, OUT; A, B)`` is the signed 4-population contrast.

    Frequencies are population means of dosages/2 (Patterson et al. 2012,
    doi:10.1534/genetics.112.145037). Default labels are 2449.info Grp.
    Non-OUT groups require n≥min_n for pairwise and outgroup-f3 contrasts;
    the designated OUT group is retained independently and its n is returned
    as ``outgroup_n``. Pairwise f3/f4 use the ``n_pairwise`` largest
    eligible non-OUT groups. If ``sites`` is given, SE and Z come from a
    chromosome-block jackknife. Not qp3Pop/qpDstat.
    """
    means = grp_allele_means(mat, ref_ids, groups)
    q = query.astype(float)
    q[q < 0] = np.nan

    qf = q
    mean_f = means
    counts = Counter(str(g) for g in groups if str(g) not in _SKIP)
    pops = sorted(
        [g for g, n in counts.items() if g != outgroup and g in mean_f and n >= min_n],
        key=lambda g: (-counts[g], g),
    )
    pair = pops[: max(2, n_pairwise)] if len(pops) >= 2 else pops
    n = int(qf.shape[0])
    blocks = None
    if sites is not None and len(sites) == n:
        blocks = chrom_blocks(list(sites))

    def _pack(stat: str, label: str, a: str, b: str, v: np.ndarray, **extra: object) -> dict:
        if blocks is not None:
            theta, se, z, nblk = jackknife_mean(v, blocks)
        else:
            ok = np.isfinite(v)
            theta = float(np.mean(v[ok])) if ok.any() else float("nan")
            se, z, nblk = float("nan"), float("nan"), 0
        row = {
            "stat": stat,
            "label": label,
            "a": a,
            "b": b,
            "value": theta,
            "se": se,
            "z": z,
            "n_blocks": nblk,
            "n_sites": int(np.isfinite(v).sum()),
        }
        row.update(extra)
        return row

    f3_rows: list[dict] = []
    for i, a in enumerate(pair):
        for b in pair[i + 1 :]:
            f3_rows.append(
                _pack("f3", f"f3(Q; {a}, {b})", a, b, f3_per_site(qf, mean_f[a], mean_f[b]))
            )
    f4_rows: list[dict] = []
    f3_out: list[dict] = []
    if outgroup in mean_f:
        og = mean_f[outgroup]
        for i, a in enumerate(pair):
            for b in pair[i + 1 :]:
                f4_rows.append(
                    _pack(
                        "f4",
                        f"f4(Q,{outgroup}; {a},{b})",
                        a,
                        b,
                        f4_per_site(qf, og, mean_f[a], mean_f[b]),
                    )
                )
        for g in pops:
            f3_out.append(
                _pack(
                    "f3_out",
                    f"f3({outgroup}; Q, {g})",
                    outgroup,
                    g,
                    f3_per_site(og, qf, mean_f[g]),
                    grp=g,
                )
            )
    return {
        "f3": f3_rows,
        "f4": f4_rows,
        "f3_out": f3_out,
        "groups_used": pops,
        "fstat_pop": "Grp",
        "query_called_sites": int(np.sum(np.asarray(query) >= 0)),
        "outgroup_n": int(counts.get(outgroup, 0)),
    }
