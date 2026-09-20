"""Score REF vs ALT using flanking DNA (Markov always; PlantCaduceus if torch exists).

This is sequence annotation of chip SNPs, not GWAS.
PlantCaduceus: Zhai et al. 2025 PNAS doi:10.1073/pnas.2421738122
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np

from grapeancestry.cloud.mas import MAS_LOCI
from grapeancestry.resource.seqfa import fetch_fa, load_fai, window_with_alt

DNA = "ACGT"
FLANK = 255  # 255 + 1 + 256 = 512, PlantCaduceus window


def parse_site(site: str) -> tuple[str, int]:
    chrom, _, pos = site.partition(":")
    return chrom, int(pos)


def load_alleles(vcf: Path, sites: list[str]) -> dict[str, tuple[str, str]]:
    """chrom:pos → (REF, first ALT). Needs bcftools."""
    import subprocess

    rarg = ",".join(f"{c}:{p}-{p}" for c, p in (parse_site(s) for s in sites))
    raw = subprocess.check_output(
        ["bcftools", "query", "-f", "%CHROM\t%POS\t%REF\t%ALT\n", "-r", rarg, str(vcf)],
        text=True,
    )
    out: dict[str, tuple[str, str]] = {}
    for line in raw.splitlines():
        chrom, pos, ref, alt = line.split("\t")
        alt0 = alt.split(",")[0]
        out[f"{chrom}:{pos}"] = (ref.upper(), alt0.upper())
    return out


def extract_windows(
    fa: Path,
    alleles: dict[str, tuple[str, str]],
    *,
    flank: int = FLANK,
) -> list[dict]:
    index = load_fai(Path(str(fa) + ".fai"))
    rows = []
    for loc in MAS_LOCI:
        site = loc["site"]
        if site not in alleles:
            continue
        chrom, pos = parse_site(site)
        ref, alt = alleles[site]
        length = index[chrom][0]
        start = max(1, pos - flank)
        end = min(length, pos + flank)
        seq = fetch_fa(fa, chrom, start, end, index)
        offset = pos - start
        if offset < 0 or offset >= len(seq):
            continue
        observed = seq[offset]
        ref_seq, alt_seq = window_with_alt(seq, offset=offset, ref=ref, alt=alt)
        rows.append(
            {
                "site": site,
                "gene": loc["gene"],
                "trait": loc["trait"],
                "chrom": chrom,
                "pos": pos,
                "vcf_ref": ref,
                "vcf_alt": alt,
                "vs1_base": observed,
                "ref_seq": ref_seq,
                "alt_seq": alt_seq,
                "flank": flank,
                "center_snippet": (
                    seq[max(0, offset - 8) : offset]
                    + "["
                    + observed
                    + "/"
                    + alt
                    + "]"
                    + seq[offset + 1 : offset + 9]
                ),
            }
        )
    return rows


def fit_markov(seq: str, order: int = 4) -> dict[str, np.ndarray]:
    """P(next | k-mer) with 0.5 pseudocount. Keys are ACGT k-mers."""
    seq = "".join(b if b in DNA else "N" for b in seq.upper())
    counts: dict[str, np.ndarray] = defaultdict(lambda: np.full(4, 0.5))
    idx = {b: i for i, b in enumerate(DNA)}
    for i in range(order, len(seq)):
        ctx, nxt = seq[i - order : i], seq[i]
        if "N" in ctx or nxt not in idx:
            continue
        counts[ctx][idx[nxt]] += 1.0
    out: dict[str, np.ndarray] = {}
    for ctx, c in counts.items():
        out[ctx] = np.log(c / c.sum())
    return out


def logp_markov(seq: str, tables: dict[str, np.ndarray], order: int = 4) -> float:
    seq = seq.upper()
    idx = {b: i for i, b in enumerate(DNA)}
    total = 0.0
    n = 0
    uniform = np.log(0.25)
    for i in range(order, len(seq)):
        ctx, nxt = seq[i - order : i], seq[i]
        if nxt not in idx:
            continue
        row = tables.get(ctx)
        total += float(row[idx[nxt]]) if row is not None else uniform
        n += 1
    return total / max(n, 1)


def markov_delta(rows: list[dict], train_seq: str, order: int = 4) -> list[dict]:
    tables = fit_markov(train_seq, order=order)
    out = []
    for r in rows:
        lp_ref = logp_markov(r["ref_seq"], tables, order)
        lp_alt = logp_markov(r["alt_seq"], tables, order)
        # >0 → ALT less like the grape background than REF (more surprising)
        rec = dict(r)
        rec["markov_logp_ref"] = round(lp_ref, 5)
        rec["markov_logp_alt"] = round(lp_alt, 5)
        rec["markov_delta"] = round(lp_ref - lp_alt, 5)
        rec["markov_note"] = (
            "delta = mean_logP(REF window) − mean_logP(ALT window) on VS-1 4-mer Markov. "
            ">0 means ALT is less typical of this genome than REF. Not a GWAS p-value."
        )
        out.append(rec)
    return out


def try_plantcaduceus(rows: list[dict], model_id: str = "kuleshov-group/PlantCaduceus_l20") -> list[dict]:
    """Masked-base logP(REF) vs logP(ALT) at the SNP. Needs CUDA mamba_ssm.

    PlantCaduceus: Zhai et al. 2025 PNAS doi:10.1073/pnas.2421738122
    """
    try:
        import mamba_ssm  # noqa: F401
    except ImportError:
        for r in rows:
            r["lm_status"] = "PlantCaduceus needs mamba_ssm (CUDA); not on this Mac"
        return rows
    try:
        import torch
        from transformers import AutoModelForMaskedLM, AutoTokenizer
    except ImportError:
        for r in rows:
            r["lm_status"] = "torch/transformers not installed"
        return rows
    device = "cpu"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = "mps"
    try:
        tok = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        model = AutoModelForMaskedLM.from_pretrained(model_id, trust_remote_code=True)
        model.to(device)
        model.eval()
    except Exception as exc:  # noqa: BLE001
        for r in rows:
            r["lm_status"] = f"load failed: {exc}"
        return rows

    id2tok = {i: t for t, i in tok.get_vocab().items()} if hasattr(tok, "get_vocab") else {}

    def base_id(letter: str) -> int | None:
        for cand in (letter, letter.lower()):
            tid = tok.convert_tokens_to_ids(cand) if hasattr(tok, "convert_tokens_to_ids") else None
            if tid is not None and tid != getattr(tok, "unk_token_id", None):
                return int(tid)
        return None

    with torch.inference_mode():
        for r in rows:
            seq = r["ref_seq"]
            flank = int(r["flank"])
            # SNP is at index min(flank, len-1) after clipping
            chrom, pos = r["chrom"], int(r["pos"])
            offset = min(flank, len(seq) - 1)
            # recompute offset from lengths
            start = max(1, pos - flank)
            offset = pos - start
            if offset >= len(seq):
                r["lm_status"] = "offset OOB"
                continue
            enc = tok.encode_plus(
                seq,
                return_tensors="pt",
                return_attention_mask=False,
                return_token_type_ids=False,
            )
            ids = enc["input_ids"].to(device)
            # character tokenizer: position 1+offset if CLS
            # try to locate by encoding a dummy
            mask_id = tok.mask_token_id
            if mask_id is None:
                r["lm_status"] = "no mask token"
                continue
            # assume one token per base, optional CLS at 0
            n_tok = ids.shape[1]
            if n_tok == len(seq):
                pos_i = offset
            elif n_tok == len(seq) + 1:
                pos_i = offset + 1
            elif n_tok == len(seq) + 2:
                pos_i = offset + 1
            else:
                r["lm_status"] = f"token/base mismatch {n_tok} vs {len(seq)}"
                continue
            masked = ids.clone()
            masked[0, pos_i] = mask_id
            logits = model(input_ids=masked).logits[0, pos_i]
            logp = torch.log_softmax(logits, dim=-1)
            rid = base_id(r["vcf_ref"])
            aid = base_id(r["vcf_alt"])
            if rid is None or aid is None:
                r["lm_status"] = f"token ids missing ref={r['vcf_ref']} alt={r['vcf_alt']}"
                continue
            r["lm_logp_ref"] = float(logp[rid].cpu())
            r["lm_logp_alt"] = float(logp[aid].cpu())
            r["lm_delta"] = r["lm_logp_ref"] - r["lm_logp_alt"]
            r["lm_model"] = model_id
            r["lm_status"] = "ok"
            r["lm_note"] = (
                "PlantCaduceus masked logP at SNP. "
                "doi:10.1073/pnas.2421738122. Pretrained on 16 angiosperms (not grape). "
                "Not a GWAS statistic."
            )
            _ = id2tok
    return rows


def try_hyenadna(rows: list[dict], model_id: str = "LongSafari/hyenadna-tiny-1k-seqlen-hf") -> list[dict]:
    """Causal logP at the SNP. HyenaDNA tiny (Nguyen et al. 2023, human genome pretrain).

    Used only when PlantCaduceus cannot load. Not a grape model. Not GWAS.
    """
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError:
        for r in rows:
            r.setdefault("lm_status", "torch/transformers not installed")
        return rows
    try:
        tok = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(model_id, trust_remote_code=True)
        model.to("cpu")
        model.eval()
    except Exception as exc:  # noqa: BLE001
        for r in rows:
            r["lm_status"] = f"HyenaDNA load failed: {exc}"
        return rows

    def _snp_logp(seq: str, offset: int, letter: str) -> float | None:
        ids = tok(seq, return_tensors="pt", add_special_tokens=True)["input_ids"]
        # tokenizer appends SEP; no CLS prefix (build_inputs_with_special_tokens)
        if ids.shape[1] < 2 or offset < 1 or offset >= len(seq):
            return None
        with torch.inference_mode():
            logits = model(input_ids=ids).logits[0]
        # hidden[i] predicts token i+1
        logp = torch.log_softmax(logits[offset - 1], dim=-1)
        tid = tok.convert_tokens_to_ids(letter.upper())
        if tid is None or tid == tok.unk_token_id:
            return None
        return float(logp[tid])

    for r in rows:
        offset = int(r["pos"]) - max(1, int(r["pos"]) - int(r["flank"]))
        lp_ref = _snp_logp(r["ref_seq"], offset, r["vcf_ref"])
        lp_alt = _snp_logp(r["alt_seq"], offset, r["vcf_alt"])
        if lp_ref is None or lp_alt is None:
            r["lm_status"] = "HyenaDNA SNP offset failed"
            continue
        r["lm_logp_ref"] = round(lp_ref, 5)
        r["lm_logp_alt"] = round(lp_alt, 5)
        r["lm_delta"] = round(lp_ref - lp_alt, 5)
        r["lm_model"] = model_id
        r["lm_status"] = "ok-hyenadna-tiny (PlantCaduceus unavailable)"
        r["lm_note"] = (
            "HyenaDNA tiny causal logP at SNP. Pretrained on human genome, not grape. "
            "https://arxiv.org/abs/2306.15794. Fallback because PlantCaduceus needs CUDA mamba_ssm."
        )
    return rows


def score_mas(root: Path, *, use_lm: bool = True) -> list[dict]:
    fa = root / "data" / "ref" / "VS1.final.fa"
    vcf = root / "data" / "panel" / "panel167k_2449.vcf.gz"
    sites = [r["site"] for r in MAS_LOCI]
    alleles = load_alleles(vcf, sites)
    rows = extract_windows(fa, alleles)
    # train Markov on chromosome 2 excluding ±2 kb around scored SNPs
    index = load_fai(Path(str(fa) + ".fai"))
    chr2 = fetch_fa(fa, "2", 1, min(index["2"][0], 2_000_000), index)
    rows = markov_delta(rows, chr2, order=4)
    if use_lm:
        rows = try_plantcaduceus(rows)
        if all(not str(r.get("lm_status", "")).startswith("ok") for r in rows):
            rows = try_hyenadna(rows)
    else:
        for r in rows:
            r["lm_status"] = "skipped"
    return rows


def write_tsv(rows: list[dict], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "site",
        "gene",
        "trait",
        "vcf_ref",
        "vcf_alt",
        "vs1_base",
        "center_snippet",
        "markov_delta",
        "markov_logp_ref",
        "markov_logp_alt",
        "lm_delta",
        "lm_logp_ref",
        "lm_logp_alt",
        "lm_status",
        "lm_model",
    ]
    with path.open("w") as fh:
        fh.write("\t".join(cols) + "\n")
        for r in rows:
            fh.write("\t".join(str(r.get(c, "")) for c in cols) + "\n")
    seq_dir = path.with_suffix(".fa")
    with seq_dir.open("w") as fh:
        for r in rows:
            fh.write(f">{r['site']}|REF|{r['gene']}\n{r['ref_seq']}\n")
            fh.write(f">{r['site']}|ALT|{r['vcf_alt']}\n{r['alt_seq']}\n")
    return path
