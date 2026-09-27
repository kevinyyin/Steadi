"""Agreement charts (SVG + PNG) and one offline HTML page for `checkin validate`.

Visual rules follow the diagram-design skill (github.com/cathrynlavery/diagram-design), skinned with the
dashboard's own tokens: white paper, ink text, one blue accent on at most two focal marks per chart, hairline
rules, no shadows, legend as a bottom strip, every drawn value bound to a data-* attribute. Archivo only
(no serif or mono), because the page must work offline and match the dashboard.
"""

import base64
import html
import json
import math
from pathlib import Path

VENDOR = Path(__file__).parent / "static" / "vendor"
W, H = 960, 540
PAPER, PAPER2, INK, MUTED, SOFT = "#ffffff", "#eef0f4", "#080912", "#464b5d", "#6b7083"
RULE, RULE_SOLID, ACCENT, ACCENT_TINT = "#cdd1db", "#9aa0b0", "#2a4093", "rgba(42,64,147,0.12)"
FONT = "Archivo, system-ui, sans-serif"
HONEST = "Agreement with hand timing and counting, not a clinical validation."


def esc(s):
    return html.escape(str(s), quote=True)


def num(v, dp=2, sign=False, unit=""):
    s = f"{abs(v):.{dp}f}"
    s = ("+" if v > 0 else "−" if v < 0 else "") + s if sign else ("−" + s if v < 0 else s)
    return s + (f" {unit}" if unit else "")


def text(x, y, s, size=13, weight=400, fill=INK, anchor="start", extra=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}" {extra}>{esc(s)}</text>')


def _width(s, size):
    return len(str(s)) * size * 0.56


def nice_ticks(lo, hi, n=5):
    span = max(hi - lo, 1e-9)
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    start = math.floor(lo / step) * step
    ticks = [round(start, 6)]
    while ticks[-1] < hi - 1e-9:
        ticks.append(round(ticks[-1] + step, 6))
    return ticks


def frame(slug, title, desc, eyebrow, heading, sub, body, legend, foot, simulated):
    """The shared page: header (eyebrow, heading, one-line subtitle), body, bottom legend strip."""
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
        f'aria-labelledby="{slug}-title {slug}-desc" font-family="{FONT}">',
        f'<title id="{slug}-title">{esc(title)}</title>',
        f'<desc id="{slug}-desc">{esc(desc)}</desc>',
        f'<rect width="{W}" height="{H}" fill="{PAPER}"/>',
        text(40, 44, eyebrow.upper(), 12, 700, MUTED, extra='letter-spacing="0.08em"'),
        text(40, 78, heading, 26, 700),
        text(40, 104, sub, 15, 400, MUTED),
    ]
    if simulated:
        tw = _width("Simulated", 14) + 20
        x = W - 40 - tw
        parts += [f'<rect x="{x:.1f}" y="26" width="{tw:.1f}" height="26" rx="2" fill="{PAPER}" stroke="{INK}" '
                  f'stroke-width="1.5" stroke-dasharray="5,3" data-simulated="true"/>',
                  text(x + tw / 2, 44, "Simulated", 14, 700, INK, "middle")]
    parts.append(body)
    parts.append(f'<line x1="40" y1="484" x2="{W - 40}" y2="484" stroke="{RULE}" stroke-width="1"/>')
    x = 40
    for kind, label in legend:
        parts.append(_key(kind, x, 508))
        parts.append(text(x + 22, 512, label, 13, 400, MUTED))
        x += 22 + _width(label, 13) + 28
    parts.append(text(W - 40, 512, foot, 12, 400, SOFT, "end"))
    parts.append("</svg>")
    return "\n".join(parts)


