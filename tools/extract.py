#!/usr/bin/env python3
"""Enkratni prenos vsebine s stare WordPress strani (ai-d.si) v čiste JSON datoteke.

Uporaba:  python3 tools/extract.py
Rezultat: content/*.json in optimizirane slike v static/media/
"""
import json, os, re, posixpath, subprocess, shutil, sys
from concurrent.futures import ThreadPoolExecutor
from html import escape
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD = os.path.join(os.path.dirname(ROOT), "ai-d.si", "ai-d.si")
CONTENT = os.path.join(ROOT, "content")
MEDIA_OUT = os.path.join(ROOT, "static", "media")

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


# ---------------------------------------------------------------- mini DOM
class Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag, attrs=None, parent=None):
        self.tag, self.attrs, self.children, self.parent = tag, dict(attrs or {}), [], parent

    def cls(self):
        return (self.attrs.get("class") or "").split()

    def has(self, c):
        return c in self.cls()

    def find_all(self, pred):
        out = []
        for ch in self.children:
            if isinstance(ch, Node):
                if pred(ch):
                    out.append(ch)
                out.extend(ch.find_all(pred))
        return out

    def find(self, pred):
        for ch in self.children:
            if isinstance(ch, Node):
                if pred(ch):
                    return ch
                r = ch.find(pred)
                if r is not None:
                    return r
        return None

    def text(self):
        parts = []
        for ch in self.children:
            if isinstance(ch, str):
                parts.append(ch)
            elif ch.tag == "br":
                parts.append(" ")
            elif ch.tag not in ("script", "style", "svg"):
                if ch.tag == "img" and ch.attrs.get("alt") and "emoji" in ch.attrs.get("src", ""):
                    parts.append(ch.attrs["alt"])
                parts.append(ch.text())
        return "".join(parts)


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        n = Node(tag, [(k, v if v is not None else "") for k, v in attrs], self.stack[-1])
        self.stack[-1].children.append(n)
        if tag not in VOID:
            self.stack.append(n)

    def handle_startendtag(self, tag, attrs):
        n = Node(tag, [(k, v if v is not None else "") for k, v in attrs], self.stack[-1])
        self.stack[-1].children.append(n)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parse(path):
    b = TreeBuilder()
    b.feed(open(path, encoding="utf-8").read())
    return b.root


def by_class(c):
    return lambda n: n.has(c)


def by_widget(w):
    return lambda n: n.attrs.get("data-widget_type") == w


def meta(root, prop):
    n = root.find(lambda n: n.tag == "meta" and (n.attrs.get("property") == prop or n.attrs.get("name") == prop))
    return n.attrs.get("content") if n else None


def clean_text(s):
    return re.sub(r"\s+", " ", s or "").strip()


# ---------------------------------------------------------------- media
MEDIA = {}  # old relative path -> new site path (relative to site root)


def media_src(old_page, src):
    """Map an <img src> from an old page to a new media path (and register it)."""
    if not src or src.startswith("data:"):
        return None
    if src.startswith("http"):
        m = re.match(r"https?://(www\.)?ai-d\.si/(.*)", src)
        if not m:
            return None
        rel = m.group(2)
    else:
        rel = posixpath.normpath(posixpath.join(posixpath.dirname(old_page), src))
    rel = rel.split("?")[0]
    if "wp-content/uploads/" not in rel:
        return None
    # prefer the full-size original if the download contains it
    base = re.sub(r"-\d+x\d+(\.\w+)$", r"\1", rel)
    if base != rel and os.path.exists(os.path.join(OLD, base)):
        rel = base
    if not os.path.exists(os.path.join(OLD, rel)):
        return None
    if rel not in MEDIA:
        sub = rel.split("wp-content/uploads/", 1)[1]
        stem, ext = os.path.splitext(sub)
        stem = re.sub(r"[^A-Za-z0-9/_.-]+", "-", stem)
        MEDIA[rel] = {"stem": "media/" + stem, "ext": ext.lower()}
    return rel


# ---------------------------------------------------------------- links
ALL_PAGES = set()


