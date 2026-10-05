#!/usr/bin/env python3
"""Zgradi novo spletno stran Zavoda AI-D v mapo site/.

Uporaba:  python3 tools/build.py
Vsebina:  content/ (urejana v uredniku na /urednik/, Sveltia CMS): novice/, dogodki/, arhiv/, strani/, pravno/, nastavitve.json
"""
import datetime as dt
import json, os, re, shutil
from html import escape
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.environ.get("AID_OUT") or os.path.join(ROOT, "site")
SRC = os.path.join(ROOT, "src")
CONTENT = os.path.join(ROOT, "content")
CONFIG = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
SITE_URL = CONFIG["site_url"].rstrip("/") + "/"
# Demo build for a preview host (e.g. GitHub Pages under /ai-d-demo/):  AID_DEMO_BASE=/ai-d-demo/ python3 tools/build.py
DEMO_BASE = os.environ.get("AID_DEMO_BASE", "")
VERSION = dt.datetime.now().strftime("%Y%m%d%H%M")
TODAY = dt.datetime.now(dt.timezone.utc)


MONTHS = ["januar", "februar", "marec", "april", "maj", "junij", "julij", "avgust", "september", "oktober", "november", "december"]
MONTHS_SHORT = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "avg", "sep", "okt", "nov", "dec"]

# old URL -> new URL (kept alive as redirect pages)
REDIRECTS = {
    "aktualno/": "novice/",
    "projekti/": "o-zavodu/",
    "kategorija-dogodka/dogodek/": "dogodki/",
    "category/nekategorizirano/": "novice/",
    "dogodki/ai-week/": "dogodek/ai-week-2026/",
    "dogodki/delavnica-z-evo-esih-psybit-30-9/": "dogodek/delavnica-z-evo-esih-psybit-30-9/",
    "dogodki/ai-v-podjetjih-ze-tece-imate-pravila-pod-nadzorom-ai-law/": "dogodek/ivo-grlica-odvetnik-ai-law-delavnica/",
}

NAV = [("", "Domov"), ("novice/", "Novice"), ("dogodki/", "Dogodki"), ("clanstvo/", "Članstvo"), ("o-zavodu/", "O zavodu"), ("kontakt/", "Kontakt")]
LEGAL_NAV = [("pravilnik-o-piskotkih/", "Pravilnik o piškotkih"), ("politika-zasebnosti/", "Politika zasebnosti"),
             ("splosni-pogoji-clanstva/", "Splošni pogoji članstva"), ("izjava-o-skladnosti/", "Izjava o skladnosti")]

TOPICS = {"zavod": "Iz zavoda", "slovenija": "Slovenija", "svet": "Svet"}


# ---------------------------------------------------------------- helpers
def e(s):
    return escape(s or "", quote=True)


def href(prefix, path):
    path = REDIRECTS.get(path, path)
    return prefix + quote(path, safe="/#?=&")


def parse_iso(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def d_long(d):
    return f"{d.day}. {MONTHS[d.month - 1]} {d.year}"


def d_short(d):
    return f"{d.day}. {d.month}. {d.year}"


def ljubljana_offset(y, m, d):
    """CET/CEST without external tz data: DST from last Sunday in March to last Sunday in October."""
    def last_sunday(month):
        x = dt.date(y, month, 31)
        return x - dt.timedelta(days=(x.weekday() + 1) % 7)
    day = dt.date(y, m, d)
    return "+02:00" if last_sunday(3) <= day < last_sunday(10) else "+01:00"


def parse_event_dt(s):
    m = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})(?:\s*ob\s*(\d{1,2}):(\d{2}))?", s or "")
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hh, mm = int(m.group(4) or 0), int(m.group(5) or 0)
    return dt.datetime.fromisoformat(f"{y:04d}-{mo:02d}-{d:02d}T{hh:02d}:{mm:02d}:00{ljubljana_offset(y, mo, d)}")


def img_tag(prefix, rel, alt="", cls="", sizes="100vw", eager=False, variant="full"):
    v = IMAGES.get(rel)
    if not v:
        return ""
    full, card = v["full"], v["card"]
    use = v[variant]
    srcset = ""
    if card["src"] != full["src"] and card.get("w") and full.get("w"):
        srcset = f' srcset="{prefix}{quote(card["src"])} {card["w"]}w, {prefix}{quote(full["src"])} {full["w"]}w" sizes="{sizes}"'
    load = 'fetchpriority="high"' if eager else 'loading="lazy"'
    c = f' class="{cls}"' if cls else ""
    size = f' width="{use["w"]}" height="{use["h"]}"' if use.get("w") else ""
    return (f'<img{c} src="{prefix}{quote(use["src"])}"{srcset}{size} '
            f'alt="{e(alt)}" {load} decoding="async">')


def img_url(rel, variant="full", absolute=False):
    v = IMAGES.get(rel)
    if not v:
        return ""
    return (SITE_URL if absolute else "") + quote(v[variant]["src"])


def render_content(html, prefix):
    def rep_img(m):
        tag = img_tag(prefix, m.group(1), alt=m.group(2).replace("&quot;", '"'), sizes="(min-width: 900px) 760px, 100vw")
        return tag
    html = re.sub(r'<img src="\{\{media:(.*?)\}\}" alt="(.*?)"[^>]*>', rep_img, html)
    html = re.sub(r'href="@/([^"]*)"', lambda m: f'href="{href(prefix, m.group(1))}"', html)
    return html


def plain(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def reading_time(words):
    return max(1, round(words / 220))


def topic_of(a):
    t = (a["title"] + " " + a["excerpt"]).lower()
    if re.search(r"ai-d|zavod|phori|ai week|aiweek|članic|članom|člani", t):
        return "zavod"
    if re.search(r"sloven|maribor|ljubljan", t):
        return "slovenija"
    return "svet"


def icon(name, size=20):
    paths = {
        "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
        "arrow-up-right": '<path d="M7 17 17 7M8 7h9v9"/>',
        "arrow-left": '<path d="M19 12H5M11 18l-6-6 6-6"/>',
        "arrow-down": '<path d="M12 5v14M6 13l6 6 6-6"/>',
        "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
        "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
        "moon": '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z"/>',
        "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
        "pin": '<path d="M12 22s7-6.2 7-12a7 7 0 1 0-14 0c0 5.8 7 12 7 12Z"/><circle cx="12" cy="10" r="2.5"/>',
        "ticket": '<path d="M3 8a2 2 0 0 0 2-2h14a2 2 0 0 0 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 0-2 2H5a2 2 0 0 0-2-2v-2a2 2 0 0 0 0-4Z"/><path d="M13 6v12" stroke-dasharray="2 2"/>',
        "copy": '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',
        "check": '<path d="m5 12 5 5 9-10"/>',
        "close": '<path d="M6 6l12 12M18 6 6 18"/>',
        "plus": '<path d="M12 5v14M5 12h14"/>',
        "link": '<path d="M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1"/><path d="M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/>',
        "share": '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.6 13.5 6.8 4M15.4 6.5l-6.8 4"/>',
        "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
        "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
        "rss": '<path d="M5 11a8 8 0 0 1 8 8M5 5a14 14 0 0 1 14 14"/><circle cx="6" cy="18" r="1.5"/>',
        "grid": '<rect x="4" y="4" width="7" height="7" rx="1"/><rect x="13" y="4" width="7" height="7" rx="1"/><rect x="4" y="13" width="7" height="7" rx="1"/><rect x="13" y="13" width="7" height="7" rx="1"/>',
        "list": '<path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01"/>',
        "eye": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
        "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
        "nodes": '<circle cx="5" cy="6" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="12" cy="18" r="2"/><circle cx="12" cy="10" r="2"/><path d="M6.7 7.1 10.3 9M17.3 7.1 13.7 9M12 12v4"/>',
        "linkedin": '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M8 10v7M8 7v.01M12 17v-4a2 2 0 0 1 4 0v4M12 10v7"/>',
        "facebook": '<path d="M14 8h3V4h-3a4 4 0 0 0-4 4v3H7v4h3v6h4v-6h3l1-4h-4V8Z"/>',
        "x": '<path d="M4 4l16 16M20 4 4 20"/>',
        "map": '<path d="m9 4-6 2v14l6-2 6 2 6-2V4l-6 2-6-2Z"/><path d="M9 4v14M15 6v14"/>',
        "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><circle cx="17" cy="9" r="2.5"/><path d="M16 14.2a5 5 0 0 1 5.5 4.8"/>',
        "spark": '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
        "book": '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2V5Z"/><path d="M19 19v2H6"/>',
        "shield": '<path d="M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6l-8-3Z"/><path d="m9 12 2 2 4-4"/>',
        "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
        "chart": '<path d="M4 19h16M7 15l4-4 3 3 5-6"/>',
        "flask": '<path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.7 3h10.6a2 2 0 0 0 1.7-3l-5-9V3"/><path d="M7.5 15h9"/>',
        "badge": '<circle cx="12" cy="9" r="6"/><path d="m8.5 14-1.5 7 5-3 5 3-1.5-7"/>',
    }
    return (f'<svg class="i" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths[name]}</svg>')


TITLES = {"dr", "prof", "mag", "doc", "red", "izr"}


def initials(name):
    words = [w for w in re.split(r"[\s–-]+", name) if w and w.rstrip(".").lower() not in TITLES and w[0].isalpha()]
    return "".join(w[0] for w in words[:2]).upper()


def fold(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def nowrap_aid(text):
    """Keep »AI-D« on one line in big headings."""
    return text.replace("AI-D", '<span class="nw">AI-D</span>')


def logo(cls=""):
    return (f'<span class="logo {cls}"><span class="logo__mark"><span class="logo__box">AI</span>'
            f'<span class="logo__d">–D</span></span><span class="logo__cap">Zavod za razvoj<br>umetne inteligence</span></span>')


# ---------------------------------------------------------------- content (edited in the Sveltia CMS at /urednik/)
def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def entries(folder):
    """All JSON files of a CMS folder collection as (slug, data), sorted by file name."""
    d = os.path.join(CONTENT, folder)
    out = []
    for name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if name.endswith(".json"):
            out.append((name[:-5], read_json(os.path.join(d, name))))
    return out


SLIKE = read_json(os.path.join(CONTENT, "slike.json"))
IMAGES = {}
for _path, _v in SLIKE["images"].items():
    _full = {"src": _path, "w": _v["w"], "h": _v["h"]}
    IMAGES[_path] = {"full": _full, "card": _v.get("card") or _full}
EXTRAS = SLIKE["extras"]


def image_key(value):
    """'/media/2026/09/x.jpg' (CMS value) -> 'media/2026/09/x.jpg'. Registers images uploaded in the CMS."""
    if not value:
        return None
    key = value.split("?")[0].lstrip("/")
    if DEMO_BASE and key.startswith(DEMO_BASE.strip("/") + "/"):
        key = key[len(DEMO_BASE.strip("/")) + 1:]
    if key not in IMAGES and os.path.isfile(os.path.join(ROOT, "static", key)):
        IMAGES[key] = new_image(key)
    return key if key in IMAGES else None


def new_image(key):
    """Size (and a smaller card copy) of an image that was uploaded in the CMS; needs Pillow, works without it too."""
    full = {"src": key, "w": None, "h": None}
    entry = {"full": full, "card": full, "pending_card": None}
    try:
        from PIL import Image
        with Image.open(os.path.join(ROOT, "static", key)) as im:
            full["w"], full["h"] = im.size
            if im.width > 960:
                card_src = "kartice/" + key[len("media/"):] if key.startswith("media/") else "kartice/" + key
                h = round(im.height * 960 / im.width)
                entry["card"] = {"src": card_src, "w": 960, "h": h}
                entry["pending_card"] = card_src
    except Exception:  # noqa: BLE001 - no Pillow or unreadable file: use the image as it is
        pass
    return entry


def write_pending_cards():
    from PIL import Image
    for key, v in IMAGES.items():
        if v.get("pending_card"):
            dst = os.path.join(OUT, v["pending_card"])
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with Image.open(os.path.join(ROOT, "static", key)) as im:
                im = im.convert("RGB") if im.mode not in ("RGB", "RGBA") else im
                im.thumbnail((960, 10000))
                im.save(dst, quality=82)


def md_html(md, strip_breaks=False):
    """Markdown from the CMS -> HTML in the site's internal format (media tokens, @/ links, figures)."""
    import markdown
    md = re.sub(r"\\\n", "  \n", md or "")
    html = markdown.markdown(md, extensions=["extra", "sane_lists"], output_format="html")

    def img(m):
        attrs = m.group(1)
        src = re.search(r'src="([^"]*)"', attrs)
        alt = re.search(r'alt="([^"]*)"', attrs)
        key = image_key(unescape_attr(src.group(1))) if src else None
        if not key:
            return ""
        return f'<img src="{{{{media:{key}}}}}" alt="{alt.group(1) if alt else ""}">'
    html = re.sub(r"<img([^>]*)/?>", img, html)

    def figure(m):
        imgs = re.findall(r"<img [^>]+>", m.group(1))
        cls = ' class="gallery"' if len(imgs) > 1 else ""
        inner = "".join(f"<figure>{i}</figure>" for i in imgs) if len(imgs) > 1 else imgs[0]
        return f"<figure{cls}>{inner}</figure>"
    html = re.sub(r"<p>((?:\s*<img [^>]+>\s*)+)</p>", figure, html)
    html = re.sub(r'href="/(?!/)', 'href="@/', html)
    html = re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" target="_blank" rel="noopener"', html)
    if strip_breaks:
        html = re.sub(r"<br\s*/?>", " ", html)
    return html.strip()


def unescape_attr(s):
    return s.replace("&amp;", "&").replace("%20", " ")


def local_dt(value, end_of_day=False):
    """'2026-11-03T09:30' (Ljubljana time, as stored by the CMS) -> aware datetime."""
    if not value:
        return None
    value = str(value).strip().replace(" ", "T")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        value += "T23:59" if end_of_day else "T12:00"
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})", value)
    if not m:
        return None
    y, mo, d, hh, mm = map(int, m.groups())
    if re.search(r"(Z|[+-]\d{2}:?\d{2})$", value):
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt.datetime.fromisoformat(f"{y:04d}-{mo:02d}-{d:02d}T{hh:02d}:{mm:02d}:00{ljubljana_offset(y, mo, d)}")


