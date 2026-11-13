"""Render every README card in cards/ as a self-contained animated SVG.

Reads data/contributions.json (refreshed daily by the Action) and live repo metadata
from the GitHub API (falls back to data/repos.json if the API is unavailable).

    python scripts/render_readme_cards.py          # animated
    STATIC=1 python scripts/render_readme_cards.py # final frame only, for screenshots

Everything works inside an <img>: inline <style> keyframes, embedded WOFF fonts, no scripts.
All motion switches off under prefers-reduced-motion.
"""
import base64
import datetime as dt
import json
import os
import urllib.request
from collections import OrderedDict
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "cards"
DATA = ROOT / "data"
USER = os.environ.get("GH_USER", "HitaarnavBhatia")
STATIC = os.environ.get("STATIC") == "1"

# ---------------------------------------------------------------- palette
PAPER = "#FBF9F4"
RULE = "#E4DFD3"
INK = "#17181C"
MUTED = "#6E6C66"
BLUE = "#2B59E8"
RED = "#EC5434"
YELLOW = "#F3B92B"
WHITE = "#FFFFFF"
GRAPH = ["#ECE8DD", "#C7D3FB", "#8EA8F6", "#5279EF", "#2B59E8"]

LINKEDIN = "https://linkedin.com/in/hitaarnavbhatia"
GH = f"https://github.com/{USER}"

# Featured work, in order. "repo" entries pull language and last push from the API;
# the rest (team / uni projects not on this account) use the fields given here.
FEATURED = [
    {"repo": "REIT4841_ThesisTool", "kind": "THESIS",
     "desc": "Honours thesis: builds a verified CVE benchmark and auto-discovers missing sinks for taint-analysis tools."},
    {"repo": "TrainForge", "kind": "REPO",
     "desc": "Django coaching platform: trainers manage clients, plans and bookings, with AI workout suggestions."},
    {"name": "WeWorkWell", "kind": "TEAM PROJECT", "lang": "HL7 FHIR", "meta": "wearables",
     "desc": "Wellbeing web app on HL7 FHIR: wearable health data in one dashboard, with consent-based data sharing."},
    {"name": "Clash of Clankers", "kind": "TEAM PROJECT", "lang": "Java", "meta": "coverage 70 → 90%",
     "desc": "42-student LibGDX RPG over 4 Agile sprints. I built item pickup and spawners, plus JUnit tests."},
]
LANG_COLORS = {
    "Python": "#3572A5", "HTML": "#E34C26", "JavaScript": "#E9CB3A", "TypeScript": "#3178C6",
    "Jupyter Notebook": "#DA5B0B", "Java": "#B07219", "CSS": "#563D7C",
}
STACK = [
    ("LANGUAGES", ["Python", "Java", "JavaScript", "C", "Haskell", "SQL"]),
    ("BUILD", ["React", "Django", "Flask", "Angular", "Tailwind", "REST"]),
    ("CLOUD", ["AWS ECS", "ECR", "S3", "Docker", "Terraform", "CI/CD"]),
]

# ---------------------------------------------------------------- fonts
FONT_FILES = {
    "serif": "serif-400.woff", "italic": "serif-italic.woff",
    "mono": "mono-400.woff", "mono6": "mono-600.woff",
    "sans": "sans-400.woff", "sans6": "sans-600.woff",
}


def font_css(names):
    out = []
    for n in names:
        b64 = base64.b64encode((ROOT / "fonts" / FONT_FILES[n]).read_bytes()).decode()
        out.append(f"@font-face{{font-family:'f-{n}';src:url(data:font/woff;base64,{b64}) format('woff')}}")
        out.append(f".{n}{{font-family:'f-{n}',ui-monospace,monospace}}" if n.startswith("mono")
                   else f".{n}{{font-family:'f-{n}',Georgia,serif}}" if n in ("serif", "italic")
                   else f".{n}{{font-family:'f-{n}',system-ui,sans-serif}}")
    return "".join(out)


