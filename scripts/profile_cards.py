#!/usr/bin/env python3
"""Profil README'sindeki analiz kartlarını ve kupaları SVG olarak üretir.

Renkler github_design/DESIGN.md'deki analytics katmanından gelir (tokyonight).
Veri GitHub REST API'den çekilir; GITHUB_TOKEN tanımlıysa kullanılır.

    python scripts/profile_cards.py --user umranmeryemkarabakal --out assets/cards
    python scripts/profile_cards.py --data data.json --out assets/cards   # önceden kaydedilmiş veriden
"""
import argparse
import json
import math
import os
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape

BG, TITLE, ICON, TEXT, GRID = "#1a1b27", "#70a5fd", "#bf91f3", "#38bdae", "#2a2c3d"
FG, MUTED, GOLD, TROPHY_TITLE = "#e6edf3", "#8b949e", "#e7c057", "#ff6b9d"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', sans-serif"
UTC_OFFSET = 3

LANG_COLORS = {
    "Python": "#3572A5", "Jupyter Notebook": "#DA5B0B", "C++": "#f34b7d", "C": "#555555",
    "MATLAB": "#e16737", "HTML": "#e34c26", "CSS": "#663399", "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6", "CMake": "#DA3434", "Shell": "#89e051", "Kotlin": "#A97BFF",
    "Java": "#b07219", "Makefile": "#427819", "Dockerfile": "#384d54", "TeX": "#3D6117",
    "Arduino": "#00979D", "Processing": "#0096D8", "Cython": "#fedf5b", "Batchfile": "#C1F12E",
}
OTHER = "#8b949e"

GITHUB_MARK = ("M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49"
               "-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 "
               "1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59"
               ".82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 "
               "1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 "
               "3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42"
               "-3.58-8-8-8z")


# ---------------------------------------------------------------- veri

