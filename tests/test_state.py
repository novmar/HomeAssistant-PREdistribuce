"""Testy výpočtu stavu tarifu.

Tohle je místo, kde se dá tiše splést a účtovat špatnou cenu — chyba se neprojeví
výjimkou, jen špatným číslem. Proto sem míří většina testů.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from state import compute_state

PRAHA = ZoneInfo("Europe/Prague")

# Skutečný rozvrh povelu 490 (D25d, PREdistribuce).
DEN = [(40, 340), (780, 960)]  # 00:40–05:40, 13:00–16:00


def at(hour: int, minute: int = 0, day: int = 13) -> datetime:
    return datetime(2026, 7, day, hour, minute, tzinfo=PRAHA)


@pytest.mark.parametrize(
    ("now", "is_nt", "to_nt", "to_vt"),
    [
        (at(2, 0), True, 0, 220),  # uvnitř nočního okna
        (at(10, 0), False, 180, 0),  # mezi okny
        (at(13, 0), True, 0, 180),  # přesně na začátku okna
        (at(16, 0), False, 520, 0),  # přesně na konci okna už NT neběží
        (at(23, 0), False, 100, 0),  # poslední okno dne skončilo, další je zítra
    ],
)
def test_zakladni_stavy(now: datetime, is_nt: bool, to_nt: int, to_vt: int) -> None:
    state = compute_state(DEN, DEN, now)
    assert state.is_nt is is_nt
    assert state.minutes_to_nt == to_nt
    assert state.minutes_to_vt == to_vt


def test_okno_pres_pulnoc_se_pocita_vcelku() -> None:
    """Okno 22:00–24:00 dnes a 00:00–06:00 zítra je ve skutečnosti jedno okno.

    Bez spojení bychom ve 23:30 hlásili, že nízký tarif za 30 minut skončí — přitom
    poběží ještě šest a půl hodiny.
    """
    dnes = [(22 * 60, 24 * 60)]
    zitra = [(0, 6 * 60)]
    state = compute_state(dnes, zitra, at(23, 30))
    assert state.is_nt is True
    assert state.minutes_to_vt == 390  # 30 minut do půlnoci + 6 hodin


def test_konec_ve_24_00_je_platny() -> None:
    """PRE zapisuje konec dne jako 24:00 (a u některých povelů jako 00:00 → 1440)."""
    state = compute_state([(23 * 60, 24 * 60)], [], at(23, 50))
    assert state.is_nt is True
    assert state.minutes_to_vt == 10


def test_den_bez_nizkeho_tarifu() -> None:
    """Den bez jediného okna je legitimní (např. povel 586 ve všední den)."""
    state = compute_state([], [], at(12, 0))
    assert state.is_nt is False
    assert state.minutes_to_nt is None  # není kam se dívat
    assert state.minutes_to_vt == 0


def test_chybejici_zitrek_neshodi_dnesek() -> None:
    """Zítřek je nepovinný — bez něj se prostě nepočítá přes půlnoc."""
    state = compute_state(DEN, [], at(2, 0))
    assert state.is_nt is True
    assert state.minutes_to_vt == 220


def test_prechod_na_zimni_cas() -> None:
    """V noci na 25. 10. 2026 se hodina 02:00–03:00 opakuje.

    Okno 01:00–05:00 wall-clock tedy reálně trvá 5 hodin, ne 4. Kdybychom počítali
    v ciferníkových minutách, spletli bychom se o hodinu.
    """
    zmena = datetime(2026, 10, 25, 1, 0, tzinfo=PRAHA)
    state = compute_state([(60, 300)], [], zmena)
    assert state.is_nt is True
    assert state.minutes_to_vt == 300  # 5 skutečných hodin, ne 4
