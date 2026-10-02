#!/usr/bin/env python3
"""Enkratna pretvorba vsebin v obliko za urednik Sveltia CMS (ena datoteka na vsebino, besedilo v Markdownu).

Uporaba: .venv/bin/python tools/migrate_cms.py
"""
import json
import os
import re
import shutil
import sys
from html import unescape
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C = os.path.join(ROOT, "content")
STATIC = os.path.join(ROOT, "static")

old = lambda n: json.load(open(os.path.join(C, n), encoding="utf-8"))
MEDIA = old("media.json")
IMAGES = MEDIA["images"]

# old key -> public path of the full image ("/media/2026/09/x.jpg")
PATH = {k: "/" + v["full"]["src"] for k, v in IMAGES.items()}


def img_path(key):
    return PATH.get(key) if key else None


# ---------------------------------------------------------------- HTML -> Markdown
VOID = {"img", "br", "hr"}


class Node:
    def __init__(self, tag, attrs=None):
        self.tag, self.attrs, self.children = tag, dict(attrs or {}), []


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs)
        self.stack[-1].children.append(n)
        if tag not in VOID:
            self.stack.append(n)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, attrs))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, d):
        self.stack[-1].children.append(d)


def esc(text):
    text = re.sub(r"\s+", " ", text)
    text = text.replace("\\", "\\\\")
    for ch in "*_`[]":
        text = text.replace(ch, "\\" + ch)
    return text.replace("<", "&lt;")


def esc_line_starts(md):
    out = []
    for line in md.split("\n"):
        s = line
        if re.match(r"^(#{1,6}\s|>|[-+*]\s|\d+[.)]\s)", s):
            m = re.match(r"^(\d+)([.)])(\s.*)$", s)
            if m:
                s = m.group(1) + "\\" + m.group(2) + m.group(3)
            else:
                s = "\\" + s
        out.append(s)
    return "\n".join(out)


def wrap(inner, mark):
    core = inner.strip()
    if not core:
        return inner
    if core.startswith(mark) and core.endswith(mark) and len(core) > 2 * len(mark) and mark not in core[len(mark):-len(mark)]:
        return inner  # already emphasised the same way (e.g. <strong><mark>…</mark></strong>)
    lead = inner[: len(inner) - len(inner.lstrip())]
    trail = inner[len(inner.rstrip()):]
    return f"{lead}{mark}{core}{mark}{trail}"


def inline(node):
    out = []
    kids = node.children
    for idx, ch in enumerate(kids):
        if isinstance(ch, str):
            out.append(esc(ch))
            continue
        t = ch.tag
        if t in ("strong", "b", "mark"):
            out.append(wrap(inline(ch), "**"))
        elif t in ("em", "i"):
            # "_" nests safely with "**", but cannot touch a letter (e.g. <em>datote</em>k): use "*" there
            nxt = kids[idx + 1] if idx + 1 < len(kids) else ""
            prev = out[-1] if out else ""
            touching = (isinstance(nxt, str) and nxt[:1].isalnum()) or prev[-1:].isalnum()
            out.append(wrap(inline(ch), "*" if touching else "_"))
        elif t == "a":
            href = ch.attrs.get("href", "")
            if href.startswith("@/"):
                href = href[1:]
            txt = inline(ch).strip()
            href = href.replace("(", "%28").replace(")", "%29").replace(" ", "%20")
            out.append(f"[{txt}]({href})" if href and txt else txt)
        elif t == "br":
            out.append("  \n")
        elif t == "img":
            m = re.match(r"\{\{media:(.*)\}\}$", ch.attrs.get("src", ""))
            p = img_path(m.group(1)) if m else None
            if p:
                out.append(f"![{esc(ch.attrs.get('alt', ''))}]({p})")
        elif t in ("script", "style"):
            continue
        else:
            out.append(inline(ch))
    return "".join(out)


def clean_inline(s):
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" *  \n *", "  \n", s)
    s = re.sub(r"^(\s|  \n)+|(\s|  \n)+$", "", s)
    return s


def heading_inline(ch):
    s = clean_inline(inline(ch))
    m = re.fullmatch(r"\*\*(.+)\*\*", s, re.S)
    if m and "**" not in m.group(1):
        s = m.group(1)
    return s.replace("  \n", " ")