def api(path, token):
    req = urllib.request.Request("https://api.github.com" + path)
    req.add_header("Accept", "application/vnd.github+json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def paged(path, token, limit=20):
    items, page = [], 1
    sep = "&" if "?" in path else "?"
    while page <= limit:
        try:
            batch = api(f"{path}{sep}per_page=100&page={page}", token)
        except urllib.error.HTTPError as e:
            if e.code == 409:  # boş depo
                return items
            raise
        items += batch
        if len(batch) < 100:
            break
        page += 1
    return items


def collect(user, token):
    profile = api(f"/users/{user}", token)
    repos = [r for r in paged(f"/users/{user}/repos?type=owner", token) if not r["fork"]]
    commits, lang_bytes = [], Counter()
    for r in repos:
        lang_bytes.update(api(f"/repos/{user}/{r['name']}/languages", token))
        for c in paged(f"/repos/{user}/{r['name']}/commits?author={user}", token):
            commits.append(c["commit"]["author"]["date"])
    count = lambda q: api(f"/search/issues?q=author:{user}+{q}&per_page=1", token)["total_count"]
    return {
        "login": profile["login"],
        "name": profile.get("name") or profile["login"],
        "created_at": profile["created_at"],
        "public_repos": profile["public_repos"],
        "followers": profile["followers"],
        "stars": sum(r["stargazers_count"] for r in repos),
        "prs": count("type:pr"),
        "issues": count("type:issue"),
        "commits": commits,
        "repo_languages": dict(Counter(r["language"] for r in repos if r["language"])),
        "language_bytes": dict(lang_bytes),
    }


# ---------------------------------------------------------------- yardımcılar

def parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def card(w, h, title, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<style>text{{font-family:{FONT}}}</style>'
            f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="4.5" fill="{BG}"/>'
            f'<text x="24" y="38" font-size="18" font-weight="600" fill="{TITLE}">{escape(title)}</text>'
            f'{body}</svg>')


def top(counter, n=5):
    items = sorted(counter.items(), key=lambda kv: -kv[1])
    head, rest = items[:n], sum(v for _, v in items[n:])
    if rest:
        head.append(("Other", rest))
    return head


def donut(cx, cy, r, stroke, items):
    total = sum(v for _, v in items) or 1
    out, angle = [], -math.pi / 2
    for name, v in items:
        sweep = 2 * math.pi * v / total
        color = LANG_COLORS.get(name, OTHER)
        if sweep >= 2 * math.pi - 1e-6:
            out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="{stroke}"/>')
        else:
            x1, y1 = cx + r * math.cos(angle), cy + r * math.sin(angle)
            x2, y2 = cx + r * math.cos(angle + sweep), cy + r * math.sin(angle + sweep)
            large = 1 if sweep > math.pi else 0
            out.append(f'<path d="M{x1:.2f} {y1:.2f} A{r} {r} 0 {large} 1 {x2:.2f} {y2:.2f}" fill="none" '
                       f'stroke="{color}" stroke-width="{stroke}"/>')
        angle += sweep
    return "".join(out)


def legend(x, y, items):
    rows = []
    for i, (name, _) in enumerate(items):
        yy = y + i * 22
        rows.append(f'<rect x="{x}" y="{yy - 10}" width="12" height="12" fill="{LANG_COLORS.get(name, OTHER)}"/>'
                    f'<text x="{x + 20}" y="{yy}" font-size="13" fill="{TEXT}">{escape(name)}</text>')
    return "".join(rows)


def smooth(points):
    d = f"M{points[0][0]:.1f} {points[0][1]:.1f}"
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        mx = (x0 + x1) / 2
        d += f" C{mx:.1f} {y0:.1f} {mx:.1f} {y1:.1f} {x1:.1f} {y1:.1f}"
    return d


# ---------------------------------------------------------------- kartlar

def profile_details(d, now):
    since = now - timedelta(days=365)
    recent = [parse(c) for c in d["commits"] if parse(c) >= since]
    months = [(now.year, now.month)]
    for _ in range(11):
        y, m = months[0]
        months.insert(0, (y - 1, 12) if m == 1 else (y, m - 1))
    per = Counter((c.year, c.month) for c in recent)
    vals = [per[m] for m in months]
    peak = max(vals) or 1
    x0, x1, y0, y1 = 360, 676, 60, 170
    pts = [(x0 + i * (x1 - x0) / 11, y1 - (y1 - y0) * v / peak) for i, v in enumerate(vals)]
    area = smooth(pts) + f" L{x1} {y1} L{x0} {y1} Z"
    grid = "".join(f'<path d="M{x0} {y} H{x1}" stroke="{GRID}"/>' for y in (y0, (y0 + y1) / 2, y1))
    labels = "".join(f'<text x="{x:.1f}" y="{y1 + 16}" font-size="10" fill="{TEXT}" text-anchor="middle">'
                     f'{m:02d}/{str(y)[2:]}</text>'
                     for (x, _), (y, m) in zip(pts, months) if months.index((y, m)) % 2 == 0)
    years = (now - parse(d["created_at"])).days / 365.25
    rows = [
        (f"{len(recent)} commits in the last year", "M3 8a5 5 0 1 0 10 0 5 5 0 0 0-10 0zm-3 0h3m10 0h3"),
        (f"{d['public_repos']} public repos", "M2 1h10l2 2v12H2z"),
        (f"Joined GitHub {years:.0f} years ago" if years >= 1.5 else "Joined GitHub a year ago",
         "M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm0 3v4l3 2"),
    ]
    body = "".join(
        f'<g transform="translate(24 {70 + i * 30})"><path d="{icon}" fill="none" stroke="{ICON}" stroke-width="1.5"/>'
        f'<text x="26" y="12" font-size="14" fill="{TEXT}">{escape(text)}</text></g>'
        for i, (text, icon) in enumerate(rows))
    body += (grid + f'<path d="{area}" fill="{ICON}" fill-opacity="0.85"/>' + labels +
             f'<text x="{x1}" y="{y0 - 10}" font-size="10" fill="{TEXT}" text-anchor="end">'
             f'commits per month · peak {peak}</text>')
    return card(700, 200, f"{d['name']} ({d['login']})", body)


def languages(title, counter):
    items = top(counter)
    body = legend(24, 76, items) + donut(250, 112, 50, 28, items)
    return card(340, 200, title, body)


def productive_time(d):
    hours = Counter((parse(c) + timedelta(hours=UTC_OFFSET)).hour for c in d["commits"])
    peak = max(hours.values(), default=0) or 1
    x0, x1, y0, y1 = 44, 316, 56, 160
    bw = (x1 - x0) / 24
    bars = "".join(
        f'<rect x="{x0 + h * bw + 1:.1f}" y="{y1 - (y1 - y0) * hours[h] / peak:.1f}" width="{bw - 2:.1f}" '
        f'height="{(y1 - y0) * hours[h] / peak:.1f}" fill="{ICON}"/>' for h in range(24))
    axis = "".join(f'<text x="{x0 + h * bw + bw / 2:.1f}" y="{y1 + 14}" font-size="10" fill="{TEXT}" '
                   f'text-anchor="middle">{h}</text>' for h in (0, 6, 12, 18, 23))
    yl = "".join(f'<text x="{x0 - 6}" y="{y + 3}" font-size="10" fill="{TEXT}" text-anchor="end">{v}</text>'
                 f'<path d="M{x0} {y} H{x1}" stroke="{GRID}"/>'
                 for v, y in ((peak, y0), (0, y1)))
    body = yl + bars + axis + f'<text x="{x1}" y="{y1 + 30}" font-size="10" fill="{TEXT}" text-anchor="end">per day hour</text>'
    return card(340, 200, f"Commits (UTC +{UTC_OFFSET})", body)


def stats(d):
    rows = [("Total Stars:", d["stars"]), ("Total Commits:", len(d["commits"])), ("Total PRs:", d["prs"]),
            ("Total Issues:", d["issues"]), ("Public Repos:", d["public_repos"])]
    body = "".join(f'<circle cx="30" cy="{66 + i * 26}" r="4" fill="none" stroke="{ICON}" stroke-width="1.5"/>'
                   f'<text x="44" y="{70 + i * 26}" font-size="14" fill="{TEXT}">{t}</text>'
                   f'<text x="170" y="{70 + i * 26}" font-size="14" fill="{TEXT}" text-anchor="end">{v}</text>'
                   for i, (t, v) in enumerate(rows))
    body += (f'<circle cx="262" cy="112" r="50" fill="{ICON}"/>'
             f'<g transform="translate(234 84) scale(3.5)"><path d="{GITHUB_MARK}" fill="{BG}"/></g>')
    return card(340, 200, "Stats", body)


TROPHIES = [
    # başlık, değer anahtarı, (S, A, B, C) eşikleri, unvanlar
    ("MultiLanguage", "languages", (10, 7, 5, 3), ("Rainbow Lang User", "Polyglot", "Multilingual", "Bilingual")),
    ("Commits", "commits", (1000, 500, 200, 50), ("Hyper Committer", "Ultra Committer", "Super Committer", "Committer")),
    ("Repositories", "repos", (50, 30, 20, 10), ("Repo Creator", "Repo Builder", "Repo Maker", "Repo Starter")),
    ("Experience", "years", (5, 4, 3, 2), ("Veteran", "Seasoned", "Experienced", "Regular")),
    ("Stars", "stars", (100, 50, 20, 5), ("Star Master", "High Star", "Star Collector", "First Stars")),
    ("Followers", "followers", (100, 50, 20, 5), ("Famous User", "Active User", "Known User", "Everyone's Friend")),
    ("PullRequest", "prs", (100, 50, 20, 5), ("Pull Master", "High Puller", "Puller", "First Pull")),
    ("Issues", "issues", (100, 50, 20, 5), ("Issue Master", "High Issuer", "Issuer", "First Issue")),
]


def trophies(d, now):
    values = {
        "languages": len(set(d["language_bytes"]) | set(d["repo_languages"])),
        "commits": len(d["commits"]), "repos": d["public_repos"],
        "years": int((now - parse(d["created_at"])).days / 365.25),
        "stars": d["stars"], "followers": d["followers"], "prs": d["prs"], "issues": d["issues"],
    }
    # yalnızca kazanılmış kupalar gösterilir
    earned = []
    for cat, key, limits, titles in TROPHIES:
        rank = next((r for r, lim in zip("SABC", limits) if values[key] >= lim), None)
        if rank:
            earned.append((cat, key, rank, titles["SABC".index(rank)]))
    w, h, gap = 110, 118, 15
    cols = max(1, min(4, len(earned)))
    rows = max(1, math.ceil(len(earned) / cols))
    W, H = cols * w + (cols - 1) * gap, rows * h + (rows - 1) * gap
    parts = []
    for i, (cat, key, rank, title) in enumerate(earned):
        x, y = (i % cols) * (w + gap), (i // cols) * (h + gap)
        v = values[key]
        cup = GOLD
        parts.append(
            f'<g transform="translate({x} {y})">'
            f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="4.5" fill="{BG}"/>'
            f'<text x="{w / 2}" y="18" font-size="10" font-weight="700" fill="{TROPHY_TITLE}" text-anchor="middle">{cat}</text>'
            f'<path d="M30 58 q-10 -4 -12 -16 M80 58 q10 -4 12 -16" fill="none" stroke="{TEXT}" stroke-width="1.5" opacity="0.7"/>'
            f'<path d="M40 30 h30 v12 a15 15 0 0 1 -30 0 z" fill="{cup}"/>'
            f'<path d="M40 34 h-6 a6 6 0 0 0 6 10 M70 34 h6 a6 6 0 0 1 -6 10" fill="none" stroke="{cup}" stroke-width="2"/>'
            f'<rect x="51" y="57" width="8" height="8" fill="{cup}"/><rect x="44" y="64" width="22" height="5" rx="1" fill="{cup}"/>'
            f'<text x="{w / 2}" y="47" font-size="13" font-weight="700" fill="{BG}" text-anchor="middle">{rank}</text>'
            f'<text x="{w / 2}" y="88" font-size="10" font-weight="600" fill="{FG}" text-anchor="middle">{escape(title)}</text>'
            f'<text x="{w / 2}" y="104" font-size="9" fill="{MUTED}" text-anchor="middle">{v} {key}</text>'
            f'</g>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            f'<style>text{{font-family:{FONT}}}</style>{"".join(parts)}</svg>')


def render(d, out):
    now = datetime.now(timezone.utc)
    os.makedirs(out, exist_ok=True)
    files = {
        "profile-details.svg": profile_details(d, now),
        "repos-per-language.svg": languages("Top Languages by Repo", d["repo_languages"]),
        "code-per-language.svg": languages("Top Languages by Code", d["language_bytes"]),
        "productive-time.svg": productive_time(d),
        "stats.svg": stats(d),
        "trophies.svg": trophies(d, now),
    }
    for name, svg in files.items():
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            f.write(svg)
    print(f"{len(files)} kart yazıldı: {out}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--user", default="umranmeryemkarabakal")
    p.add_argument("--data", help="API yerine bu JSON dosyasındaki veriyi kullan")
    p.add_argument("--save", help="çekilen veriyi bu JSON dosyasına da yaz")
    p.add_argument("--out", default="assets/cards")
    a = p.parse_args()
    if a.data:
        with open(a.data, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = collect(a.user, os.environ.get("GITHUB_TOKEN"))
    if a.save:
        with open(a.save, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    render(data, a.out)
