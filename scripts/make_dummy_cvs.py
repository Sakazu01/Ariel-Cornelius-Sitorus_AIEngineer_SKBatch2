"""Bikin CV PDF dummy dan label jawabannya.

Pakai: python scripts/make_dummy_cvs.py   (butuh reportlab)
Hasil: data/cvs/*.pdf (13 CV: 5 dari core_cvs.py + 8 dari cv_specs.py) dan data/golden/labels.json
Datanya ada di cv_specs.py. Ada 4 gaya CV, masing-masing 2 CV (relevan dan tidak relevan).
"""
import json
import re
from pathlib import Path

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (BaseDocTemplate, Flowable, Frame, FrameBreak, HRFlowable, PageTemplate, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from core_cvs import CORE_LABELS, render_core
from cv_fonts import SANS, SANS_B, SANS_I, SERIF, SERIF_B, SERIF_I
from cv_specs import SPECS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "cvs"
REF = "2026-11"
JOB = json.loads((ROOT / "data" / "jobs" / "ai_engineer.json").read_text(encoding="utf-8"))
W, H = A4

# salinan kecil daftar alias skill dari notebook (dipakai buat cek label)
ALIASES = {
    "python": ["python", "python3"],
    "sql": ["sql", "postgresql", "postgres", "mysql", "sqlite"],
    "machine learning": ["machine learning", "ml", "scikit-learn", "sklearn", "xgboost", "lightgbm", "deep learning", "pytorch",
                         "tensorflow", "keras", "neural network", "neural networks"],
    "nlp": ["nlp", "natural language processing"],
    "llm": ["llm", "llms", "large language model", "large language models", "prompt engineering", "langchain", "llamaindex", "openai api"],
    "rag": ["rag", "retrieval-augmented generation", "retrieval augmented generation", "vector database", "vector db", "faiss", "pinecone", "chromadb"],
    "docker": ["docker", "docker compose", "containerization"],
    "fastapi": ["fastapi"],
    "cloud": ["aws", "gcp", "google cloud", "azure"],
}
_B = r"(?<![A-Za-z0-9+#])(?:{})(?![A-Za-z0-9+#])"
_PAT = {k: re.compile(_B.format("|".join(re.escape(a) for a in sorted(v, key=len, reverse=True))), re.I) for k, v in ALIASES.items()}


def mentions(text):
    return {k for k, p in _PAT.items() if p.search(text)}


# ----------------------------------------------------------------------------- tanggal dan label
MON = {"en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
       "id": ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]}
LONG = {"en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
        "id": ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]}
NOW = {"en": "Present", "id": "Sekarang"}


def fmt(ym, lang, style):
    if ym is None:
        return NOW[lang]
    y, m = int(ym[:4]), int(ym[5:])
    return f"{(LONG if style == 'long' else MON)[lang][m - 1]} {y}"


def span(s, e, lang, style):
    return f"{fmt(s, lang, style)} - {fmt(e, lang, style)}"


def months(exp):
    iv = sorted((int(s[:4]) * 12 + int(s[5:]), int((e or REF)[:4]) * 12 + int((e or REF)[5:])) for _, _, _, s, e, _ in exp)
    total, cur = 0, None
    for a, b in iv:
        if cur and a <= cur[1]:
            cur[1] = max(cur[1], b)
        else:
            if cur:
                total += cur[1] - cur[0] + 1
            cur = [a, b]
    return total + (cur[1] - cur[0] + 1 if cur else 0)


TITLES = {
    1: dict(en=dict(edu="Education", exp="Work Experience", orgs="Related Experiences", proj="Projects", certs="Certification", awards="Award", skills="Skills")),
    3: dict(en=dict(summary="Summary", exp="Work Experience", proj="Projects", skills="Skills", edu="Education", certs="Certifications", langs="Languages")),
}


def T(c, key):
    return c.get("titles", {}).get(key) or TITLES[c["style"]]["en"][key]


