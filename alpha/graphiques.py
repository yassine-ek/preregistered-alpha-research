"""Figures (PNG, dpi 130) : PnL cumulé, corrélations, Sharpe VAL avec IC, coûts annuels."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DPI = 130
COULEURS = {"S1": "#1f77b4", "S2": "#ff7f0e", "S3": "#2ca02c", "S4": "#d62728",
            "S5": "#9467bd", "S6": "#8c564b", "S7": "#e377c2", "PILE": "#000000"}


def _sauver(fig, chemin: Path) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(chemin, dpi=DPI, bbox_inches="tight")
    plt.close(fig)


def pnl_cumule(nets: pd.DataFrame, bruts: pd.DataFrame, fin_train: pd.Timestamp, chemin: Path) -> None:
    """Deux panneaux : net (après coûts) et brut (avant coûts). Somme cumulée des
    rendements quotidiens ; ligne verticale = frontière TRAIN | VAL. Les séries qui sortent
    du cadre (coûts énormes) sont rognées et leur valeur finale est écrite dans la légende."""
    fig, axes = plt.subplots(2, 1, figsize=(10, 8.5), sharex=True)
    for ax, df, titre in ((axes[0], nets, "Net (après coûts réels)"), (axes[1], bruts, "Brut (avant coûts)")):
        for col in df.columns:
            cum = df[col].fillna(0.0).cumsum()
            epais = 2.4 if col == "PILE" else 1.1
            ax.plot(cum.index, cum.values, color=COULEURS.get(col), lw=epais,
                    label=f"{col} (final {cum.iloc[-1]:+.2f})")
        ax.axvline(fin_train + pd.Timedelta(days=1), color="grey", ls="--", lw=1)
        ax.set_title(titre)
        ax.set_ylabel("rendement cumulé (somme, fraction du capital)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7, ncol=4, loc="lower left")
    axes[0].set_ylim(-3.0, 1.5)
    axes[1].set_ylim(-1.5, 1.5)
    axes[0].text(fin_train - pd.Timedelta(days=300), 1.25, "TRAIN", ha="center")
    axes[0].text(fin_train + pd.Timedelta(days=500), 1.25, "VAL", ha="center")
    fig.suptitle("PnL cumulé par sleeve et pile, TRAIN | VAL")
    _sauver(fig, chemin)


def matrice_correlation(corr_train: pd.DataFrame, corr_val: pd.DataFrame, chemin: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    for ax, c, t in ((axes[0], corr_train, "TRAIN"), (axes[1], corr_val, "VAL")):
        im = ax.imshow(c.values, vmin=-1, vmax=1, cmap="RdBu_r")
        ax.set_xticks(range(len(c)), c.columns)
        ax.set_yticks(range(len(c)), c.index)
        for i in range(len(c)):
            for j in range(len(c)):
                ax.text(j, i, f"{c.values[i, j]:.2f}", ha="center", va="center", fontsize=7)
        ax.set_title(f"Corrélation des rendements nets, {t}")
    fig.colorbar(im, ax=axes, shrink=0.8)
    _sauver(fig, chemin)


def sharpe_val_ic(stats_val: dict, chemin: Path) -> None:
    noms = list(stats_val)
    sh = np.array([stats_val[k]["sharpe_net"] for k in noms])
    bas = np.array([stats_val[k]["ic95_sharpe"][0] for k in noms])
    haut = np.array([stats_val[k]["ic95_sharpe"][1] for k in noms])
    brut = np.array([stats_val[k]["sharpe_brut"] for k in noms])
    fig, ax = plt.subplots(figsize=(9, 5))
    y = np.arange(len(noms))
    ax.barh(y, sh, color=[COULEURS.get(k) for k in noms], alpha=0.8)
    ax.errorbar(sh, y, xerr=[sh - bas, haut - sh], fmt="none", ecolor="black", capsize=3)
    ax.scatter(brut, y, marker="D", color="white", edgecolor="black", zorder=3, label="Sharpe brut (avant coûts)")
    ax.axvline(0, color="black", lw=0.8)
    ax.axvline(1.0, color="green", ls="--", lw=1, label="gate G1 (1,0)")
    ax.set_yticks(y, noms)
    ax.invert_yaxis()
    ax.set_xlabel("Sharpe net annualisé, VAL 2019-2022 (barre = IC 95 % bootstrap)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis="x")
    _sauver(fig, chemin)


def cout_annuel(stats_train: dict, stats_val: dict, chemin: Path) -> None:
    noms = list(stats_val)
    x = np.arange(len(noms))
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.bar(x - 0.2, [100 * stats_train[k]["cout_annuel"] for k in noms], 0.4, label="TRAIN", color="#9ecae1")
    ax.bar(x + 0.2, [100 * stats_val[k]["cout_annuel"] for k in noms], 0.4, label="VAL", color="#3182bd")
    ax.axhline(10, color="red", ls="--", lw=1, label="vol cible de chaque sleeve (10 %)")
    ax.set_yscale("log")
    ax.set_xticks(x, noms)
    ax.set_ylabel("coût annuel (% du capital, échelle log)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis="y")
    _sauver(fig, chemin)
