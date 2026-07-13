"""Testy běží bez nainstalovaného Home Assistantu.

`state.py` a `pre_client.py` jsou schválně bez závislosti na HA — je v nich všechna
logika, ve které se dá tiše splést. Importují se proto přímo, ne přes balíček
`custom_components.predistribuce`, jehož `__init__` už HA potřebuje.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "custom_components" / "predistribuce"))