def map_href(old_page, href):
    href = (href or "").strip()
    if not href or href == "#":
        return None
    if href.startswith("mailto:"):
        return None if "http" in href else href
    if href.startswith(("tel:", "#")):
        return href
    m = re.match(r"https?://(www\.)?ai-d\.si/?(.*)", href)
    if m:
        href = m.group(2)
        rel = posixpath.normpath(href) if href else "index.html"
    elif href.startswith("http"):
        return href
    else:
        rel = posixpath.normpath(posixpath.join(posixpath.dirname(old_page), href))
    rel = rel.split("#")[0]
    if rel.endswith("index.html"):
        rel = rel[: -len("index.html")]
    rel = rel.strip("/")
    if rel == ".":
        rel = ""
    if rel and rel + "/index.html" not in ALL_PAGES and "dogodki/" + rel + "/index.html" in ALL_PAGES:
        rel = "dogodki/" + rel
    return "@/" + (rel + "/" if rel else "")


# ---------------------------------------------------------------- sanitizer
KEEP = {"p", "h2", "h3", "h4", "ul", "ol", "li", "a", "strong", "em", "br", "blockquote", "figure",
        "figcaption", "img", "table", "thead", "tbody", "tr", "th", "td", "hr", "mark", "cite", "sup", "sub"}
RENAME = {"b": "strong", "i": "em", "h1": "h2", "h5": "h4", "h6": "h4"}
DROP = {"script", "style", "svg", "noscript", "form", "input", "button", "select", "textarea", "label", "iframe", "footer"}


def sanitize(node, old_page):
    out = []
    for ch in node.children:
        if isinstance(ch, str):
            out.append(escape(ch, quote=False))
            continue
        tag = RENAME.get(ch.tag, ch.tag)
        if tag in DROP:
            continue
        if tag == "img":
            src = ch.attrs.get("src", "")
            if "emoji" in src:
                out.append(escape(ch.attrs.get("alt", "")))
                continue
            rel = media_src(old_page, src)
            if rel:
                alt = escape(ch.attrs.get("alt", ""))
                out.append(f'<img src="{{{{media:{rel}}}}}" alt="{alt}" loading="lazy" decoding="async">')
            continue
        inner = sanitize(ch, old_page)
        if tag not in KEEP:
            out.append(inner)
            continue
        attrs = ""
        if tag == "a":
            href = map_href(old_page, ch.attrs.get("href"))
            if not href:
                out.append(inner)
                continue
            attrs = f' href="{escape(href)}"'
            if href.startswith("http"):
                attrs += ' target="_blank" rel="noopener"'
        elif tag == "p" and any(c.startswith("has-") and c.endswith("-font-size") for c in ch.cls()):
            if re.sub(r"<[^>]+>|\s|&nbsp;|\xa0", "", inner):
                tag = "h3"
        elif tag == "figure" and ch.has("wp-block-gallery"):
            attrs = ' class="gallery"'
        elif tag in ("td", "th") and ch.attrs.get("colspan"):
            attrs = f' colspan="{escape(ch.attrs["colspan"])}"'
        if tag in VOID:
            out.append(f"<{tag}{attrs}>")
        else:
            out.append(f"<{tag}{attrs}>{inner}</{tag}>")
    html = "".join(out)
    return html


def tidy(html):
    html = html.replace("\xa0", " ")
    html = re.sub(r"[ \t\r\f\v]*\n[\s]*", "\n", html)
    # empty paragraphs / headings
    for _ in range(3):
        html = re.sub(r"<(p|h2|h3|h4|li|strong|em|mark)>(\s|<br>)*</\1>", "", html)
    html = re.sub(r"<p>(\s*<br>\s*)+", "<p>", html)
    html = re.sub(r"(\s*<br>\s*)+</p>", "</p>", html)
    html = re.sub(r"<p>\s*(<img[^>]+>)\s*</p>", r"<figure>\1</figure>", html)
    html = re.sub(r"\n{2,}", "\n", html)
    return html.strip()


# ---------------------------------------------------------------- extractors
def page_title(root):
    t = root.find(lambda n: n.tag == "title")
    s = clean_text(t.text()) if t else ""
    return re.sub(r"\s*-\s*Zavod za razvoj umetne inteligence$", "", s)


