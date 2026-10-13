"""Figures de l'APPROFONDISSEMENT (figures/appro_*.png). Toutes portent le bandeau EXPLORATOIRE."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter
from scipy import stats as sps

from . import theorie
from ..graphiques import COULEURS, _sauver

BANDEAU = "EXPLORATOIRE — non pré-enregistré, ne modifie pas le verdict"
ROUGE = "#b00020"


def _titre(fig, texte: str) -> None:
    fig.suptitle(f"{texte}\n{BANDEAU}", fontsize=10, color=ROUGE, fontweight="bold")


def figure_q1(t1: dict, chemin: Path) -> None:
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(13, 5.4))
    for nom, blocs in t1["sleeves"].items():
        for p, mk in (("TRAIN", "o"), ("VAL", "s")):
            b = blocs[p]
            if b.get("ir_predit") is None:
                continue
            ax.errorbar(b["ir_predit"], b["sharpe_brut"], xerr=b.get("se_ir_predit"), fmt=mk, color=COULEURS[nom], ms=7,
                        alpha=0.9, lw=1, label=f"{nom} {p}" if p == "VAL" else None)
    lim = [-1.5, 0.8]
    ax.plot(lim, lim, "k--", lw=1, label="IR prédit = Sharpe brut")
    ax.axhline(0, color="grey", lw=0.6)
    ax.axvline(0, color="grey", lw=0.6)
    ax.set_xlim(lim)
    ax.set_ylim(-1.6, 0.8)
    ax.set_xlabel("IR prédit = TC x IC x racine(breadth)")
    ax.set_ylabel("Sharpe brut réalisé")
    ac = t1["pile"]["accord_predit_realise"]
    ax.set_title(f"Loi fondamentale vs réalisé (cercle TRAIN, carré VAL) ; corrélation {ac['correlation']:.2f} sur {ac['n_couples']} couples", fontsize=9)
    ax.legend(fontsize=7, ncol=2)
    ax.grid(alpha=0.3)
    noms = list(t1["sleeves"])
    x = np.arange(len(noms))
    ic = [t1["sleeves"][k]["VAL"]["ic"] for k in noms]
    se = [t1["sleeves"][k]["VAL"].get("se_ic") or 0.0 for k in noms]
    req = [t1["sleeves"][k]["VAL"]["ic_requis_pour_ir_2"] for k in noms]
    bx.bar(x - 0.18, ic, 0.36, yerr=[1.96 * s for s in se], color=[COULEURS[k] for k in noms], label="IC observé VAL (± 1,96 SE)")
    bx.bar(x + 0.18, req, 0.36, color="lightgrey", edgecolor="k", label="IC requis pour IR = 2 (même breadth, même TC)")
    bx.axhline(0.05, color="green", ls=":", lw=1)
    bx.text(len(noms) - 0.5, 0.055, "IC « très bon » ~ 0,05", fontsize=7, color="green", ha="right")
    bx.axhline(0, color="k", lw=0.8)
    bx.set_xticks(x)
    bx.set_xticklabels(noms)
    bx.set_ylabel("IC (corrélation de rang)")
    bx.set_title("IC observé et IC nécessaire (VAL)", fontsize=9)
    bx.legend(fontsize=7)
    bx.grid(alpha=0.3, axis="y")
    _titre(fig, "Q1 — Loi fondamentale de la gestion active")
    _sauver(fig, chemin)


def figure_q2(t2: dict, chemin: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    ax, bx, cx, dx = axes.ravel()
    H = t2["horizons_jours"]
    for nom in ("S1", "S2", "S3", "S6"):
        c = t2["sleeves_quotidiennes"][nom]["ic"]["cumule"]["TOUT"]  # clés = horizons en chaînes (JSON)
        y = np.array([np.nan if c[str(h)]["ic"] is None else c[str(h)]["ic"] for h in H])
        s = np.array([np.nan if c[str(h)].get("se") is None else c[str(h)]["se"] for h in H])
        ax.errorbar(H, y, yerr=1.96 * s, marker="o", color=COULEURS[nom], capsize=3, label=nom, lw=1.3)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xscale("log")
    ax.set_xticks(H)
    ax.set_xticklabels(H)
    ax.set_xlabel("horizon h (jours après l'exécution)")
    ax.set_ylabel("IC cumulé TRAIN+VAL (± 1,96 SE de Newey-West)")
    ax.set_title("IC selon l'horizon : S2 négatif à tout horizon, S3 positif à 60 j", fontsize=9)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    for nom in ("S1", "S2", "S3"):
        pg = t2["sleeves_quotidiennes"][nom]["profil_gain_cout"]
        for p, ls in (("TRAIN", "-"), ("VAL", "--")):
            hs = [h for h in H if pg[p][str(h)] is not None]
            ys = [pg[p][str(h)]["net_bps_par_jour"] for h in hs]
            bx.plot(hs, ys, ls=ls, marker="o", color=COULEURS[nom], label=f"{nom} {p}")
    bx.axhline(0, color="k", lw=0.8)
    bx.set_xscale("log")
    bx.set_xticks(H)
    bx.set_xticklabels(H)
    bx.set_xlabel("horizon de re-signalisation h (jours)")
    bx.set_ylabel("rendement net par jour (bps de l'exposition brute)")
    bx.set_title("Gain marginal vs coût de rotation : net par jour selon h", fontsize=9)
    bx.legend(fontsize=7, ncol=2)
    bx.grid(alpha=0.3)
    for ax_, nom, titre in ((cx, "S4", "S4 : gain brut moyen par trade vs coût aller-retour"),
                            (dx, "S7", "S7 : gain brut moyen par trade vs coût aller-retour")):
        mm = t2["minutes"][nom]
        for p, ls in (("TRAIN", "-"), ("VAL", "--")):
            ks = sorted(mm[p], key=lambda k: int(k))
            ys = [mm[p][k]["gain_bps"] if mm[p][k] else np.nan for k in ks]
            ax_.plot([int(k) for k in ks], ys, ls=ls, marker="o", color=COULEURS[nom], label=f"gain {p}")
        cout = next(v["cout_aller_retour_bps"] for v in mm["VAL"].values() if v)
        ax_.axhline(cout, color=ROUGE, ls=":", lw=1.4, label=f"coût aller-retour {cout:.1f} bps")
        ax_.axhline(0, color="k", lw=0.8)
        ax_.set_xlabel("minutes après l'entrée")
        ax_.set_ylabel("bps")
        ax_.set_title(titre, fontsize=9)
        ax_.legend(fontsize=7)
        ax_.grid(alpha=0.3)
    dx.set_ylim(-4, 26)
    _titre(fig, "Q2 — Décroissance du signal et rotation")
    _sauver(fig, chemin)


def figure_q3(t3: dict, chemin: Path) -> None:
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(13, 5.4))
    ans = np.linspace(0.5, 30, 200)
    ax.plot(ans, [theorie.sharpe_min_detectable(a) for a in ans], color="C0", label="Sharpe minimal détectable (80 %, test unilatéral 5 %)")
    ax.plot(ans, [theorie.sharpe_min_detectable(a, n_tests=7) for a in ans], color="C1", label="idem avec Bonferroni sur 7 sleeves")
    ax.plot(ans, 1 / np.sqrt(ans), color="grey", ls="--", label="erreur-type du Sharpe  1/racine(années)")
    ax.axvline(t3["annees_val"], color=ROUGE, ls=":", label=f"VAL = {t3['annees_val']:.1f} ans")
    ax.axhline(0.5, color="green", ls=":", lw=1)
    ax.text(29.5, 0.53, "Sharpe 0,5", color="green", fontsize=8, ha="right")
    ax.set_xlabel("années d'historique")
    ax.set_ylabel("Sharpe annualisé")
    ax.set_ylim(0, 2.6)
    ax.set_title("Puissance : ce que 4 ans peuvent (ne pas) détecter", fontsize=9)
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)
    x = np.linspace(-2.2, 2.4, 400)
    se = t3["se_sharpe_val_sr05"]
    bx.plot(x, sps.norm.pdf(x, 0.5, se), color="C0", label="Sharpe estimé si le vrai Sharpe vaut 0,5")
    bx.plot(x, sps.norm.pdf(x, 0.0, se), color="grey", ls="--", label="si le vrai Sharpe vaut 0")
    for k, v in t3["par_serie"].items():
        if k in ("PILE", "S7", "S4"):
            continue
        bx.axvline(v["sharpe_net_val"], color=COULEURS[k], lw=1.5)
        bx.text(v["sharpe_net_val"], 0.02 + 0.07 * "S1S2S3S5S6".index(k) / 2, f"{k}\nP={v['p_sharpe_vrai_05_donne_au_plus_obs']['bootstrap']:.2f}",
                color=COULEURS[k], fontsize=7, ha="center")
    bx.set_xlabel("Sharpe net VAL")
    bx.set_ylabel("densité")
    bx.set_title("P(Sharpe estimé <= observé | vrai Sharpe 0,5) pour chaque sleeve (bootstrap)", fontsize=9)
    bx.legend(fontsize=7, loc="upper left")
    bx.grid(alpha=0.3)
    _titre(fig, "Q3 — Puissance statistique de 4 ans de VAL")
    _sauver(fig, chemin)


def figure_q4(t4: dict, chemin: Path) -> None:
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(13, 5.4))
    sig = t4["sigma_sharpe_val"]
    n = np.unique(np.round(np.logspace(np.log10(2), np.log10(1e6), 80)).astype(int))
    ax.plot(n, [theorie.sharpe_max_attendu(int(k), sig) for k in n], color="C0", label="formule de Bailey-López de Prado")
    ax.plot(n, [theorie.esperance_max_gaussien(int(k)) * sig if k < 3000 else np.nan for k in n], color="C1", ls="--", label="espérance exacte du max de N gaussiennes")
    sim = t4["validation_formule_vs_simulation"]
    ax.errorbar([int(k) for k in sim], [v["simulation_moyenne"] for v in sim.values()],
                yerr=[v["simulation_ecart_type"] for v in sim.values()], fmt="ko", capsize=3, label="simulation (bruit blanc, 1044 jours)")
    ax.axhline(2.0, color=ROUGE, ls=":", label="Sharpe 2")
    for h in t4["historique_essais_anterieurs"]:
        ax.axvline(h["n_essais"], color="grey", lw=0.5, alpha=0.5)
    ax.text(134, 0.3, "134 essais\n(plancher déclaré)", fontsize=7, ha="right", va="bottom")
    ax.set_xscale("log")
    ax.set_xlabel("nombre d'essais N")
    ax.set_ylabel("Sharpe annualisé maximal attendu SANS aucun edge")
    ax.set_title(f"Sharpe max attendu sous H0 (ecart-type d'un Sharpe VAL = {sig:.2f})", fontsize=9)
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)
    b = t4["n_essais_pour_sharpe_2_selon_duree_backtest_annees"]
    ans = [float(k) for k in b]
    bx.plot(ans, [v["n_essais_pour_sr_attendu_2"] for v in b.values()], "o-", color="C0")
    bx.set_xscale("log")
    bx.set_yscale("log")
    for a, v in zip(ans, b.values()):
        bx.annotate(f"{v['n_essais_pour_sr_attendu_2']:.3g}", (a, v["n_essais_pour_sr_attendu_2"]), textcoords="offset points", xytext=(4, 6), fontsize=8)
    bx.set_xlabel("durée du backtest (années)")
    bx.set_ylabel("N d'essais pour qu'un Sharpe de 2 sorte du pur hasard")
    bx.set_title("Combien d'essais fabriquent un « Sharpe 2 » sans edge", fontsize=9)
    bx.grid(alpha=0.3, which="both")
    _titre(fig, "Q4 — Tests multiples")
    _sauver(fig, chemin)


def figure_q5(t5: dict, rolls: dict, chemin_glissant: Path, chemin_regimes: Path) -> None:
    fig, axes = plt.subplots(2, 4, figsize=(15, 6.5), sharex=True)
    for ax, (nom, s) in zip(axes.ravel(), rolls.items()):
        ax.plot(s.index, s.values, color=COULEURS[nom], lw=1.3)
        ax.axhline(0, color="k", lw=0.7)
        ax.axvspan(np.datetime64("2019-01-01"), np.datetime64("2022-12-31"), color="grey", alpha=0.12)
        ax.set_title(nom, fontsize=9)
        ax.grid(alpha=0.3)
    fig.supylabel("Sharpe net glissant sur 1 an", fontsize=9)
    _titre(fig, "Q5 — Sharpe net glissant 1 an (zone grisée = VAL)")
    _sauver(fig, chemin_glissant)

    noms = list(t5["sleeves"])
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(13, 5))
    x = np.arange(len(noms))
    for i, (g, c) in enumerate((("bas", "#7fbf7b"), ("moyen", "#bdbdbd"), ("haut", "#d73027"))):
        ax.bar(x + (i - 1) * 0.26, [t5["sleeves"][k]["regime"][g]["sharpe_brut"] for k in noms], 0.26, color=c, label=f"vol {g}")
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(noms)
    ax.set_ylabel("Sharpe BRUT (TRAIN+VAL)")
    ax.set_title("Sharpe brut par régime de volatilité (terciles TRAIN du facteur indices)", fontsize=9)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis="y")
    for i, (p, c) in enumerate((("TRAIN", "#4575b4"), ("VAL", "#f46d43"))):
        bx.bar(x + (i - 0.5) * 0.36, [t5["sleeves"][k]["facteur"][p]["indices"]["correlation"] for k in noms], 0.36, color=c, label=f"corrélation au facteur indices, {p}")
    bx.axhline(0, color="k", lw=0.8)
    bx.set_xticks(x)
    bx.set_xticklabels(noms)
    bx.set_ylabel("corrélation des rendements nets quotidiens")
    bx.set_title("Exposition au facteur de marché (moyenne équipondérée des 8 indices)", fontsize=9)
    bx.legend(fontsize=8)
    bx.grid(alpha=0.3, axis="y")
    _titre(fig, "Q5 — Régime et facteur de marché")
    _sauver(fig, chemin_regimes)


def figure_q6(t6: dict, chemin: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 5.4))
    n = np.arange(1, 61)
    rho_obs = t6["rho_moyen_val"]
    for rho, ls in ((0.0, "-"), (rho_obs, "-"), (0.05, "--"), (0.10, ":")):
        ax.plot(n, [theorie.sharpe_pile(0.5, int(k), rho) for k in n], ls=ls, lw=2 if rho == rho_obs else 1.2,
                label=f"s = 0,5, rho = {rho:.3f}" + (" (observé, VAL)" if rho == rho_obs else ""))
    ax.plot(n, [theorie.sharpe_pile(0.3, int(k), rho_obs) for k in n], color="grey", ls="-.", label=f"s = 0,3, rho = {rho_obs:.3f}")
    ax.axhline(2.0, color=ROUGE, ls=":", lw=1.5)
    ax.text(60, 2.05, "Sharpe 2", color=ROUGE, ha="right", fontsize=8)
    ax.axvline(7, color="k", lw=0.7)
    ax.text(7.5, 0.3, "7 sleeves ici", fontsize=7)
    ax.set_xlabel("nombre de sleeves N")
    ax.set_ylabel("Sharpe de la pile")
    ax.set_title("SR_pile = s racine(N / (1 + (N-1) rho))", fontsize=9)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    _titre(fig, "Q6 — Diversification")
    _sauver(fig, chemin)


def figure_q7(t7: dict, chemin: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 5.4))
    aum = np.logspace(6, 12, 200)
    for nom, ls in (("S1", "-"), ("S6", "--")):
        for p, c in (("TRAIN", "C0"), ("VAL", "C3")):
            b = t7["sleeves"][nom][p]
            net = b["rendement_net_avant_impact"] - b["K_impact_par_racine_usd"] * np.sqrt(aum)
            ax.plot(aum, 100 * net, ls=ls, color=c, label=f"{nom} {p}")
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xscale("log")
    ax.set_xlabel("capital géré (USD)")
    ax.set_ylabel("rendement net annuel après impact (%)")
    ax.set_title("Rendement net après impact racine carrée (ADV et préfacteur : hypothèses d'ordre de grandeur)", fontsize=9)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, which="both")
    _titre(fig, "Q7 — Capacité de S1 et S6")
    _sauver(fig, chemin)


def figure_controle_positif(rapport: dict, rendements: np.ndarray, dates, chemin: Path) -> None:
    """Contrôle positif : à gauche la sleeve synthétique (Sharpe vrai connu) sur le calendrier réel, à droite les taux de détection."""
    import pandas as pd

    il, pu = rapport["illustration"], rapport["puissance"]
    fin_train = pd.Timestamp(rapport["frontieres"]["train_fin"])
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(12.5, 5.4), gridspec_kw={"width_ratios": [1.1, 1]})
    eq = 100 * np.cumprod(1.0 + rendements)
    ax.axvspan(dates[0], fin_train, color="#e7e9ee", zorder=0)
    ax.axvline(fin_train + pd.Timedelta(days=1), color="0.35", ls="--", lw=1)
    ax.semilogy(dates, eq, color="#0b3d91", lw=1.8)
    t, v = il["TRAIN"], il["VAL"]
    ax.text(0.03, 0.96, f"TRAIN : Sharpe estimé {t['sharpe_net']:.2f}\nIC 95 % [{t['ic95_sharpe'][0]:.2f} ; {t['ic95_sharpe'][1]:.2f}]",
            transform=ax.transAxes, va="top", fontsize=10)
    ax.text(0.97, 0.04, f"VAL : Sharpe estimé {v['sharpe_net']:.2f}\nIC 95 % [{v['ic95_sharpe'][0]:.2f} ; {v['ic95_sharpe'][1]:.2f}]",
            transform=ax.transAxes, va="bottom", ha="right", fontsize=10)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:g}"))
    ax.yaxis.set_minor_formatter(FuncFormatter(lambda y, _: f"{y:g}" if y in (80, 150, 200, 300) else ""))
    ax.set_ylabel("capital (base 100, échelle log)")
    ax.set_title(f"Sleeve synthétique, Sharpe VRAI {il['sharpe_vrai']:.1f} (graine {il['graine']})", fontsize=10.5)
    ax.grid(alpha=0.3, which="both", axis="y")
    srs = sorted(pu["par_sharpe_vrai"], key=float)
    x = [float(s) for s in srs]
    for cle, lab, c, mk in (("taux_G2", "G2 : borne basse de l'IC 95 % > 0", "#0b3d91", "o"), ("taux_G1", "G1 : Sharpe estimé ≥ 1", "#2ca02c", "s"),
                            ("taux_G3", "G3 : DSR ≥ 0,95 (N = 8)", "#d62728", "^")):
        bx.plot(x, [100 * pu["par_sharpe_vrai"][s][cle] for s in srs], marker=mk, color=c, lw=1.8, label=lab)
    bx.axhline(80, color="0.5", ls=":", lw=1)
    bx.text(x[-1], 76, "puissance 80 %", fontsize=9, color="0.35", ha="right")
    if rapport.get("sharpe_min_detectable_80pct") is not None:
        s80 = rapport["sharpe_min_detectable_80pct"]
        bx.axvline(s80, color=ROUGE, ls=":", lw=1)
        bx.text(s80 + 0.03, 1.0, f"détectable à 80 % : {s80:.2f}", color=ROUGE, fontsize=9)
    bx.set_xlabel("Sharpe VRAI de la sleeve simulée")
    bx.set_ylabel(f"part des {pu['n_rep']} simulations où la gate passe (%)")
    bx.set_ylim(-3, 103)
    bx.set_title(f"Détection sur {pu['n_jours']} jours (= VAL) ; à Sharpe vrai 0 : faux positifs", fontsize=10.5)
    bx.legend(fontsize=9, loc="upper left")
    bx.grid(alpha=0.3)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.suptitle(f"Contrôle positif : le pipeline retrouve-t-il un edge connu ?\n{BANDEAU}", fontsize=10, color=ROUGE, fontweight="bold", y=0.995)
    _sauver(fig, chemin)