def blocks(node, depth=0):
    out = []
    loose = []

    def flush():
        s = clean_inline("".join(loose))
        loose.clear()
        if s:
            out.append(esc_line_starts(s))

    for ch in node.children:
        if isinstance(ch, str) or ch.tag in ("strong", "b", "em", "i", "a", "br", "mark", "span", "sup", "sub"):
            loose.append(esc(ch) if isinstance(ch, str) else inline(_single(ch)))
            continue
        flush()
        t = ch.tag
        if t == "p":
            s = clean_inline(inline(ch))
            if s:
                out.append(esc_line_starts(s))
        elif t in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = {"h1": 2, "h2": 2, "h3": 3, "h4": 4, "h5": 4, "h6": 4}[t]
            s = heading_inline(ch)
            if s:
                out.append("#" * level + " " + s)
        elif t in ("ul", "ol"):
            items = []
            n = 0
            for li in [c for c in ch.children if not isinstance(c, str) and c.tag == "li"]:
                n += 1
                marker = f"{n}. " if t == "ol" else "- "
                inner_blocks = [c for c in li.children if not isinstance(c, str) and c.tag in ("ul", "ol", "p")]
                if inner_blocks:
                    sub = blocks(li, depth + 1).split("\n\n")
                    first, rest = sub[0], sub[1:]
                    lines = marker + first.replace("\n", "\n    ")
                    for r in rest:
                        lines += "\n\n    " + r.replace("\n", "\n    ")
                    items.append(lines)
                else:
                    s = clean_inline(inline(li))
                    items.append(marker + esc_line_starts(s).replace("\n", "\n    "))
            if items:
                out.append("\n".join(items))
        elif t == "blockquote":
            inner = blocks(ch, depth + 1) or clean_inline(inline(ch))
            if inner:
                out.append("\n".join("> " + l if l else ">" for l in inner.split("\n")))
        elif t == "figure":
            imgs = [inline(_single(i)) for i in _all(ch, "img")]
            imgs = [i for i in imgs if i]
            cap = [c for c in ch.children if not isinstance(c, str) and c.tag == "figcaption"]
            # tables wrapped in figures
            for tbl in _all(ch, "table"):
                out.append(table(tbl))
            if imgs:
                out.append(" ".join(imgs))
            if cap:
                s = clean_inline(inline(cap[0]))
                if s:
                    out.append(f"*{s}*")
        elif t == "hr":
            out.append("---")
        elif t == "table":
            out.append(table(ch))
        elif t == "img":
            s = inline(_single(ch))
            if s:
                out.append(s)
        else:
            inner = blocks(ch, depth + 1)
            if inner:
                out.append(inner)
    flush()
    return "\n\n".join(b for b in out if b.strip())


def _single(n):
    wrapper = Node("#")
    wrapper.children = [n]
    return wrapper


def _all(node, tag):
    found = []
    for ch in node.children:
        if isinstance(ch, str):
            continue
        if ch.tag == tag:
            found.append(ch)
        found.extend(_all(ch, tag))
    return found


def table(tbl):
    rows = []
    for tr in _all(tbl, "tr"):
        cells = [clean_inline(inline(c)).replace("|", "\\|").replace("  \n", " ") for c in tr.children if not isinstance(c, str) and c.tag in ("td", "th")]
        rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines)


def to_md(html, strip_br=False):
    if strip_br:
        html = re.sub(r"<br>\s*", " ", html or "")
    t = Tree()
    t.feed(html or "")
    t.close()
    md = blocks(t.root)
    return re.sub(r"\n{3,}", "\n\n", md).strip() + "\n" if md.strip() else ""


# ---------------------------------------------------------------- dates
def local(iso):
    """'2026-08-24T08:16:52+00:00' -> '2026-08-24T10:16' (Ljubljana time)."""
    import datetime as dt
    if not iso:
        return None
    d = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if d.tzinfo is None:
        return d.strftime("%Y-%m-%dT%H:%M")
    u = d.astimezone(dt.timezone.utc).replace(tzinfo=None)

    def last_sunday(y, m):
        x = dt.date(y, m, 31)
        return x - dt.timedelta(days=(x.weekday() + 1) % 7)
    off = 2 if last_sunday(u.year, 3) <= (u + dt.timedelta(hours=1)).date() < last_sunday(u.year, 10) else 1
    return (u + dt.timedelta(hours=off)).strftime("%Y-%m-%dT%H:%M")


def parse_fact(txt):
    m = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})(?:\s*ob\s*(\d{1,2}):(\d{2}))?", txt or "")
    if not m:
        return None
    return f"{int(m.group(3)):04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}T{int(m.group(4) or 0):02d}:{m.group(5) or '00'}"


def strip_tags(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html or ""))).strip()


