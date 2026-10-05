#!/usr/bin/env python3
"""Dogodke, ki so se končali, premakne iz content/dogodki/ v content/dogodki-pretekli/ (urednik jih nato kaže med preteklimi).

Teče ob vsaki gradnji na GitHubu (in vsako noč). Spletni naslov dogodka ostane enak.
"""
import datetime as dt
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPCOMING = os.path.join(ROOT, "content", "dogodki")
PAST = os.path.join(ROOT, "content", "dogodki-pretekli")


def ljubljana_now():
    utc = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    y = utc.year

    def last_sunday(month):
        x = dt.date(y, month, 31)
        return x - dt.timedelta(days=(x.weekday() + 1) % 7)
    summer = last_sunday(3) <= utc.date() < last_sunday(10)
    return utc + dt.timedelta(hours=2 if summer else 1)


def ended(ev, now):
    value = (ev.get("end") or ev.get("start") or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?", value)
    if not m:
        return False
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hh, mm = (int(m.group(4)), int(m.group(5))) if m.group(4) else (23, 59)
    return dt.datetime(y, mo, d, hh, mm) < now


def main():
    now = ljubljana_now()
    os.makedirs(PAST, exist_ok=True)
    moved = []
    for name in sorted(os.listdir(UPCOMING)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(UPCOMING, name), encoding="utf-8") as f:
            ev = json.load(f)
        if ended(ev, now) and not os.path.exists(os.path.join(PAST, name)):
            os.replace(os.path.join(UPCOMING, name), os.path.join(PAST, name))
            moved.append(ev.get("title", name))
    for t in moved:
        print("Premaknjeno med pretekle:", t)
    if not moved:
        print("Ni dogodkov za premik.")


if __name__ == "__main__":
    main()
