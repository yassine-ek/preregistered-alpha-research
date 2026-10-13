"""Les 7 sleeves du prereg (section 5). Paramètres FIGÉS, aucune grille.

Chaque fonction renvoie des POIDS datés (fraction du capital en notionnel, signé), calculés
uniquement avec des données <= la date de la ligne :
 - sleeves quotidiennes (S1, S2, S3, S6) : poids DÉCIDÉ au jour J avec les prix <= instantané J.
   Le moteur applique ensuite l'exécution à J+1 et le gain J+1 -> J+2.
 - sleeves intrajournalières (S4, S5, S7) : poids du jour J pour la fenêtre du jour J ; le
   risque utilisé ne voit que les fenêtres des jours < J (décalage de 1 ligne).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from . import risque

# ------------------------------------------------------------------ paramètres figés
VITESSES_S1 = [(16, 64), (32, 128), (64, 256)]
ECHELLES_S1 = [3.75, 2.65, 1.87]          # échelles de prévision de Carver
PLAFOND_PREVISION = 20.0
TAMPON_S1 = 0.10                          # tampon de rebalancement = 10 % de la position moyenne
SIGMA_MIN_QUOTIDIEN = 0.01 / np.sqrt(252)  # plancher de vol annuelle 1 % pour dimensionner

# devise -> (paire, +1 si la paire est DEVISExUSD, -1 si USDxDEVISE)
DEVISES = {
    "EUR": ("EURUSD", +1), "GBP": ("GBPUSD", +1), "AUD": ("AUDUSD", +1), "NZD": ("NZDUSD", +1),
    "CAD": ("USDCAD", -1), "CHF": ("USDCHF", -1), "JPY": ("USDJPY", -1),
    "NOK": ("USDNOK", -1), "SEK": ("USDSEK", -1),
}
HORIZON_S2 = 63
HORIZON_S3 = 5
N_COTE = 3  # 3 longs et 3 shorts

# S4 : (paire, direction), fenêtre = devise étrangère vendue contre USD pendant SA session
S4_LONDRES = {"EURUSD": -1, "GBPUSD": -1, "USDCHF": +1}   # fenêtre 08h-14h Europe/London
S4_TOKYO = {"USDJPY": +1, "AUDUSD": -1, "NZDUSD": -1}      # fenêtre 09h-15h Asia/Tokyo
# S5 : paire -> (direction « acheter la devise contre USD », indice étranger)
S5_PAIRES = {"EURUSD": (+1, "FRXEUR"), "GBPUSD": (+1, "UKXGBP"), "USDJPY": (-1, "JPXJPY"), "AUDUSD": (+1, "AUXAUD")}
S5_INDICE_US = "SPXUSD"
# S6
INDICES_S6 = ["SPXUSD", "NSXUSD", "UKXGBP", "JPXJPY", "FRXEUR", "HKXHKD", "AUXAUD"]
LEVIER_MAX_S6 = 2.0


# --------------------------------------------------------------------- utilitaires
def rendements_et_signal(prix: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(prix de signal, rendements). Signal : report du dernier prix connu, 3 jours max.
    Rendements : un jour sans prix vaut 0 ; au retour du prix le rendement rattrape l'écart
    (le PnL total est conservé, il n'est ni créé ni perdu)."""
    p_sig = prix.ffill(limit=3)
    rend = prix.ffill().pct_change(fill_method=None)
    return p_sig, rend


def dernier_jour_ouvre_du_mois(jours: pd.DatetimeIndex) -> np.ndarray:
    """Vrai si le jour est le dernier jour ouvré (lundi-vendredi) de son mois. Règle de
    CALENDRIER : elle ne regarde pas les données, donc un historique tronqué ne crée pas
    de faux « fin de mois »."""
    return np.asarray((jours + pd.offsets.BMonthEnd(0)) == jours)


