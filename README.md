# Spletna stran Zavoda AI-D z urednikom

## Zagon urednika
Dvokliknite **`zazeni.command`** v tej mapi. Odpre se okno Terminala, v brskalniku pa urednik:
**http://localhost:8800/urednik/**. Urednik deluje, dokler je okno Terminala odprto.

Javna stran (z delujočimi obrazci) je med tem na http://localhost:8800/

**Prva prijava:** e-naslov in geslo sta v datoteki `data/prva-prijava.txt`. Po prvi prijavi geslo spremenite v »Moj račun«, datoteko pa izbrišite.

## Kaj omogoča urednik
- **Novice:** pisanje, slike, oznake, osnutki, predogled pred objavo, brisanje.
- **Dogodki:** datum, lokacija, cena, opis, program po dnevih s predavatelji in fotografijami, lokacije za zemljevid in prijavni obrazec (tudi »člani brezplačno«). Izbirate lahko tudi izpostavljen dogodek za domačo stran in trak na vrhu. Ko dogodek mine, se sam premakne med pretekle.
- **Strani:** besedila domače strani, strani O zavodu, Članstvo in Kontakt, podatki zavoda in pravne strani. Zgradbe in videza ni mogoče spremeniti.
- **Prejeto:** prijave na dogodke, povpraševanja za članstvo, sporočila in prijave na e-novice z izvozom v Excel (CSV). Na voljo so tudi obvestila po e-pošti (Nastavitve).
- **Slike:** nalaganje (samodejno pomanjšanje), knjižnica, brisanje neuporabljenih.
- **Uporabniki:** urednik (objavlja) in skrbnik (dodaja uporabnike, ureja nastavitve).

Po vsakem shranjevanju se javna stran v nekaj sekundah posodobi sama.

## Predogled na spletu
https://mitjagodnic.github.io/ai-d-demo/ – posodobite ga v uredniku: **Nastavitve → Objavi predogled**.
Predogled je skrit pred Googlom. Na njem obrazci odprejo e-pošto, ker tam ni urednika.

## Za tehnično pomoč: namestitev na strežnik
- Potrebuje Python 3.9+: `pip install -r requirements.txt`, nato zagon z `AID_HOST=0.0.0.0 AID_PORT=8800 python -m admin`.
- Za spletnim strežnikom (nginx ali Caddy) z HTTPS nastavite še `AID_HTTPS=1` (varni piškotki) in `AID_PROXY=1`.
- Uporabnika dodate na strežniku z ukazom `python -m admin.uporabnik`.
- Vsebine so v `content/` (JSON), slike v `static/media/`. Prijave, uporabniki in nastavitve so v `data/`, zato to mapo redno varnostno kopirajte.
- Javno stran zgradi `tools/build.py` v mapo `site/`. Če stran gostuje drugje, nastavite `form_endpoint` v `config.json` na `https://<strežnik>/api/obrazec`.
