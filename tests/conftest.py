import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def prix_synthetiques(colonnes, n=1300, graine=0, debut="2012-01-02"):
    """Marches aléatoires multiplicatives sur jours ouvrés (vol ~0,6 %/jour)."""
    rng = np.random.default_rng(graine)
    idx = pd.bdate_range(debut, periods=n)
    rend = rng.normal(0.0002, 0.006, size=(n, len(colonnes)))
    return pd.DataFrame(100 * np.exp(np.cumsum(rend, axis=0)), index=idx, columns=list(colonnes))


@pytest.fixture
def fabrique_prix():
    return prix_synthetiques