def appliquer_tampon(cible: pd.DataFrame, unite: pd.DataFrame, frac: float = TAMPON_S1) -> pd.DataFrame:
    """Tampon de non-trading (Carver) : on ne bouge que si la position courante sort de
    [cible - tampon ; cible + tampon], et alors on revient au bord le plus proche.
    tampon = frac * |position à prévision 10| (= la taille unitaire). Cela réduit la
    rotation sans retarder les vrais changements de tendance."""
    c = cible.to_numpy()
    u = unite.to_numpy()
    sortie = np.zeros_like(c)
    courant = np.zeros(c.shape[1])
    for t in range(len(c)):
        tampon = frac * np.abs(u[t])
        nouveau = np.clip(courant, c[t] - tampon, c[t] + tampon)
        nouveau = np.where(u[t] == 0, 0.0, nouveau)  # actif sans signal valide -> à plat
        sortie[t] = nouveau
        courant = nouveau
    return pd.DataFrame(sortie, index=cible.index, columns=cible.columns)


# ------------------------------------------------------------------------------ S1
def previsions_ewmac(prix: pd.DataFrame) -> pd.DataFrame:
    """Prévision moyenne (échelle ~±10) = moyenne de 3 EWMAC normalisés par la vol des
    variations de prix, chacun mis à l'échelle de Carver puis plafonné à ±20."""
    p_sig = prix.ffill(limit=3)
    vol_prix = risque.vol_ewma(p_sig.diff())
    morceaux = []
    for (rapide, lente), echelle in zip(VITESSES_S1, ECHELLES_S1):
        ema_r = p_sig.ewm(span=rapide, adjust=False, min_periods=rapide).mean()
        ema_l = p_sig.ewm(span=lente, adjust=False, min_periods=lente).mean()
        f = ((ema_r - ema_l) / vol_prix * echelle).clip(-PLAFOND_PREVISION, PLAFOND_PREVISION)
        morceaux.append(f)
    # la moyenne n'existe que si les trois prévisions existent (NaN sinon)
    moyenne = sum(morceaux) / len(morceaux)
    return moyenne.where(p_sig.notna())


def sleeve_s1(prix: pd.DataFrame) -> pd.DataFrame:
    """S1 : trend following EWMAC sur tous les actifs non exclus."""
    _, rend = rendements_et_signal(prix)
    signal = previsions_ewmac(prix) / 10.0  # position ∝ prévision/10
    cible, unite = risque.poids_vol_cible(signal, rend, jours_actifs_par_an=252, sigma_min=SIGMA_MIN_QUOTIDIEN)
    return appliquer_tampon(cible, unite, TAMPON_S1)


# ---------------------------------------------------------------------- S2 et S3
def valeurs_devises(prix: pd.DataFrame) -> pd.DataFrame:
    """Valeur de chaque devise en USD (1/P si la paire est USDxDEVISE)."""
    cols = {}
    for dev, (paire, signe) in DEVISES.items():
        cols[dev] = prix[paire] if signe > 0 else 1.0 / prix[paire]
    return pd.DataFrame(cols)