BASE_CSS = """
.a{animation-fill-mode:both;animation-timing-function:cubic-bezier(.2,.8,.2,1);transform-box:fill-box;transform-origin:center}
@keyframes rise{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes pop{0%{opacity:0;transform:scale(.2)}65%{opacity:1;transform:scale(1.25)}100%{opacity:1;transform:scale(1)}}
@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@keyframes swing{0%{opacity:0;transform:translateY(80px) rotate(-8deg)}55%{opacity:1;transform:translateY(-9px) rotate(1.6deg)}78%{transform:translateY(3px) rotate(-.6deg)}100%{opacity:1;transform:none}}
@keyframes blink{0%{opacity:0}1%{opacity:1}99%{opacity:1}100%{opacity:0}}
@keyframes nudge{0%,70%,100%{transform:none}80%{transform:translate(3px,-3px)}90%{transform:translate(0,0)}}
@keyframes pulse{0%{opacity:.55;transform:scale(1)}100%{opacity:0;transform:scale(2.6)}}
@keyframes ring{0%{opacity:.6;transform:scale(.2)}100%{opacity:0;transform:scale(1.6)}}
@keyframes print{0%{opacity:0}40%{opacity:1;fill:#2B59E8}100%{opacity:1}}
.cf{opacity:0}
.ring,.shine{opacity:0}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
"""
STATIC_CSS = "*{animation:none!important}"


def anim(name, delay, dur=0.6, extra=""):
    """Inline style for a one-shot animation."""
    return f'class="a" style="animation-name:{name};animation-duration:{dur}s;animation-delay:{delay:.3f}s{extra}"'


def svg(w, h, body, fonts, css="", title="", vb_pad=0):
    style = font_css(fonts) + BASE_CSS + css + (STATIC_CSS if STATIC else "")
    vb = f"{-vb_pad} {-vb_pad} {w + 2 * vb_pad} {h + 2 * vb_pad}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w + 2 * vb_pad}" height="{h + 2 * vb_pad}" '
        f'viewBox="{vb}" role="img" aria-label="{escape(title)}">'
        f"<title>{escape(title)}</title><style>{style}</style>{body}</svg>"
    )


def card_bg(w, h, fill=PAPER, stroke=RULE, r=18):
    return f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="{r}" fill="{fill}" stroke="{stroke}"/>'


def t(x, y, s, cls, size, fill=INK, extra=""):
    return f'<text x="{x}" y="{y}" class="{cls}" font-size="{size}" fill="{fill}" {extra}>{escape(str(s))}</text>'


def wrap(text, width):
    lines, cur = [], ""
    for word in text.split():
        if len(cur) + len(word) + (1 if cur else 0) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}" if cur else word
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------- data
def load_days():
    days = json.loads((DATA / "contributions.json").read_text())["days"]
    for d in days:
        d["d"] = dt.date.fromisoformat(d["date"])
    return days


def stats(days):
    total = sum(d["count"] for d in days)
    active = sum(1 for d in days if d["count"])
    busiest = max(days, key=lambda d: d["count"])
    longest = run = 0
    for d in days:
        run = run + 1 if d["count"] else 0
        longest = max(longest, run)
    current = 0
    seq = list(reversed(days))
    if seq and seq[0]["count"] == 0:  # today not yet counted doesn't break the streak
        seq = seq[1:]
    for d in seq:
        if not d["count"]:
            break
        current += 1
    months = OrderedDict()
    for d in days:
        key = d["d"].replace(day=1)
        months[key] = months.get(key, 0) + d["count"]
    return dict(total=total, active=active, busiest=busiest, longest=longest, current=current, months=months)


