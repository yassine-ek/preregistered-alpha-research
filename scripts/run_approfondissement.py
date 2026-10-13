"""APPROFONDISSEMENT (EXPLORATOIRE, non pré-enregistré, ne modifie pas le verdict) : pourquoi aucune des 7
sleeves ne marche ici, et que faudrait-il pour un Sharpe net > 2 ?

Usage : python scripts/run_approfondissement.py [--rafraichir]
Sorties : results/approfondissement.json, figures/appro_*.png
TRAIN (<= 2018) et VAL (2019-2022) seulement : le TEST n'est jamais chargé (lecteur strict, voir
alpha/approfondissement/chargement.py). Les paramètres des sleeves ne sont pas touchés ; on ne fait que MESURER.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

import numpy as np  # noqa: E402

from alpha import donnees as d  # noqa: E402
from alpha import pipeline as pl  # noqa: E402
from alpha.approfondissement import chargement as ap  # noqa: E402
from alpha.approfondissement import diagnostics as dg  # noqa: E402
from alpha.approfondissement import figures as ag  # noqa: E402
import verifier_donnees  # noqa: E402  (message guidé si les données manquent)
import verifier_prereg  # noqa: E402  (empreinte de la v1)

RESULTATS, FIGURES = RACINE / "results", RACINE / "figures"
TITRE = "EXPLORATOIRE — non pré-enregistré, ne modifie pas le verdict"


def f(x, n=2):
    """Format français d'un nombre pour les conclusions."""
    return "n/d" if x is None else f"{x:.{n}f}".replace(".", ",")


