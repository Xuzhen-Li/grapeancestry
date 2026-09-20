"""CNN-GS: 1D CNN over genotype dosage sites (PyTorch if available, else numpy fallback)."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def _impute(X: np.ndarray) -> np.ndarray:
    X = X.astype(np.float32).copy()
    for j in range(X.shape[1]):
        col = X[:, j]
        ok = col >= 0
        mu = float(col[ok].mean()) if ok.any() else 0.0
        col[~ok] = mu
        X[:, j] = col
    return X


def train_cnn_gs(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    *,
    seed: int = 0,
    epochs: int = 80,
    lr: float = 1e-3,
    weight_path: Path | None = None,
) -> tuple[np.ndarray, dict]:
    """Train 1D CNN; return test predictions + diagnostics."""
    try:
        import torch
        import torch.nn as nn
    except ImportError:
        return _numpy_cnn_fallback(X_train, y_train, X_test, seed=seed)

    torch.manual_seed(seed)
    Xt = _impute(X_train)
    Xs = _impute(X_test)
    y = y_train.astype(np.float32)
    y_mu = float(y.mean())
    y = y - y_mu
    # shape (N, 1, L) — single channel dosage
    xt = torch.from_numpy(Xt[:, None, :])
    xs = torch.from_numpy(Xs[:, None, :])
    yt = torch.from_numpy(y)

    class CNN(nn.Module):
        def __init__(self, length: int):
            super().__init__()
            self.conv = nn.Sequential(
                nn.Conv1d(1, 16, kernel_size=9, padding=4),
                nn.ReLU(),
                nn.MaxPool1d(4),
                nn.Conv1d(16, 32, kernel_size=9, padding=4),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(32),
            )
            self.fc = nn.Sequential(
                nn.Flatten(),
                nn.Linear(32 * 32, 64),
                nn.ReLU(),
                nn.Linear(64, 1),
            )

        def forward(self, x):
            return self.fc(self.conv(x)).squeeze(-1)

    model = CNN(Xt.shape[1])
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()
    model.train()
    for _ in range(epochs):
        opt.zero_grad()
        pred = model(xt)
        loss = loss_fn(pred, yt)
        loss.backward()
        opt.step()
    model.eval()
    with torch.no_grad():
        pred_te = model(xs).numpy() + y_mu
    if weight_path is not None:
        weight_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"state": model.state_dict(), "y_mu": y_mu, "length": Xt.shape[1]}, weight_path)
    return pred_te.astype(float), {"epochs": epochs, "backend": "torch"}


def _numpy_cnn_fallback(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    *,
    seed: int = 0,
) -> tuple[np.ndarray, dict]:
    """Lightweight local-window ridge as CNN stand-in when torch missing."""
    from grapeancestry.breeding.gs import rrblup_predict

    pred = rrblup_predict(X_train, y_train, X_test)
    return pred, {"backend": "numpy_rrblup_fallback", "seed": seed}
