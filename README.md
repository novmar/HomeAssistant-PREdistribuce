# PRE Distribuce — nízký tarif (HDO) a cena elektřiny pro Home Assistant

Integrace pro zákazníky **PREdistribuce** (Praha a Roztoky). Podle povelu vašeho HDO
přijímače zjistí, kdy běží **nízký tarif**, a spočítá **aktuální cenu elektřiny** —
volitelně i to, **kolik vás právě teď stojí odběr** (Kč/h a Kč/min).

> Fork původní integrace [slesinger/HomeAssistant-PREdistribuce](https://github.com/slesinger/HomeAssistant-PREdistribuce),
> kompletně přepsaný. Poděkování patří původnímu autorovi za nalezení zdroje dat.

## Co přibylo oproti originálu

- **Žádné závislosti.** Původní verze vyžadovala `lxml` (C-extension), který se rozbíjel
  při upgradech Home Assistantu. Nová verze si vystačí se standardní knihovnou.
- **Nastavení klikáním.** Povel se vybírá z nabídky, kterou integrace stáhne přímo z webu
  PRE. Žádné ruční editování `configuration.yaml`.
- **Jedno stahování místo mnoha.** Rozvrh se stahuje jednou denně přes `DataUpdateCoordinator`,
  ne zvlášť pro každou entitu.
- **Asynchronně**, bez blokujících HTTP volání v event loopu.
- **Cenové senzory** — cena za kWh podle aktuálního tarifu a náklady na aktuální odběr.
- **Korektní přechod přes půlnoc.** Okno nízkého tarifu, které pokračuje do dalšího dne,
  se počítá vcelku.

## Instalace

**HACS** → tři tečky → *Custom repositories* → přidat
`https://github.com/novmar/HomeAssistant-PREdistribuce`, kategorie **Integration**.
Pak *Download*, restart HA a **Nastavení → Zařízení a služby → Přidat integraci → PRE Distribuce**.

## Kde vzít povel HDO

Trojčíslí (261–778). Najdete ho:

1. **na štítku HDO přijímače** u elektroměru — bývá tam řádek jako `K1: 490`
2. v portálu **Můj PRE** → *Moje odběrné místo*

Nevíte-li si rady, otevřete [stránku PRE se stavem HDO](https://www.predistribuce.cz/cs/potrebuji-zaridit/zakaznici/stav-hdo/)
a porovnejte rozvrhy jednotlivých povelů s tím, kdy vám reálně spíná bojler.

## Entity

| Entita | Popis |
|---|---|
| `binary_sensor.nizky_tarif` | Zapnuto, když běží nízký tarif. V atributech jsou dnešní okna NT. |
| `sensor.minut_do_nizkeho_tarifu` | Za kolik minut začne nízký tarif (0 = běží). |
| `sensor.minut_do_vysokeho_tarifu` | Za kolik minut nízký tarif skončí (0 = neběží). |
| `sensor.cena_elektriny` | Cena za kWh podle právě běžícího tarifu. |
| `sensor.naklady_za_hodinu` | Kolik stojí aktuální odběr. Jen když nastavíte senzor příkonu. |
| `sensor.naklady_za_minutu` | Totéž po minutách. |

### Hlídané délky nízkého tarifu

V nastavení integrace lze zadat minuty (např. `30, 90, 180`). Pro každou vznikne senzor,
který je zapnutý **jen když nízký tarif běží a zároveň vydrží aspoň tak dlouho**.

Automatizace pak nemusí řešit, jestli se pračka stihne doprat, než se přepne tarif:

```yaml
automation:
  - alias: Pračka v nízkém tarifu
    triggers:
      - trigger: state
        entity_id: binary_sensor.nizky_tarif_180_min
        to: "on"
    actions:
      - action: switch.turn_on
        target:
          entity_id: switch.pracka
```

## Ceny

Zadávejte **konečnou cenu za kWh včetně distribuce a DPH**, ne jen silovou elektřinu.
Spočítáte ji z faktury jako součet: silová elektřina + daň z elektřiny + distribuce
(liší se pro VT a NT!) + systémové služby + POZE, celé × 1,21.

Stálé měsíční platby (jistič, odběrné místo, OTE) do ceny za kWh nepatří — platí se tak jako tak.

## Jak to funguje

PRE nemá veřejné API. Stránka se stavem HDO si data dotahuje AJAXem z endpointu, který
nevyžaduje přihlášení — integrace volá přímo ten a parsuje z odpovědi okna nízkého tarifu.

Endpoint je nezdokumentovaný a PRE ho může kdykoli změnit. Integrace je proto psaná tak,
aby při jakékoli odchylce **spadla do stavu `unavailable`** místo aby tipovala tarif —
špatná cena, která vypadá správně, je horší než žádná.

## Licence

MIT, stejně jako původní projekt.