# ---------------------------------------------------------------- write
def dump(path, data):
    full = os.path.join(C, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main():
    arts = old("articles.json")
    for a in arts:
        dump(f"novice/{a['slug']}.json", {
            "title": a["title"], "date": local(a["date"]), "draft": a.get("status") == "osnutek",
            "image": img_path(a.get("image")), "excerpt": a.get("excerpt", ""), "body": to_md(a["html"]), "tags": a.get("tags", []),
        })

    evs = old("events.json")
    past = {p["slug"]: p for p in old("past-events.json")}
    concept = past.get("dogodki/ai-week")
    for ev in evs:
        fact = {f["label"]: f for f in ev["facts"]}
        termin = fact.get("Termin", {})
        reg = ev.get("registration") or {}
        data = {
            "title": ev["title"], "eyebrow": ev.get("eyebrow") or "Dogodek",
            "start": local(ev.get("start_iso")) or parse_fact(termin.get("value")),
            "end": local(ev.get("end_iso")) or parse_fact((termin.get("extra") or "").replace("do ", "")) or parse_fact(termin.get("value")),
            "location": fact.get("Lokacija", {}).get("value", ""), "price": fact.get("Cena", {}).get("value", ""),
            "lead": strip_tags(ev.get("lead")), "image": img_path(ev.get("image")), "body": to_md(ev["html"]),
            "program": [], "registration": {
                "open": bool(reg.get("open")), "title": reg.get("title") or "Prijava na dogodek", "intro": reg.get("intro") or "",
                "members_free": bool(reg.get("member_label")), "nonmember_price": reg.get("price") or "",
            },
            "draft": ev.get("status") == "osnutek",
        }
        for d in ev.get("program") or []:
            data["program"].append({
                "label": d["label"], "description": d.get("description", ""),
                "locations": [{"name": l["name"], "address": l["address"]} for l in d.get("locations", [])],
                "items": [{"time": "" if it.get("time") in ("—", None) else it["time"], "title": it["title"], "subtitle": it.get("subtitle", ""),
                           "image": img_path(it.get("image")), "description": to_md(it.get("html", ""), strip_br=True)} for it in d["items"]],
            })
        if ev["slug"] == "dogodek/ai-week-2026" and concept:
            themes = re.findall(r"<h3>(.*?)</h3>\s*<p>(.*?)</p>", concept["html"], re.S)
            data["themes_title"] = "Think. Build. Experience."
            data["themes"] = [{"title": strip_tags(t).replace(" :", ":"), "text": strip_tags(d)} for t, d in themes]
            note = re.search(r"<p><em>(\*Tretji dan konference je brezplačen\.)</em></p>", concept["html"])
            data["themes_note"] = note.group(1) if note else ""
        dump(f"dogodki/{ev['slug'].split('/', 1)[1]}.json", data)

    skip = {"dogodki/ai-week", "dogodki/delavnica-z-evo-esih-psybit-30-9", "dogodki/ai-v-podjetjih-ze-tece-imate-pravila-pod-nadzorom-ai-law"}
    for p in old("past-events.json"):
        if p["slug"] in skip:
            continue
        dump(f"arhiv/{p['slug'].split('/', 1)[1]}.json", {
            "title": p["title"], "date": p.get("event_date"), "draft": p.get("status") == "osnutek",
            "image": img_path(p.get("image")), "body": to_md(p["html"]),
        })

    for page in old("legal.json"):
        dump(f"pravno/{page['slug']}.json", {"title": page["title"], "body": to_md(page["html"])})

    pages = old("pages.json")
    names = {"domov": "domov", "o_zavodu": "o-zavodu", "clanstvo": "clanstvo", "kontakt": "kontakt", "podjetje": "podatki"}
    for k, fname in names.items():
        dump(f"strani/{fname}.json", pages[k])

    s = old("settings.json")
    dump("nastavitve.json", {"featured_event": (s.get("izpostavljen_dogodek") or "").split("/", 1)[-1] or None,
                             "show_banner": bool(s.get("obvestilo", True)), "web3forms_key": ""})

    # images: index by public path; card variants move out of the editor's media folder
    index = {}
    for key, v in IMAGES.items():
        full = v["full"]["src"]
        card = v["card"]["src"]
        entry = {"w": v["full"]["w"], "h": v["full"]["h"]}
        if card != full:
            new_card = "kartice/" + full[len("media/"):]
            os.makedirs(os.path.dirname(os.path.join(STATIC, new_card)), exist_ok=True)
            if os.path.exists(os.path.join(STATIC, card)):
                shutil.move(os.path.join(STATIC, card), os.path.join(STATIC, new_card))
            entry["card"] = {"src": new_card, "w": v["card"]["w"], "h": v["card"]["h"]}
        index[full] = entry
    extras = {name: IMAGES[key]["full"]["src"] for name, key in MEDIA["extras"].items()}
    dump("slike.json", {"images": index, "extras": extras})
    print(f"novice: {len(arts)}, dogodki: {len(evs)}, slike: {len(index)}")


if __name__ == "__main__":
    if "--md" in sys.argv:
        print(to_md(sys.stdin.read()))
    else:
        main()
