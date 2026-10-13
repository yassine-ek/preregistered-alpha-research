"""Figures « vitrine » du README : hero_equity.png, toutes_variantes.png, overfit_scatter.png.

Lit UNIQUEMENT results/rendements_train_val.csv, results/train_val.json et (frais) results/reproduction_et_trades.json :
aucune donnée de marché, TEST jamais chargé (le CSV s'arrête au 2022-12-30). Convention de courbe : capital composé,
base 100, net de frais réels ; le drawdown et les Sharpe sont ceux des fichiers de résultats.

Usage : python scripts/generer_figures_vitrine.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from alpha.graphiques import COULEURS  # noqa: E402

RESULTATS, FIGURES = RACINE / "results", RACINE / "figures"
DPI = 130
GRIS_TRAIN = "#e7e9ee"


def f2(x: float, d: int = 2) -> str:
    return f"{x:.{d}f}".replace(".", ",").replace("-", "−")


def charger():
    tv = json.loads((RESULTATS / "train_val.json").read_text(encoding="utf-8"))
    csv = pd.read_csv(RESULTATS / "rendements_train_val.csv", index_col=0, parse_dates=True)
    tr_chemin = RESULTATS / "reproduction_et_trades.json"
    tr = json.loads(tr_chemin.read_text(encoding="utf-8")) if tr_chemin.exists() else None
    fin_train = pd.Timestamp(tv["meta"]["periodes"]["TRAIN"][1])
    assert csv.index.max() < pd.Timestamp("2023-01-01"), "TEST interdit"
    return tv, csv, tr, fin_train


def equity(csv: pd.DataFrame, tv: dict, k: str) -> pd.Series:
    """Capital composé (base 100) de la série k, à partir de son premier jour actif."""
    net = (csv[f"{k}_brut"] - csv[f"{k}_cout"]).loc[pd.Timestamp(tv["series"][k]["debut_actif"]):]
    return 100.0 * (1.0 + net).cumprod()


def texte_frais(tr: dict | None) -> str:
    if not tr:
        return "coûts réels par actif (indices 12 bps/jambe)"
    cl = tr["frais_univers"]["par_classe"]
    fx = cl["FX"]["mediane_bps"]
    ind = cl["Indice"]["mediane_bps"]
    mat = next(v for n, v in cl.items() if n.startswith("Mati"))["mediane_bps"]
    return f"coûts par jambe : FX {f2(fx, 1)} bp, indices {f2(ind, 0)} bp, métaux/pétrole {f2(mat, 1)} bp"


def _zones(ax, debut, fin_train):
    ax.axvspan(debut, fin_train, color=GRIS_TRAIN, zorder=0)
    ax.axvline(fin_train + pd.Timedelta(days=1), color="0.35", ls="--", lw=1, zorder=1)


def _fmt_axe_log(ax):
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))


def hero(tv, csv, tr, fin_train):
    """Figure héro lisible : 2 panneaux (equity, drawdown), police >= 11 pt pour un affichage réduit dans le README."""
    eq = equity(csv, tv, "PILE")
    # drawdown calculé période par période (celui des tableaux : le sommet repart de zéro au début de VAL)
    dd = pd.concat([100 * (e / e.cummax() - 1.0) for e in (eq.loc[:fin_train], eq.loc[fin_train + pd.Timedelta(days=1):])])
    s = tv["series"]["PILE"]
    with plt.rc_context({"font.size": 11, "axes.labelsize": 11, "xtick.labelsize": 11, "ytick.labelsize": 11}):
        fig, (ax, ax2) = plt.subplots(2, 1, figsize=(8.2, 6.2), sharex=True, gridspec_kw={"height_ratios": [3, 1.2], "hspace": 0.08})
        _zones(ax, eq.index[0], fin_train)
        _zones(ax2, eq.index[0], fin_train)
        ax.semilogy(eq.index, eq.values, color="#0b3d91", lw=2.4)
        _fmt_axe_log(ax)
        ax.set_ylabel("capital (base 100, log)")
        ax.grid(alpha=0.3, which="both", axis="y")
        trans = ax.get_xaxis_transform()
        milieu_train = eq.index[0] + (fin_train - eq.index[0]) / 2
        ax.text(milieu_train, 0.96, f"TRAIN\nSharpe net {f2(s['TRAIN']['sharpe_net'])}", transform=trans, ha="center", va="top", fontsize=11.5)
        milieu_val = fin_train + (eq.index[-1] - fin_train) / 2
        ax.text(milieu_val, 0.96, f"VAL\nSharpe net {f2(s['VAL']['sharpe_net'])}", transform=trans, ha="center", va="top", fontsize=11.5)
        ax2.fill_between(dd.index, dd.values, 0, color="#b91c1c", alpha=0.45, lw=0)
        ax2.set_ylim(-100, 0)
        ax2.set_ylabel("drawdown (%)")
        ax2.grid(alpha=0.3)
        fig.suptitle("Pile des 7 sleeves, nette de frais réels, rien n'est écarté", fontsize=13.5, y=0.995)
        ax.set_title(texte_frais(tr), fontsize=11, color="0.25", pad=6)
        fig.savefig(FIGURES / "hero_equity.png", dpi=170, bbox_inches="tight")
        plt.close(fig)


def _etiquettes_sans_chevauchement(ys, pas=0.085):
    """Positions (log10) d'étiquettes triées, écartées d'au moins `pas`."""
    ordre = np.argsort(ys)
    pos = np.array(ys, dtype=float)[ordre]
    for i in range(1, len(pos)):
        pos[i] = max(pos[i], pos[i - 1] + pas)
    out = np.empty(len(ys))
    out[ordre] = pos
    return out


def toutes_variantes(tv, csv, tr, fin_train):
    sleeves = [k for k in tv["series"] if k != "PILE"]
    eqs = {k: equity(csv, tv, k) for k in [*sleeves, "PILE"]}
    debut = min(e.index[0] for e in eqs.values())
    fig, ax = plt.subplots(figsize=(11, 6.2))
    _zones(ax, debut, fin_train)
    ymin, ymax = 0.05, 400.0
    horscadre = []
    for k in sleeves:
        e = eqs[k]
        ax.semilogy(e.index, e.values, color="0.55", lw=1.0, alpha=0.9)
        if e.iloc[-1] < ymin:
            horscadre.append(f"{k} → {e.iloc[-1]:.0e}".replace("e-0", "·10⁻").replace("e-", "·10⁻"))
    e = eqs["PILE"]
    ax.semilogy(e.index, e.values, color="#0b3d91", lw=2.8, zorder=5, label="PILE (combinaison de toutes les sleeves)")
    ax.set_ylim(ymin, ymax)
    _fmt_axe_log(ax)
    ax.grid(alpha=0.3, which="both", axis="y")
    ax.set_ylabel("capital (base 100, échelle log)")
    finaux = {k: float(eqs[k].iloc[-1]) for k in [*sleeves, "PILE"]}
    visibles = [k for k in finaux if ymin <= finaux[k] <= ymax]
    pos = _etiquettes_sans_chevauchement([np.log10(finaux[k]) for k in visibles])
    x_txt = eqs["PILE"].index[-1] + pd.Timedelta(days=25)
    for k, p in zip(visibles, pos):
        ax.text(x_txt, 10 ** p, f"{k} {f2(finaux[k], 2 if finaux[k] < 1 else 1)}", va="center", fontsize=8.5,
                color="#0b3d91" if k == "PILE" else "0.35", fontweight="bold" if k == "PILE" else "normal")
    ax.set_xlim(debut, eqs["PILE"].index[-1] + pd.Timedelta(days=330))
    if horscadre:
        ax.text(0.01, 0.02, "Hors cadre (sous 0,05) : " + ", ".join(horscadre), transform=ax.transAxes, fontsize=8.5, color="0.3")
    trans = ax.get_xaxis_transform()
    ax.text(debut + (fin_train - debut) / 2, 0.96, "TRAIN", transform=trans, ha="center", va="top", fontsize=10)
    ax.text(fin_train + (eqs["PILE"].index[-1] - fin_train) / 2, 0.96, "VAL", transform=trans, ha="center", va="top", fontsize=10)
    ax.legend(loc="lower left", bbox_to_anchor=(0.01, 0.08), fontsize=9)
    fig.suptitle("Toutes les variantes testées : 7 sleeves (gris) et la pile (bleu), nettes de frais", fontsize=12.5, y=0.99)
    ax.set_title(texte_frais(tr) + ", rien n'est écarté", fontsize=9.5, color="0.25", pad=6)
    fig.savefig(FIGURES / "toutes_variantes.png", dpi=DPI, bbox_inches="tight")
    plt.close(fig)


def overfit_scatter(tv):
    noms = list(tv["series"])
    x = np.array([tv["series"][k]["TRAIN"]["sharpe_net"] for k in noms])
    y = np.array([tv["series"][k]["VAL"]["sharpe_net"] for k in noms])
    fig, ax = plt.subplots(figsize=(7.6, 6.6))
    ax.set_xscale("symlog", linthresh=1.0)
    ax.set_yscale("symlog", linthresh=1.0)
    lim = (-20, 3)
    g = np.linspace(*lim, 400)
    ax.fill_between(g, lim[0], g, color="#b91c1c", alpha=0.06, lw=0)
    ax.plot(g, g, color="0.4", ls="--", lw=1, label="VAL = TRAIN (pas d'overfit)")
    ax.axhline(0, color="0.2", lw=0.8)
    ax.axvline(0, color="0.2", lw=0.8)
    for k, xi, yi in zip(noms, x, y):
        ax.scatter([xi], [yi], s=120 if k == "PILE" else 80, marker="D" if k == "PILE" else "o",
                   color=COULEURS.get(k, "k"), edgecolor="white", linewidth=0.8, zorder=4)
        ax.annotate(k, (xi, yi), textcoords="offset points", xytext=(7, 6), fontsize=10, fontweight="bold" if k == "PILE" else "normal")
    ax.set_xlim(*lim)
    ax.set_ylim(*lim)
    ticks = [-15, -5, -2, -1, 0, 1, 2]
    for axe in (ax.xaxis, ax.yaxis):
        axe.set_major_locator(matplotlib.ticker.FixedLocator(ticks))
        axe.set_major_formatter(FuncFormatter(lambda v, _: f2(v, 0)))
    ax.set_xlabel("Sharpe net TRAIN (échelle symlog)")
    ax.set_ylabel("Sharpe net VAL (échelle symlog)")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", fontsize=9)
    ax.text(0.98, 0.03, "zone rose : pire en VAL qu'en TRAIN", transform=ax.transAxes, ha="right", fontsize=8.5, color="#7f1d1d")
    ax.set_title("Overfit ? Sharpe net TRAIN contre VAL, une variante = un point\n(7 sleeves + pile, rien n'est écarté)", fontsize=11.5)
    fig.savefig(FIGURES / "overfit_scatter.png", dpi=DPI, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    FIGURES.mkdir(exist_ok=True)
    tv, csv, tr, fin_train = charger()
    hero(tv, csv, tr, fin_train)
    toutes_variantes(tv, csv, tr, fin_train)
    overfit_scatter(tv)
    print("figures/hero_equity.png, toutes_variantes.png, overfit_scatter.png écrites")


if __name__ == "__main__":
    main()
