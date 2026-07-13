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

# Stav VT/NT se mění v celých minutách, rozvrh sám ale jen jednou denně — proto se
# přepočítává každou minutu, kdežto stahuje se jen při změně dne (viz PreHdoCoordinator).
UPDATE_INTERVAL = timedelta(minutes=1)

# Když stahování selže, nemá smysl zkoušet to znovu každou minutu: byl by to 1440 požadavků
# denně na cizí web, který nás o to neprosil.
RETRY_BACKOFF_START = 60
RETRY_BACKOFF_MAX = 3600

HDO_PAGE = "https://www.predistribuce.cz/cs/potrebuji-zaridit/zakaznici/stav-hdo/"
HDO_AJAX = "https://www.predistribuce.cz/com/PREdi/UI/Forms/Hdo/HdoForm:hdoOneDayAjax"