def fact_time(d):
    return f"{d.day}. {d.month}. {d.year} ob {d:%H:%M}"


def load_articles():
    out = []
    for slug, a in entries("novice"):
        if a.get("draft"):
            continue
        html = md_html(a.get("body"))
        d = local_dt(a.get("date"))
        out.append({"slug": slug, "title": a.get("title", slug), "date": d.isoformat() if d else None, "modified": None,
                    "excerpt": (a.get("excerpt") or "").strip() or plain(html)[:220], "image": image_key(a.get("image")),
                    "html": html, "words": len(plain(html).split()), "tags": a.get("tags") or []})
    return out


# older event write-ups taken over from the WordPress site: shown as simple pages at dogodki/<slug>/
LEGACY_EVENTS = set(json.load(open(os.path.join(ROOT, "tools", "stari-dogodki.json"), encoding="utf-8")))


def event_files():
    """Upcoming events (content/dogodki) and past ones (content/dogodki-pretekli, moved there automatically)."""
    return entries("dogodki") + entries("dogodki-pretekli")


def load_events():
    out = []
    for slug, ev in event_files():
        if ev.get("draft") or slug in LEGACY_EVENTS:
            continue
        start = local_dt(ev.get("start"))
        end = local_dt(ev.get("end")) or start
        if not start:
            continue
        reg = ev.get("registration") or {}
        price = reg.get("nonmember_price") or ev.get("price", "")
        program = []
        for day in ev.get("program") or []:
            program.append({"label": day.get("label", ""), "description": day.get("description", ""),
                            "locations": [l for l in (day.get("locations") or []) if l.get("name") or l.get("address")],
                            "items": [{"time": it.get("time") or "—", "title": it.get("title", ""), "subtitle": it.get("subtitle", ""),
                                       "image": image_key(it.get("image")), "html": md_html(it.get("description"), strip_breaks=True)}
                                      for it in (day.get("items") or []) if it.get("title")]})
        out.append({
            "slug": "dogodek/" + slug, "title": ev.get("title", slug), "eyebrow": ev.get("eyebrow") or "Dogodek",
            "lead": f"<p>{escape(ev['lead'])}</p>" if ev.get("lead") else "", "image": image_key(ev.get("image")),
            "html": md_html(ev.get("body")), "start_iso": start.isoformat(), "end_iso": end.isoformat(),
            "facts": [{"label": "Termin", "value": fact_time(start), "extra": "do " + fact_time(end)},
                      {"label": "Lokacija", "value": ev.get("location", ""), "extra": None},
                      {"label": "Cena", "value": ev.get("price", ""), "extra": None}],
            "program": program or None,
            "themes": [t for t in (ev.get("themes") or []) if t.get("title")], "themes_title": ev.get("themes_title") or "",
            "themes_note": ev.get("themes_note") or "",
            "registration": {"open": bool(reg.get("open")), "title": reg.get("title") or "Prijava na dogodek", "intro": reg.get("intro") or "",
                             "member_label": "Sem član Zavoda AI-D – brezplačna udeležba" if reg.get("members_free") else None,
                             "price": price if reg.get("members_free") else None,
                             "price_note": f"Za člane Zavoda AI-D brezplačno, za zunanje udeležence {price}." if reg.get("members_free") else None},
        })
    return out


def load_archive():
    out = []
    for slug, x in event_files():
        if x.get("draft") or slug not in LEGACY_EVENTS:
            continue
        out.append({"slug": "dogodki/" + slug, "title": x.get("title", slug), "image": image_key(x.get("image")),
                    "html": md_html(x.get("body")), "event_date": (x.get("start") or "")[:10] or None})
    return out


def load_legal():
    order = ["politika-zasebnosti", "pravilnik-o-piskotkih", "splosni-pogoji-clanstva", "izjava-o-skladnosti"]
    items = {slug: x for slug, x in entries("pravno")}
    return [{"slug": s, "title": items[s]["title"], "html": md_html(items[s].get("body"))} for s in order if s in items]


def load_pages():
    f = lambda n: read_json(os.path.join(CONTENT, "strani", n + ".json"))
    return {"domov": f("domov"), "o_zavodu": f("o-zavodu"), "clanstvo": f("clanstvo"), "kontakt": f("kontakt"), "podjetje": f("podatki")}


_settings = read_json(os.path.join(CONTENT, "nastavitve.json"))
SETTINGS = {"izpostavljen_dogodek": ("dogodek/" + _settings["featured_event"]) if _settings.get("featured_event") else None,
            "obvestilo": _settings.get("show_banner", True), "web3forms_key": (_settings.get("web3forms_key") or "").strip()}

ARTICLES = load_articles()
EVENTS = load_events()
PAST = load_archive()
LEGAL = load_legal()
PAGES = load_pages()
CO = PAGES["podjetje"]


# ---------------------------------------------------------------- data prep
for a in ARTICLES:
    a["d"] = parse_iso(a["date"])
    a["url"] = a["slug"] + "/"
    a["topic"] = topic_of(a)
    a["mins"] = reading_time(a["words"])
ARTICLES.sort(key=lambda a: a["d"], reverse=True)  # newest first, also for items added in the editor

for ev in EVENTS:
    termin = next(f for f in ev["facts"] if f["label"] == "Termin")
    ev["start"] = parse_iso(ev.get("start_iso")) or parse_event_dt(termin["value"])
    ev["end"] = parse_iso(ev.get("end_iso")) or parse_event_dt(termin["extra"]) or ev["start"]
    ev["url"] = ev["slug"] + "/"
    ev["fact"] = {f["label"]: f for f in ev["facts"]}
    ev["upcoming"] = ev["end"] > TODAY

for p in PAST:
    p["url"] = p["slug"] + "/"
    d = p.get("event_date")
    p["d"] = dt.datetime.fromisoformat(d + "T12:00:00+01:00") if d else None

ARCHIVE = [p for p in PAST if p["slug"] + "/" not in REDIRECTS]
ARCHIVE.sort(key=lambda p: p["d"] or dt.datetime.min.replace(tzinfo=dt.timezone.utc), reverse=True)
# the featured event (set in the editor) drives the top banner and the big block on the home page
FEATURED = next((ev for ev in EVENTS if ev["slug"] == SETTINGS.get("izpostavljen_dogodek")), None)
AIWEEK = FEATURED

UPCOMING = sorted([ev for ev in EVENTS if ev["upcoming"]], key=lambda ev: ev["start"])
FINISHED = sorted([ev for ev in EVENTS if not ev["upcoming"]], key=lambda ev: ev["start"], reverse=True)

SEARCH = []


# ---------------------------------------------------------------- layout
def head(prefix, path, title, desc, image=None, kind="website", jsonld=None):
    full_title = title if title.startswith("Zavod AI-D") else f"{title} — Zavod AI-D"
    fallback = FEATURED["image"] if FEATURED else EXTRAS["hero"]
    og_img = img_url(image or fallback, absolute=True)
    ld = f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>' if jsonld else ""
    return f"""<!doctype html>
<html lang="sl" data-root="{prefix}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(full_title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{SITE_URL}{quote(path)}">
<meta property="og:locale" content="sl_SI">
<meta property="og:site_name" content="Zavod za razvoj umetne inteligence">
<meta property="og:type" content="{kind}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{SITE_URL}{quote(path)}">
<meta property="og:image" content="{og_img}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#0c0b0a">
<meta name="color-scheme" content="light dark">{'<meta name="robots" content="noindex, nofollow">' if DEMO_BASE else ''}
<link rel="icon" href="{prefix}assets/favicon.svg" type="image/svg+xml">
<link rel="alternate" type="application/rss+xml" title="Zavod AI-D — Novice" href="{prefix}feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@300..700&family=Geist+Mono:wght@400;500&family=Instrument+Serif:ital@0;1&display=swap">
<link rel="stylesheet" href="{prefix}assets/site.css?v={VERSION}">
<script>(function(){{try{{var t=localStorage.getItem("aid-theme");if(t)document.documentElement.dataset.theme=t}}catch(e){{}}}})()</script>
<script src="{prefix}assets/config.js?v={VERSION}" defer></script>
<script src="{prefix}assets/site.js?v={VERSION}" defer></script>
{ld}
</head>"""


def date_range(ev):
    s, en = ev["start"], ev["end"]
    if s.date() == en.date():
        return f"{s.day}. {MONTHS[s.month - 1]} {s.year}"
    if (s.month, s.year) == (en.month, en.year):
        return f"{s.day}.–{en.day}. {MONTHS[s.month - 1]} {s.year}"
    return f"{s.day}. {MONTHS[s.month - 1]} – {en.day}. {MONTHS[en.month - 1]} {en.year}"