# ----------------------------------------------------------------------------- label jawaban
def expected_tier(c):
    if c.get("hidden"):
        return "flag_manual_review"
    lvl = {s: 1.0 for s in c["demo"]} | {s: JOB["listed_credit"] for s in c["listed"]}
    must = sum(lvl.get(s, 0) for s in JOB["must_have"]) / len(JOB["must_have"])
    nice = sum(lvl.get(s, 0) for s in JOB["nice_to_have"]) / len(JOB["nice_to_have"])
    exp = min(1.0, months(c["exp"]) / JOB["min_experience_months"])
    w, t = JOB["weights"], JOB["thresholds"]
    score = w["must_have"] * must + w["nice_to_have"] * nice + w["experience"] * exp
    return "strong_match" if score >= t["strong"] else "partial_match" if score >= t["partial"] else "weak_match"


def check(c):
    """Label harus persis dengan isi CV: demo ada di bullet, listed cuma di daftar skill, tidak ada skill baku lain."""
    bl = [b for e in c["exp"] for b in e[5]] + [b for e in c["orgs"] for b in e[4]] + [b for e in c["proj"] for b in e[2]] + [b for e in c["edu"] for b in e[4]]
    in_bullets = mentions(" ".join(bl))
    in_skills = mentions(" ".join(v for _, v in c["skills"]))
    everything = " ".join(bl + [c["summary"], c.get("headline", ""), " ".join(x for x, _ in c["certs"]), " ".join(c["awards"]), " ".join(v for _, v in c["skills"])])
    assert set(c["demo"]) <= in_bullets, (c["id"], "demo tidak ada di bullet", set(c["demo"]) - in_bullets)
    for s in c["listed"]:
        assert s in in_skills and s not in in_bullets, (c["id"], "listed salah", s)
    extra = mentions(everything) - set(c["demo"]) - set(c["listed"])
    assert not extra, (c["id"], "skill baku tidak berlabel", extra)


# ----------------------------------------------------------------------------- helper tampilan
def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def rich(s):
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc(s))


def st(font, size, color="#000000", align=TA_LEFT, lead=None, **kw):
    return ParagraphStyle("x", fontName=font, bulletFontName=font, fontSize=size, leading=lead or size * 1.28, textColor=HexColor(color), alignment=align, **kw)


def P(text, style):
    return Paragraph(rich(text), style)


def bullets(items, style):
    return [Paragraph(rich(x), style, bulletText="•") for x in items]


def lr(l, r, wl, wr):
    t = Table([[l, r]], colWidths=[wl, wr])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return t


def hidden_line(c):
    return Paragraph(esc(c["hidden_text"]), st(SANS, 1, "#ffffff", lead=1.2))  # putih, ukuran 1: manusia tidak lihat


class Icon(Flowable):
    """Ikon kecil bulat untuk baris kontak (surel, telepon, in, lokasi)."""

    def __init__(self, kind, d=11, color="#222222"):
        super().__init__()
        self.kind, self.d, self.color = kind, d, color
        self.width = self.height = d

    def draw(self):
        c, r = self.canv, self.d / 2
        c.setFillColor(HexColor(self.color))
        c.circle(r, r, r, stroke=0, fill=1)
        c.setFillColor(white)
        c.setStrokeColor(white)
        c.setLineWidth(0.7)
        if self.kind == "mail":
            c.rect(r - 3, r - 2, 6, 4, stroke=1, fill=0)
            c.line(r - 3, r + 2, r, r - 0.3)
            c.line(r + 3, r + 2, r, r - 0.3)
        elif self.kind == "phone":
            c.roundRect(r - 1.8, r - 3.2, 3.6, 6.4, 0.8, stroke=1, fill=0)
        elif self.kind == "pin":
            c.circle(r, r + 0.6, 2.3, stroke=1, fill=0)
            c.circle(r, r + 0.6, 0.7, stroke=0, fill=1)
        else:
            c.setLineWidth(0.9)  # huruf "in" digambar sebagai garis supaya tidak ikut terbaca sebagai teks
            c.line(r - 2.4, r - 2, r - 2.4, r + 0.8)
            c.circle(r - 2.4, r + 2.4, 0.5, stroke=0, fill=1)
            c.line(r - 0.4, r - 2, r - 0.4, r + 0.8)
            c.line(r - 0.4, r + 0.5, r + 1.4, r + 0.8)
            c.line(r + 1.8, r - 2, r + 1.8, r + 0.6)