def _key(kind, x, y):
    if kind == "dot":
        return f'<circle cx="{x + 7}" cy="{y}" r="5" fill="{INK}" fill-opacity="0.7" stroke="{INK}"/>'
    if kind == "ring":
        return f'<circle cx="{x + 7}" cy="{y}" r="5" fill="{PAPER}" stroke="{INK}" stroke-width="1.5"/>'
    if kind == "band":
        return (f'<rect x="{x}" y="{y - 7}" width="14" height="14" fill="{ACCENT_TINT}" stroke="{ACCENT}" '
                'stroke-opacity="0.35"/>')
    if kind == "identity":
        return (f'<line x1="{x}" y1="{y}" x2="{x + 14}" y2="{y}" stroke="{INK}" stroke-opacity="0.5" '
                'stroke-dasharray="4,3"/>')
    if kind == "bias":
        return f'<line x1="{x}" y1="{y}" x2="{x + 14}" y2="{y}" stroke="{ACCENT}" stroke-width="2"/>'
    if kind == "loa":
        return f'<line x1="{x}" y1="{y}" x2="{x + 14}" y2="{y}" stroke="{MUTED}" stroke-dasharray="5,4"/>'
    if kind == "bar":
        return f'<rect x="{x}" y="{y - 7}" width="14" height="14" fill="{INK}" fill-opacity="0.22" stroke="{MUTED}"/>'
    if kind == "bar-accent":
        return f'<rect x="{x}" y="{y - 7}" width="14" height="14" fill="{ACCENT}"/>'
    raise ValueError(kind)


def _stat(x, y, big, small, focal=False, size=30):
    fill = ACCENT if focal else INK
    return text(x, y, big, size, 700, fill) + text(x, y + 22, small, 14, 400, MUTED)


def _people(stats):
    n = sum(s["n"] + s["not_scored"] for s in stats)
    people = max((s["people"] for s in stats), default=0)
    return f"{n} trials" + (f", {people} people" if people else "")


# ---- charts --------------------------------------------------------------------------------------------