def announce(prefix):
    if not (FEATURED and FEATURED["upcoming"] and SETTINGS.get("obvestilo", True)):
        return ""
    when = date_range(FEATURED).rsplit(" ", 1)[0]
    return f"""<div class="announce theme-dark" data-announce>
  <div class="container announce__inner">
    <span class="announce__dot" aria-hidden="true"></span>
    <p><strong>{e(FEATURED['title'])}</strong><span class="announce__sep">·</span>{e(when)}<span class="announce__sep">·</span>{e(FEATURED['fact'].get('Lokacija', {}).get('value', ''))}
      <span class="announce__cd" data-countdown="{FEATURED['start'].isoformat()}" data-countdown-format="short"></span></p>
    <a href="{href(prefix, FEATURED['url'])}">{'Program in prijava' if FEATURED.get('program') else 'Več in prijava'} {icon('arrow', 16)}</a>
    <button class="announce__close" type="button" data-announce-close aria-label="Skrij obvestilo">{icon('close', 16)}</button>
  </div>
</div>"""


def header(prefix, section):
    links = "".join(
        f'<a href="{href(prefix, p)}"{" aria-current=page" if section == p else ""}>{label}</a>' for p, label in NAV[1:])
    mlinks = "".join(
        f'<li><a href="{href(prefix, p)}"{" aria-current=page" if section == p else ""}><span class="mmenu__n">0{i + 1}</span>{label}</a></li>'
        for i, (p, label) in enumerate(NAV))
    return f"""<header class="hdr" data-hdr>
  <div class="container hdr__inner">
    <a class="hdr__logo" href="{href(prefix, '')}" aria-label="Zavod AI-D — domov">{logo()}</a>
    <nav class="nav" aria-label="Glavna navigacija">{links}</nav>
    <div class="hdr__tools">
      <button class="tool-btn tool-btn--search" type="button" data-search-open aria-label="Iskanje po strani">{icon('search', 18)}<span class="tool-btn__label">Iskanje</span><kbd data-kbd>⌘K</kbd></button>
      <button class="tool-btn" type="button" data-theme-toggle aria-label="Preklopi svetlo/temno temo"><span class="theme-ico theme-ico--sun">{icon('sun', 18)}</span><span class="theme-ico theme-ico--moon">{icon('moon', 18)}</span></button>
      <a class="btn btn--primary btn--sm hdr__cta" href="{href(prefix, 'clanstvo/')}" data-magnetic>Pridruži se {icon('arrow-up-right', 16)}</a>
      <button class="burger" type="button" data-menu-toggle aria-expanded="false" aria-controls="mmenu" aria-label="Odpri meni"><span></span><span></span></button>
    </div>
  </div>
</header>
<div class="mmenu theme-dark" id="mmenu" data-menu hidden>
  <div class="container mmenu__inner">
    <ul class="mmenu__list">{mlinks}</ul>
    <div class="mmenu__foot">
      <a class="btn btn--primary" href="{href(prefix, 'clanstvo/')}">Pridruži se nam {icon('arrow-up-right', 16)}</a>
      <p>{e(CO['naslov'])}<br><a href="mailto:{e(CO['email'])}">{e(CO['email'])}</a></p>
    </div>
  </div>
</div>"""


def newsletter_form(prefix, where="footer"):
    return f"""<form class="newsletter" data-form="newsletter" data-subject="Prijava na e-novice" novalidate>
  <label class="sr-only" for="nl-{where}">E-naslov</label>
  <input id="nl-{where}" type="email" name="email" placeholder="Tvoj e-mail naslov" autocomplete="email" required>
  <input class="hp" type="text" name="website" tabindex="-1" autocomplete="off" aria-hidden="true">
  <button class="btn btn--primary" type="submit" data-magnetic>Naroči se {icon('arrow', 16)}</button>
</form>
<p class="newsletter__note">S pritiskom na gumb »Naroči se« se strinjate s <a href="{href(prefix, 'politika-zasebnosti/')}">politiko zasebnosti</a>.</p>"""


def footer(prefix):
    nav = "".join(f'<li><a href="{href(prefix, p)}">{label}</a></li>' for p, label in NAV)
    legal = "".join(f'<li><a href="{href(prefix, p)}">{label}</a></li>' for p, label in LEGAL_NAV)
    return f"""<footer class="ftr theme-dark">
  <div class="container">
    <section class="ftr__news" aria-labelledby="ftr-news-title" data-reveal>
      <div>
        <p class="eyebrow">E-novice</p>
        <h2 id="ftr-news-title" class="ftr__title">Naročite se na <em class="nw">e-novice</em></h2>
      </div>
      <div class="ftr__form">{newsletter_form(prefix)}</div>
    </section>
    <div class="ftr__grid">
      <div class="ftr__brand">
        <a href="{href(prefix, '')}" aria-label="Zavod AI-D — domov">{logo('logo--lg')}</a>
        <address>{e(CO['polno_ime'])}<br>{e(CO['naslov'])}<br>E-naslov: <a href="mailto:{e(CO['email'])}">{e(CO['email'])}</a></address>
      </div>
      <nav aria-label="Povezave"><h3 class="ftr__h">Povezave</h3><ul>{nav}</ul></nav>
      <nav aria-label="Pravne informacije"><h3 class="ftr__h">Pravno</h3><ul>{legal}</ul></nav>
      <div><h3 class="ftr__h">Spremljajte</h3><ul>
        <li><a href="{href(prefix, 'feed.xml')}">{icon('rss', 16)} RSS novice</a></li>
        <li><button type="button" class="linklike" data-search-open>{icon('search', 16)} Iskanje po strani</button></li>
        <li><a href="#top" data-top>{icon('arrow-up-right', 16)} Na vrh</a></li>
      </ul></div>
    </div>
    <div class="ftr__mark" aria-hidden="true" data-ftr-mark><span class="ftr__mark-box">AI</span><span>–D</span></div>
    <p class="ftr__copy">© 2025 | www.ai-d.si | Zavod za razvoj umetne inteligence Ljubljana | Vse pravice pridržane</p>
  </div>
</footer>"""


def search_dialog():
    return f"""<dialog class="cmdk" data-cmdk aria-label="Iskanje po strani">
  <div class="cmdk__box">
    <div class="cmdk__bar">{icon('search', 20)}<input type="search" placeholder="Išči novice, dogodke, ljudi …" aria-label="Iskalni niz" autocomplete="off" spellcheck="false" data-cmdk-input><kbd>Esc</kbd></div>
    <div class="cmdk__results" role="listbox" aria-label="Zadetki" data-cmdk-results></div>
    <div class="cmdk__foot"><span><kbd>↑</kbd><kbd>↓</kbd> izbira</span><span><kbd>↵</kbd> odpri</span><span class="cmdk__count" data-cmdk-count></span></div>
  </div>
</dialog>"""


def write(path, title, desc, body, section=None, image=None, kind="website", jsonld=None, body_class="", prefix=None):
    depth = len([p for p in path.split("/") if p])
    if prefix is None:
        prefix = "../" * depth
    content = body(prefix) if callable(body) else body
    html = f"""{head(prefix, path, title, desc, image, kind, jsonld)}
<body class="{body_class}" id="top">
<a class="skip" href="#main">Preskoči na vsebino</a>
{announce(prefix)}
{header(prefix, section if section is not None else path)}
<main id="main">
{content}
</main>
{footer(prefix)}
{search_dialog()}
<div class="toast" role="status" aria-live="polite" data-toast></div>
</body>
</html>
"""
    out = os.path.join(OUT, path, "index.html") if not path.endswith(".html") else os.path.join(OUT, path)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write(html)


def write_redirect(old, new):
    depth = len([p for p in old.split("/") if p])
    target = "../" * depth + quote(new)
    out = os.path.join(OUT, old, "index.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write(
        f'<!doctype html><html lang="sl"><head><meta charset="utf-8"><title>Preusmeritev …</title>'
        f'<link rel="canonical" href="{SITE_URL}{quote(new)}"><meta name="robots" content="noindex">'
        f'<meta http-equiv="refresh" content="0; url={target}"><script>location.replace("{target}"+location.search+location.hash)</script>'
        f'</head><body><p>Stran se je preselila: <a href="{target}">{SITE_URL}{e(new)}</a></p></body></html>')


# ---------------------------------------------------------------- components
def article_card(prefix, a, variant="", eager=False):
    img = img_tag(prefix, a["image"], sizes="(min-width: 1100px) 420px, (min-width: 700px) 50vw, 100vw", eager=eager, variant="card") if a.get("image") else ""
    year = a["d"].year if a.get("d") else ""
    words = " ".join([a["title"], a["excerpt"], " ".join(a.get("tags", []))])
    return f"""<article class="card {variant}" data-reveal data-card data-topic="{a['topic']}" data-year="{year}" data-date="{a['date'] or ''}" data-search="{e(words)}">
  <a class="card__link" href="{href(prefix, a['url'])}">
    <div class="card__media">{img}</div>
    <div class="card__body">
      <p class="card__meta"><time datetime="{a['date'] or ''}">{d_short(a['d']) if a.get('d') else ''}</time><span aria-hidden="true">·</span><span>{a['mins']} min branja</span></p>
      <h3 class="card__title">{e(a['title'])}</h3>
      <p class="card__excerpt">{e(a['excerpt'])}</p>
      <span class="card__more" aria-hidden="true">Preberi {icon('arrow', 16)}</span>
    </div>
  </a>
</article>"""


def event_card(prefix, ev, big=False):
    s = ev["start"]
    status = "Prihajajoči" if ev["upcoming"] else "Zaključen"
    loc = ev["fact"].get("Lokacija", {}).get("value", "")
    price = ev["fact"].get("Cena", {}).get("value", "")
    multi = ev["end"].date() != s.date()
    days = f"{s.day}.–{ev['end'].day}." if multi else f"{s.day}."
    img = img_tag(prefix, ev["image"], sizes="(min-width: 900px) 50vw, 100vw", variant="card")
    return f"""<article class="ecard{' ecard--big' if big else ''}{'' if ev['upcoming'] else ' is-past'}" data-reveal data-event-end="{ev['end'].isoformat()}">
  <a class="ecard__link" href="{href(prefix, ev['url'])}">
    <div class="ecard__media">{img}</div>
    <div class="ecard__date" aria-hidden="true"><span class="ecard__day">{days}</span><span class="ecard__mon">{MONTHS_SHORT[s.month - 1]} {s.year}</span></div>
    <div class="ecard__body">
      <p class="ecard__status"><span class="pill{' pill--live' if ev['upcoming'] else ''}" data-status>{status}</span>
        {'<span class="ecard__cd" data-countdown="' + s.isoformat() + '" data-countdown-format="days"></span>' if ev['upcoming'] else ''}</p>
      <h3 class="ecard__title">{e(ev['title'])}</h3>
      <ul class="ecard__facts">
        <li>{icon('calendar', 16)}<span><time datetime="{s.isoformat()}">{d_short(s)}</time>{' – ' + d_short(ev['end']) if multi else ''}, ob {s.strftime('%H:%M')}</span></li>
        <li>{icon('pin', 16)}<span>{e(loc)}</span></li>
        <li>{icon('ticket', 16)}<span>{e(price)}</span></li>
      </ul>
      <span class="ecard__more">{'Program in prijava' if ev['upcoming'] else 'Več o dogodku'} {icon('arrow', 16)}</span>
    </div>
  </a>
</article>"""