def _long_court_vendredi(score: pd.DataFrame, rend: pd.DataFrame) -> pd.DataFrame:
    """Chaque vendredi : long les 3 plus hauts scores, short les 3 plus bas. Dans chaque
    jambe le risque est égal (poids ∝ 1/sigma) ; chaque jambe pèse 0,5 en brut, donc la
    somme des poids est NULLE (neutre au dollar). Puis un facteur unique k ramène la vol
    ex ante à 10 %. Les poids restent constants jusqu'au vendredi suivant."""
    cov, nobs = risque.covariance_ewma(rend)
    sigma = np.sqrt(np.einsum("tii->ti", cov))
    sigma_eff = np.maximum(sigma, SIGMA_MIN_QUOTIDIEN)
    s = score.to_numpy()
    T, N = s.shape
    poids = np.full((T, N), np.nan)
    for t in range(T):
        if score.index[t].dayofweek != 4:
            continue
        if not (np.isfinite(s[t]).all() and (nobs[t] >= risque.MIN_OBS).all() and (sigma[t] > 0).all()):
            poids[t] = 0.0
            continue
        ordre = np.argsort(s[t], kind="stable")
        courts, longs = ordre[:N_COTE], ordre[-N_COTE:]
        w = np.zeros(N)
        inv = 1.0 / sigma_eff[t]
        w[longs] = 0.5 * inv[longs] / inv[longs].sum()
        w[courts] = -0.5 * inv[courts] / inv[courts].sum()
        var_annuelle = 252 * w @ cov[t] @ w
        k = risque.CIBLE_VOL / np.sqrt(var_annuelle) if var_annuelle > 0 else 0.0
        poids[t] = k * w
    out = pd.DataFrame(poids, index=score.index, columns=score.columns)
    return out.ffill().fillna(0.0)


def sleeve_s2(prix: pd.DataFrame) -> pd.DataFrame:
    """S2 : momentum cross-sectionnel devises (rendement 63 j, long les 3 meilleures)."""
    val = valeurs_devises(prix)
    v_sig = val.ffill(limit=3)
    rend = val.ffill().pct_change(fill_method=None)
    score = v_sig / v_sig.shift(HORIZON_S2) - 1.0
    return _long_court_vendredi(score, rend)


def sleeve_s3(prix: pd.DataFrame) -> pd.DataFrame:
    """S3 : retournement court terme (rendement 5 j, long les 3 pires)."""
    val = valeurs_devises(prix)
    v_sig = val.ffill(limit=3)
    rend = val.ffill().pct_change(fill_method=None)
    score = -(v_sig / v_sig.shift(HORIZON_S3) - 1.0)  # signe moins : on achète les perdants
    return _long_court_vendredi(score, rend)


# ------------------------------------------------------------------------------ S4
def sleeve_s4(fen: pd.DataFrame) -> pd.DataFrame:
    """S4 : saisonnalité intrajournalière. `fen` = rendements open->open des fenêtres de
    chaque paire (colonnes = les 6 paires ; index = date locale). On est vendeur de la
    devise étrangère pendant sa session, à plat le reste du temps (donc 2 jambes/jour/paire).
    Vol visée : somme des variances de la session Londres et de la session Tokyo (leurs
    fenêtres ne se chevauchent pas, covariance croisée nulle)."""
    directions = {**S4_LONDRES, **S4_TOKYO}
    signal = pd.DataFrame({a: float(d) for a, d in directions.items()}, index=fen.index)
    poids, _ = risque.poids_vol_cible(signal, fen[list(directions)], jours_actifs_par_an=252,
                                      groupes=[list(S4_LONDRES), list(S4_TOKYO)], decalage=1)
    return poids


# ------------------------------------------------------------------------------ S5
def signal_s5(px06: pd.DataFrame) -> pd.DataFrame:
    """Signal de fin de mois (par paire) : +1 = acheter la devise contre USD (l'indice US
    a surperformé l'indice étranger depuis le début du mois), -1 sinon. Défini UNIQUEMENT le
    dernier jour ouvré du mois, NaN ailleurs. `px06` : prix des indices à 06h00 EST."""
    jours = px06.index
    mois = jours.to_period("M")
    premier = px06.groupby(mois).transform("first")
    # 'first' saute les NaN : si le 1er jour est manquant on prend le premier prix connu du mois
    perf = px06 / premier - 1.0
    est_dernier = dernier_jour_ouvre_du_mois(jours)
    sortie = pd.DataFrame(np.nan, index=jours, columns=list(S5_PAIRES))
    for paire, (direction, indice) in S5_PAIRES.items():
        us = perf[S5_INDICE_US]
        etr = perf[indice]
        s = np.where(us > etr, 1.0, -1.0)  # >: les nuls (rares) tombent du côté « acheter USD »
        s = np.where(us.notna() & etr.notna(), s, np.nan)
        sortie[paire] = np.where(est_dernier, s * direction, np.nan)
    return sortie