def extract_post(path):
    root = parse(os.path.join(OLD, path))
    content = root.find(by_widget("theme-post-content.default"))
    container = content.find(by_class("elementor-widget-container")) if content else None
    title_w = root.find(by_widget("theme-post-title.default"))
    title = clean_text(title_w.text()) if title_w else page_title(root)
    img_w = root.find(by_widget("theme-post-featured-image.default"))
    img = img_w.find(lambda n: n.tag == "img") if img_w else None
    image = media_src(path, img.attrs.get("src")) if img else None
    if not image:
        og = meta(root, "og:image")
        image = media_src(path, og) if og else None
    html = tidy(sanitize(container, path)) if container else ""
    slug = path.split("/index.html")[0]
    plain = clean_text(re.sub(r"<[^>]+>", " ", html))
    desc = meta(root, "og:description") or meta(root, "description") or plain[:220]
    return {
        "slug": slug,
        "title": title,
        "date": meta(root, "article:published_time"),
        "modified": meta(root, "article:modified_time"),
        "excerpt": clean_text(desc),
        "image": image,
        "html": html,
        "words": len(plain.split()),
    }


def extract_event(path):
    root = parse(os.path.join(OLD, path))
    art = root.find(by_class("aid-event-single__article"))
    hero = art.find(by_class("aid-event-single__hero"))
    hero_img = hero.find(lambda n: n.tag == "img") if hero else None
    header = art.find(by_class("aid-event-single__header"))
    lead = art.find(by_class("aid-event-single__lead"))
    facts = []
    dl = art.find(by_class("aid-event-facts"))
    for div in [c for c in dl.children if isinstance(c, Node)]:
        dt = div.find(lambda n: n.tag == "dt")
        dd = div.find(lambda n: n.tag == "dd")
        span = dd.find(lambda n: n.tag == "span")
        main = clean_text("".join(c if isinstance(c, str) else "" for c in dd.children))
        facts.append({"label": clean_text(dt.text()), "value": main, "extra": clean_text(span.text()) if span else None})
    body = art.find(by_class("aid-event-single__content"))
    ev = {
        "slug": path.split("/index.html")[0],
        "title": clean_text(header.find(lambda n: n.tag == "h1").text()),
        "eyebrow": clean_text(header.find(by_class("aid-eyebrow")).text()),
        "lead": tidy(sanitize(lead, path)) if lead else "",
        "image": media_src(path, hero_img.attrs.get("src")) if hero_img else None,
        "facts": facts,
        "html": tidy(sanitize(body, path)) if body else "",
        "date": meta(root, "article:published_time"),
        "program": None,
        "registration": None,
    }
    prog = art.find(by_class("aid-event-program"))
    if prog:
        tabs = [clean_text(b.text()) for b in prog.find_all(by_class("aid-program-tab"))]
        panels = prog.find_all(by_class("aid-program-panel"))
        days = []
        for label, panel in zip(tabs, panels):
            d = panel.find(by_class("aid-program-panel__description"))
            items = []
            for it in panel.find_all(by_class("aid-program-accordion__item")):
                trig = it.find(by_class("aid-program-accordion__trigger"))
                t = trig.find(by_class("aid-program-accordion__time"))
                ti = trig.find(by_class("aid-program-accordion__title"))
                st = trig.find(by_class("aid-program-accordion__subtitle"))
                pop = it.find(by_class("aid-program-popup"))
                item = {
                    "time": clean_text(t.text()) if t else "",
                    "title": clean_text(ti.text()) if ti else "",
                    "subtitle": clean_text(st.text()) if st else "",
                    "image": None,
                    "html": "",
                }
                if pop:
                    fig = pop.find(by_class("aid-program-popup__speaker-image"))
                    im = fig.find(lambda n: n.tag == "img") if fig else None
                    item["image"] = media_src(path, im.attrs.get("src")) if im else None
                    desc = pop.find(by_class("aid-program-popup__description"))
                    item["html"] = tidy(sanitize(desc, path)) if desc else ""
                items.append(item)
            days.append({"label": label, "description": clean_text(d.text()) if d else "", "items": items})
        maps = []
        for sec in art.find_all(by_class("aid-registration-map")):
            inter = sec.find(by_class("aid-event-map__interactive"))
            pts = json.loads(inter.attrs.get("data-map-points", "[]")) if inter else []
            seen, uniq = set(), []
            for p in pts:
                k = p["address"].replace("cesta ", "").lower()
                if k not in seen:
                    seen.add(k)
                    uniq.append(p)
            maps.append(uniq)
        for i, d in enumerate(days):
            d["locations"] = maps[i] if i < len(maps) else []
        ev["program"] = days
    reg = art.find(by_class("aid-event-registration")) or art.find(lambda n: n.tag == "section" and "registration" in n.attrs.get("class", ""))
    form = art.find(by_class("aid-registration-form"))
    closed = art.find(lambda n: "aid-registration-closed" in n.attrs.get("class", "") or "closed" in n.attrs.get("class", "") and n.tag in ("div", "section", "p"))
    r = {"title": None, "intro": None, "open": form is not None, "closed_text": None, "price_note": None, "member_label": None, "price": None}
    regsec = art.find(lambda n: n.attrs.get("id") == "aid-registration-title")
    if regsec:
        r["title"] = clean_text(regsec.text())
        par = regsec.parent
        p = par.find(lambda n: n.tag == "p" and not n.has("aid-eyebrow"))
        r["intro"] = clean_text(p.text()) if p else None
    if form:
        txt = clean_text(form.text())
        m = re.search(r"(Za člane Zavoda AI-D brezplačno[^.]*?\+ DDV\.)", txt)
        r["price_note"] = m.group(1) if m else None
        m = re.search(r"(Sem član Zavoda AI-D[^C]*?udeležba)", txt)
        r["member_label"] = clean_text(m.group(1)) if m else None
        m = re.search(r"Cena prijave:\s*([^S*]+?\+ DDV)", txt)
        r["price"] = clean_text(m.group(1)) if m else None
    else:
        sec = regsec.parent.parent if regsec else None
        if sec:
            blocks = [clean_text(n.text()) for n in sec.find_all(lambda n: n.tag in ("p", "strong", "h3", "span", "div") and not any(isinstance(c, Node) and c.tag in ("p", "div") for c in n.children))]
            blocks = [b for b in blocks if b]
            i = next((k for k, b in enumerate(blocks) if b.startswith("Prijave so zaključene")), None)
            if i is not None:
                r["closed_title"] = "Prijave so zaključene"
                rest = " ".join(b for b in blocks[i:] if b != "Prijave so zaključene").replace("Prijave so zaključene", "")
                sentences = []
                for snt in re.split(r"(?<=\.)\s+", rest):
                    if snt.strip() and snt.strip() not in sentences:
                        sentences.append(snt.strip())
                r["closed_text"] = " ".join(sentences)
    ev["registration"] = r
    return ev


