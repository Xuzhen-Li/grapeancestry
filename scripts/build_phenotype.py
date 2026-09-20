#!/usr/bin/env python3
"""Build data/phenotype.tsv from the 2022-05-23 ST1 workbook."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grapeancestry.breeding.phenotype import MIN_PHENO_N, build_phenotype_outputs  # noqa: E402
from grapeancestry.breeding.provenance import file_ref, write_provenance  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--xlsx",
        type=Path,
        default=ROOT / "2022-05-23 Phenotype from DX" / "2022-05-23-ST1表型 3K sequenced samples.xlsx",
    )
    p.add_argument(
        "--euvitis-dict",
        type=Path,
        default=ROOT / "2022-05-23 Phenotype from DX" / "www.eu-vitis.de.xlsx",
    )
    p.add_argument(
        "--descep-dict",
        type=Path,
        default=ROOT / "2022-05-23 Phenotype from DX" / "des-cep-monde-edition-2009.xlsx",
    )
    p.add_argument("--info", type=Path, default=ROOT / "data" / "panel" / "2449.info")
    p.add_argument("--out-dir", type=Path, default=ROOT / "data")
    p.add_argument("--coverage-dir", type=Path, default=ROOT / "results" / "phenotype")
    args = p.parse_args(argv)

    res = build_phenotype_outputs(
        xlsx=args.xlsx,
        euvitis_dict=args.euvitis_dict,
        descep_dict=args.descep_dict,
        info=args.info,
        out_dir=args.out_dir,
        coverage_dir=args.coverage_dir,
    )
    c = res["counts"]
    print(
        f"union_ids={c['ids_in_panel_union']} euvitis={c['ids_in_panel_euvitis']} "
        f"descep={c['ids_in_panel_descep']} n>=50={c['traits_n_ge_50_total']} "
        f"(MIN_PHENO_N={MIN_PHENO_N})"
    )
    print(f"wrote {res['paths']}")
    write_provenance(
        ROOT / "results" / "provenance",
        step="phenotype_etl",
        inputs=[
            file_ref(args.xlsx, note="ST1 phenotypes"),
            file_ref(args.euvitis_dict, note="OIV dictionary eu-vitis"),
            file_ref(args.descep_dict, note="OIV dictionary des-cep"),
            file_ref(args.info, note="2449 panel IDs"),
        ],
        parameters={"min_pheno_n": MIN_PHENO_N},
        counts=c,
        methods=[
            {"name": "OIV_descriptor_parse", "ref_keys": ["oiv2009", "euvitis", "vivc"]},
        ],
        outputs=[
            file_ref(res["paths"]["phenotype"], n_rows=res["n_pheno"]),
            file_ref(res["paths"]["oiv_traits"]),
            file_ref(res["paths"]["sample_annot"]),
            file_ref(res["paths"]["coverage"]),
        ],
        caveats=[
            "eu-vitis and des-cep values are not merged (2022-05-23 file note).",
            "0 coded as missing; multi-value ordinal mean / nominal consensus.",
            "GRIN/NPGS and the 41MB all-matched workbook unused (no Library-ID map).",
            "des-cep Excel used range is 2256 rows including blanks; nonempty Library-ID rows = unique IDs (no ST1 replicates).",
            "traits_n_ge_50_total is after parse (out-of-scale / nominal disagreement dropped); raw non-zero n≥50 was 168 (plan §0).",
        ],
        git_cwd=ROOT,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