def gh_api(path):
    headers = {"User-Agent": "profile-readme-cards", "Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    req = urllib.request.Request(f"https://api.github.com{path}", headers=headers)
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def load_repos():
    cache = DATA / "repos.json"
    try:
        repos = gh_api(f"/users/{USER}/repos?per_page=100&type=owner")
        slim = [{k: r[k] for k in ("name", "description", "language", "fork", "pushed_at", "html_url", "stargazers_count")}
                for r in repos]
        cache.write_text(json.dumps(slim, indent=1))
        return slim
    except Exception as e:  # offline or rate-limited: keep yesterday's numbers
        print(f"GitHub API unavailable ({e}); using cached repos.json")
        return json.loads(cache.read_text())


# ---------------------------------------------------------------- cards
def hero(st):
    W, H = 840, 340
    art = (DATA / "portrait.txt").read_text().rstrip("\n").split("\n")
    b = [card_bg(W, H)]
    # label
    b.append(f'<g {anim("rise", 0.05)}>'
             + t(48, 62, "SOFTWARE ENGINEER  ·  UQ, BRISBANE", "mono6", 11, MUTED, 'letter-spacing="1.6"') + "</g>")
    # name: line 1 upright, line 2 italic with a blue shine sweeping through it
    b.append(f'<g {anim("rise", 0.18, 0.8)}>' + t(44, 148, "Hitaarnav", "serif", 84) + "</g>")
    b.append(
        '<defs><clipPath id="nm"><text x="46" y="226" class="italic" font-size="84">Bhatia.</text></clipPath>'
        f'<linearGradient id="sh" x1="0" x2="1"><stop offset="0" stop-color="{BLUE}" stop-opacity="0"/>'
        f'<stop offset=".5" stop-color="{BLUE}"/><stop offset="1" stop-color="{BLUE}" stop-opacity="0"/></linearGradient></defs>'
        f'<g {anim("rise", 0.34, 0.8)}>' + t(46, 226, "Bhatia.", "italic", 84)
        + '<g clip-path="url(#nm)"><rect class="shine sweep" x="-160" y="150" width="140" height="100" fill="url(#sh)"/></g></g>'
    )
    # one-liner
    for i, line in enumerate(["Full-stack developer who takes apps from code",
                              "to cloud: Django, React, Docker, AWS, Terraform."]):
        b.append(f'<g {anim("rise", 0.55 + i * 0.08)}>' + t(48, 266 + i * 22, line, "sans", 15.5, MUTED) + "</g>")
    # status line with pulsing dot
    b.append(
        f'<g {anim("fade", 0.9)}>'
        f'<circle cx="54" cy="311" r="4" fill="{BLUE}"/>'
        f'<circle class="a dot" cx="54" cy="311" r="4" fill="{BLUE}"/>'
        + t(66, 315, "Final-year BE (Hons) Software Eng  ·  open to graduate roles", "mono", 11, INK) + "</g>"
    )
    # ascii portrait printing in row by row
    x0, y0, lh, fs = 538, 46, 7.3, 7
    for i, row in enumerate(art):
        b.append(f'<text x="{x0}" y="{y0 + i * lh:.1f}" class="mono a" font-size="{fs}" fill="{INK}" xml:space="preserve" '
                 f'style="animation-name:print;animation-duration:.5s;animation-delay:{0.3 + i * 0.035:.3f}s">'
                 f"{escape(row)}</text>")
    css = (
        ".sweep{animation:sweep 5s 2.2s infinite ease-in-out}"
        "@keyframes sweep{0%{opacity:1;transform:translateX(0)}35%,100%{opacity:1;transform:translateX(560px)}}"
        ".dot{animation:pulse 1.8s infinite ease-out}"
    )
    return svg(W, H, "".join(b), ["serif", "italic", "mono", "mono6", "sans"], css, "Hitaarnav Bhatia, software engineer")


def graph(days, st):
    W, H = 840, 232
    cell, gap = 12, 3
    first = days[0]["d"] - dt.timedelta(days=(days[0]["d"].weekday() + 1) % 7)  # back to Sunday
    weeks = (days[-1]["d"] - first).days // 7 + 1
    x0 = (W - (weeks * (cell + gap) - gap)) / 2
    y0 = 82
    b = [card_bg(W, H)]
    b.append(f'<g {anim("rise", 0.1)}>'
             + f'<text x="{x0}" y="48" font-size="30" fill="{INK}"><tspan class="serif">{st["total"]:,} contributions</tspan>'
             + f'<tspan class="italic" fill="{MUTED}"> in the last year</tspan></text>'
             + "</g>")
    b.append(f'<g {anim("fade", 0.2)}>' + t(W - x0, 46, "LAST 53 WEEKS", "mono6", 10, MUTED,
                                             'text-anchor="end" letter-spacing="1.4"') + "</g>")
    seen = set()
    for d in days:
        col = (d["d"] - first).days // 7
        row = (d["d"].weekday() + 1) % 7
        x, y = x0 + col * (cell + gap), y0 + row * (cell + gap)
        if d["d"].day <= 7 and row == 0 and d["d"].month not in seen and col < weeks - 2:
            seen.add(d["d"].month)
            b.append(t(x, y0 - 8, d["d"].strftime("%b"), "mono", 9, MUTED))
        b.append(f'<rect x="{x:.1f}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{GRAPH[d["level"]]}" '
                 f'{anim("pop", 0.35 + col * 0.03 + row * 0.012, 0.45)}/>')
    # legend
    lx = W - x0 - 5 * (cell + gap) + gap - 30
    ly = y0 + 7 * (cell + gap) + 12
    b.append(f'<g {anim("fade", 2.2)}>' + t(lx - 8, ly + 10, "less", "mono", 9, MUTED, 'text-anchor="end"'))
    for i, c in enumerate(GRAPH):
        b.append(f'<rect x="{lx + i * (cell + gap)}" y="{ly}" width="{cell}" height="{cell}" rx="3" fill="{c}"/>')
    b.append(t(lx + 5 * (cell + gap) + 4, ly + 10, "more", "mono", 9, MUTED) + "</g>")
    return svg(W, H, "".join(b), ["serif", "italic", "mono", "mono6"], "", f"{st['total']} GitHub contributions in the last year")


def activity(st):
    W, H = 840, 270
    months = list(st["months"].items())[-13:]
    best_m, best_v = max(months, key=lambda kv: kv[1])
    top = max(best_v, 1)
    b = [card_bg(W, H)]
    b.append(f'<g {anim("rise", 0.1)}>' + t(44, 54, "Month by month", "serif", 30) + "</g>")
    b.append(f'<g {anim("fade", 0.2)}>' + t(44, 76, "CONTRIBUTIONS PER MONTH", "mono6", 10, MUTED,
                                             'letter-spacing="1.4"') + "</g>")
    base, maxh, bw = 222, 112, 24
    span = 500
    step = (span - bw) / (len(months) - 1)
    for i, (m, v) in enumerate(months):
        x = 44 + i * step
        h = max(v / top * maxh, 3)
        color = BLUE if m == best_m else (INK if v else RULE)
        b.append(f'<rect x="{x:.1f}" y="{base - h:.1f}" width="{bw}" height="{h:.1f}" rx="4" fill="{color}" '
                 f'class="a" style="animation-name:grow;animation-duration:.7s;animation-delay:{0.3 + i * 0.06:.2f}s;'
                 f'transform-origin:bottom"/>')
        b.append(t(x + bw / 2, base + 20, m.strftime("%b"), "mono", 9, BLUE if m == best_m else MUTED,
                   'text-anchor="middle"'))
        if m == best_m:
            b.append(f'<g {anim("pop", 0.3 + len(months) * 0.06 + 0.3, 0.5)}>'
                     + t(x + bw / 2, base - h - 10, v, "mono6", 13, BLUE, 'text-anchor="middle"') + "</g>")
    b.append(f'<line x1="44" x2="{44 + span}" y1="{base + .5}" y2="{base + .5}" stroke="{RULE}"/>')
    # stats grid
    bd = st["busiest"]
    items = [
        ("CURRENT STREAK", f"{st['current']}", "days" if st["current"] != 1 else "day"),
        ("LONGEST STREAK", f"{st['longest']}", "days" if st["longest"] != 1 else "day"),
        ("ACTIVE DAYS", f"{st['active']}", "of 365"),
        ("BUSIEST DAY", f"{bd['count']}", bd["d"].strftime("%b %-d")),
    ]
    b.append(f'<line x1="590" x2="590" y1="40" y2="{H - 40}" stroke="{RULE}"/>')
    for i, (label, val, unit) in enumerate(items):
        cx, cy = 618 + (i % 2) * 106, 92 + (i // 2) * 88
        b.append(f'<g {anim("rise", 0.5 + i * 0.1)}>'
                 + t(cx, cy, label, "mono6", 9, MUTED, 'letter-spacing="1.2"')
                 + t(cx, cy + 42, val, "serif", 44)
                 + t(cx + len(val) * 21 + 6, cy + 42, unit, "italic", 17, MUTED)
                 + "</g>")
    return svg(W, H, "".join(b), ["serif", "italic", "mono", "mono6"], "", "Contributions per month and streaks")


def tile(idx, label, color, fg, number, caption, cta, start):
    W, H, P = 272, 300, 14
    frames = 18
    b = [f'<g {anim("swing", start, 1.05)}>']
    b.append(f'<defs><clipPath id="c{idx}"><rect width="{W}" height="{H}" rx="20"/></clipPath>'
             f'<linearGradient id="g{idx}" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
             f'<stop offset=".5" stop-color="#fff" stop-opacity=".38"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>'
             f'</linearGradient></defs>')
    b.append(f'<rect width="{W}" height="{H}" rx="20" fill="{color}"/>')
    b.append(f'<g clip-path="url(#c{idx})">'
             f'<circle class="ring r1" cx="{W - 34}" cy="34" r="60" fill="none" stroke="{fg}" stroke-width="2"/>'
             f'<circle class="ring r2" cx="{W - 34}" cy="34" r="60" fill="none" stroke="{fg}" stroke-width="2"/>'
             f'<rect class="shine sw" x="-140" y="-60" width="110" height="{H + 120}" fill="url(#g{idx})" '
             f'transform="rotate(18 0 0)"/></g>')
    b.append(f'<circle cx="{W - 34}" cy="34" r="6" fill="{fg}"/>')
    b.append(t(24, 40, f"0{idx}", "mono6", 11, fg, 'opacity=".7"') + t(48, 40, label, "mono6", 11, fg, 'letter-spacing="1.8"'))
    # count-up: one text per frame, each shown for a moment, then the real number
    fs = start + 0.55
    for i in range(frames):
        v = round(number * (1 - (1 - i / frames) ** 3))
        b.append(f'<text x="22" y="150" class="serif cf" font-size="104" fill="{fg}" '
                 f'style="animation:blink .05s linear {fs + i * 0.05:.3f}s both">{v}</text>')
    b.append(f'<g {anim("fade", fs + frames * 0.05, 0.01)}>' + t(22, 150, number, "serif", 104, fg) + "</g>")
    for i, line in enumerate(caption):
        b.append(t(24, 192 + i * 20, line, "sans", 14, fg, 'opacity=".9"'))
    b.append(f'<line x1="24" x2="{W - 24}" y1="244" y2="244" stroke="{fg}" stroke-opacity=".25"/>')
    b.append(t(24, 272, cta, "mono6", 12, fg))
    b.append(f'<g class="a nud">' + t(W - 40, 273, "↗", "mono6", 16, fg) + "</g>")
    b.append("</g>")
    css = (
        f".r1{{animation:ring 3.2s {start + 1.2:.2f}s infinite ease-out}}"
        f".r2{{animation:ring 3.2s {start + 2.8:.2f}s infinite ease-out}}"
        f".sw{{animation:tsweep 6s {start + 1.6 + idx * 0.4:.2f}s infinite ease-in-out}}"
        "@keyframes tsweep{0%{opacity:1;transform:rotate(18deg) translateX(0)}30%,100%{opacity:1;transform:rotate(18deg) translateX(520px)}}"
        ".nud{animation:nudge 2.4s infinite}"
    )
    return svg(W, H, "".join(b), ["serif", "mono6", "sans"], css, f"{label}: {number}", vb_pad=P)


def stack_card():
    W, H = 840, 176
    b = [card_bg(W, H)]
    b.append(f'<g {anim("rise", 0.1)}>' + t(44, 52, "Tools I reach for", "serif", 30) + "</g>")
    k = 0
    for r, (label, items) in enumerate(STACK):
        y = 82 + r * 32
        b.append(f'<g {anim("fade", 0.2 + r * 0.1)}>' + t(44, y + 15, label, "mono6", 10, MUTED, 'letter-spacing="1.4"') + "</g>")
        x = 160
        for it in items:
            w = len(it) * 7.4 + 24
            col = [BLUE, INK, RED][r]
            b.append(f'<g {anim("pop", 0.3 + k * 0.035, 0.45)}>'
                     f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="22" rx="11" fill="none" stroke="{RULE}"/>'
                     f'<circle cx="{x + 12:.1f}" cy="{y + 11}" r="3" fill="{col}"/>'
                     + t(x + 20, y + 15, it, "mono", 11.5) + "</g>")
            x += w + 8
            k += 1
    return svg(W, H, "".join(b), ["serif", "mono", "mono6"], "", "Languages and tools")


def repo_card(i, name, kind, desc, lang, meta):
    W, H = 412, 192
    size = 26 if len(name) <= 18 else 21
    b = [f'<g {anim("rise", 0.15 + i * 0.12, 0.7)}>', card_bg(W, H, r=16)]
    b.append(t(26, 32, f"0{i + 1}  ·  {kind}", "mono6", 9.5, MUTED, 'letter-spacing="1.4"'))
    b.append(t(26, 66, name, "serif", size))
    b.append(f'<g class="a nud">' + t(W - 40, 36, "↗", "mono6", 16, BLUE) + "</g>")
    for j, line in enumerate(wrap(desc, 52)[:3]):
        b.append(t(26, 98 + j * 19, line, "sans", 13, MUTED))
    b.append(f'<circle cx="31" cy="{H - 27}" r="5" fill="{LANG_COLORS.get(lang, MUTED)}"/>')
    b.append(t(42, H - 23, lang, "mono", 11))
    b.append(t(W - 26, H - 23, meta, "mono", 11, MUTED, 'text-anchor="end"'))
    b.append("</g>")
    css = ".nud{animation:nudge 2.4s infinite}"
    return svg(W, H, "".join(b), ["serif", "mono", "mono6", "sans"], css, f"{name}: {desc}")


# ---------------------------------------------------------------- main
def main():
    CARDS.mkdir(exist_ok=True)
    days = load_days()
    st = stats(days)
    repos = load_repos()
    by_name = {r["name"]: r for r in repos}
    own = [r for r in repos if not r["fork"]]

    out = {
        "hero.svg": hero(st),
        "graph.svg": graph(days, st),
        "activity.svg": activity(st),
        "stack.svg": stack_card(),
        "build.svg": tile(1, "BUILD", BLUE, WHITE, len(own),
                          ["public repos: Django, React,", "Angular and a thesis tool"], "see the code", 0.1),
        "cloud.svg": tile(2, "CLOUD", RED, WHITE, 5,
                          ["AWS & IaC tools in my stack:", "Docker · ECS · ECR · S3 · TF"], "how I ship", 0.25),
        "learn.svg": tile(3, "LEARN", YELLOW, INK, st["active"],
                          ["days I pushed code this year,", "final-year SE at UQ"], "say hi", 0.4),
    }
    for i, f in enumerate(FEATURED):
        if "repo" in f:
            r = by_name.get(f["repo"])
            if not r:
                continue
            pushed = dt.datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00")).strftime("%b %Y")
            card = repo_card(i, r["name"], f["kind"], f["desc"] or r.get("description") or "",
                             r.get("language") or "Code", f"pushed {pushed}")
        else:
            card = repo_card(i, f["name"], f["kind"], f["desc"], f["lang"], f["meta"])
        out[f"repo-{i + 1}.svg"] = card
    for name, body in out.items():
        (CARDS / name).write_text(body)
        print(f"{name:14s} {len(body) / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
