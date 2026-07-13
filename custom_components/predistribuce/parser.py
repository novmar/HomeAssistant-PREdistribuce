"""Parsování odpovědí z webu PREdistribuce.

Bez závislostí — ani na Home Assistantu, ani na HTTP klientovi. Je to jediné místo,
které rozumí cizímu markupu, a ten se může kdykoli změnit, takže patří pod testy.

Rozlišujeme tři situace:

* rozvrh dorazil a rozumíme mu   → vrátíme okna (klidně prázdný seznam)
* PRE hlásí, že pro daný den data nemá → PreNoData
* odpověď nevypadá jako rozvrh   → PreError

Ten rozdíl je zásadní: chybějící data jsou normální stav, kdežto nesrozumitelná odpověď
znamená, že se web změnil a nesmíme z ní nic dovozovat. Tiše tvrdit „dnes není nízký
tarif" by znamenalo účtovat vysokou sazbu, aniž by cokoli vypadalo rozbitě.
"""

from __future__ import annotations

import re

MINUTES_PER_DAY = 24 * 60

Window = tuple[int, int]
"""Okno nízkého tarifu jako (začátek, konec) v minutách od půlnoci. Konec smí být 1440."""

# Třída okna a jeho čas jsou ve dvou po sobě jdoucích <span>, ne v jednom.
_SPAN_RE = re.compile(
    r'class="(hdont|hdovt|span-overflow)"'
    r'(?:[^>]*title="(\d\d:\d\d) - (\d\d:\d\d)")?'
)
_OPTION_RE = re.compile(r'<option[^>]*value="(\d{3})"[^>]*>(.*?)</option>', re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


class PreError(Exception):
    """Odpovědi z PRE nerozumíme — nesmíme z ní nic dovozovat."""


class PreNoData(PreError):
    """PRE pro daný den rozvrh nemá. Legitimní stav, ne chyba."""


def _to_minutes(value: str, *, is_end: bool) -> int:
    """Převede 'HH:MM' na minuty od půlnoci.

    PRE je v zápisu konce dne nekonzistentní: většina povelů vrací 24:00, ale některé
    (např. 490) vracejí 00:00. Bez tohohle převodu by okno 22:40–00:00 vyšlo jako
    (1360, 0), tedy start > end, podmínka „jsme uvnitř okna" by nikdy neplatila
    a noční nízký tarif by tiše zmizel.
    """
    minutes = int(value[:2]) * 60 + int(value[3:])
    if is_end and minutes == 0:
        return MINUTES_PER_DAY
    return minutes


def parse_povel_list(page: str) -> dict[str, str]:
    """Vytáhne nabídku povelů ze stránky se stavem HDO."""
    povely = {
        code: re.sub(r"\s+", " ", _TAG_RE.sub("", label)).strip()
        for code, label in _OPTION_RE.findall(page)
    }
    if not povely:
        raise PreError("Na stránce PRE nejsou žádné povely — změnila se struktura?")
    return povely


def parse_nt_windows(html: str, *, povel: str = "?", den: object = "?") -> list[Window]:
    """Vytáhne okna nízkého tarifu z HTML fragmentu.

    Prázdný seznam je platná odpověď — znamená den, kdy nízký tarif vůbec neběží
    (třeba povel 586, který spíná jen o víkendu).
    """
    if "error flash" in html or "neexistují data" in html:
        raise PreNoData(f"PRE nemá rozvrh povelu {povel} pro {den}.")

    if "hdo-bar" not in html:
        raise PreError(
            f"Odpověď PRE pro povel {povel} nevypadá jako rozvrh HDO — změnila se stránka?"
        )

    windows: list[Window] = []
    seen_any_span = False
    pending: str | None = None
    for css_class, start, end in _SPAN_RE.findall(html):
        if css_class in ("hdont", "hdovt"):
            pending = css_class
            seen_any_span = True
        elif css_class == "span-overflow" and start and pending:
            if pending == "hdont":
                windows.append(
                    (_to_minutes(start, is_end=False), _to_minutes(end, is_end=True))
                )
            pending = None

    if not seen_any_span:
        raise PreError(
            f"V rozvrhu povelu {povel} nejsou žádná okna — změnila se struktura stránky?"
        )

    # Oknu, kterému nerozumíme, se raději postavíme čelem, než abychom s ním počítali.
    for start, end in windows:
        if not 0 <= start < end <= MINUTES_PER_DAY:
            raise PreError(
                f"Rozvrh povelu {povel} obsahuje nesmyslné okno {start}–{end} minut."
            )

    return sorted(windows)
