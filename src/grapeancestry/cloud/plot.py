"""K=8 ancestry bars for the chip companion (PNG bytes)."""

from __future__ import annotations

import io

from grapeancestry.adna.admixture import SCIENCE_K8_COLORS, SCIENCE_K8_LABELS


def k8_png_bytes(q8: dict[str, float], title: str = "") -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    labels = list(SCIENCE_K8_LABELS)
    vals = [float(q8.get(f"K{i}", 0.0)) for i in range(1, 9)]
    colors = list(SCIENCE_K8_COLORS)
    fig, ax = plt.subplots(figsize=(7.2, 1.8))
    left = 0.0
    for v, c in zip(vals, colors):
        ax.barh([0], [v], left=left, color=c, height=0.55)
        left += v
    ax.set_xlim(0, 1)
    ax.set_yticks([])
    ax.set_xlabel("K=8 ancestry (in-panel lookup)")
    if title:
        ax.set_title(title, loc="left", fontsize=10)
    handles = [Patch(color=c, label=lab) for lab, c in zip(labels, colors)]
    ax.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.55),
        ncol=4,
        fontsize=7,
        frameon=False,
    )
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
