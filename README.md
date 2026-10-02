# Spletna stran Zavoda AI-D

- **Stran:** https://mitjagodnic.github.io/ai-d-demo/
- **Urednik:** https://mitjagodnic.github.io/ai-d-demo/urednik/

## Kako deluje
Vsebine se urejajo v uredniku (Sveltia CMS) na naslovu `/urednik/`. Vsaka shranjena sprememba se zapiše v ta repozitorij na GitHubu. GitHub nato stran v 1–2 minutah sam zgradi in objavi (`.github/workflows/objava.yml`). Enkrat na dan se stran zgradi tudi sama od sebe, da se pretekli dogodki premaknejo.

V uredniku se urejajo novice, dogodki (s programom in prijavami), pretekli dogodki, besedila stalnih strani, pravne strani in nastavitve. Videza in zgradbe strani v uredniku ni mogoče spremeniti.

## Prijava v urednik (enkrat na brskalnik)
1. Na GitHubu (račun mitjagodnic) odprite https://github.com/settings/personal-access-tokens/new
2. **Token name:** Urednik AI-D. **Expiration:** npr. 1 leto.
3. **Repository access:** Only select repositories → `ai-d-demo`.
4. **Permissions → Repository permissions → Contents:** Read and write.
5. Kliknite **Generate token** in ključ kopirajte.
6. V uredniku kliknite **Sign In Using Access Token** in ključ prilepite. Gumb »Sign In with GitHub« ne deluje, ker zanj ni nastavljenega strežnika.

Vsak urednik, ki ima dostop do repozitorija, si ustvari svoj ključ.

## Obrazci
Brez dodatnih nastavitev obrazci na strani odprejo e-poštni program obiskovalca s pripravljenim sporočilom. Če v uredniku pod **Nastavitve** vpišete brezplačen ključ s strani web3forms.com, prijave in sporočila prihajajo neposredno na e-pošto.

## Za tehnično pomoč
- Vsebine so v `content/` (JSON, besedila v Markdownu), slike v `static/media/`, pomanjšane kopije slik pa v `static/kartice/`.
- Stran zgradi `tools/build.py` (Python 3.9+, `pip install -r requirements.txt`) v mapo `site/`. Za objavo pod podmapo dodajte `AID_DEMO_BASE=/ai-d-demo/`.
- Nastavitve urednika so v `src/cms/config.yml`.
- Za objavo na ai-d.si: zgradite brez `AID_DEMO_BASE` in naložite mapo `site/` na koren domene. V `src/cms/config.yml` posodobite `site_url`.