def archive_card(prefix, p):
    img = img_tag(prefix, p["image"], sizes="(min-width: 900px) 33vw, 100vw", variant="card")
    date = f'<time datetime="{p["d"].date().isoformat()}">{d_long(p["d"])}</time>' if p.get("d") else ""
    return f"""<article class="acard" data-reveal data-year="{p['d'].year if p.get('d') else ''}">
  <a class="acard__link" href="{href(prefix, p['url'])}">
    <div class="acard__media">{img}</div>
    <p class="acard__date">{date}</p>
    <h3 class="acard__title">{e(p['title'])}</h3>
  </a>
</article>"""


def countdown_block(iso, label="Do začetka"):
    units = "".join(f'<div class="cd__unit"><span class="cd__num" data-cd="{k}">00</span><span class="cd__lbl">{l}</span></div>'
                    for k, l in (("d", "dni"), ("h", "ur"), ("m", "minut"), ("s", "sekund")))
    return f'<div class="cd" data-countdown="{iso}" data-countdown-format="full" role="timer" aria-label="{label}"><p class="cd__label">{label}</p><div class="cd__units">{units}</div></div>'


def section_head(eyebrow, title, link=None, cls=""):
    more = f'<a class="link-arrow" href="{link[0]}">{link[1]} {icon("arrow", 16)}</a>' if link else ""
    return f'<div class="sec-head {cls}" data-reveal><div><p class="eyebrow">{eyebrow}</p><h2 class="sec-title">{title}</h2></div>{more}</div>'


# ---------------------------------------------------------------- pages
def build_home():
    P = PAGES["domov"]
    latest = ARTICLES[:7]
    ticker = "".join(f'<a href="{{p}}{quote(a["url"])}">{e(a["title"])}</a><span aria-hidden="true">✦</span>' for a in ARTICLES[:10])

    pillar_icons = ["eye", "target", "nodes"]

    def body(p):
        tick = ticker.replace("{p}", p)
        pillars = "".join(f"""<article class="pillar" data-reveal data-spotlight>
      <div class="pillar__top"><span class="pillar__n">{i + 1:02d}</span>{icon(pillar_icons[i % 3], 28)}</div>
      <h2 class="pillar__title">{e(x['naslov'])}</h2>
      <p>{e(x['besedilo'])}</p>
    </article>""" for i, x in enumerate(P["stebri"]))
        others = [ev for ev in UPCOMING if ev is not FEATURED] or FINISHED[:1]
        upcoming_cards = "".join(event_card(p, ev, big=len(others) == 1) for ev in others)
        news = article_card(p, latest[0], "card--feature", eager=False) + "".join(article_card(p, a) for a in latest[1:7])
        aiweek_block = ""
        if FEATURED and FEATURED["upcoming"]:
            AIWEEK = FEATURED
            words = AIWEEK["title"].split()
            if len(words) > 1 and re.fullmatch(r"\d{4}", words[-1]):
                big_title = f'{e(" ".join(words[:-1]))} <span>{words[-1]}</span>'
                cd_label = "Do začetka " + " ".join(words[:-1])
            else:
                big_title = e(AIWEEK["title"])
                cd_label = "Do začetka"
            title_cls = " aiweek__title--long" if len(AIWEEK["title"]) > 18 else ""
            days = ""
            if AIWEEK.get("program"):
                days = '<ol class="aiweek__days">' + "".join(f'<li><span class="aiweek__dn">{i + 1:02d}</span><span class="aiweek__dl">{e(d["label"])}</span><span class="aiweek__dd">{e(d["description"])}</span></li>' for i, d in enumerate(AIWEEK['program'])) + "</ol>"
            aiweek_block = f"""
<section class="aiweek theme-dark" aria-labelledby="aiweek-title">
  <div class="aiweek__glow" aria-hidden="true"><div class="eclipse eclipse--sm"><span></span></div></div>
  <div class="container aiweek__grid">
    <div class="aiweek__copy" data-reveal>
      <p class="eyebrow eyebrow--accent">Dogodki · {AIWEEK['eyebrow']}</p>
      <h2 id="aiweek-title" class="aiweek__title{title_cls}">{big_title}</h2>
      <div class="aiweek__lead">{AIWEEK['lead']}</div>
      <ul class="aiweek__facts">
        <li>{icon('calendar', 18)}<span>{date_range(AIWEEK)}</span></li>
        <li>{icon('pin', 18)}<span>{e(AIWEEK['fact'].get('Lokacija', {}).get('value', ''))}</span></li>
        <li>{icon('ticket', 18)}<span>{e(AIWEEK['fact'].get('Cena', {}).get('value', ''))}</span></li>
      </ul>
      <div class="btn-row">
        <a class="btn btn--primary" href="{href(p, AIWEEK['url'])}" data-magnetic>{'Program in prijava' if AIWEEK.get('program') else 'Več in prijava'} {icon('arrow', 16)}</a>
        <a class="btn btn--ghost" href="{href(p, 'dogodki/')}">Vsi dogodki</a>
      </div>
    </div>
    <div class="aiweek__side" data-reveal>
      {countdown_block(AIWEEK['start'].isoformat(), cd_label)}
      {days}
    </div>
  </div>
</section>"""
        return f"""
<section class="hero theme-dark" aria-labelledby="hero-title">
  <canvas class="hero__canvas" data-network aria-hidden="true"></canvas>
  <div class="hero__eclipse" aria-hidden="true"><div class="eclipse"><span></span></div></div>
  <div class="container hero__inner">
    <p class="eyebrow hero__eyebrow" data-hero-in>Zavod AI-D · Ljubljana</p>
    <h1 id="hero-title" class="hero__title" data-hero-in><span class="line"><span>{e(P['naslov_1'])}</span></span> <span class="line"><em>{e(P['naslov_2'])}</em></span></h1>
    <p class="hero__tagline" data-hero-in>{e(P['slogan'])}</p>
    <div class="btn-row" data-hero-in>
      <a class="btn btn--primary btn--lg" href="{href(p, 'clanstvo/')}" data-magnetic>Pridruži se nam {icon('arrow-up-right', 18)}</a>
      <a class="btn btn--ghost btn--lg" href="{href(p, 'kontakt/')}">Spoznajmo se</a>
    </div>
  </div>
  <div class="hero__foot">
    <div class="container hero__meta" data-hero-in>
      <span>Tehnologija.</span><span class="accent">Znanje.</span><span>Skupnost.</span>
      <a class="hero__scroll" href="#o-nas" aria-label="Pomakni se navzdol">{icon('arrow-down', 18)}</a>
    </div>
    <div class="ticker" aria-label="Zadnje novice"><div class="ticker__track">{tick}{tick}</div></div>
  </div>
</section>

<section class="intro" id="o-nas" aria-label="O zavodu">
  <div class="container intro__grid">
    <p class="eyebrow" data-reveal>Kdo smo</p>
    <p class="intro__text" data-scrolltext>{e(P['uvod'])}</p>
  </div>
</section>

<section class="pillars" aria-label="Vizija, cilji in aktivnosti">
  <div class="container pillars__grid">
    {pillars}
  </div>
</section>

{aiweek_block}
<section class="section" aria-labelledby="ev-title">
  <div class="container">
    {section_head('Koledar', '<span id="ev-title">Dogodki</span>', (href(p, 'dogodki/'), 'Vsi dogodki'))}
    <div class="ecards">{upcoming_cards}</div>
  </div>
</section>

<section class="section section--tight" aria-labelledby="news-title">
  <div class="container">
    {section_head('Aktualno', '<span id="news-title">Novice</span>', (href(p, 'novice/'), f'Vse novice ({len(ARTICLES)})'))}
    <div class="bento">{news}</div>
  </div>
</section>

<section class="cta" aria-labelledby="cta-title">
  <div class="container">
    <div class="cta__box theme-dark" data-reveal data-spotlight>
      <div class="cta__glow" aria-hidden="true"></div>
      <p class="eyebrow eyebrow--accent">Članstvo</p>
      <h2 id="cta-title" class="cta__title">{nowrap_aid(e(P['cta_naslov']))} <em>{e(P['cta_poudarek'])}</em></h2>
      <p class="cta__text">{e(P['cta_besedilo'])}</p>
      <div class="btn-row">
        <a class="btn btn--primary btn--lg" href="{href(p, 'clanstvo/')}" data-magnetic>Pridruži se nam {icon('arrow-up-right', 18)}</a>
        <a class="btn btn--ghost btn--lg" href="{href(p, 'kontakt/')}">Spoznajmo se</a>
      </div>
    </div>
  </div>
</section>"""

    ld = {"@context": "https://schema.org", "@type": "Organization", "name": CO["ime"], "alternateName": "Zavod za razvoj umetne inteligence",
          "url": SITE_URL, "email": CO["email"], "logo": SITE_URL + img_url(EXTRAS["logo"]),
          "address": {"@type": "PostalAddress", "streetAddress": CO["naslov"].split(",")[0], "addressCountry": "SI"},
          "taxID": CO["davcna"], "identifier": CO["maticna"]}
    write("", "Zavod AI-D — Zavod za razvoj umetne inteligence", P["uvod"], body, section="", jsonld=ld, body_class="page-home")
    SEARCH.append({"t": "Domov", "u": "", "k": "Stran", "x": "Zavod za razvoj umetne inteligence"})


def build_news():
    years = sorted({a["d"].year for a in ARTICLES}, reverse=True)
    counts = {k: sum(1 for a in ARTICLES if a["topic"] == k) for k in TOPICS}

    def body(p):
        chips = f'<button class="chip is-active" type="button" data-topic-chip="">Vse <span>{len(ARTICLES)}</span></button>' + "".join(
            f'<button class="chip" type="button" data-topic-chip="{k}">{v} <span>{counts[k]}</span></button>' for k, v in TOPICS.items())
        ychips = '<button class="chip is-active" type="button" data-year-chip="">Vsa leta</button>' + "".join(
            f'<button class="chip" type="button" data-year-chip="{y}">{y}</button>' for y in years)
        cards = "".join(article_card(p, a) for a in ARTICLES)
        return f"""
<section class="page-hero">
  <div class="container">
    <p class="eyebrow" data-reveal>Aktualno</p>
    <h1 class="page-title" data-reveal>Novice</h1>
    <p class="page-lead" data-reveal><span class="num">{len(ARTICLES)}</span> objav · zadnja {d_long(ARTICLES[0]['d'])}</p>
  </div>
</section>
<div class="news-tools" data-news-tools>
  <div class="container news-tools__inner">
    <label class="field-search">{icon('search', 18)}<span class="sr-only">Išči med novicami</span><input type="search" placeholder="Išči med novicami …" data-news-q autocomplete="off"></label>
    <div class="chips" role="group" aria-label="Tema">{chips}</div>
    <div class="chips" role="group" aria-label="Leto">{ychips}</div>
    <div class="view-toggle" role="group" aria-label="Prikaz">
      <button type="button" class="is-active" data-view="grid" aria-label="Mreža" aria-pressed="true">{icon('grid', 18)}</button>
      <button type="button" data-view="list" aria-label="Seznam" aria-pressed="false">{icon('list', 18)}</button>
    </div>
  </div>
</div>
<section class="section section--news">
  <div class="container">
    <p class="news-count" aria-live="polite" data-news-count></p>
    <div class="news-grid" data-news-grid>{cards}</div>
    <div class="news-empty" data-news-empty hidden><p>Ni zadetkov za izbrane filtre.</p><button class="btn btn--ghost" type="button" data-news-reset>Počisti filtre</button></div>
    <div class="news-more"><button class="btn btn--ghost btn--lg" type="button" data-news-more>Naloži več {icon('plus', 16)}</button></div>
  </div>
</section>"""
    write("novice/", "Novice", "Novice Zavoda AI-D o umetni inteligenci v Sloveniji in po svetu.", body, section="novice/", body_class="page-news")
    SEARCH.append({"t": "Novice", "u": "novice/", "k": "Stran", "x": f"Vseh {len(ARTICLES)} objav"})


