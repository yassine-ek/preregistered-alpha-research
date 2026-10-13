"""Moteur : poids -> rendements nets quotidiens (exécution décalée, coûts réels).

Convention d'horloge (prereg, section 4) pour les sleeves quotidiennes, avec w[t] le
poids décidé à l'instantané t (données <= t) :
    position détenue après l'instantané t        e[t] = w[t-1]      (exécution à J+1)
    rendement brut gagné au jour t               e[t-1] . R[t]      (de J+1 à J+2)
    coût payé au jour t (au prix de l'instantané) c . |e[t] - e[t-1]|
Aucune position ne gagne jamais un rendement qui précède son exécution.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Resultat:
    """Série quotidienne d'une sleeve (fractions du capital)."""
    nom: str
    brut: pd.Series       # rendement avant coûts
    cout: pd.Series       # coûts de transaction payés (>= 0)
    rotation: pd.Series   # sum |delta position| du jour, en multiples du capital
    debut: pd.Timestamp   # premier jour avec une position détenue

    @property
    def net(self) -> pd.Series:
        return self.brut - self.cout

    def tranche(self, debut: pd.Timestamp, fin: pd.Timestamp) -> "Resultat":
        s = slice(debut, fin)
        return Resultat(self.nom, self.brut.loc[s], self.cout.loc[s], self.rotation.loc[s], self.debut)


def rendement_brut_quotidien(poids: pd.DataFrame, rend: pd.DataFrame) -> pd.Series:
    """Rendement brut d'une sleeve quotidienne (sans coûts). Sert aussi à calibrer S6."""
    detenu = poids.fillna(0.0).shift(1).fillna(0.0)
    return (detenu.shift(1).fillna(0.0) * rend.reindex_like(detenu).fillna(0.0)).sum(axis=1)


def resultat_quotidien(nom: str, poids: pd.DataFrame, rend: pd.DataFrame, couts_bps: pd.Series) -> Resultat:
    """Sleeve quotidienne -> Resultat. `couts_bps` indexé par les colonnes de `poids`."""
    poids = poids.fillna(0.0)
    rend = rend.reindex(index=poids.index, columns=poids.columns)
    c = couts_bps.reindex(poids.columns).to_numpy() / 1e4
    detenu = poids.shift(1).fillna(0.0)                       # exécuté à J+1
    brut = (detenu.shift(1).fillna(0.0) * rend.fillna(0.0)).sum(axis=1)
    delta = detenu.diff().fillna(detenu).abs()
    cout = (delta * c).sum(axis=1)
    rotation = delta.sum(axis=1)
    actif = detenu.shift(1).fillna(0.0).abs().sum(axis=1) > 0
    debut = actif.index[actif.to_numpy()][0] if actif.any() else poids.index[-1]
    return Resultat(nom, brut, cout, rotation, debut)


def resultat_intrajournalier(nom: str, poids: pd.DataFrame, ret_fenetre: pd.DataFrame,
                             date_pnl: pd.DataFrame, couts_bps: pd.Series,
                             calendrier: pd.DatetimeIndex) -> Resultat:
    """Sleeve intrajournalière -> Resultat quotidien.

    Un trade = ouverture + fermeture dans la journée : 2 jambes, donc coût
    2 x c x |poids|. Si le prix d'entrée ou de sortie manque (rendement NaN), le trade n'a
    pas lieu : ni gain, ni coût. Le PnL est daté du jour comptable de sa sortie
    (cf. donnees.date_comptable). Un poids nul ne coûte rien."""
    cols = list(poids.columns)
    c = couts_bps.reindex(cols).to_numpy() / 1e4
    w = poids.reindex(columns=cols).fillna(0.0).to_numpy()
    r = ret_fenetre.reindex(index=poids.index, columns=cols).to_numpy()
    d = date_pnl.reindex(index=poids.index, columns=cols)
    trade = (w != 0) & np.isfinite(r)
    brut_t = np.where(trade, w * np.where(np.isfinite(r), r, 0.0), 0.0)
    cout_t = np.where(trade, 2.0 * np.abs(w) * c[None, :], 0.0)
    rot_t = np.where(trade, 2.0 * np.abs(w), 0.0)
    dates = pd.DatetimeIndex(d.to_numpy().ravel())
    longs = pd.DataFrame({"brut": brut_t.ravel(), "cout": cout_t.ravel(), "rot": rot_t.ravel()}, index=dates)
    longs = longs[longs.index.notna()]
    agg = longs.groupby(level=0).sum().reindex(calendrier).fillna(0.0)
    actif = np.where(trade.any(axis=1))[0]
    premier = d.to_numpy()[actif[0]][np.where(trade[actif[0]])[0][0]] if len(actif) else calendrier[-1]
    return Resultat(nom, agg["brut"], agg["cout"], agg["rot"], pd.Timestamp(premier))