def scatter(slug, series, stats, tol, unit, what, simulated, truth_word="stopwatch"):
    """Belt (y) against ground truth (x) on one square plot with the ±tolerance band; stats on the right.

    `series`: list of (label, "dot" | "ring", pairs)."""
    pts = [(p["truth"], p["belt"]) for _, _, ps in series for p in ps]
    lo, hi = min(min(a, b) for a, b in pts), max(max(a, b) for a, b in pts)
    pad = max((hi - lo) * 0.08, tol)
    ticks = nice_ticks(max(0.0, lo - pad), hi + pad, 5)
    v0, v1 = ticks[0], ticks[-1]
    x0, y0, side = 112, 136, 288

    def sx(v):
        return x0 + (v - v0) / (v1 - v0) * side

    def sy(v):
        return y0 + side - (v - v0) / (v1 - v0) * side

    b = []
    for t in ticks:
        b.append(f'<line x1="{sx(t):.1f}" y1="{y0}" x2="{sx(t):.1f}" y2="{y0 + side}" stroke="{RULE}" '
                 'stroke-width="0.8"/>')
        b.append(f'<line x1="{x0}" y1="{sy(t):.1f}" x2="{x0 + side}" y2="{sy(t):.1f}" stroke="{RULE}" '
                 'stroke-width="0.8"/>')
        b.append(text(sx(t), y0 + side + 22, f"{t:g}", 12, 400, MUTED, "middle", f'data-tick="x" data-value="{t:g}"'))
        b.append(text(x0 - 10, sy(t) + 4, f"{t:g}", 12, 400, MUTED, "end", f'data-tick="y" data-value="{t:g}"'))
    band = [(v0, v0 - tol), (v1, v1 - tol), (v1, v1 + tol), (v0, v0 + tol)]
    clip = f"{slug}-plot"
    b.append(f'<clipPath id="{clip}"><rect x="{x0}" y="{y0}" width="{side}" height="{side}"/></clipPath>')
    b.append(f'<polygon clip-path="url(#{clip})" points="' + " ".join(f"{sx(a):.1f},{sy(c):.1f}" for a, c in band)
             + f'" fill="{ACCENT_TINT}" data-tolerance="{tol:g}"/>')
    b.append(f'<line x1="{sx(v0):.1f}" y1="{sy(v0):.1f}" x2="{sx(v1):.1f}" y2="{sy(v1):.1f}" stroke="{INK}" '
             f'stroke-opacity="0.5" stroke-dasharray="4,3"/>')
    b.append(f'<rect x="{x0}" y="{y0}" width="{side}" height="{side}" fill="none" stroke="{RULE_SOLID}"/>')
    b.append(text(x0 + side / 2, y0 + side + 44, f"{truth_word.capitalize()} ({unit})", 13, 700, INK, "middle"))
    b.append(text(x0, y0 - 12, f"Belt ({unit})", 13, 700, INK, "start"))
    stacked = {}
    for _, kind, ps in series:
        for p in ps:
            stacked[(p["truth"], p["belt"])] = stacked.get((p["truth"], p["belt"]), 0) + 1
            cx, cy = sx(p["truth"]), sy(p["belt"])
            attrs = f'data-x="{p["truth"]:g}" data-y="{p["belt"]:g}" data-step="{esc(p["step"])}"'
            if kind == "dot":
                b.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" fill="{INK}" fill-opacity="0.7" '
                         f'stroke="{PAPER}" stroke-width="1" {attrs}/>')
            else:
                b.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" fill="{PAPER}" fill-opacity="0.6" '
                         f'stroke="{INK}" stroke-width="1.5" {attrs}/>')
    for (tx, by), k in stacked.items():
        if k > 2:
            lx, ly = sx(tx) + 10, sy(by) + 24
            b.append(f'<rect x="{lx - 4:.1f}" y="{ly - 13:.1f}" width="{_width(f"×{k}", 12) + 8:.1f}" '
                     f'height="18" rx="2" fill="{PAPER}"/>')
            b.append(text(lx, ly, f"×{k}", 12, 700, MUTED, "start", f'data-count="{k}"'))
    s = stats
    px = 472
    b.append(_stat(px, 172, f"{s['within']} of {s['n']}", f"trials within ±{tol:g} {unit} of the {truth_word}",
                   True, 40))
    b.append(_stat(px, 250, num(s["bias"], 2, True, unit), f"mean difference, belt minus {truth_word}"))
    typical = num(s["mae"], 2, unit=unit) + (f" ({s['mae_pct']:g}%)" if s.get("mae_pct") is not None else "")
    b.append(_stat(px, 318, typical, "typical error (mean absolute difference)"))
    if s.get("cutoff"):
        c = s["cutoff"]
        b.append(_stat(px, 386, f"{c['agree']} of {c['n']}", f"on the same side of the STEADI {c['what']}"))
    legend = [(kind, label) for label, kind, _ in series] + [("band", f"within ±{tol:g} {unit}"),
                                                            ("identity", f"belt = {truth_word}")]
    n = sum(len(ps) for _, _, ps in series)
    return frame(slug, f"Belt vs {truth_word}: {what}",
                 f"Scatter of {n} {what} trials, belt time against {truth_word} time, {s['within']} of {s['n']} "
                 f"within {tol:g} {unit}; mean difference {num(s['bias'], 2, True, unit)}.",
                 f"Steady hardware check · {what}", f"Belt vs {truth_word}: {what}",
                 f"Each dot is one trial. Dots on the dashed line mean the belt and the {truth_word} agreed exactly.",
                 "\n".join(b), legend, HONEST, simulated)