def icon_row(items, size=8.6, color="#222222", font=SANS):
    cells, widths = [], []
    for kind, text in items:
        cells += [Icon(kind), Paragraph(esc(text), st(font, size, color, lead=size + 2))]
        widths += [15, stringWidth(text, font, size) + 14]
    t = Table([cells], colWidths=widths)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    t.hAlign = "LEFT"
    return t


class Avatar(Flowable):
    """Placeholder foto: siluet abu-abu di lingkaran biru muda (bukan foto orang)."""

    def __init__(self, d=76):
        super().__init__()
        self.d = self.width = self.height = d

    def draw(self):
        c, d = self.canv, self.d
        c.saveState()
        p = c.beginPath()
        p.circle(d / 2, d / 2, d / 2)
        c.clipPath(p, stroke=0, fill=0)
        c.setFillColor(HexColor("#d6e4f5"))
        c.rect(0, 0, d, d, stroke=0, fill=1)
        c.setFillColor(HexColor("#7d8fb0"))
        c.ellipse(d * 0.12, -d * 0.30, d * 0.88, d * 0.50, stroke=0, fill=1)
        c.setFillColor(HexColor("#8e9fbf"))
        c.circle(d / 2, d * 0.60, d * 0.20, stroke=0, fill=1)
        c.restoreState()


def heading(text, style, thick=0.9, color="#000000", before=0, after=3):
    return [Paragraph(esc(text), style), HRFlowable(width="100%", thickness=thick, color=HexColor(color), spaceBefore=1, spaceAfter=after)]


def mark(c):
    return [Spacer(1, 2)]


# ----------------------------------------------------------------------------- style 1: klasik serif
def style1(c):
    M = 42
    CW = W - 2 * M - 12  # frame SimpleDocTemplate punya padding 6 di tiap sisi
    F, FB, FI = SERIF, SERIF_B, SERIF_I
    name = st(F, 27, align=TA_CENTER, lead=31)
    ctr = st(F, 10.5, align=TA_CENTER, lead=13.5)
    body = st(F, 11, lead=14.4)
    bl = st(F, 10.7, lead=13.8, leftIndent=13, bulletIndent=2, spaceAfter=1.5)
    org, orgr, role, rolr = st(FB, 11), st(FB, 10.6, align=TA_RIGHT), st(FI, 10.8), st(FB, 10.6, align=TA_RIGHT)
    hd = st(FB, 12, lead=15, spaceBefore=11)
    link = "#1a56b0"
    parts = []
    for x in c["contact"]:
        parts.append(f'<font color="{link}">{esc(x)}</font>' if ("@" in x or "linkedin" in x or "github" in x) else esc(x))
    s = [Paragraph(esc(c["name"].upper()), name), Paragraph(" &nbsp;|&nbsp; ".join(parts), ctr), Paragraph(esc(c["loc"]), ctr), Spacer(1, 8), P(c["summary"], body)]
    if c.get("hidden"):
        s.append(hidden_line(c))
    wl, wr = CW - 150, 150

    def sec(key):
        s.extend(heading(T(c, key).upper(), hd))

    sec("edu")
    for inst, deg, loc, yrs, bl_ in c["edu"]:
        s += [lr(P(inst, org), P(loc, orgr), wl, wr), lr(P(deg, role), P(yrs, rolr), wl, wr)] + bullets(bl_, bl) + [Spacer(1, 3)]
    if c["exp"]:
        sec("exp")
        for t, co, loc, a, b, bl_ in c["exp"]:
            s += [lr(P(co, org), P(loc, orgr), wl, wr), lr(P(t, role), P(span(a, b, c["lang"], c["dates"]), rolr), wl, wr)] + bullets(bl_, bl) + [Spacer(1, 3)]
    if c["orgs"]:
        sec("orgs")
        for t, co, loc, per, bl_ in c["orgs"]:
            s += [lr(P(co, org), P(loc, orgr), wl, wr), lr(P(t, role), P(per, rolr), wl, wr)] + bullets(bl_, bl) + [Spacer(1, 3)]
    if c["certs"]:
        sec("certs")
        s += bullets([f"{x}, {y}" for x, y in c["certs"]], bl)
    if c["awards"]:
        sec("awards")
        s += bullets(c["awards"], bl)
    sec("skills")
    s += bullets([f"{k}: {v}" if k else v for k, v in c["skills"]], bl)
    return s, dict(leftMargin=M, rightMargin=M, topMargin=34, bottomMargin=30)


