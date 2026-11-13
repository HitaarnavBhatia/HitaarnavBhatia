"""Scrape the public GitHub contribution calendar into data/contributions.json.

No token needed: reads https://github.com/users/<user>/contributions (last ~53 weeks).
"""
import json
import os
import re
import urllib.request
from pathlib import Path

USER = os.environ.get("GH_USER", "HitaarnavBhatia")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "contributions.json"


def main():
    req = urllib.request.Request(
        f"https://github.com/users/{USER}/contributions",
        headers={"User-Agent": "profile-readme-cards"},
    )
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")

    # cell id -> (date, level)
    cells = {}
    for m in re.finditer(r'<td[^>]*data-date="(\d{4}-\d{2}-\d{2})"[^>]*>', html):
        tag = m.group(0)
        cid = re.search(r'id="([^"]+)"', tag)
        lvl = re.search(r'data-level="(\d)"', tag)
        if cid:
            cells[cid.group(1)] = (m.group(1), int(lvl.group(1)) if lvl else 0)

    # tooltip text holds the count: "3 contributions on ..." / "No contributions on ..."
    counts = {}
    for m in re.finditer(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)<', html):
        text = m.group(2).strip()
        n = re.match(r"(\d[\d,]*) contribution", text)
        counts[m.group(1)] = int(n.group(1).replace(",", "")) if n else 0

    days = sorted(
        ({"date": d, "count": counts.get(cid, 0), "level": lvl} for cid, (d, lvl) in cells.items()),
        key=lambda x: x["date"],
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"user": USER, "days": days}, indent=1))
    print(f"wrote {len(days)} days, {sum(d['count'] for d in days)} contributions -> {OUT}")


if __name__ == "__main__":
    main()
