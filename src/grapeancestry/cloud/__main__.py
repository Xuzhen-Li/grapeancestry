"""python -m grapeancestry.cloud.pack  →  data/cloud/fingerprint.npz"""

from __future__ import annotations

from grapeancestry.cloud.pack import build_cloud_pack, suite_root


def main() -> None:
    root = suite_root()
    counts = build_cloud_pack(root)
    print(counts)


if __name__ == "__main__":
    main()
