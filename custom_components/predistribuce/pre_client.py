"""HTTP klient k webu PREdistribuce.

PRE nemá veřejné API. Stránka se stavem HDO si data dotahuje AJAXem z endpointu, který
nevyžaduje přihlášení ani CSRF token — voláme tedy přímo ten. Samotné rozumění odpovědi
je v `parser.py`.
"""

from __future__ import annotations

import logging
from datetime import date

import aiohttp

from .const import HDO_AJAX, HDO_PAGE
from .parser import PreError, Window, parse_nt_windows, parse_povel_list

_LOGGER = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Home Assistant PREdistribuce integration)",
}


class PreClient:
    """Stahuje HDO rozvrhy z webu PREdistribuce."""

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

        return parse_povel_list(page)

    async def async_get_nt_windows(self, povel: str, den: date) -> list[Window]:
        """Vrátí okna nízkého tarifu pro daný den."""
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
        if html is None:
            raise PreError("Odpověď PRE neobsahuje očekávaný HTML blok.")

        return parse_nt_windows(html, povel=povel, den=den)