def build_articles():
    for i, a in enumerate(ARTICLES):
        newer = ARTICLES[i - 1] if i > 0 else None
        older = ARTICLES[i + 1] if i + 1 < len(ARTICLES) else None
        related = [x for x in ARTICLES if x is not a and set(x["tags"]) & set(a["tags"]) - {"AI", "UI", "umetna inteligenca"}][:3]
        for x in ARTICLES:
            if len(related) >= 3:
                break
            if x is not a and x not in related and x["topic"] == a["topic"]:
                related.append(x)

        def body(p, a=a, newer=newer, older=older, related=related):
            tags = "".join(f'<a class="tag" href="{href(p, "novice/")}?q={quote(t)}">#{e(t)}</a>' for t in a["tags"])
            cover = f'<figure class="post__cover" data-reveal>{img_tag(p, a["image"], sizes="(min-width: 1200px) 1200px, 100vw", eager=True)}</figure>' if a["image"] else ""
            nav = ""
            if older or newer:
                nav = '<nav class="post__nav" aria-label="Sosednji članki">'
                nav += (f'<a class="post__nav-prev" href="{href(p, older["url"])}"><span>{icon("arrow-left", 16)} Starejši</span><strong>{e(older["title"])}</strong></a>' if older else '<span></span>')
                nav += (f'<a class="post__nav-next" href="{href(p, newer["url"])}"><span>Novejši {icon("arrow", 16)}</span><strong>{e(newer["title"])}</strong></a>' if newer else '<span></span>')
                nav += "</nav>"
            share = f"""<div class="share" data-share data-title="{e(a['title'])}">
  <span class="share__label">Deli</span>
  <button type="button" class="share__btn" data-share-native aria-label="Deli">{icon('share', 18)}</button>
  <a class="share__btn" data-share-to="linkedin" href="#" aria-label="Deli na LinkedIn">{icon('linkedin', 18)}</a>
  <a class="share__btn" data-share-to="facebook" href="#" aria-label="Deli na Facebooku">{icon('facebook', 18)}</a>
  <a class="share__btn" data-share-to="x" href="#" aria-label="Deli na X">{icon('x', 18)}</a>
  <a class="share__btn" data-share-to="mail" href="#" aria-label="Pošlji po e-pošti">{icon('mail', 18)}</a>
  <button type="button" class="share__btn" data-copy-link aria-label="Kopiraj povezavo">{icon('link', 18)}</button>
</div>"""
            rel = "".join(article_card(p, x) for x in related)
            return f"""
<div class="progress" aria-hidden="true"><span data-progress></span></div>
<article class="post" data-article>
  <header class="post__head container">
    <a class="back-link" href="{href(p, 'novice/')}">{icon('arrow-left', 16)} Vse novice</a>
    <p class="post__meta" data-reveal><time datetime="{a['date']}">{d_long(a['d'])}</time><span aria-hidden="true">·</span><span>{icon('clock', 15)} {a['mins']} min branja</span><span aria-hidden="true">·</span><span>{TOPICS[a['topic']]}</span></p>
    <h1 class="post__title" data-reveal>{e(a['title'])}</h1>
  </header>
  <div class="container">{cover}</div>
  <div class="container post__layout">
    <aside class="post__aside">{share}</aside>
    <div class="prose" data-prose>{render_content(a['html'], p)}</div>
  </div>
  <footer class="container post__foot">
    {f'<div class="post__tags">{tags}</div>' if tags else ''}
    {nav}
  </footer>
</article>
<section class="section section--tight related" aria-labelledby="rel-title">
  <div class="container">
    {section_head('Preberite še', '<span id="rel-title">Več novic</span>', (href(p, 'novice/'), 'Vse novice'))}
    <div class="news-grid news-grid--3">{rel}</div>
  </div>
</section>"""

        ld = {"@context": "https://schema.org", "@type": "NewsArticle", "headline": a["title"], "datePublished": a["date"], "dateModified": a["modified"],
              "image": [SITE_URL + img_url(a["image"])] if a["image"] else [], "inLanguage": "sl",
              "publisher": {"@type": "Organization", "name": "Zavod AI-D", "url": SITE_URL}, "mainEntityOfPage": SITE_URL + quote(a["url"])}
        write(a["url"], a["title"], a["excerpt"], body, section="novice/", image=a["image"], kind="article", jsonld=ld, body_class="page-article")
        SEARCH.append({"t": a["title"], "u": a["url"], "k": "Novica", "d": d_short(a["d"]), "x": a["excerpt"][:180],
                       "b": plain(a["html"])[:9000]})


def build_events_index():
    def body(p):
        ordered = sorted(UPCOMING, key=lambda ev: ev["start"])  # chronological: the soonest event first
        up = "".join(event_card(p, ev, big=True) for ev in ordered)
        past = [{"url": ev["url"], "image": ev["image"], "title": ev["title"], "d": ev["start"]} for ev in FINISHED] + ARCHIVE
        arch = "".join(archive_card(p, x) for x in past)
        return f"""
<section class="page-hero">
  <div class="container">
    <p class="eyebrow" data-reveal>Koledar</p>
    <h1 class="page-title" data-reveal>Dogodki</h1>
  </div>
</section>
<section class="section section--flush">
  <div class="container">
    <h2 class="sub-title" data-reveal>Prihajajoči dogodki</h2>
    <div class="ecards ecards--index">{up or '<p class="muted">Trenutno ni napovedanih dogodkov.</p>'}</div>
  </div>
</section>
<section class="section">
  <div class="container">
    <h2 class="sub-title" data-reveal>Pretekli dogodki</h2>
    <div class="acards">{arch}</div>
  </div>
</section>"""
    write("dogodki/", "Dogodki", "Dogodki, delavnice in konference Zavoda AI-D.", body, section="dogodki/", body_class="page-events")
    SEARCH.append({"t": "Dogodki", "u": "dogodki/", "k": "Stran", "x": "Prihajajoči in pretekli dogodki"})


def ics_for(ev):
    fmt = lambda d: d.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    loc = ev["fact"].get("Lokacija", {}).get("value", "")
    desc = plain(ev["lead"]) + " " + SITE_URL + quote(ev["url"])
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Zavod AI-D//SL", "CALSCALE:GREGORIAN", "BEGIN:VEVENT",
             f"UID:{ev['slug'].replace('/', '-')}@ai-d.si", f"DTSTAMP:{fmt(TODAY)}", f"DTSTART:{fmt(ev['start'])}", f"DTEND:{fmt(ev['end'])}",
             f"SUMMARY:{ev['title']}", f"LOCATION:{loc}", f"DESCRIPTION:{desc}", f"URL:{SITE_URL}{quote(ev['url'])}", "END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(l.replace(",", "\\,") if l.startswith(("LOCATION", "DESCRIPTION", "SUMMARY")) else l for l in lines) + "\r\n"


def gcal_link(ev):
    fmt = lambda d: d.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    loc = ev["fact"].get("Lokacija", {}).get("value", "")
    return ("https://calendar.google.com/calendar/render?action=TEMPLATE&text=" + quote(ev["title"]) +
            f"&dates={fmt(ev['start'])}/{fmt(ev['end'])}&location=" + quote(loc) + "&details=" + quote(SITE_URL + quote(ev["url"])))


def registration(p, ev):
    r = ev["registration"]
    title = r.get("title") or "Prijava"
    if ev["upcoming"] and not r.get("open"):
        return ""  # registration switched off in the editor
    if not ev["upcoming"]:
        return f"""<section class="register" id="prijava" aria-labelledby="reg-title">
  <div class="container register__grid">
    <div><p class="eyebrow">Udeležite se</p><h2 id="reg-title" class="sec-title">{e(title)}</h2></div>
    <div class="register__closed" data-reveal><p class="register__closed-title">{icon('check', 22)} {e(r.get('closed_title') or 'Prijave so zaključene')}</p><p>{e(r.get('closed_text') or 'Prijava na ta dogodek ni več mogoča. Prijave se najpozneje zaprejo ob začetku dneva dogodka.')}</p>
      <a class="btn btn--ghost" href="{href(p, 'dogodki/')}">Prihajajoči dogodki {icon('arrow', 16)}</a></div>
  </div>
</section>"""
    member = ""
    if r.get("member_label"):
        member = f"""<div class="member-toggle" data-member>
  <p class="member-toggle__note">{e(r['price_note'])}</p>
  <label class="switch"><input type="checkbox" name="clan" value="da" data-member-input><span class="switch__track"><span class="switch__thumb"></span></span><span>{e(r['member_label'])}</span></label>
  <p class="member-toggle__price">Cena prijave: <strong data-price data-price-full="{e(r['price'])}" data-price-member="brezplačno">{e(r['price'])}</strong></p>
</div>"""
    return f"""<section class="register" id="prijava" aria-labelledby="reg-title">
  <div class="container register__grid">
    <div class="register__intro" data-reveal>
      <p class="eyebrow">Udeležite se</p>
      <h2 id="reg-title" class="sec-title">{e(title)}</h2>
      <p>{e(r.get('intro') or '')}</p>
      <ul class="register__facts">
        <li>{icon('calendar', 18)}<span>{e(ev['fact']['Termin']['value'])}<br><small>{e(ev['fact']['Termin']['extra'] or '')}</small></span></li>
        <li>{icon('pin', 18)}<span>{e(ev['fact'].get('Lokacija', {}).get('value', ''))}</span></li>
        <li>{icon('ticket', 18)}<span>{e(ev['fact'].get('Cena', {}).get('value', ''))}</span></li>
      </ul>
    </div>
    <form class="form card-surface" data-form="event" data-event="{e(ev['slug'])}" data-subject="Prijava na dogodek: {e(ev['title'])}" novalidate data-reveal>
      <div class="form__grid">
        <div class="field"><label for="f-ime">Ime <span aria-hidden="true">*</span></label><input id="f-ime" name="ime" type="text" autocomplete="given-name" required maxlength="120"></div>
        <div class="field"><label for="f-priimek">Priimek <span aria-hidden="true">*</span></label><input id="f-priimek" name="priimek" type="text" autocomplete="family-name" required maxlength="120"></div>
        <div class="field"><label for="f-email">E-pošta <span aria-hidden="true">*</span></label><input id="f-email" name="email" type="email" autocomplete="email" required maxlength="191"></div>
        <div class="field"><label for="f-tel">Telefon <span aria-hidden="true">*</span></label><input id="f-tel" name="telefon" type="tel" autocomplete="tel" required maxlength="60"></div>
        <div class="field field--wide"><label for="f-org">Organizacija <span aria-hidden="true">*</span></label><input id="f-org" name="organizacija" type="text" autocomplete="organization" required maxlength="191"></div>
        <div class="field field--wide"><label for="f-op">Opomba ali posebne potrebe</label><textarea id="f-op" name="opomba" rows="3" maxlength="5000"></textarea></div>
      </div>
      {member}
      <input class="hp" type="text" name="website" tabindex="-1" autocomplete="off" aria-hidden="true">
      <label class="check"><input type="checkbox" name="soglasje" value="da" required><span>Strinjam se z obdelavo navedenih podatkov za namen prijave in izvedbe dogodka. *</span></label>
      <div class="form__actions"><button class="btn btn--primary btn--lg" type="submit" data-magnetic>Oddaj prijavo {icon('arrow', 16)}</button><p class="form__req">* Obvezno polje</p></div>
      <div class="form__done" data-form-done hidden><p class="form__done-title">{icon('check', 22)} Hvala za prijavo!</p><p>Potrdilo o prijavi boste prejeli po e-pošti.</p></div>
    </form>
  </div>
</section>"""