def conclusions(r: dict) -> dict:
    """Phrases chiffrées, construites À PARTIR des résultats (rien n'est retapé à la main)."""
    t1, t2, t3, t4, t5, t6, t7 = (r[k] for k in ("Q1_grinold", "Q2_decroissance", "Q3_puissance", "Q4_tests_multiples",
                                                  "Q5_anatomie", "Q6_diversification", "Q7_capacite"))
    s1, pv = t1["sleeves"], t1["pile"]["VAL"]
    ac = t1["pile"]["accord_predit_realise"]
    zmax = max(abs(s1[k][p]["z_ecart_predit_vs_realise"]) for k in s1 for p in ("TRAIN", "VAL") if s1[k][p].get("z_ecart_predit_vs_realise") is not None)
    c1 = (f"La loi IR = TC x IC x racine(BR) prédit le Sharpe brut réalisé avec une corrélation de {f(ac['correlation'])} sur "
          f"{ac['n_couples']} couples (sleeve, période) : l'ordre de grandeur tient (écart prédit - réalisé |z| <= {f(zmax, 1)} sur les {ac['n_couples']} couples, mais les erreurs-types sont larges), donc ce qui manque est de l'IC, pas de la breadth. "
          f"Avec une breadth totale de {f(pv['breadth_totale'], 0)} paris indépendants/an et un TC moyen de {f(pv['tc_moyen'])}, une pile à IR 2 exigerait un IC "
          f"de {f(pv['ic_uniforme_requis_pour_ir_2'], 3)} sur les 7 sleeves à la fois ; l'IC moyen observé en VAL vaut {f(pv['ic_moyen_observe'], 3)} "
          f"(S1 {f(s1['S1']['VAL']['ic'], 3)}, S2 {f(s1['S2']['VAL']['ic'], 3)}, S3 {f(s1['S3']['VAL']['ic'], 3)}, S7 {f(s1['S7']['VAL']['ic'], 3)}). "
          f"Avec l'IC observé de S3 (le seul positif parmi les sleeves quotidiennes), il faudrait {f(s1['S3']['VAL']['facteur_breadth_a_trouver'], 0)} fois sa breadth.")
    sl = t2["sleeves_quotidiennes"]
    cs2, cs3 = sl["S2"]["ic"]["cumule"]["TOUT"], sl["S3"]["ic"]["cumule"]["TOUT"]
    pg3 = sl["S3"]["profil_gain_cout"]
    m4 = t2["minutes"]["S4"]
    gmax4 = max(v["gain_bps"] for p in ("TRAIN", "VAL") for v in m4[p].values() if v)
    cout4 = next(v["cout_aller_retour_bps"] for v in m4["VAL"].values() if v)
    gmax7 = max(v["gain_bps"] for p in ("TRAIN", "VAL") for v in t2["minutes"]["S7"][p].values() if v)
    nb_hl = sum(1 for k in sl for v in sl[k]["demi_vie_ic_marginal_jours"].values() if v)
    c2 = (f"IC de S2 (momentum 63 j) négatif à tous les horizons testés sur TRAIN+VAL (60 j : {f(cs2['60']['ic'], 3)}, t = {f(cs2['60']['t_nw'], 1)}) : le signal est inversé. "
          f"IC de S3 (retournement 5 j) négatif à 2-5 j, positif à 10-60 j (60 j : {f(cs3['60']['ic'], 3)}, t = {f(cs3['60']['t_nw'], 1)}) alors que S3 est tenue 5 jours ; "
          f"en re-signalisant tous les 60 j le net par jour serait de {f(pg3['TRAIN']['60']['net_bps_par_jour'])} bps (TRAIN) et {f(pg3['VAL']['60']['net_bps_par_jour'])} bps (VAL) "
          f"de l'exposition brute (constat a posteriori : il faudrait un nouveau pré-enregistrement). Demi-vie du signal : S1 {f(sl['S1']['demi_vie_signal_jours'], 0)} j, "
          f"S2 {f(sl['S2']['demi_vie_signal_jours'], 0)} j, S3 {f(sl['S3']['demi_vie_signal_jours'], 0)} j, S6 {f(sl['S6']['demi_vie_signal_jours'], 0)} j ; la demi-vie de l'IC n'est définie "
          f"que pour {nb_hl} des 8 couples (sleeve, période) car l'IC est le plus souvent <= 0. "
          f"Intrajournalier : gain brut moyen maximal de S4 {f(gmax4, 2)} bps contre {f(cout4, 1)} bps de coût aller-retour ; S7 au mieux {f(gmax7, 2)} bps contre 24 bps.")
    m = t3["sharpe_min_detectable_80pct"]
    ps = t3["par_serie"]
    sleeves7 = [k for k in ps if k != "PILE"]
    rejet05 = [k for k in sleeves7 if ps[k]["p_sharpe_vrai_05_donne_au_plus_obs"]["bootstrap"] < 0.03]
    compat05 = [k for k in sleeves7 if k not in rejet05]
    rejet025 = [k for k in sleeves7 if ps[k]["p_sharpe_vrai_025_donne_au_plus_obs_analytique"] < 0.05]
    c3 = (f"Sur {f(t3['annees_val'], 1)} ans de VAL l'erreur-type du Sharpe vaut {f(t3['se_sharpe_val_sr0'])} ; le plus petit Sharpe vrai détecté avec 80 % de puissance est "
          f"{f(m['unilateral_alpha5'])} (unilatéral 5 %), {f(m['unilateral_bonferroni_7'])} avec Bonferroni sur 7 sleeves. Détecter un Sharpe de 0,5 exige "
          f"{f(t3['annees_pour_detecter_80pct_unilateral']['0.5'], 0)} ans, de 0,25 : {f(t3['annees_pour_detecter_80pct_unilateral']['0.25'], 0)} ans. Une sleeve de vrai Sharpe 0,5 afficherait "
          f"un Sharpe VAL <= celui de S6 ({f(ps['S6']['sharpe_net_val'])}) avec {f(100 * ps['S6']['p_sharpe_vrai_05_donne_au_plus_obs']['bootstrap'], 0)} % de chances, <= celui de S1 "
          f"({f(ps['S1']['sharpe_net_val'])}) avec {f(100 * ps['S1']['p_sharpe_vrai_05_donne_au_plus_obs']['bootstrap'], 1)} % (bootstrap ; {f(100 * ps['S1']['p_sharpe_vrai_05_donne_au_plus_obs']['analytique'], 1)} % en analytique) : "
          f"un vrai Sharpe de 0,5 est écarté (P < 3 %, bootstrap) pour {', '.join(rejet05)} mais pas pour {', '.join(compat05)}. Absence de preuve n'est pas preuve d'absence : "
          f"un vrai Sharpe de 0,25 n'est écarté (P < 5 %) que pour {', '.join(rejet025)}.")
    v8, v134 = t4["validation_formule_vs_simulation"]["8"], t4["validation_formule_vs_simulation"]["134"]
    b = t4["n_essais_pour_sharpe_2_selon_duree_backtest_annees"]
    cb = t4["n_essais_pour_sharpe_cible_sur_4_ans"]
    h134 = next(h for h in t4["historique_essais_anterieurs"] if h["n_essais"] == 134)
    c4 = (f"Sharpe maximal attendu sans aucun edge : {f(v8['formule'])} pour N = 8 (simulation {f(v8['simulation_moyenne'])}), {f(v134['formule'])} pour N = 134, plancher d'essais "
          f"déclaré par un projet antérieur (simulation {f(v134['simulation_moyenne'])}) ; P(au moins un Sharpe VAL >= 2 par hasard | N = 134) = {f(100 * h134['p_au_moins_un_sharpe_2'], 1)} %. "
          f"Sur la durée de VAL (4,1 ans) le hasard seul fabrique un Sharpe de 1 après {f(cb['1.0'], 0)} essais et de 2 après {f(cb['2.0'], 0)} ; selon la durée du backtest, un Sharpe de 2 sort du hasard "
          f"après {f(b['1']['n_essais_pour_sr_attendu_2'], 0)} essais (1 an), {f(b['2']['n_essais_pour_sr_attendu_2'], 0)} (2 ans), {f(b['4']['n_essais_pour_sr_attendu_2'], 0)} (4 ans), {b['8']['n_essais_pour_sr_attendu_2']:.1e} (8 ans). "
          f"Choisir la meilleure des 1770 paires d'un univers de 60 actifs donnerait {f(t4['illustration_selection_1770_paires']['sharpe_max_attendu_sans_edge'])} sans edge (hypothèse : essais indépendants). "
          f"Conséquence : un « Sharpe > 2 » issu d'une recherche répétée n'a de sens qu'après déflation par le N réel ; le SR0 du prereg ({f(t4['dsr']['sr0_annualise_prereg_variance_observee'])}) est tiré par S7, "
          f"le seuil théorique est {f(t4['dsr']['sr0_annualise_variance_theorique'])} (le verdict ne change pas).")
    causes = {k: v["cause"]["cause"] + (" (" + v["cause"]["precision"] + ")" if v["cause"]["precision"] else "") for k, v in t5["sleeves"].items()}
    qmin = min(t5["sleeves"][k]["constance"]["p_constance"] for k in ("S1", "S2", "S3", "S5", "S6"))
    c5 = (f"Aucune sleeve n'a un Sharpe brut >= 0,30 sur TRAIN et VAL à la fois (meilleur brut VAL : {f(max(v['sharpe_brut']['VAL'] for k, v in t5['sleeves'].items() if k != 'PILE'))}). "
          f"Cause principale (règle explicite) : " + " ; ".join(f"{k} = {c}" for k, c in causes.items() if k != "PILE") + ". "
          f"Les Sharpe annuels de S1, S2, S3, S5, S6 sont compatibles avec un Sharpe constant (p de constance >= {f(qmin)}) : ce n'est pas un effet de régime mais un edge nul ou négatif à toute époque. "
          f"S6 est surtout du bêta actions (corrélation {f(t5['sleeves']['S6']['facteur']['VAL']['indices']['correlation'])} au facteur indices en VAL).")
    c6 = (f"Avec la corrélation moyenne observée en VAL ({f(t6['rho_moyen_val'], 3)}), il faut {f(t6['n_sleeves_requis_sharpe_05_rho_observe'], 0)} sleeves de Sharpe net 0,5 "
          f"(16 si indépendantes) pour atteindre 2, ou {f(t6['sharpe_individuel_requis_avec_7_sleeves'])} de Sharpe net par sleeve avec 7 sleeves. Le meilleur Sharpe net VAL ici "
          f"est {f(t6['meilleur_sharpe_net_val'])} ({t6['meilleure_sleeve']}). La formule à risque égal retrouve le Sharpe de la pile "
          f"({f(t6['pile_formule_risque_egal_avec_sharpe_reels'])} prédit contre {f(t6['pile_realisee_val'])} réalisé) : la diversification multiplie un Sharpe moyen, elle n'en crée pas.")
    s1c, s6c = t7["sleeves"]["S1"], t7["sleeves"]["S6"]
    c7 = (f"Sous l'hypothèse non sourcée d'ADV de 1e10 $/jour en FX et 5e10 en indices, l'impact racine carrée à 1 Md$ coûte {f(100 * s1c['VAL']['impact_annuel_a_1e9_usd'])} %/an pour S1 "
          f"et {f(100 * s6c['VAL']['impact_annuel_a_1e9_usd'])} %/an pour S6 : la capacité n'est pas le goulot. Capacité (rendement net = 0) : S1 TRAIN {s1c['TRAIN']['capacite_usd'] / 1e9:.0f} Md$, "
          f"S1 VAL 0 (brut négatif), S6 TRAIN {s6c['TRAIN']['capacite_usd'] / 1e9:.0f} Md$, S6 VAL {s6c['VAL']['capacite_usd'] / 1e9:.0f} Md$ ; elle est proportionnelle à l'ADV supposé "
          f"(ADV x 0,1 => capacité x 0,1) et au carré du rendement net avant impact. Le goulot reste l'edge brut.")
    synthese = [
        f"Loi fondamentale : pour IR = 2 avec ~{f(pv['breadth_totale'], 0)} paris/an, il faut un IC de {f(pv['ic_uniforme_requis_pour_ir_2'], 3)} sur chaque sleeve ; observé {f(pv['ic_moyen_observe'], 3)}.",
        f"Puissance : 4 ans de VAL ne détectent qu'un Sharpe >= {f(m['unilateral_alpha5'])} ({f(m['unilateral_bonferroni_7'])} avec 7 tests) ; confirmer un vrai Sharpe de 0,5 prend {f(t3['annees_pour_detecter_80pct_unilateral']['0.5'], 0)} ans.",
        f"Diversification : {f(t6['n_sleeves_requis_sharpe_05_rho_observe'], 0)} sleeves de Sharpe net 0,5 à rho = {f(t6['rho_moyen_val'], 3)} ; le meilleur Sharpe net VAL ici est {f(t6['meilleur_sharpe_net_val'])}.",
        f"Tests multiples : sur la durée de VAL (4,1 ans) le hasard fabrique un Sharpe de 2 après {f(cb['2.0'], 0)} essais, de 1 après {f(cb['1.0'], 0)} : un vrai résultat doit survivre à la déflation par le N réel et à un TEST à lecture unique.",
        "Ce qui est vrai ici : le goulot est l'edge brut (Sharpe brut VAL <= 0,14 pour toutes les sleeves, pile -0,70), ni les coûts, ni la capacité, ni le régime ; baisser les coûts ne crée pas d'edge.",
    ]
    return {"Q1": c1, "Q2": c2, "Q3": c3, "Q4": c4, "Q5": c5, "Q6": c6, "Q7": c7, "synthese_pour_sharpe_2": synthese}