def sleeve_s5(fen: pd.DataFrame, px06: pd.DataFrame) -> pd.DataFrame:
    """S5 : fixing de fin de mois, 06h00->10h00 EST. 12 jours actifs par an : la vol annuelle
    ex ante vaut 12 x variance d'une fenêtre (la variance est estimée sur TOUS les jours)."""
    paires = list(S5_PAIRES)
    signal = signal_s5(px06).reindex(fen.index)
    poids, _ = risque.poids_vol_cible(signal[paires], fen[paires], jours_actifs_par_an=12, decalage=1)
    return poids


# ------------------------------------------------------------------------------ S6
def _poids_mensuels(prix: pd.DataFrame, c: float) -> pd.DataFrame:
    p, rend = rendements_et_signal(prix)
    mois = rend.index.to_period("M")
    n_valides = rend.notna().groupby(mois).sum()
    rv = (rend ** 2).groupby(mois).mean() * 252      # variance réalisée annualisée du mois
    rv = rv.where((n_valides >= 10) & (rv > 0))      # au moins 10 jours valides dans le mois
    with np.errstate(divide="ignore", invalid="ignore"):
        levier = np.minimum(c / rv, LEVIER_MAX_S6)   # poids = c / variance, plafonné à 2
    n_actifs = levier.notna().sum(axis=1)
    poids_mois = levier.div(n_actifs.replace(0, np.nan), axis=0)  # équipondéré entre indices dispo
    # décision au DERNIER jour ouvré du mois M avec la variance du mois M, valable pour M+1
    idx = rend.index
    est_dernier = dernier_jour_ouvre_du_mois(idx)
    sortie = pd.DataFrame(np.nan, index=idx, columns=rend.columns)
    lignes = poids_mois.reindex(mois).to_numpy()
    sortie.loc[est_dernier] = lignes[est_dernier]
    return sortie.ffill().fillna(0.0)


def sleeve_s6(prix: pd.DataFrame, c: float) -> pd.DataFrame:
    """S6 : exposition actions gérée par la volatilité (Moreira-Muir), long seulement."""
    return _poids_mensuels(prix[INDICES_S6], c)


def calibrer_c_s6(prix_train: pd.DataFrame, cible: float = risque.CIBLE_VOL) -> float:
    """Trouve c tel que la vol annualisée réalisée de S6 sur TRAIN soit 10 %.
    c est une CONSTANTE calibrée sur TRAIN seul, puis figée pour VAL et TEST."""
    from . import moteur  # import local : moteur n'importe pas sleeves

    px = prix_train[INDICES_S6]
    _, rend = rendements_et_signal(px)

    def vol_realisee(c: float) -> float:
        w = _poids_mensuels(px, c)
        brut = moteur.rendement_brut_quotidien(w, rend)
        actif = brut.index[(w.shift(2).abs().sum(axis=1) > 0).to_numpy()]
        return brut.loc[actif[0]:].std() * np.sqrt(252)

    return float(brentq(lambda c: vol_realisee(c) - cible, 1e-5, 5.0, xtol=1e-9))


# ------------------------------------------------------------------------------ S7
def sleeve_s7(fen_spx: pd.Series, rendement_matin: pd.Series) -> pd.DataFrame:
    """S7 : momentum intrajournalier de l'indice US. On suit le signe du rendement
    veille-16h00 -> 10h00 ET pendant la dernière demi-heure."""
    idx = fen_spx.index
    signal = pd.DataFrame({"SPXUSD": np.sign(rendement_matin.reindex(idx))})
    signal = signal.replace(0.0, np.nan)
    poids, _ = risque.poids_vol_cible(signal, fen_spx.to_frame("SPXUSD"), jours_actifs_par_an=252, decalage=1)
    return poids