def program_section(p, ev):
    tabs, panels, dialogs = [], [], []
    for di, day in enumerate(ev["program"]):
        sel = di == 0
        tabs.append(f'<button class="ptab{" is-active" if sel else ""}" role="tab" type="button" id="ptab-{di}" aria-controls="ppanel-{di}" aria-selected="{"true" if sel else "false"}" tabindex="{0 if sel else -1}"><span class="ptab__n">0{di + 1}</span><span>{e(day["label"])}</span></button>')
        rows = []
        for si, s in enumerate(day["items"]):
            time = s["time"] if s["time"] and s["time"] != "—" else ""
            thumb = f'<span class="session__thumb">{img_tag(p, s["image"], sizes="96px", variant="card")}</span>' if s["image"] else f'<span class="session__thumb session__thumb--empty" aria-hidden="true">{initials(s["title"])}</span>'
            inner = f'<span class="session__time">{e(time) or "<span class=dot></span>"}</span>{thumb}<span class="session__who"><strong>{e(s["title"])}</strong><span>{e(s["subtitle"])}</span></span>'
            if s["html"]:
                did = f"sp-{di}-{si}"
                rows.append(f'<li class="session" data-reveal><button class="session__btn" type="button" data-dialog-open="{did}" aria-haspopup="dialog">{inner}<span class="session__plus">{icon("plus", 18)}</span></button></li>')
                desc = render_content(re.sub(r"<br>\s*", " ", s["html"]), p)  # bios were pasted with hard line breaks
                photo = f'<figure class="speaker__photo">{img_tag(p, s["image"], sizes="(min-width: 800px) 360px, 100vw")}</figure>' if s["image"] else ""
                dialogs.append(f"""<dialog class="speaker" id="{did}" aria-labelledby="{did}-t">
  <div class="speaker__box">
    <button class="speaker__close" type="button" data-dialog-close aria-label="Zapri">{icon('close', 20)}</button>
    {photo}
    <div class="speaker__body">
      <p class="eyebrow">{e(day['label'])}{' · ' + e(time) if time else ''}</p>
      <h3 id="{did}-t" class="speaker__name">{e(s['title'])}</h3>
      <p class="speaker__sub">{e(s['subtitle'])}</p>
      <div class="prose prose--sm">{desc}</div>
    </div>
  </div>
</dialog>""")
            else:
                rows.append(f'<li class="session session--static" data-reveal><div class="session__btn">{inner}</div></li>')
        locs = ""
        if day.get("locations"):
            items = "".join(
                f'<li><button type="button" class="loc{" is-active" if li == 0 else ""}" data-map-q="{e(l["name"] + ", " + l["address"])}"><span class="loc__n">{li + 1}</span><span><strong>{e(l["name"])}</strong><span>{e(l["address"])}</span></span></button>'
                f'<a class="loc__ext" href="https://www.google.com/maps/search/?api=1&query={quote(l["name"] + ", " + l["address"])}" target="_blank" rel="noopener" aria-label="Odpri {e(l["name"])} v Google Maps">{icon("arrow-up-right", 16)}</a></li>'
                for li, l in enumerate(day["locations"]))
            first = day["locations"][0]
            locs = f"""<div class="locations">
  <h3 class="locations__title">{icon('map', 18)} Lokacije</h3>
  <ul class="locations__list">{items}</ul>
  <div class="map" data-map data-map-q="{e(first['name'] + ', ' + first['address'])}">
    <button class="map__load" type="button" data-map-load>{icon('pin', 22)}<span>Prikaži zemljevid</span><small>Zemljevid naloži Google Maps.</small></button>
  </div>
</div>"""
        panels.append(f"""<div class="ppanel{' is-active' if sel else ''}" role="tabpanel" id="ppanel-{di}" aria-labelledby="ptab-{di}"{'' if sel else ' hidden'}>
  <p class="ppanel__desc">{e(day['description'])}</p>
  <div class="ppanel__grid"><ol class="sessions">{''.join(rows)}</ol>{locs}</div>
</div>""")
    return f"""<section class="program" id="program" aria-labelledby="program-title">
  <div class="container">
    <div class="sec-head" data-reveal><div><p class="eyebrow">Potek dogodka</p><h2 id="program-title" class="sec-title">Program</h2></div><p class="muted program__hint">Kliknite predavatelja za opis.</p></div>
    <div class="ptabs" role="tablist" aria-label="Dnevi programa" data-tabs>{''.join(tabs)}</div>
    {''.join(panels)}
  </div>
  {''.join(dialogs)}
</section>"""


def themes_section(ev):
    items = "".join(
        f'<li class="theme-card" data-reveal data-spotlight><span class="theme-card__n">{i + 1:02d}</span><h3>{e(t["title"])}</h3><p>{e(t.get("text", ""))}</p></li>'
        for i, t in enumerate(ev["themes"]))
    note = f'<p class="concept__note">{e(ev["themes_note"])}</p>' if ev.get("themes_note") else ""
    return f"""<section class="section concept" aria-labelledby="concept-title">
  <div class="container">
    {section_head('Zasnova', '<span id="concept-title">' + e(ev.get("themes_title") or "Tematski sklopi") + '</span>')}
    <ol class="theme-cards">{items}</ol>
    {note}
  </div>
</section>"""


def build_event(ev):
    has_themes = bool(ev.get("themes"))

    def body(p):
        hero_img = img_tag(p, ev["image"], sizes="100vw", eager=True)
        loc = ev["fact"].get("Lokacija", {}).get("value", "")
        cd = countdown_block(ev["start"].isoformat()) if ev["upcoming"] else ""
        status = '<span class="pill pill--live" data-status>Prihajajoči</span>' if ev["upcoming"] else '<span class="pill" data-status>Zaključen</span>'
        termin = ev["fact"]["Termin"]
        cal = ""
        if ev["upcoming"]:
            cal = f"""<div class="facts__actions">
  {f'<a class="btn btn--primary" href="#prijava">Prijava {icon("arrow-down", 16)}</a>' if ev["registration"].get("open") else ''}
  <a class="btn btn--ghost" href="dogodek.ics" download>{icon('calendar', 16)} Dodaj v koledar</a>
  <a class="btn btn--ghost" href="{gcal_link(ev)}" target="_blank" rel="noopener">Google Koledar {icon('arrow-up-right', 14)}</a>
</div>"""
        content = render_content(ev["html"], p)
        return f"""
<section class="ev-hero theme-dark" data-event-end="{ev['end'].isoformat()}">
  <div class="ev-hero__bg" aria-hidden="true">{hero_img}</div>
  <div class="container ev-hero__inner">
    <a class="back-link" href="{href(p, 'dogodki/')}">{icon('arrow-left', 16)} Vsi dogodki</a>
    <p class="ev-hero__eyebrow"><span class="eyebrow eyebrow--accent">{e(ev['eyebrow'])}</span>{status}</p>
    <h1 class="ev-hero__title">{e(ev['title'])}</h1>
    <div class="ev-hero__lead">{ev['lead']}</div>
    {cd}
  </div>
</section>
<section class="facts" aria-label="Podatki o dogodku">
  <div class="container">
    <dl class="facts__list" data-reveal>
      <div><dt>{icon('calendar', 18)} Termin</dt><dd>{e(termin['value'])}<span>{e(termin['extra'] or '')}</span></dd></div>
      <div><dt>{icon('pin', 18)} Lokacija</dt><dd>{e(loc)}</dd></div>
      <div><dt>{icon('ticket', 18)} Cena</dt><dd>{e(ev['fact'].get('Cena', {}).get('value', ''))}</dd></div>
    </dl>
    {cal}
  </div>
</section>
<section class="section section--flush">
  <div class="container"><div class="prose prose--event" data-prose>{content}</div></div>
</section>
{themes_section(ev) if has_themes else ''}
{program_section(p, ev) if ev.get('program') else ''}
{registration(p, ev)}"""

    s = ev["start"]
    ld = {"@context": "https://schema.org", "@type": "Event", "name": ev["title"], "startDate": ev["start"].isoformat(), "endDate": ev["end"].isoformat(),
          "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode", "eventStatus": "https://schema.org/EventScheduled",
          "location": {"@type": "Place", "name": ev["fact"].get("Lokacija", {}).get("value", ""), "address": ev["fact"].get("Lokacija", {}).get("value", "")},
          "image": [SITE_URL + img_url(ev["image"])], "description": plain(ev["lead"]),
          "organizer": {"@type": "Organization", "name": "Zavod AI-D", "url": SITE_URL}}
    write(ev["url"], ev["title"], plain(ev["lead"]) or plain(ev["html"])[:200], body, section="dogodki/", image=ev["image"], kind="article", jsonld=ld, body_class="page-event")
    open(os.path.join(OUT, ev["slug"], "dogodek.ics"), "w", encoding="utf-8", newline="").write(ics_for(ev))
    speakers = " ".join(f'{s["title"]} {s["subtitle"]}' for d in (ev.get("program") or []) for s in d["items"])
    SEARCH.append({"t": ev["title"], "u": ev["url"], "k": "Dogodek", "d": d_short(s), "x": plain(ev["lead"])[:180], "b": (plain(ev["html"]) + " " + speakers)[:2400]})


def build_archive_events():
    for x in ARCHIVE:
        def body(p, x=x):
            cover = f'<figure class="post__cover" data-reveal>{img_tag(p, x["image"], sizes="(min-width: 1200px) 1200px, 100vw", eager=True)}</figure>' if x["image"] else ""
            date = f'<time datetime="{x["d"].date().isoformat()}">{d_long(x["d"])}</time><span aria-hidden="true">·</span>' if x.get("d") else ""
            return f"""
<div class="progress" aria-hidden="true"><span data-progress></span></div>
<article class="post" data-article>
  <header class="post__head container">
    <a class="back-link" href="{href(p, 'dogodki/')}">{icon('arrow-left', 16)} Vsi dogodki</a>
    <p class="post__meta" data-reveal>{date}<span>Pretekli dogodek</span></p>
    <h1 class="post__title" data-reveal>{e(x['title'])}</h1>
  </header>
  <div class="container">{cover}</div>
  <div class="container post__layout post__layout--solo">
    <div class="prose" data-prose>{render_content(x['html'], p)}</div>
  </div>
</article>
<section class="section section--tight" aria-labelledby="more-ev">
  <div class="container">
    {section_head('Koledar', '<span id="more-ev">Prihajajoči dogodki</span>', (href(p, 'dogodki/'), 'Vsi dogodki'))}
    <div class="ecards">{''.join(event_card(p, ev) for ev in UPCOMING[:2])}</div>
  </div>
</section>"""
        write(x["url"], x["title"], plain(x["html"])[:200], body, section="dogodki/", image=x["image"], kind="article", body_class="page-article")
        SEARCH.append({"t": x["title"], "u": x["url"], "k": "Dogodek", "d": d_short(x["d"]) if x.get("d") else "", "x": plain(x["html"])[:180], "b": plain(x["html"])[:1600]})


