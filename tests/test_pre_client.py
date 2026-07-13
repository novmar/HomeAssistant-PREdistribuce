"""Testy parseru HTML z PRE.

Parser je vázaný na cizí markup, který se může změnit bez varování. Fixtures jsou
skutečné odpovědi endpointu, ne vymyšlené.
"""

from __future__ import annotations

import pytest

from parser import PreError, PreNoData, parse_nt_windows

# Povel 490, 13. 7. 2026. Všimni si posledního okna: PRE u tohoto povelu zapisuje konec
# dne jako 00:00, ne 24:00 — u povelů 485, 519 nebo 261 přitom používá 24:00.
FIXTURE_490 = """
<div class="hdo-bar">
  <span class="hdovt"></span><span class="span-overflow" title="00:00 - 00:40"></span>
  <span class="hdont"></span><span class="span-overflow" title="00:40 - 05:40"></span>
  <span class="hdovt"></span><span class="span-overflow" title="05:40 - 13:00"></span>
  <span class="hdont"></span><span class="span-overflow" title="13:00 - 16:00"></span>
  <span class="hdovt"></span><span class="span-overflow" title="16:00 - 00:00"></span>
</div>
"""

# Povel 519 — okno nízkého tarifu, které přechází přes půlnoc, zapsané jako 24:00.
FIXTURE_519 = """
<div class="hdo-bar">
  <span class="hdont"></span><span class="span-overflow" title="00:00 - 06:40"></span>
  <span class="hdovt"></span><span class="span-overflow" title="06:40 - 22:40"></span>
  <span class="hdont"></span><span class="span-overflow" title="22:40 - 24:00"></span>
</div>
"""

# Skutečná odpověď pro den, na který PRE rozvrh nemá (povel 586 ve středu).
FIXTURE_NO_DATA = (
    '\t<div class="error flash">Pro časový interval neexistují data. '
    'Data jsou k dispozici do 27.07.2026</div>\n'
)


def test_parsuje_okna_nizkeho_tarifu() -> None:
    assert parse_nt_windows(FIXTURE_490) == [(40, 340), (780, 960)]


def test_konec_00_00_znamena_pulnoc_a_ne_zacatek_dne() -> None:
    """Kdyby se 00:00 bralo doslova, vzniklo by okno (1360, 0) a tiše by zmizelo."""
    windows = parse_nt_windows(FIXTURE_519)
    assert windows == [(0, 400), (1360, 1440)]
    assert all(start < end for start, end in windows)


def test_chybejici_data_nejsou_chyba_parseru() -> None:
    with pytest.raises(PreNoData):
        parse_nt_windows(FIXTURE_NO_DATA)


def test_zmena_strankyparser_pozna() -> None:
    """Kdyby PRE stránku předělal, nesmíme tiše tvrdit, že dnes není nízký tarif."""
    with pytest.raises(PreError):
        parse_nt_windows("<div class='neco-uplne-jineho'>...</div>")


def test_prazdny_hdo_bar_je_chyba() -> None:
    """Bar bez jediného okna znamená, že jsme přestali rozumět struktuře."""
    with pytest.raises(PreError):
        parse_nt_windows('<div class="hdo-bar"></div>')