# ----------------------------------------------------------------------------- style 2: sederhana ala Word
def style2(c):
    M = 46
    CW = W - 2 * M - 12  # frame SimpleDocTemplate punya padding 6 di tiap sisi
    F, FB, FI = SANS, SANS_B, SANS_I
    name = st(FB, 12.5, align=TA_CENTER, lead=16)
    ctr = st(F, 9.4, align=TA_CENTER, lead=12.4)
    body = st(F, 9.8, lead=13)
    bl = st(F, 9.8, lead=12.8, leftIndent=12, bulletIndent=2, spaceAfter=1)
    org, orgr = st(SANS_B, 10), st(SANS_B, 9.8, align=TA_RIGHT)
    hd = st(FB, 10.4, lead=13, spaceBefore=12)
    s = [Paragraph(esc(c["name"].upper()), name), Paragraph(" | ".join(esc(x) for x in c["contact"]), ctr), Paragraph(esc(c["loc"]), ctr)]
    s += [Paragraph(esc(x), ctr) for x in c.get("extra", [])]
    s.append(Spacer(1, 6))
    wl, wr = CW - 175, 175

    def sec(key):
        s.extend(heading(c["titles"][key], hd, thick=0.8))

    sec("summary")
    s.append(P(c["summary"], body))
    if c.get("hidden"):
        s.append(hidden_line(c))
    sec("edu")
    for inst, deg, loc, yrs, bl_ in c["edu"]:
        s += [lr(P(inst, org), P(yrs, orgr), wl, wr), P(deg, body)] + bullets(bl_, bl)
    if c["certs"]:
        sec("certs")
        for x, y in c["certs"]:
            s.append(lr(P(x, body), P(y, st(F, 9, align=TA_RIGHT)), wl, wr))
    sec("skills")
    s += [P("; ".join(f"{k}: {v}" if k else v for k, v in c["skills"]), body)]
    sec("exp")
    for t, co, loc, a, b, bl_ in c["exp"]:
        s += [lr(P(f"{co} / {t}", org), P(span(a, b, c["lang"], c["dates"]), orgr), wl, wr)] + bullets(bl_, bl) + [Spacer(1, 3)]
    if c["orgs"]:
        sec("orgs")
        for t, co, loc, per, bl_ in c["orgs"]:
            s += [lr(P(f"{t} / {co}", org), P(per, orgr), wl, wr)] + bullets(bl_, bl) + [Spacer(1, 3)]
    return s, dict(leftMargin=M, rightMargin=M, topMargin=36, bottomMargin=30)