def extract_region(path, start_marker_widget=None):
    """Main content of an Elementor page: everything after the header, before the newsletter footer."""
    root = parse(os.path.join(OLD, path))
    main = root.find(lambda n: n.tag == "main") or root
    page = main.find(lambda n: n.attrs.get("data-elementor-type") == "wp-page") or main
    h1 = page.find(lambda n: n.tag == "h1")
    title = clean_text(h1.text()) if h1 else page_title(root)
    if h1:
        h1.parent.children.remove(h1)
    return {"slug": path.split("/index.html")[0], "title": title, "html": tidy(sanitize(page, path))}


# ---------------------------------------------------------------- images
def sips_info(p):
    out = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", "-g", "hasAlpha", p],
                         capture_output=True, text=True).stdout
    w = int(re.search(r"pixelWidth: (\d+)", out).group(1))
    h = int(re.search(r"pixelHeight: (\d+)", out).group(1))
    a = re.search(r"hasAlpha: (\w+)", out)
    return w, h, bool(a and a.group(1) == "yes")


def process_image(rel):
    info = MEDIA[rel]
    src = os.path.join(OLD, rel)
    w, h, alpha = sips_info(src)
    # small PNGs are logos/icons with real transparency; everything else becomes JPEG
    keep_png = info["ext"] == ".png" and os.path.getsize(src) < 60_000
    ext = ".png" if keep_png else ".jpg"
    fmt = "png" if keep_png else "jpeg"
    variants = {}
    for name, limit in (("full", 1800), ("card", 960)):
        if name == "card" and w <= limit:
            variants["card"] = variants["full"]
            continue
        suffix = "" if name == "full" else "-960"
        dst_rel = info["stem"] + suffix + ext
        dst = os.path.join(os.path.dirname(MEDIA_OUT), dst_rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        scale = min(1.0, limit / max(w, h)) if name == "full" else min(1.0, limit / w)
        tw, th = round(w * scale), round(h * scale)
        if not os.path.exists(dst):
            cmd = ["sips", "-s", "format", fmt]
            if fmt == "jpeg":
                cmd += ["-s", "formatOptions", "0.72"]  # sips: 0–1 range gives real compression
            if scale < 1.0:
                cmd += ["-z", str(th), str(tw)]
            cmd += [src, "--out", dst]
            subprocess.run(cmd, capture_output=True)
        variants[name] = {"src": dst_rel, "w": tw, "h": th}
    return rel, variants


# ---------------------------------------------------------------- main
def main():
    for dp, dn, fn in os.walk(OLD):
        for f in fn:
            if f == "index.html":
                ALL_PAGES.add(os.path.relpath(os.path.join(dp, f), OLD).replace(os.sep, "/"))

    posts, old_events = [], []
    for p in sorted(ALL_PAGES):
        if re.match(r"^(tag|category|author|aktualno|novice|kategorija-dogodka|2027)/", p):
            continue
        txt = open(os.path.join(OLD, p), encoding="utf-8").read()
        if "theme-post-content" not in txt:
            continue
        (old_events if p.startswith("dogodki/") else posts).append(p)

    articles = [extract_post(p) for p in posts]
    articles.sort(key=lambda a: a["date"] or "", reverse=True)

    # tags from tag archive pages
    tags = {}
    for p in ALL_PAGES:
        m = re.match(r"tag/([^/]+)/", p)
        if not m:
            continue
        root = parse(os.path.join(OLD, p))
        h1 = root.find(lambda n: n.tag == "h1")
        name = clean_text(h1.text()).replace("Oznaka:", "").strip() if h1 else m.group(1)
        for a in root.find_all(lambda n: n.tag == "a" and n.attrs.get("href", "").endswith("/index.html")):
            target = posixpath.normpath(posixpath.join(posixpath.dirname(p), a.attrs["href"])).split("/index.html")[0]
            tags.setdefault(target, set()).add(name)
    for a in articles:
        a["tags"] = sorted(tags.get(a["slug"], []), key=str.lower)

    past = [extract_post(p) for p in old_events]
    past.sort(key=lambda a: a["date"] or "", reverse=True)

    events = [extract_event(p) for p in ("dogodek/ai-week-2026/index.html",
                                         "dogodek/ivo-grlica-odvetnik-ai-law-delavnica/index.html",
                                         "dogodek/delavnica-z-evo-esih-psybit-30-9/index.html")]

    legal = [extract_region(p) for p in ("politika-zasebnosti/index.html", "pravilnik-o-piskotkih/index.html",
                                         "splosni-pogoji-clanstva/index.html", "izjava-o-skladnosti/index.html")]

    # extra imagery used by hand-built pages
    extras = {}
    for key, p in {
        "hero": "wp-content/uploads/2026/07/ChatGPT-Image-Jul-14-2026-12_45_28-PM-1024x427.png",
        "logo": "wp-content/uploads/2025/04/ai-d_logo.png",
        "eu_banner": "wp-content/uploads/2026/09/viber_image_2026-09-28_11-35-39-052.jpg",
    }.items():
        extras[key] = media_src("index.html", p)

    print(f"članki: {len(articles)}, pretekli dogodki: {len(past)}, dogodki: {len(events)}, slike: {len(MEDIA)}")
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = dict(ex.map(process_image, list(MEDIA)))

    os.makedirs(CONTENT, exist_ok=True)
    dump = lambda name, data: json.dump(data, open(os.path.join(CONTENT, name), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    dump("articles.json", articles)
    dump("past-events.json", past)
    dump("events.json", events)
    dump("legal.json", legal)
    dump("media.json", {"images": results, "extras": extras})
    print("končano")


if __name__ == "__main__":
    main()