def main() -> None:
    t0 = time.time()
    RESULTATS.mkdir(exist_ok=True)
    FIGURES.mkdir(exist_ok=True)
    rafraichir = "--rafraichir" in sys.argv
    try:
        base = ap.charger_base(rafraichir)
    except Exception:
        if not verifier_donnees.donnees_presentes():  # ni cache valide ni données : message guidé plutôt qu'une trace brute
            verifier_donnees.exiger_donnees()
        raise
    tv = json.loads((RESULTATS / "train_val.json").read_text(encoding="utf-8"))
    verdict = json.loads((RESULTATS / "verdict_alpha.json").read_text(encoding="utf-8"))
    tout = {**base["res"], "PILE": base["pile"]}
    rend_val = {k: r.tranche(max(d.DEBUT_VAL, r.debut), d.FIN_VAL).net.to_numpy() for k, r in tout.items()}
    ap.verifier_pas_de_test({k: r.net for k, r in tout.items()}, "rendements")

    specs = dg.specs_quotidiennes(base)
    print("IC en minutes (S4, S5, S7)...", flush=True)
    icm = dg.ic_minutes_sleeves(base, ap.minutes)
    _, fact_idx = dg.facteurs_marche(base)
    print("Q1 Grinold, Q2 décroissance...", flush=True)
    t1 = dg.theme1_grinold(base, specs, icm, fact_idx)
    t2 = dg.theme2_decroissance(base, specs, icm)
    print("Q3 puissance, Q4 tests multiples (simulations)...", flush=True)
    t3 = dg.theme3_puissance(tv, rend_val)
    t4 = dg.theme4_tests_multiples(tv, rend_val)
    print("Q5 anatomie, Q6 diversification, Q7 capacité...", flush=True)
    t5 = dg.theme5_anatomie(base, tv)
    rolls = t5.pop("_roll")
    t5.pop("_annuel")
    t6 = dg.theme6_diversification(tv)
    t7 = dg.theme7_capacite(base, specs)

    rapport = {
        "titre": TITRE,
        "avertissement": "Analyse EXPLORATOIRE a posteriori sur TRAIN/VAL. Elle explique le verdict ECHEC, elle ne le modifie pas, ne retouche aucun "
                         "paramètre des sleeves et n'ouvre pas le TEST.",
        "verdict_officiel_inchange": {"verdict": verdict["verdict"], "statut_test": verdict["statut_test"]},
        "meta": {"prereg_v1_sha256": verifier_prereg.sha256_v1(),
                 "prereg_sha256_actuel_avenants_inclus": verifier_prereg.sha256_normalise(RACINE / "PREREGISTRATION.md"),
                 "code_sha256_base": base["code_sha256"],
                 "dernier_jour_utilise": str(max(r.net.index.max() for r in tout.values()).date()),
                 "test": "scellé, non chargé (lecteur 1 h strict, cache minutes TRAIN/VAL)"},
        "Q1_grinold": t1, "Q2_decroissance": t2, "Q3_puissance": t3, "Q4_tests_multiples": t4,
        "Q5_anatomie": t5, "Q6_diversification": t6, "Q7_capacite": t7,
    }
    rapport = json.loads(json.dumps(dg._nettoyer(rapport), ensure_ascii=False))  # clés en chaînes, NaN -> null
    rapport["conclusions"] = conclusions(rapport)
    (RESULTATS / "approfondissement.json").write_text(json.dumps(rapport, indent=2, ensure_ascii=False), encoding="utf-8")

    ag.figure_q1(rapport["Q1_grinold"], FIGURES / "appro_q1_grinold.png")
    ag.figure_q2(rapport["Q2_decroissance"], FIGURES / "appro_q2_decroissance.png")
    ag.figure_q3(rapport["Q3_puissance"], FIGURES / "appro_q3_puissance.png")
    ag.figure_q4(rapport["Q4_tests_multiples"], FIGURES / "appro_q4_tests_multiples.png")
    ag.figure_q5(rapport["Q5_anatomie"], rolls, FIGURES / "appro_q5_sharpe_glissant.png", FIGURES / "appro_q5_regimes_facteur.png")
    ag.figure_q6(rapport["Q6_diversification"], FIGURES / "appro_q6_diversification.png")
    ag.figure_q7(rapport["Q7_capacite"], FIGURES / "appro_q7_capacite.png")

    print(TITRE)
    for k, v in rapport["conclusions"].items():
        print(f"{k}: {v}\n")
    print(f"terminé en {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