def mentions(name):
    """How many news items the site search finds for this person's surname."""
    last = fold(name.split()[-1])
    return sum(1 for a in ARTICLES if last in fold(" ".join([a["title"], a["excerpt"], " ".join(a["tags"]), plain(a["html"])[:9000]])))


def objav(c):
    return "objava" if c % 100 == 1 else "objavi" if c % 100 == 2 else "objave" if c % 100 in (3, 4) else "objav"


BENEFIT_ICONS = ["chart", "users", "globe", "spark", "badge"]


def build_about():
    P = PAGES["o_zavodu"]
    M = PAGES["clanstvo"]

    def body(p):
        members = ""
        for n in P["svet_clani"]:
            c = mentions(n)
            more = f'<a class="member__more" href="{href(p, "novice/")}?q={quote(n.split()[-1])}">{c} {objav(c)} {icon("arrow", 14)}</a>' if c else ""
            members += f'<li class="member" data-reveal data-spotlight><span class="member__avatar" aria-hidden="true">{initials(n)}</span><span class="member__name">{e(n)}</span>{more}</li>'
        goals = "".join(f'<li data-reveal><span class="numbered__n">{i + 1:02d}</span><p>{e(g)}</p></li>' for i, g in enumerate(P["cilji"]))
        topics = "".join(f"<li>{e(t)}</li>" for t in P["delovanje_podrocja"])
        benefits = "".join(f'<li data-reveal data-spotlight>{icon(BENEFIT_ICONS[i % 5], 24)}<p>{e(b)}</p></li>' for i, b in enumerate(M["ugodnosti"]))
        organs = "".join(f'<li data-reveal><span class="organs__n">{i + 1:02d}</span><div><strong>{e(o["naziv"])}</strong><p>{e(o["opis"])}</p></div></li>' for i, o in enumerate(P["organi"]))
        quote_block = ""
        if P.get("citat"):
            quote_block = f"""<figure class="quote" data-reveal>
        <blockquote><p>»{e(P['citat'])}«</p></blockquote>
        <figcaption><span class="member__avatar" aria-hidden="true">{initials(P['citat_avtor'])}</span><span><strong>{e(P['citat_avtor'])}</strong>{e(P['citat_vloga'])}</span></figcaption>
      </figure>"""
        return f"""
<section class="page-hero page-hero--about">
  <div class="container">
    <p class="eyebrow" data-reveal>O zavodu</p>
    <h1 class="page-title" data-reveal>Zavod <em>AI-D</em></h1>
  </div>
</section>
<div class="container doc">
  <nav class="toc" aria-label="Vsebina strani" data-toc>
    <p class="toc__title">Vsebina</p>
    <ol>
      <li><a href="#o-zavodu">O zavodu</a></li>
      <li><a href="#cilji">Glavni cilji</a></li>
      <li><a href="#delovanje">Delovanje</a></li>
      <li><a href="#za-clane">Za člane</a></li>
      <li><a href="#vizija">Vizija in poslanstvo</a></li>
      <li><a href="#strokovni-svet">Strokovni svet</a></li>
      <li><a href="#statut">Statut zavoda</a></li>
      <li><a href="#organi">Organi zavoda</a></li>
      <li><a href="#podatki">Podatki zavoda</a></li>
    </ol>
  </nav>
  <div class="doc__body">
    <section id="o-zavodu" class="doc__sec">
      <p class="lead" data-reveal>{e(P['uvod'])}</p>
    </section>

    <section id="cilji" class="doc__sec">
      <h2 class="doc__h" data-reveal>{e(P['cilji_naslov'])}</h2>
      <ol class="numbered">{goals}</ol>
    </section>

    <section id="delovanje" class="doc__sec">
      <h2 class="doc__h" data-reveal>Delovanje</h2>
      <p data-reveal>{e(P['delovanje'])}</p>
      <div class="org" data-reveal aria-label="Shema delovanja zavoda">
        <div class="org__core"><span class="org__logo">AI–D</span><span>svetovalno-izobraževalni center</span></div>
        <div class="org__bodies">
          <div class="org__body">{icon('users', 22)}<strong>Strokovni svet</strong></div>
          <div class="org__body">{icon('flask', 22)}<strong>Raziskovalno-razvojni odbor</strong></div>
          <div class="org__body">{icon('nodes', 22)}<strong>Tematske delovne skupine</strong></div>
        </div>
        <ul class="org__topics">{topics}</ul>
      </div>
    </section>

    <section id="za-clane" class="doc__sec">
      <h2 class="doc__h" data-reveal>{e(M['ugodnosti_naslov'])}</h2>
      <ul class="benefits">{benefits}</ul>
      <a class="link-arrow" href="{href(p, 'clanstvo/')}" data-reveal>Postani član {icon('arrow', 16)}</a>
    </section>

    <section id="vizija" class="doc__sec">
      <h2 class="doc__h" data-reveal>Vizija in poslanstvo</h2>
      <div class="vm">
        <article class="vm__card" data-reveal data-spotlight><p class="eyebrow">Vizija Zavoda AI-D</p><p>{e(P['vizija'])}</p></article>
        <article class="vm__card" data-reveal data-spotlight><p class="eyebrow">Poslanstvo Zavoda AI-D</p><p>{e(P['poslanstvo'])}</p></article>
      </div>
    </section>

    <section id="strokovni-svet" class="doc__sec">
      <h2 class="doc__h" data-reveal>Strokovni svet</h2>
      <p data-reveal>{e(P['svet_opis'])}</p>
      <h3 class="doc__h3" data-reveal>Člani strokovnega sveta:</h3>
      <ul class="members">{members}</ul>
      {quote_block}
    </section>

    <section id="statut" class="doc__sec">
      <h2 class="doc__h" data-reveal>Statut zavoda</h2>
      <p data-reveal>{e(P['statut'])}</p>
    </section>

    <section id="organi" class="doc__sec">
      <h2 class="doc__h" data-reveal>Organi zavoda</h2>
      <p data-reveal>Organi Zavoda AI-D vključujejo:</p>
      <ol class="organs">{organs}</ol>
    </section>

    <section id="podatki" class="doc__sec">
      <h2 class="doc__h" data-reveal>Podatki zavoda</h2>
      {company_data()}
    </section>
  </div>
</div>"""
    write("o-zavodu/", "O zavodu", P["uvod"][:200], body, section="o-zavodu/", body_class="page-about")
    SEARCH.append({"t": "O zavodu", "u": "o-zavodu/", "k": "Stran", "x": "Cilji, vizija in poslanstvo, strokovni svet, organi in podatki zavoda",
                   "b": "Strokovni svet " + " ".join(P["svet_clani"]) + " statut organi zavoda matična davčna transakcijski račun"})


def company_data():
    rows = [("Ime", CO["ime"], False), ("Sedež", CO["naslov"], True), ("E-naslov", CO["email"], True),
            ("Matična številka", CO["maticna"], True), ("Davčna številka", CO["davcna"], True), ("Transakcijski račun", CO["trr"], True)]
    out = []
    for k, v, c in rows:
        if not v:
            continue
        val = f'<a href="mailto:{e(v)}">{e(v)}</a>' if "@" in v else e(v)
        btn = f'<button type="button" class="copy-btn" data-copy="{e(v)}" aria-label="Kopiraj: {e(k)}">{icon("copy", 16)}<span>Kopiraj</span></button>' if c else ""
        out.append(f'<div class="data__row"><dt>{k}:</dt><dd><span class="data__val">{val}</span>{btn}</dd></div>')
    return f'<dl class="data" data-reveal>{"".join(out)}</dl>'


def build_membership():
    M = PAGES["clanstvo"]
    tier_icons = ["users", "spark", "globe"]
    tiers = [(t["naziv"], t["cena"], f"paket-{i}", tier_icons[i % 3]) for i, t in enumerate(M["paketi"])]
    default = 1 if len(tiers) > 1 else 0

    def body(p):
        cards = "".join(f"""<button type="button" class="tier{' is-selected' if i == default else ''}" data-tier="{k}" data-tier-name="{e(n)}" aria-pressed="{'true' if i == default else 'false'}" data-reveal data-spotlight>
  <span class="tier__top">{icon(ic, 26)}<span class="tier__check">{icon('check', 16)}</span></span>
  <span class="tier__name">{e(n)}</span>
  <span class="tier__price"><span data-count="{re.sub(r'[^0-9]', '', pr)}">{e(pr)}</span><span class="tier__cur">€</span></span>
</button>""" for i, (n, pr, k, ic) in enumerate(tiers))
        options = "".join(f'<option value="{e(n)}"{" selected" if i == default else ""}>{e(n)} — {e(pr)} €</option>' for i, (n, pr, k, ic) in enumerate(tiers))
        checklist = "".join(f'<li data-reveal>{icon("check", 18)}<span>{e(b)}</span></li>' for b in M["ugodnosti"])
        return f"""
<section class="page-hero page-hero--member">
  <div class="container">
    <p class="eyebrow" data-reveal>Članstvo</p>
    <h1 class="page-title" data-reveal>Postani <em>član</em></h1>
  </div>
</section>
<section class="section section--flush">
  <div class="container member-intro">
    <p class="lead" data-reveal><strong>{e(M['uvod_poudarek'])}</strong> {e(M['uvod'])}</p>
    <p data-reveal>{e(M['uvod_2'])}</p>
  </div>
</section>
<section class="section section--tight" aria-labelledby="price-title">
  <div class="container">
    <div class="sec-head" data-reveal><div><p class="eyebrow">Cena</p><h2 id="price-title" class="sec-title">Članstvo v Zavodu <span class="nw">AI-D</span></h2></div><p class="muted">Izberite paket in nam pošljite povpraševanje.</p></div>
    <div class="tiers" role="group" aria-label="Paketi članstva" data-tiers>{cards}</div>
    <table class="sr-only"><caption>Cenik članstva</caption><thead><tr><th>Članstvo v Zavodu AI-D</th><th>Cena</th></tr></thead><tbody>{''.join(f'<tr><td>{e(n)}</td><td>{e(pr)}€</td></tr>' for n, pr, k, ic in reversed(tiers))}</tbody></table>
  </div>
</section>
<section class="section section--tight" aria-labelledby="ben-title">
  <div class="container split">
    <div data-reveal><p class="eyebrow">Ugodnosti</p><h2 id="ben-title" class="sec-title">{e(M['ugodnosti_naslov'])}</h2></div>
    <ul class="checklist">{checklist}</ul>
  </div>
</section>
<section class="section" id="povprasevanje" aria-labelledby="join-title">
  <div class="container register__grid">
    <div class="register__intro" data-reveal>
      <p class="eyebrow">Pridruži se</p>
      <h2 id="join-title" class="sec-title">Postani član</h2>
      <p>Izbrani paket: <strong data-tier-label>{e(tiers[default][0]) if tiers else ''}</strong></p>
      <p class="muted">Z oddajo povpraševanja potrjujete, da ste seznanjeni s <a href="{href(p, 'splosni-pogoji-clanstva/')}">splošnimi pogoji članstva</a>.</p>
    </div>
    <form class="form card-surface" data-form="membership" data-subject="Povpraševanje za članstvo" novalidate data-reveal>
      <div class="form__grid">
        <div class="field field--wide"><label for="m-paket">Paket</label><select id="m-paket" name="paket" data-tier-select>{options}</select></div>
        <div class="field"><label for="m-ime">Ime in priimek <span aria-hidden="true">*</span></label><input id="m-ime" name="ime" autocomplete="name" required></div>
        <div class="field"><label for="m-org">Organizacija</label><input id="m-org" name="organizacija" autocomplete="organization"></div>
        <div class="field"><label for="m-email">E-naslov <span aria-hidden="true">*</span></label><input id="m-email" name="email" type="email" autocomplete="email" required></div>
        <div class="field"><label for="m-tel">Telefon</label><input id="m-tel" name="telefon" type="tel" autocomplete="tel"></div>
        <div class="field field--wide"><label for="m-msg">Sporočilo</label><textarea id="m-msg" name="sporocilo" rows="4"></textarea></div>
      </div>
      <input class="hp" type="text" name="website" tabindex="-1" autocomplete="off" aria-hidden="true">
      <label class="check"><input type="checkbox" name="soglasje" value="da" required><span>Strinjam se s <a href="{href(p, 'politika-zasebnosti/')}">pravilnikom o zasebnosti</a>. *</span></label>
      <div class="form__actions"><button class="btn btn--primary btn--lg" type="submit" data-magnetic>Pošlji {icon('arrow', 16)}</button><p class="form__req">* Obvezno polje</p></div>
      <div class="form__done" data-form-done hidden><p class="form__done-title">{icon('check', 22)} Hvala!</p><p>Vaše sporočilo smo prejeli. Odgovorili vam bomo v najkrajšem možnem času.</p></div>
    </form>
  </div>
</section>"""
    write("clanstvo/", "Članstvo", f"{M['uvod_poudarek']} {M['uvod']}"[:200], body, section="clanstvo/", body_class="page-member")
    SEARCH.append({"t": "Članstvo", "u": "clanstvo/", "k": "Stran", "x": "Paketi: " + ", ".join(f"{n} {pr} €" for n, pr, k, ic in tiers),
                   "b": "postani član cena članarina prednosti " + " ".join(M["ugodnosti"])})


