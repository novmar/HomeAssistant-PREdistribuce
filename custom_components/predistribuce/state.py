"""Výpočet stavu tarifu z rozvrhu.

Čistá funkce bez vazby na Home Assistant, aby šla otestovat — je to místo, kde se dá
nejsnáz tiše splést a účtovat špatný tarif.

Okna z PRE jsou ve wall-clock minutách od půlnoci. Převádíme je na konkrétní okamžiky
v místní zóně, takže:

* zbývající čas je skutečná doba, ne rozdíl ciferníkových minut (jinak by byl dvakrát
  ročně o hodinu vedle kvůli přechodu na letní/zimní čas),
* okno přecházející přes půlnoc se počítá vcelku.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone, tzinfo

Window = tuple[int, int]
"""Okno nízkého tarifu jako (začátek, konec) v minutách od půlnoci. Konec smí být 1440.

Záměrně nesdílíme typ s parser.py: tenhle modul musí zůstat bez jediného importu z okolí,
aby šla logika testovat bez Home Assistantu i bez sítě.
"""



@dataclass(frozen=True)
class HdoState:
    """Stav HDO v daném okamžiku."""

    is_nt: bool
    minutes_to_nt: int | None
    """Za kolik minut začne nízký tarif. 0 pokud už běží, None pokud v dohledu není."""
    minutes_to_vt: int | None
    """Za kolik minut nízký tarif skončí. 0 pokud neběží."""
    windows_today: list[Window]


def _at(day: date, minutes: int, tz: tzinfo) -> datetime:
    """Wall-clock minuta daného dne jako okamžik v místní zóně. 1440 = půlnoc dalšího dne."""
    naive = datetime.combine(day, time.min) + timedelta(minutes=minutes)
    return naive.replace(tzinfo=tz)


def compute_state(
    today_windows: list[Window],
    tomorrow_windows: list[Window],
    now: datetime,
) -> HdoState:
    """Spočítá stav tarifu. `now` musí být aware datetime v místní zóně."""
    tz = now.tzinfo
    assert tz is not None, "compute_state vyžaduje aware datetime"

    today = now.date()
    tomorrow = today + timedelta(days=1)

    spans = [(_at(today, s, tz), _at(today, e, tz)) for s, e in today_windows]
    spans += [(_at(tomorrow, s, tz), _at(tomorrow, e, tz)) for s, e in tomorrow_windows]
    spans.sort()

    # Okno, které končí o půlnoci a zítra hned pokračuje, je ve skutečnosti jedno okno.
    # Bez spojení bychom o půlnoci hlásili konec nízkého tarifu, i když běží dál.
    merged: list[tuple[datetime, datetime]] = []
    for start, end in spans:
        if merged and merged[-1][1] == start:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))

    def _minutes_until(moment: datetime) -> int:
        """Skutečný počet minut do daného okamžiku.

        Pozor: odečtení dvou aware datetime ve *stejné* zóně počítá Python ciferníkově,
        ne reálně — 05:00 minus 01:00 vyjde 4 hodiny i v noci, kdy se hodina opakuje
        a reálně uplyne 5 hodin. Proto se převádí na UTC, kde žádné přeskoky nejsou.
        """
        delta = moment.astimezone(timezone.utc) - now.astimezone(timezone.utc)
        return max(0, math.ceil(delta.total_seconds() / 60))

    for start, end in merged:
        if start <= now < end:
            return HdoState(
                is_nt=True,
                minutes_to_nt=0,
                minutes_to_vt=_minutes_until(end),
                windows_today=today_windows,
            )

    upcoming = [start for start, _ in merged if start > now]
    return HdoState(
        is_nt=False,
        minutes_to_nt=_minutes_until(min(upcoming)) if upcoming else None,
        minutes_to_vt=0,
        windows_today=today_windows,
    )