def bland_altman(slug, pairs, s, tol, unit, what, simulated, truth_word="stopwatch"):
    """Difference (belt − truth) against the mean of the two, with bias and 95% limits of agreement."""
    means = [(p["belt"] + p["truth"]) / 2 for p in pairs]
    diffs = [p["diff"] for p in pairs]
    xt = nice_ticks(min(means) - 0.5, max(means) + 0.5, 6)
    reach = max([abs(d) for d in diffs] + [tol, abs(s["loa"][0]), abs(s["loa"][1])]) * 1.25
    yt = nice_ticks(-reach, reach, 6)
    x0, x1, y0, y1 = 112, 604, 136, 424

    def sx(v):
        return x0 + (v - xt[0]) / (xt[-1] - xt[0]) * (x1 - x0)

    def sy(v):
        return y1 - (v - yt[0]) / (yt[-1] - yt[0]) * (y1 - y0)

    b = []
    for t in xt:
        b.append(f'<line x1="{sx(t):.1f}" y1="{y0}" x2="{sx(t):.1f}" y2="{y1}" stroke="{RULE}" stroke-width="0.8"/>')
        b.append(text(sx(t), y1 + 22, f"{t:g}", 12, 400, MUTED, "middle", f'data-tick="x" data-value="{t:g}"'))
    for t in yt:
        b.append(f'<line x1="{x0}" y1="{sy(t):.1f}" x2="{x1}" y2="{sy(t):.1f}" stroke="{RULE}" stroke-width="0.8"/>')
        label = num(t, 1, True) if t else "0"
        b.append(text(x0 - 10, sy(t) + 4, label, 12, 400, MUTED, "end", f'data-tick="y" data-value="{t:g}"'))
    b.append(f'<rect x="{x0}" y="{sy(tol):.1f}" width="{x1 - x0}" height="{sy(-tol) - sy(tol):.1f}" '
             f'fill="{ACCENT_TINT}" data-tolerance="{tol:g}"/>')
    b.append(f'<line x1="{x0}" y1="{sy(0):.1f}" x2="{x1}" y2="{sy(0):.1f}" stroke="{RULE_SOLID}" stroke-width="1"/>')
    for v in s["loa"]:
        b.append(f'<line x1="{x0}" y1="{sy(v):.1f}" x2="{x1}" y2="{sy(v):.1f}" stroke="{MUTED}" '
                 f'stroke-dasharray="5,4" data-loa="{v:g}"/>')
    b.append(f'<line x1="{x0}" y1="{sy(s["bias"]):.1f}" x2="{x1}" y2="{sy(s["bias"]):.1f}" stroke="{ACCENT}" '
             f'stroke-width="2" data-bias="{s["bias"]:g}"/>')
    b.append(f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" fill="none" stroke="{RULE_SOLID}"/>')
    for m, p in zip(means, pairs, strict=True):
        b.append(f'<circle cx="{sx(m):.1f}" cy="{sy(p["diff"]):.1f}" r="5" fill="{INK}" fill-opacity="0.6" '
                 f'stroke="{PAPER}" stroke-width="1" data-x="{m:g}" data-y="{p["diff"]:g}"/>')
    b.append(text((x0 + x1) / 2, y1 + 44, f"Average of belt and {truth_word} ({unit})", 13, 700, INK, "middle"))
    b.append(text(x0, y0 - 12, f"Belt minus {truth_word} ({unit})", 13, 700, INK))
    px = 652
    b.append(_stat(px, 172, num(s["bias"], 2, True, unit), "mean difference (bias)", True, 40))
    b.append(_stat(px, 250, f"{num(s['loa'][0], 2, True)} to {num(s['loa'][1], 2, True)} {unit}",
                   "95% limits of agreement", size=26))
    b.append(_stat(px, 318, f"{s['within']} of {s['n']}", f"within ±{tol:g} {unit}", size=26))
    b.append(text(px, 386, "About 95% of trials should fall", 14, 400, MUTED))
    b.append(text(px, 406, "between the dashed lines. A bias", 14, 400, MUTED))
    b.append(text(px, 426, "away from zero is a steady offset.", 14, 400, MUTED))
    legend = [("dot", "one trial"), ("bias", "mean difference"), ("loa", "95% limits"), ("band", f"±{tol:g} {unit}")]
    return frame(slug, f"Bland-Altman: {what}",
                 f"Bland-Altman plot of {len(pairs)} {what} trials: mean difference {num(s['bias'], 2, True, unit)}, "
                 f"95% limits of agreement {num(s['loa'][0], 2, True)} to {num(s['loa'][1], 2, True)} {unit}.",
                 f"Steady hardware check · {what}", f"How far apart the belt and {truth_word} are: {what}",
                 "Bland-Altman plot: the gap between the two methods against the size of the measurement.",
                 "\n".join(b), legend, HONEST, simulated)


def counts(slug, groups, simulated):
    """Small multiples: how many trials the belt counted exactly, one over, one under, …

    `groups`: list of (stats, pairs) for count measures."""
    bins = [-3, -2, -1, 0, 1, 2, 3]
    b = []
    gap = 48
    pw = (W - 80 - gap * (len(groups) - 1)) / len(groups)
    for i, (s, pairs) in enumerate(groups):
        px = 40 + i * (pw + gap)
        hist = {k: 0 for k in bins}
        for p in pairs:
            hist[max(-3, min(3, round(p["diff"])))] += 1
        top = max(hist.values()) or 1
        b.append(text(px, 152, s["label"], 18, 700))
        b.append(text(px, 176, f"{s['exact']} of {s['n']} counted exactly · {s['within']} of {s['n']} within ±1",
                      14, 400, MUTED))
        bw, y1, hmax = pw / len(bins), 424, 196
        for j, k in enumerate(bins):
            h = hist[k] / top * hmax
            x = px + j * bw + bw * 0.18
            w = bw * 0.64
            if hist[k]:
                if k == 0:
                    b.append(f'<rect x="{x:.1f}" y="{y1 - h:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{ACCENT}" '
                             f'data-bin="{k}" data-value="{hist[k]}"/>')
                else:
                    b.append(f'<rect x="{x:.1f}" y="{y1 - h:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{INK}" '
                             f'fill-opacity="0.22" stroke="{MUTED}" data-bin="{k}" data-value="{hist[k]}"/>')
                b.append(text(x + w / 2, y1 - h - 8, hist[k], 14, 700, ACCENT if k == 0 else INK, "middle"))
            label = "exact" if k == 0 else ("< −2" if k == -3 else "> +2" if k == 3 else num(k, 0, True))
            b.append(text(x + w / 2, y1 + 22, label, 13, 700 if k == 0 else 400, INK if k == 0 else MUTED, "middle"))
        b.append(f'<line x1="{px}" y1="{y1}" x2="{px + pw:.1f}" y2="{y1}" stroke="{RULE_SOLID}"/>')
        b.append(text(px + pw / 2, y1 + 44, "Belt minus hand count", 13, 700, INK, "middle"))
    what = " and ".join(s["label"].split(" (")[0].lower() for s, _ in groups)
    total = sum(s["n"] for s, _ in groups)
    exact = sum(s["exact"] for s, _ in groups)
    legend = [("bar-accent", "belt count = hand count"), ("bar", "belt over (+) or under (−) by that many")]
    return frame(slug, "Belt vs hand count", f"Histogram of belt count minus hand count for {what}: {exact} of "
                 f"{total} trials counted exactly.", "Steady hardware check · counting",
                 "Belt vs hand count", "Each bar is how many trials landed at that difference.",
                 "\n".join(b), legend, HONEST, simulated)


def summary(slug, stats, simulated):
    """One row per measure: the share of trials in agreement, as a bar, with its numbers."""
    rows = list(stats.values())
    b = []
    y = 140
    step = min(64, 320 / max(1, len(rows)))
    bx, bw = 464, 300
    for i, s in enumerate(rows):
        if s["n"] == 0:
            continue
        focal = i == 0
        if s["kind"] == "count":
            k, what = s["exact"], "counted exactly"
            detail = (f"{s['within']} of {s['n']} within ±{s['tol']:g} · "
                      f"mean difference {num(s['bias'], 2, True, s['unit'])}")
        else:
            k, what = s["within"], f"within ±{s['tol']:g} {s['unit']}"
            detail = (f"mean difference {num(s['bias'], 2, True, s['unit'])} · "
                      f"typical error {num(s['mae'], 2, unit=s['unit'])}")
        share = k / s["n"]
        b.append(text(40, y + 16, s["label"], 18, 700))
        b.append(text(40, y + 38, detail, 13, 400, MUTED))
        b.append(f'<rect x="{bx}" y="{y + 8}" width="{bw}" height="20" fill="{PAPER2}"/>')
        b.append(f'<rect x="{bx}" y="{y + 8}" width="{bw * share:.1f}" height="20" fill="{ACCENT if focal else INK}" '
                 f'fill-opacity="{1 if focal else 0.78}" data-value="{k}" data-of="{s["n"]}"/>')
        b.append(text(bx + bw + 20, y + 24, f"{k} of {s['n']}", 20, 700, ACCENT if focal else INK))
        b.append(text(bx + bw + 20, y + 44, what, 13, 400, MUTED))
        y += step
    legend = [("bar-accent", "share of trials in agreement (the headline test)"), ("bar", "other tests")]
    return frame(slug, "Belt agreement summary",
                 "Share of trials where the belt agreed with the stopwatch or hand count, per test: "
                 + "; ".join(f"{s['label']} {s.get('exact', s['within'])} of {s['n']}" for s in rows if s["n"]) + ".",
                 "Steady hardware check", "How closely the belt matches a stopwatch and a hand count",
                 _people(rows) + (" · simulated sessions with made-up ground truth" if simulated else
                                  " · ground truth timed and counted by hand"),
                 "\n".join(b), legend, HONEST, simulated)


# ---- files ---------------------------------------------------------------------------------------------

def charts(pairs, stats, simulated):
    """{slug: svg} for every chart the data supports."""
    scored = [p for p in pairs if p["belt"] is not None]
    by = {m: [p for p in scored if p["measure"] == m] for m in stats}
    out = {"summary": summary("summary", stats, simulated)}
    walk = [(label, kind, by[m]) for m, label, kind in
            (("tug", "TUG", "dot"), ("dual_tug", "Dual-task TUG", "ring")) if by.get(m)]
    if walk:
        s = stats["tug"] if by.get("tug") else stats["dual_tug"]
        allp = [p for _, _, ps in walk for p in ps]
        from .validate import agreement

        pooled = agreement(allp, s["tol"], "time")
        if by.get("tug") and "cutoff" in s:
            pooled["cutoff"] = s["cutoff"]
        out["tug-scatter"] = scatter("tug-scatter", walk, pooled, s["tol"], "s", "Timed Up and Go", simulated)
        out["tug-bland-altman"] = bland_altman("tug-bland-altman", allp, pooled, s["tol"], "s", "Timed Up and Go",
                                               simulated)
    if by.get("balance"):
        s = stats["balance"]
        out["balance-scatter"] = scatter("balance-scatter", [("Balance hold", "dot", by["balance"])], s, s["tol"],
                                         "s", "balance holds", simulated)
        out["balance-bland-altman"] = bland_altman("balance-bland-altman", by["balance"], s, s["tol"], "s",
                                                   "balance holds", simulated)
    groups = [(stats[m], by[m]) for m in ("chair_stand", "sit_to_stand") if by.get(m)]
    if groups:
        out["counts"] = counts("counts", groups, simulated)
    return out


def to_png(svg, path, zoom=2):
    import resvg_py

    png = resvg_py.svg_to_bytes(svg_string=svg, font_dirs=[str(VENDOR)], skip_system_fonts=True, zoom=zoom)
    Path(path).write_bytes(bytes(png))


def page(pairs, stats, svgs, simulated, source):
    font = base64.b64encode((VENDOR / "archivo.woff2").read_bytes()).decode()
    rows = []
    for s in stats.values():
        if s["n"] == 0:
            rows.append(f"<tr><td>{esc(s['label'])}</td><td>0</td><td colspan=6>none scored</td></tr>")
            continue
        u = s["unit"]
        agree = (f"{s['exact']} of {s['n']} exact" if s["kind"] == "count"
                 else f"{s['within']} of {s['n']}")
        within = f"{s['within']} of {s['n']} (±{s['tol']:g})"
        cut = f"{s['cutoff']['agree']} of {s['cutoff']['n']}" if s.get("cutoff") else "–"
        missed = f" (+{s['not_scored']} not scored)" if s["not_scored"] else ""
        rows.append(
            f"<tr><td>{esc(s['label'])}</td><td>{s['n']}{missed}</td>"
            f"<td>{esc(num(s['bias'], 2, True, u))}</td><td>{esc(num(s['mae'], 2, unit=u))}</td>"
            f"<td>{esc(num(s['loa'][0], 2, True))} to {esc(num(s['loa'][1], 2, True, u))}</td>"
            f"<td>{esc(within)}</td><td>{esc(agree if s['kind'] == 'count' else '–')}</td><td>{cut}</td></tr>")
    trials = []
    for p in pairs:
        belt = "not scored: " + p["not_scored"] if p["belt"] is None else f"{p['belt']:g}"
        diff = "–" if p["diff"] is None else num(p["diff"], 2, True)
        trials.append(f"<tr><td>{esc(p['recording'])}</td><td>{esc(p['step'])}</td><td>{esc(p['person'])}</td>"
                      f"<td>{p['truth']:g}</td><td>{esc(belt)}</td><td>{esc(diff)}</td>"
                      f"<td>{'Simulated' if p['simulated'] else ''}</td></tr>")
    sections = []
    titles = {"summary": "At a glance", "tug-scatter": "Timed Up and Go: belt vs stopwatch",
              "tug-bland-altman": "Timed Up and Go: how far apart",
              "balance-scatter": "Balance holds: belt vs stopwatch",
              "balance-bland-altman": "Balance holds: how far apart",
              "counts": "Chair stands and reps: belt vs hand count"}
    for slug, svg in svgs.items():
        sections.append(f'<section aria-label="{esc(titles[slug])}"><figure>{svg}</figure>'
                        f'<p class="files">Files: <a href="{slug}.svg">{slug}.svg</a> · '
                        f'<a href="{slug}.png">{slug}.png</a></p>'
                        f"</section>")
    banner = ('<p class="sim"><strong>Simulated.</strong> These sessions came from the simulator and the ground-truth '
              "numbers were made up to exercise this report. They are not measurements of the belt.</p>"
              if simulated else "")
    total = sum(s["n"] + s["not_scored"] for s in stats.values())
    n_people = max((s["people"] for s in stats.values()), default=0)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Steady hardware check{' (Simulated)' if simulated else ''}</title>
<style>
@font-face {{ font-family: "Archivo"; src: url(data:font/woff2;base64,{font}) format("woff2");
  font-weight: 100 900; font-stretch: 62% 125%; }}
:root {{ --ink: {INK}; --muted: {MUTED}; --line: {RULE}; --blue: {ACCENT}; --ground: {PAPER2}; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #fff; color: var(--ink); font: 18px/1.5 "Archivo", system-ui, sans-serif; }}
main {{ max-width: 1040px; margin: 0 auto; padding: 48px 24px 64px; }}
.eyebrow {{ margin: 0; color: var(--muted); font-weight: 700; font-size: 14px; letter-spacing: 0.08em;
  text-transform: uppercase; }}
h1 {{ margin: 8px 0 8px; font-size: clamp(2rem, 1.5rem + 2vw, 3rem); line-height: 1.05; font-weight: 780;
  letter-spacing: -0.015em; }}
.lede {{ margin: 0 0 24px; color: var(--muted); max-width: 64ch; }}
.sim {{ border: 2px dashed var(--ink); border-radius: 2px; padding: 12px 16px; max-width: 72ch; }}
section {{ border-top: 1px solid var(--line); padding-top: 24px; margin-top: 40px; }}
h2 {{ margin: 0 0 16px; font-size: 1.5rem; font-weight: 750; }}
figure {{ margin: 0; overflow-x: auto; }}
figure svg {{ width: 100%; height: auto; display: block; }}
.files {{ color: var(--muted); font-size: 15px; }}
a {{ color: var(--blue); }}
table {{ border-collapse: collapse; width: 100%; font-size: 16px; font-variant-numeric: tabular-nums; }}
th, td {{ text-align: left; padding: 8px 12px 8px 0; border-bottom: 1px solid var(--line); vertical-align: top; }}
th {{ font-weight: 700; }}
.wide {{ overflow-x: auto; }}
details summary {{ cursor: pointer; font-weight: 700; padding: 8px 0; }}
ul {{ max-width: 72ch; padding-left: 1.2em; }}
footer {{ margin-top: 48px; border-top: 1px solid var(--line); padding-top: 16px; color: var(--muted);
  font-size: 15px; }}
</style></head>
<body><main>
<p class="eyebrow">Steady hardware check</p>
<h1>How closely the belt matches a stopwatch and a hand count</h1>
<p class="lede">{total} trials{f' from {n_people} people' if n_people else ''}.
The belt's number is re-scored from each raw recording by the same code the dashboard uses; the stopwatch and hand
counts were entered separately. {esc(HONEST)}</p>
{banner}
{''.join(sections)}
<section><h2>The numbers</h2><div class="wide"><table>
<tr><th>Test</th><th>Trials</th><th>Mean difference (belt minus hand)</th><th>Typical error</th>
<th>95% limits of agreement</th><th>Within tolerance</th><th>Exact count</th><th>Same side of STEADI cutoff</th></tr>
{''.join(rows)}</table></div></section>
<section><h2>What this shows, and what it doesn't</h2><ul>
<li>It shows how often the belt lands close to a person with a stopwatch or counting out loud, on our own team
and volunteers. The stopwatch has its own error (reaction time on start and stop), so this is agreement between two
methods, not the belt's true accuracy.</li>
<li>It is not a clinical validation: no patients, no clinic, no fall outcomes. The belt is a fall-risk screening aid;
it doesn't diagnose anything or say when someone will fall.</li>
<li>"Typical error" is the mean absolute difference. The 95% limits are mean difference ± 1.96 standard
deviations of the differences (Bland-Altman). "Same side of the cutoff" counts trials where the belt and the
stopwatch agree on whether a STEADI cutoff (TUG 12 s, tandem stance 10 s) was crossed.</li>
<li>Every trial with a ground-truth number is listed below, including any the belt could not score.</li>
</ul></section>
<section><details><summary>Every trial ({len(pairs)})</summary><div class="wide"><table>
<tr><th>Recording</th><th>Step</th><th>Person</th><th>Hand</th><th>Belt</th><th>Difference</th><th></th></tr>
{''.join(trials)}</table></div></details></section>
<footer>Made by <code>checkin validate {esc(source)}</code>. Charts: SVG and PNG next to this file; numbers in
results.json.</footer>
</main></body></html>
"""


def write(out_dir, pairs, stats, simulated, source, png=True):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    svgs = charts(pairs, stats, simulated)
    files = []
    for slug, svg in svgs.items():
        (out / f"{slug}.svg").write_text(svg)
        files.append(out / f"{slug}.svg")
        if png:
            to_png(svg, out / f"{slug}.png")
            files.append(out / f"{slug}.png")
    (out / "report.html").write_text(page(pairs, stats, svgs, simulated, source))
    (out / "results.json").write_text(json.dumps({"simulated": simulated, "stats": stats, "trials": pairs}, indent=1))
    return [out / "report.html", out / "results.json", *files]