# ----------------------------------------------------------------------------- style 3: modern dua kolom
def build_style3(c, path):
    M, GAP = 40, 22
    LW = 322
    RW = W - 2 * M - GAP - LW
    F, FB, FI = SANS, SANS_B, SANS_I
    name = st(FB, 27, lead=31)
    head = st(SANS_B, 11, "#222222", lead=14)
    body = st(F, 9.7, "#222222", lead=13)
    bl = st(F, 9.5, "#222222", lead=12.6, leftIndent=11, bulletIndent=1, spaceAfter=2)
    hd = st(FB, 9.4, lead=12, spaceBefore=11)
    ttl, dt, sub = st(FB, 10, lead=12.6), st(F, 9, "#555555", align=TA_RIGHT, lead=12.6), st(FI, 9.4, "#444444", lead=12)
    HH = 98
    top = H - 34
    hdr = Frame(M, top - HH, W - 2 * M, HH, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    left = Frame(M, 30, LW, top - HH - 30, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    right = Frame(M + LW + GAP, 30, RW, top - HH - 30, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc = BaseDocTemplate(path, pagesize=A4, title=c["name"], author="dummy")
    doc.addPageTemplates([PageTemplate(id="p", frames=[hdr, left, right])])

    def sec(key, w=None):
        return heading(T(c, key).upper(), hd, thick=0.6, color="#555555", after=4)

    s = [Paragraph(esc(c["name"]), name), Spacer(1, 2), Paragraph(esc(c["headline"]), head), Spacer(1, 10), icon_row(c["contact_items"], size=8.6), FrameBreak()]
    s += sec("summary") + [P(c["summary"], body)]
    if c.get("hidden"):
        s.append(hidden_line(c))
    s += sec("exp")
    for t, co, loc, a, b, bl_ in c["exp"]:
        s += [lr(P(t, ttl), P(span(a, b, c["lang"], c["dates"]), dt), LW - 112, 112), P(f"{co} | {loc}", sub), Spacer(1, 2)] + bullets(bl_, bl) + [Spacer(1, 4)]
    if c["proj"]:
        s += sec("proj")
        for n, k, bl_ in c["proj"]:
            s += [lr(P(n, ttl), P(k, dt), LW - 150, 150)] + bullets(bl_, bl) + [Spacer(1, 3)]
    s.append(FrameBreak())
    s += sec("skills") + bullets([f"{k}: {v}" if k else v for k, v in c["skills"]], bl)
    s += sec("edu")
    for inst, deg, loc, yrs, bl_ in c["edu"]:
        s += [P(deg, ttl), P(inst, sub), P(yrs, st(F, 9, "#555555")), Spacer(1, 4)]
    if c["certs"]:
        s += sec("certs") + bullets([f"{x} ({y})" for x, y in c["certs"]], bl)
    if c.get("langs"):
        s += sec("langs") + bullets(c["langs"], bl)
    doc.build(s)
    return doc.page


# ----------------------------------------------------------------------------- style 4: fresh graduate + foto
def style4(c):
    M = 44
    CW = W - 2 * M - 12  # frame SimpleDocTemplate punya padding 6 di tiap sisi
    F, FB, FI = SANS, SANS_B, SANS_I
    name = st(FB, 22, lead=26)
    ttl = st(F, 12, "#333333", lead=15)
    body = st(F, 9.8, "#222222", lead=13.2)
    bl = st(F, 9.7, "#222222", lead=13, leftIndent=12, bulletIndent=2, spaceAfter=2)
    org, orgr, sub = st(FB, 10.2), st(FB, 9.8, align=TA_RIGHT), st(FI, 9.8, "#333333")
    hd = st(FB, 10.6, lead=13.5, spaceBefore=12)
    left = [Paragraph(esc(c["name"]), name), Paragraph(esc(c["headline"]), ttl), Spacer(1, 9), icon_row(c["contact_items"], size=8.4)]
    hdr = Table([[left, Avatar(74)]], colWidths=[CW - 90, 90])
    hdr.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                             ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0), ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
    s = [hdr, Spacer(1, 8), HRFlowable(width="100%", thickness=0.8, color=black, spaceAfter=2)]
    wl, wr = CW - 150, 150

    def sec(key):
        s.extend(heading(c["titles"][key], hd, thick=0.7, color="#222222"))

    sec("summary")
    s.append(P(c["summary"], body))
    if c.get("hidden"):
        s.append(hidden_line(c))
    sec("edu")
    for inst, deg, loc, yrs, bl_ in c["edu"]:
        s += [lr(P(inst, org), P(yrs, orgr), wl, wr), P(deg, sub)] + bullets(bl_, bl) + [Spacer(1, 3)]
    sec("exp")
    for t, co, loc, a, b, bl_ in c["exp"]:
        s += [lr(P(f"{co}", org), P(span(a, b, c["lang"], c["dates"]), orgr), wl, wr), P(f"{t} | {loc}", sub)] + bullets(bl_, bl) + [Spacer(1, 3)]
    if c["orgs"]:
        sec("orgs")
        for t, co, loc, per, bl_ in c["orgs"]:
            s += [lr(P(co, org), P(per, orgr), wl, wr), P(t, sub)] + bullets(bl_, bl) + [Spacer(1, 3)]
    if c["proj"]:
        sec("proj")
        for n, k, bl_ in c["proj"]:
            s += [lr(P(n, org), P(k, st(F, 9, "#444444", align=TA_RIGHT)), wl, wr)] + bullets(bl_, bl) + [Spacer(1, 3)]
    if c["skills"]:
        sec("skills")
        s += bullets([f"{k}: {v}" if k else v for k, v in c["skills"]], bl)
    if c["certs"]:
        sec("certs")
        for x, y in c["certs"]:
            s.append(lr(Paragraph(f"• {esc(x)}", body), P(y, st(F, 9.2, "#222222", align=TA_RIGHT)), CW - 60, 60))
    return s, dict(leftMargin=M, rightMargin=M, topMargin=40, bottomMargin=30)


def tint(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(HexColor("#faf9ff"))
    canvas.rect(0, 0, W, H, stroke=0, fill=1)
    canvas.restoreState()


def build(c, path):
    if c["style"] == 3:
        return build_style3(c, path)
    story, margins = {1: style1, 2: style2, 4: style4}[c["style"]](c)
    doc = SimpleDocTemplate(path, pagesize=A4, title=c["name"], author="dummy", **margins)
    doc.build(story, onFirstPage=tint if c["style"] == 4 else (lambda *a: None), onLaterPages=tint if c["style"] == 4 else (lambda *a: None))
    return doc.page


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.pdf"):
        old.unlink()
    gold = {"_note": "Label tangan untuk 13 CV dummy. Skill, bulan, dan pendidikan ditulis dari isi CV, bukan dari keluaran pipeline; tier dihitung dari skill berlabel dengan rumus skor yang sama. Cuma 9 skill baku yang dinilai. Pengalaman organisasi/relawan tidak dihitung sebagai bulan pengalaman."}
    render_core(OUT)
    gold.update(CORE_LABELS)
    for c in SPECS:
        check(c)
        pages = build(c, str(OUT / f"{c['id']}.pdf"))
        gold[c["id"]] = {
            "lang": c["lang"], "style": c["style"], "expected_tier": expected_tier(c),
            "skills": {s: "demonstrated" for s in c["demo"]} | {s: "listed" for s in c["listed"]},
            "experience_months": months(c["exp"]), "education": [e[0] for e in c["edu"]], "injection": bool(c.get("hidden")),
        }
    (ROOT / "data" / "golden" / "labels.json").write_text(json.dumps(gold, indent=2, ensure_ascii=False), encoding="utf-8")
    for k, v in gold.items():
        if not k.startswith("_"):
            print(f"  {k:<42} gaya {v['style']}  {v['expected_tier']:<20} {v['experience_months']:>3} bln")
    print(f"{len(gold) - 1} PDF -> {OUT}")


if __name__ == "__main__":
    main()
