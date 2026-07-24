#!/usr/bin/env python3
"""Generate the terminal-styled SVG blocks for the profile README.

Stdlib only. Fetches public GitHub data (user, repos, contribution calendar)
and renders each README section as a dark + light SVG under assets/.
"""

import json
import os
import re
import sys
import urllib.request
from datetime import date, datetime
from pathlib import Path
from string import Template
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

WIDTH = 880
PAD_X = 28
LINE_H = 22
FONT_SIZE = 14
CHAR_W = 8.4
FONT_STACK = (
    "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
)

PALETTES = {
    "dark": {
        "fg": "#e6edf3",
        "dim": "#848d97",
        "faint": "#3d444d",
        "green": "#3fb950",
    },
    "light": {
        "fg": "#1f2328",
        "dim": "#59636e",
        "faint": "#d1d9e0",
        "green": "#1a7f37",
    },
}


# ---------------------------------------------------------------- data fetch

def fetch(url: str) -> bytes:
    headers = {"User-Agent": "derFinlay-profile-generator"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def fetch_json(url: str):
    return json.loads(fetch(url))


def fetch_contributions(login: str) -> list[tuple[str, int]]:
    """Return [(iso_date, count)] for every day on the public calendar."""
    html = fetch(f"https://github.com/users/{login}/contributions").decode()
    days = {}
    for td in re.finditer(r"<td\b[^>]*ContributionCalendar-day[^>]*>", html):
        tag = td.group(0)
        m_id = re.search(r'id="([^"]+)"', tag)
        m_date = re.search(r'data-date="([\d-]+)"', tag)
        m_level = re.search(r'data-level="(\d+)"', tag)
        if m_id and m_date:
            level = int(m_level.group(1)) if m_level else 0
            days[m_id.group(1)] = [m_date.group(1), level]
    counts = {}
    for m in re.finditer(r'<tool-tip\b[^>]*for="([^"]+)"[^>]*>([^<]*)</tool-tip>', html):
        num = re.match(r"(\d+) contribution", m.group(2).strip())
        counts[m.group(1)] = int(num.group(1)) if num else 0
    result = []
    for key, (day, level) in days.items():
        result.append((day, counts.get(key, level)))
    return sorted(result)


# ------------------------------------------------------------- svg plumbing

def seg(style: str, text: str) -> tuple[str, str]:
    return (style, text)


CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def esc_text(text: str) -> str:
    return escape(CONTROL_CHARS.sub("", text))


def esc_attr(text: str) -> str:
    return escape(CONTROL_CHARS.sub("", text), {'"': "&quot;"})


def render_line(segments: list[tuple[str, str]], y: float, pal: dict) -> str:
    spans = "".join(
        f'<tspan fill="{pal[style.removesuffix("-b")]}"'
        + (' font-weight="600"' if style.endswith("-b") else "")
        + f">{esc_text(text)}</tspan>"
        for style, text in segments
    )
    return f'<text x="{PAD_X}" y="{y:g}" xml:space="preserve">{spans}</text>'


def svg_block(lines: list[list[tuple[str, str]]], pal: dict, label: str,
              extra: str = "", height_extra: int = 0) -> str:
    pad_top = 8
    height = pad_top + len(lines) * LINE_H + 10 + height_extra
    body = "".join(
        render_line(line, pad_top + 15 + i * LINE_H, pal)
        for i, line in enumerate(lines)
        if line
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{esc_attr(label)}">'
        f"<style>text{{font-family:{FONT_STACK};font-size:{FONT_SIZE}px;"
        f"white-space:pre}}</style>{extra}{body}</svg>"
    )


def cmd_line(command: str) -> list[tuple[str, str]]:
    return [seg("dim", "$ "), seg("fg-b", command)]


# ------------------------------------------------------------------- blocks

def build_hero(cfg: dict, pal: dict) -> str:
    typed = "whoami"
    prompt = [("dim", "finlay@arch"), ("faint", ":"), ("dim", "~"), ("fg", "$ ")]
    prompt_chars = sum(len(t) for _, t in prompt)
    x0 = PAD_X
    top = 56
    css = Template("""
    text{font-family:$font;font-size:14px;white-space:pre}
    .c{animation:show .01s steps(1) both}
    .out{animation:show .01s steps(1) 1.15s both}
    .l3{animation:show .01s steps(1) 1.55s both}
    .cur1{opacity:0;animation:on .01s steps(1) .18s forwards,
      mv .66s steps(6,end) .2s forwards,off .01s steps(1) 1.1s forwards}
    .cur2{animation:blink 1.2s steps(1) 1.6s infinite both}
    @keyframes show{from{opacity:0}to{opacity:1}}
    @keyframes on{to{opacity:1}}
    @keyframes off{to{opacity:0}}
    @keyframes mv{from{transform:translateX(0)}to{transform:translateX(${travel}px)}}
    @keyframes blink{0%,49%{opacity:1}50%,100%{opacity:0}}
    @media (prefers-reduced-motion:reduce){*{animation:none !important}.cur1{opacity:0}}
    """).substitute(font=FONT_STACK, travel=f"{len(typed) * CHAR_W:g}")

    def prompt_spans() -> str:
        return "".join(
            f'<tspan fill="{pal[s]}" textLength="{len(t) * CHAR_W:g}" '
            f'lengthAdjust="spacingAndGlyphs">{escape(t)}</tspan>'
            for s, t in prompt
        )

    typed_spans = "".join(
        f'<tspan class="c" style="animation-delay:{0.2 + i * 0.11:.2f}s" '
        f'fill="{pal["fg"]}" textLength="{CHAR_W:g}" '
        f'lengthAdjust="spacingAndGlyphs">{c}</tspan>'
        for i, c in enumerate(typed)
    )
    cursor_x = x0 + prompt_chars * CHAR_W
    height = 148
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" role="img" aria-label="Terminal: whoami — {esc_attr(cfg['hero_output'])}">
<style>{css}</style>
<rect x="1.5" y="1.5" width="{WIDTH - 3}" height="{height - 3}" rx="8" fill="none" stroke="{pal['faint']}" stroke-width="1.5"/>
<line x1="1.5" y1="34" x2="{WIDTH - 1.5}" y2="34" stroke="{pal['faint']}" stroke-width="1"/>
<text x="{WIDTH / 2:g}" y="22" text-anchor="middle" fill="{pal['dim']}" xml:space="preserve">finlay@arch — zsh</text>
<text x="{x0}" y="{top + 8}" xml:space="preserve">{prompt_spans()}{typed_spans}</text>
<rect class="cur1" x="{cursor_x:g}" y="{top - 5}" width="{CHAR_W:g}" height="17" fill="{pal['fg']}"/>
<text class="out" x="{x0}" y="{top + 8 + LINE_H + 4}" fill="{pal['fg']}" xml:space="preserve">{esc_text(cfg['hero_output'])}</text>
<g class="l3"><text x="{x0}" y="{top + 8 + 2 * (LINE_H + 4)}" xml:space="preserve">{prompt_spans()}</text>
<rect class="cur2" x="{cursor_x:g}" y="{top - 5 + 2 * (LINE_H + 4)}" width="{CHAR_W:g}" height="17" fill="{pal['fg']}"/></g>
</svg>"""


def uptime_since(start: str) -> str:
    begin = date.fromisoformat(start)
    today = date.today()
    months = (today.year - begin.year) * 12 + today.month - begin.month
    if today.day < begin.day:
        months -= 1
    years, months = divmod(months, 12)
    parts = []
    if years:
        parts.append(f"{years} year" + ("s" if years != 1 else ""))
    if months:
        parts.append(f"{months} month" + ("s" if months != 1 else ""))
    return " ".join(parts) or "0 months"


def build_status(user: dict, cfg: dict, pal: dict) -> str:
    bio = (user.get("bio") or "").strip()
    title = f" ({bio})" if bio else ""
    langs = " · ".join(cfg["tasks"])
    lines = [
        cmd_line("systemctl status finlay.service"),
        [seg("green-b", "●"), seg("fg-b", " finlay.service"),
         seg("fg", f" - {user.get('name', '').strip()}{title}")],
        [seg("dim", "     Loaded:"), seg("fg", " loaded (/home/finlay/.career; "),
         seg("green", "enabled"), seg("fg", "; preset: "), seg("green", "enabled"), seg("fg", ")")],
        [seg("dim", "     Active:"), seg("green-b", " active (running)"),
         seg("fg", f" since {cfg['career_start']}; {uptime_since(cfg['career_start'])} ago")],
        [seg("dim", "   Main PID:"), seg("fg", f" {user['id']} (github)")],
        [seg("dim", "      Tasks:"), seg("fg", f" {len(cfg['tasks'])} ({langs})")],
        [seg("dim", "     CGroup:"), seg("fg", " /career.slice/finlay.service")],
    ]
    branches = cfg["cgroup"]
    for i, entry in enumerate(branches):
        arm = "└─" if i == len(branches) - 1 else "├─"
        text, _, note = entry.partition(" — ")
        lines.append([seg("faint", f"             {arm} "), seg("fg", text),
                      seg("dim", f" — {note}" if note else "")])
    return svg_block(lines, pal, "systemctl status finlay.service — active (running)")


def build_career(cfg: dict, pal: dict) -> str:
    entries = cfg["career"]
    unit_w = max(len(e["unit"]) for e in entries) + 2
    desc_w = max(len(e["desc"]) for e in entries) + 2
    lines = [
        cmd_line("systemctl list-units 'career-*' --all"),
        [seg("dim", f"{'UNIT':<{unit_w}}{'LOAD':<8}{'ACTIVE':<10}DESCRIPTION")],
    ]
    for e in entries:
        state = ("green-b", "active   ") if e["active"] else ("dim", "inactive ")
        lines.append([
            seg("fg-b", f"{e['unit']:<{unit_w}}"), seg("dim", f"{'loaded':<8}"),
            seg(*state), seg("fg", f" {e['desc']:<{desc_w}}"),
            seg("dim", e["period"]),
        ])
    lines.append([seg("faint", f"{len(entries)} loaded units listed.")])
    return svg_block(lines, pal, "systemctl list-units career — " +
                     "; ".join(f"{e['desc']} ({e['period']})" for e in entries))


def build_journal(contribs: list[tuple[str, int]], pal: dict) -> str:
    active = [(d, c) for d, c in contribs if c > 0]
    recent = active[-8:]
    lines = [cmd_line("journalctl -u finlay.service -n 8 --no-pager")]
    for day, count in recent:
        stamp = datetime.strptime(day, "%Y-%m-%d").strftime("%b %d")
        noun = "contribution" if count == 1 else "contributions"
        msg = f"pushed {count} {noun}"
        lines.append([
            seg("dim", f"{stamp}  "), seg("faint", "arch "),
            seg("dim", "finlay[git]: "), seg("fg", f"{msg:<28}"),
            seg("fg", "▮" * min(count, 12)),
        ])
    lines.append([seg("faint", f"── {len(active)} active days in the last year ──")])
    return svg_block(lines, pal, f"journalctl — {len(active)} active days in the last year")


def build_skills(cfg: dict, pal: dict) -> str:
    lines = [cmd_line("pacman -Q skills")]
    for name, level in cfg["skills"]:
        level = max(0, min(10, int(level)))
        bar = [seg("fg", f"{name:<18}"), seg("faint", "["),
               seg("fg", "#" * level), seg("faint", "-" * (10 - level) + "]")]
        lines.append(bar)
    return svg_block(lines, pal, "pacman -Q skills — " + ", ".join(n for n, _ in cfg["skills"]))


def build_projects(repos: list[dict], cfg: dict, pal: dict) -> str:
    shown = [r for r in repos
             if not r["fork"] and r["name"].lower() != cfg["login"].lower()]
    shown.sort(key=lambda r: r["pushed_at"], reverse=True)
    width = max((len(r["name"]) for r in shown), default=8) + 2
    lines = [cmd_line("ls -l ~/projects")]
    for repo in shown:
        desc = cfg["project_descriptions"].get(repo["name"]) or repo.get("description") or ""
        lines.append([
            seg("dim", "drwxr-xr-x  finlay  "),
            seg("fg-b", f"{repo['name'] + '/':<{width}}"),
            seg("dim", desc),
        ])
    return svg_block(lines, pal, "ls ~/projects — " + ", ".join(r["name"] for r in shown))


def build_contact(user: dict, cfg: dict, pal: dict) -> str:
    entries = [("email", cfg["contact"]["email"]),
               ("web", cfg["contact"]["web"]),
               ("location", user.get("location") or "Germany")]
    lines = [cmd_line("cat ~/.config/contact.conf"), [seg("faint", "[contact]")]]
    for key, value in entries:
        lines.append([seg("dim", f"{key:<9}"), seg("faint", "= "), seg("fg", value)])
    return svg_block(lines, pal, "contact — " + " · ".join(v for _, v in entries))


# --------------------------------------------------------------------- main

def main() -> int:
    cfg = json.loads((ROOT / "profile.json").read_text())
    login = cfg["login"]
    user = fetch_json(f"https://api.github.com/users/{login}")
    repos = fetch_json(f"https://api.github.com/users/{login}/repos?per_page=100&type=owner")
    contribs = fetch_contributions(login)

    builders = {
        "hero": lambda pal: build_hero(cfg, pal),
        "status": lambda pal: build_status(user, cfg, pal),
        "career": lambda pal: build_career(cfg, pal),
        "journal": lambda pal: build_journal(contribs, pal),
        "skills": lambda pal: build_skills(cfg, pal),
        "projects": lambda pal: build_projects(repos, cfg, pal),
        "contact": lambda pal: build_contact(user, cfg, pal),
    }
    ASSETS.mkdir(exist_ok=True)
    for name, build in builders.items():
        for theme, pal in PALETTES.items():
            path = ASSETS / f"{name}-{theme}.svg"
            path.write_text(build(pal) + "\n")
            print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
