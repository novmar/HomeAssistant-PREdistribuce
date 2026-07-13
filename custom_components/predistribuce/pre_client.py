"""Klient pro HDO rozvrhy PREdistribuce.

PRE nemá veřejné API. Stránka se stavem HDO si data dotahuje AJAXem z endpointu, který
nevyžaduje přihlášení ani CSRF token — voláme tedy přímo ten. Vrací kus HTML, ve kterém
jsou okna zakódovaná dvojicí sousedních <span>: první nese třídu (hdont = nízký tarif,
hdovt = vysoký), druhý má v atributu title časový rozsah.

Endpoint je nezdokumentovaný a může se kdykoli změnit. Proto se při jakékoli odchylce
raději tváříme jako nedostupní (vyhodíme PreError), než abychom tipovali tarif — špatná
cena by se totiž tvářila jako správná.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import aiohttp

from .const import HDO_AJAX, HDO_PAGE

_LOGGER = logging.getLogger(__name__)

# Třída okna a jeho čas jsou ve dvou po sobě jdoucích <span>, ne v jednom.
_SPAN_RE = re.compile(
    r'class="(hdont|hdovt|span-overflow)"'
    r'(?:[^>]*title="(\d\d:\d\d) - (\d\d:\d\d)")?'
)
_OPTION_RE = re.compile(r'<option[^>]*value="(\d{3})"[^>]*>(.*?)</option>', re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Home Assistant PREdistribuce integration)",
}


class PreError(Exception):
    """Rozvrh HDO se nepodařilo získat nebo mu nerozumíme."""


def _to_minutes(value: str) -> int:
    return int(value[:2]) * 60 + int(value[3:])


class PreClient:
    """Stahuje a parsuje HDO rozvrhy z webu PREdistribuce."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def async_get_povel_list(self) -> dict[str, str]:
        """Vrátí nabídku povelů jako {kód: popis} pro výběr v config flow."""
        try:
            async with self._session.get(
                HDO_PAGE, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                resp.raise_for_status()
                page = await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise PreError(f"Nepodařilo se načíst seznam povelů: {err}") from err

        povely = {
            code: re.sub(r"\s+", " ", _TAG_RE.sub("", label)).strip()
            for code, label in _OPTION_RE.findall(page)
        }
        if not povely:
            raise PreError("Na stránce PRE nejsou žádné povely — změnila se struktura?")
        return povely

    async def async_get_nt_windows(self, povel: str, den: date) -> list[tuple[int, int]]:
        """Vrátí okna nízkého tarifu pro daný den jako [(začátek, konec)] v minutách od půlnoci."""
        payload = {
            "datum": den.strftime("%d.%m.%Y"),
            "povel": povel,
            "povelTitle": povel,
        }
        try:
            async with self._session.post(
                HDO_AJAX,
                data=payload,
                # Bez této hlavičky endpoint neodpoví JSONem. Naopak na HDO_PAGE se
                # posílat nesmí, jinak stránka vrátí jinou (AJAXovou) variantu bez <option>.
                headers={**HEADERS, "X-Requested-With": "XMLHttpRequest"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                resp.raise_for_status()
                body = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise PreError(f"Nepodařilo se stáhnout rozvrh HDO: {err}") from err

        html = body.get("html") if isinstance(body, dict) else None
        if not html:
            raise PreError("Odpověď PRE neobsahuje očekávaný HTML blok.")

        windows: list[tuple[int, int]] = []
        pending: str | None = None
        for css_class, start, end in _SPAN_RE.findall(html):
            if css_class in ("hdont", "hdovt"):
                pending = css_class
            elif css_class == "span-overflow" and start and pending:
                if pending == "hdont":
                    windows.append((_to_minutes(start), _to_minutes(end)))
                pending = None

        if not windows:
            raise PreError(
                f"V rozvrhu povelu {povel} pro {den} nejsou žádná okna nízkého tarifu."
            )
        return sorted(windows)
