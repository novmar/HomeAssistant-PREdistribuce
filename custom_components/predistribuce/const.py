"""Konstanty integrace PREdistribuce."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "predistribuce"

CONF_POVEL = "povel"
CONF_CENA_VT = "cena_vt"
CONF_CENA_NT = "cena_nt"
CONF_POWER_SENSOR = "power_sensor"
CONF_PERIODS = "periods"

DEFAULT_CENA_VT = 5.27
DEFAULT_CENA_NT = 3.48

# Rozvrh se pro daný den nemění, ale stav VT/NT ano — proto přepočítáváme každou minutu
# a stránku staháme jen když se změní den (viz PreHdoCoordinator).
UPDATE_INTERVAL = timedelta(minutes=1)

HDO_PAGE = "https://www.predistribuce.cz/cs/potrebuji-zaridit/zakaznici/stav-hdo/"
HDO_AJAX = "https://www.predistribuce.cz/com/PREdi/UI/Forms/Hdo/HdoForm:hdoOneDayAjax"