def build_contact():
    K = PAGES["kontakt"]

    def body(p):
        return f"""
<section class="page-hero">
  <div class="container">
    <p class="eyebrow" data-reveal>Kontakt</p>
    <h1 class="page-title" data-reveal>Kontakt</h1>
    <p class="page-lead" data-reveal>{e(K['uvod'])}</p>
  </div>
</section>
<section class="section section--flush">
  <div class="container contact">
    <div class="contact__info">
      <a class="contact__mail" href="mailto:{e(CO['email'])}" data-reveal>{icon('mail', 22)}<span>{e(CO['email'])}</span>{icon('arrow-up-right', 20)}</a>
      {company_data()}
    </div>
    <form class="form card-surface" data-form="contact" data-subject="Sporočilo s spletne strani" novalidate data-reveal>
      <div class="form__grid">
        <div class="field field--wide"><label for="c-ime">Ime <span aria-hidden="true">*</span></label><input id="c-ime" name="ime" autocomplete="name" required></div>
        <div class="field field--wide"><label for="c-email">E-naslov <span aria-hidden="true">*</span></label><input id="c-email" name="email" type="email" autocomplete="email" required></div>
        <div class="field field--wide"><label for="c-msg">Sporočilo <span aria-hidden="true">*</span></label><textarea id="c-msg" name="sporocilo" rows="6" required></textarea></div>
      </div>
      <input class="hp" type="text" name="website" tabindex="-1" autocomplete="off" aria-hidden="true">
      <label class="check"><input type="checkbox" name="soglasje" value="da" required><span>Strinjam se s <a href="{href(p, 'politika-zasebnosti/')}">pravilnikom o zasebnosti</a>.</span></label>
      <div class="form__actions"><button class="btn btn--primary btn--lg" type="submit" data-magnetic>Pošlji {icon('arrow', 16)}</button></div>
      <div class="form__done" data-form-done hidden><p class="form__done-title">{icon('check', 22)} Hvala!</p><p>Vaše sporočilo smo prejeli. Odgovorili vam bomo v najkrajšem možnem času.</p></div>
    </form>
  </div>
</section>
<section class="section section--tight">
  <div class="container">
    <div class="map map--wide" data-map data-map-q="{e(CO['naslov'])}" data-reveal>
      <button class="map__load" type="button" data-map-load>{icon('pin', 24)}<span>{e(CO['naslov'])}</span><small>Prikaži zemljevid (naloži Google Maps)</small></button>
    </div>
  </div>
</section>"""
    write("kontakt/", "Kontakt", f"{CO['ime']}, {CO['naslov']}. E-naslov: {CO['email']}.", body, section="kontakt/", body_class="page-contact")
    SEARCH.append({"t": "Kontakt", "u": "kontakt/", "k": "Stran", "x": f"{CO['naslov']} · {CO['email']}", "b": "naslov telefon e-pošta zemljevid matična davčna TRR"})


def build_legal():
    for page in LEGAL:
        def body(p, page=page):
            html = render_content(page["html"], p)
            heads = []

            def add_id(m):
                txt = plain(m.group(2))
                slug = re.sub(r"[^a-z0-9]+", "-", txt.lower().translate(str.maketrans("čšžćđ", "cszcd"))).strip("-")[:50] or f"s{len(heads)}"
                heads.append((slug, txt))
                return f'<{m.group(1)} id="{slug}">{m.group(2)}</{m.group(1)}>'
            html = re.sub(r"<(h2)>(.*?)</h2>", add_id, html)
            toc = "".join(f'<li><a href="#{s}">{e(t[:60].capitalize() if t.isupper() else t[:60])}</a></li>' for s, t in heads)
            return f"""
<section class="page-hero page-hero--legal">
  <div class="container">
    <p class="eyebrow" data-reveal>Pravne informacije</p>
    <h1 class="page-title page-title--md" data-reveal>{e(page['title'])}</h1>
  </div>
</section>
<div class="container doc">
  <nav class="toc" aria-label="Vsebina strani" data-toc>{'<p class="toc__title">Vsebina</p><ol>' + toc + '</ol>' if toc else ''}
    <p class="toc__title toc__title--gap">Ostalo</p><ul class="toc__other">{''.join(f'<li><a href="{href(p, u)}"{" aria-current=page" if u == page["slug"] + "/" else ""}>{l}</a></li>' for u, l in LEGAL_NAV)}</ul>
  </nav>
  <div class="doc__body prose prose--legal">{html}</div>
</div>"""
        write(page["slug"] + "/", page["title"], f"{page['title']} — Zavod AI-D", body, section=page["slug"] + "/", body_class="page-legal")
        SEARCH.append({"t": page["title"], "u": page["slug"] + "/", "k": "Pravno", "x": plain(page["html"])[:160]})


def build_404():
    def body(p):
        return f"""
<section class="notfound theme-dark">
  <canvas class="hero__canvas" data-network aria-hidden="true"></canvas>
  <div class="container notfound__inner">
    <p class="eyebrow eyebrow--accent">Napaka 404</p>
    <h1 class="notfound__title">Te strani <em>ni.</em></h1>
    <p class="notfound__text">Stran, ki jo iščete, ne obstaja ali je bila premaknjena.</p>
    <div class="btn-row">
      <a class="btn btn--primary btn--lg" href="{DEMO_BASE or '/'}">Na domačo stran {icon('arrow', 16)}</a>
      <button class="btn btn--ghost btn--lg" type="button" data-search-open>{icon('search', 18)} Iskanje</button>
    </div>
  </div>
</section>"""
    # served from any URL, so it needs absolute paths (site must live at the domain root)
    write("404.html", "Stran ne obstaja", "Stran ne obstaja.", body, section="none", body_class="page-404", prefix=DEMO_BASE or "/")


def build_feeds():
    now = TODAY.strftime("%a, %d %b %Y %H:%M:%S +0000")
    items = []
    for a in ARTICLES[:30]:
        items.append(f"""<item><title>{e(a['title'])}</title><link>{SITE_URL}{quote(a['url'])}</link><guid>{SITE_URL}{quote(a['url'])}</guid>
<pubDate>{a['d'].strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate><description>{e(a['excerpt'])}</description></item>""")
    open(os.path.join(OUT, "feed.xml"), "w", encoding="utf-8").write(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>Zavod AI-D — Novice</title><link>{SITE_URL}</link>'
        f'<description>Zavod za razvoj umetne inteligence</description><language>sl</language><lastBuildDate>{now}</lastBuildDate>{"".join(items)}</channel></rss>\n')
    urls = [""] + [p for p, _ in NAV[1:]] + [a["url"] for a in ARTICLES] + [ev["url"] for ev in EVENTS] + [x["url"] for x in ARCHIVE] + [p for p, _ in LEGAL_NAV]
    open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' +
        "".join(f"<url><loc>{SITE_URL}{quote(u)}</loc></url>" for u in urls) + "</urlset>\n")
    open(os.path.join(OUT, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n")
    if DEMO_BASE:
        open(os.path.join(OUT, ".nojekyll"), "w").close()
    json.dump(SEARCH, open(os.path.join(OUT, "assets", "search.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))


def build_redirects():
    for old, new in REDIRECTS.items():
        write_redirect(old, new)
    # old WordPress archive URLs (tags, authors, paged lists) all lead to the news page
    for old in json.load(open(os.path.join(ROOT, "tools", "stare-povezave.json"), encoding="utf-8")):
        write_redirect(old, "novice/")
    write_redirect("politika-zasebnosti.html/", "politika-zasebnosti/")
    for x in PAST:
        write_redirect("dogodek/" + x["slug"].split("/", 1)[1] + "/", x["url"])


def main():
    # build into a fresh folder, then swap it in, so a running server never serves a half-built site
    global OUT
    final = OUT
    OUT = final + ".novo"
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(os.path.join(SRC, "assets"), os.path.join(OUT, "assets"))
    shutil.copytree(os.path.join(ROOT, "static"), OUT, dirs_exist_ok=True)
    shutil.copytree(os.path.join(SRC, "cms"), os.path.join(OUT, "urednik"))
    endpoint = os.environ.get("AID_FORM_ENDPOINT", CONFIG.get("form_endpoint", ""))
    if DEMO_BASE and not endpoint.startswith("http"):
        endpoint = ""  # a static preview host has no backend: forms fall back to e-mail
    cfg = {"formEndpoint": endpoint, "web3forms": SETTINGS.get("web3forms_key", ""), "email": CO.get("email") or CONFIG.get("email", "info@ai-d.si")}
    open(os.path.join(OUT, "assets", "config.js"), "w", encoding="utf-8").write("window.AID_CONFIG = " + json.dumps(cfg) + ";\n")
    build_home()
    build_news()
    build_articles()
    build_events_index()
    for ev in EVENTS:
        build_event(ev)
    build_archive_events()
    build_about()
    build_membership()
    build_contact()
    build_legal()
    build_404()
    build_redirects()
    build_feeds()
    if any(v.get("pending_card") for v in IMAGES.values()):
        write_pending_cards()
    n = sum(len(f) for _, _, f in os.walk(OUT))
    old = final + ".staro"
    if os.path.exists(old):
        shutil.rmtree(old)
    if os.path.exists(final):
        os.rename(final, old)
    os.rename(OUT, final)
    shutil.rmtree(old, ignore_errors=True)
    OUT = final
    print(f"Zgrajeno: {n} datotek v {OUT}")


if __name__ == "__main__":
    main()
