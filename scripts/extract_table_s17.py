#!/usr/bin/env python3
"""Extract trait-locus rows from Table S1-17 Final.xlsx into data/trait_locus.tsv.

Usage (from grapeancestry_suite/):
  python scripts/extract_table_s17.py \\
    --xlsx /path/to/Table\\ S1-17\\ Final.xlsx \\
    --out data/trait_locus.tsv
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--xlsx",
        type=Path,
        default=Path(
            "/Users/lixuzhen/Desktop/Write_write/grapevine_array&adna_capture/V4_nc/Table S1-17 Final.xlsx"
        ),
    )
    p.add_argument("--out", type=Path, default=Path("data/trait_locus.tsv"))
    p.add_argument("--keep-existing", action="store_true", help="Union with existing out")
    args = p.parse_args()

    rows: list[dict[str, str]] = []
    existing: set[tuple[str, str, str]] = set()
    if args.keep_existing and args.out.exists():
        with args.out.open() as fh:
            for r in csv.DictReader(fh, delimiter="\t"):
                key = (r.get("chrom", ""), r.get("pos", ""), r.get("trait", ""))
                existing.add(key)
                rows.append(r)

    if not args.xlsx.exists():
        print(f"[warn] xlsx not found: {args.xlsx}; writing existing/empty only")
    else:
        try:
            import pandas as pd
        except ImportError:
            print("[error] pandas/openpyxl required")
            return 1
        xl = pd.ExcelFile(args.xlsx)
        for sheet in xl.sheet_names:
            df = xl.parse(sheet)
            cols = {c.lower(): c for c in df.columns.astype(str)}
            chrom_c = next((cols[k] for k in cols if k in {"chrom", "chr", "chromosome"}), None)
            pos_c = next((cols[k] for k in cols if k in {"pos", "position", "bp"}), None)
            trait_c = next((cols[k] for k in cols if "trait" in k or k.startswith("oiv")), None)
            if not (chrom_c and pos_c):
                continue
            for _, row in df.iterrows():
                chrom = str(row[chrom_c]).strip()
                pos = str(row[pos_c]).strip()
                if not chrom or chrom.lower() == "nan" or not pos or pos.lower() == "nan":
                    continue
                try:
                    int(float(pos))
                except ValueError:
                    continue
                trait = str(row[trait_c]).strip() if trait_c else sheet
                key = (chrom, str(int(float(pos))), trait)
                if key in existing:
                    continue
                existing.add(key)
                rows.append(
                    {
                        "chrom": key[0],
                        "pos": key[1],
                        "trait": trait,
                        "note": f"from_S1-17:{sheet}",
                    }
                )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["chrom", "pos", "trait", "note"], delimiter="\t")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in w.fieldnames})
    print(f"wrote {args.out} n={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
