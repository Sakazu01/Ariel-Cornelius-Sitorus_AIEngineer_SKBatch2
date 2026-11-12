"""Daftarkan font TrueType supaya teks PDF bisa diekstrak dengan benar (font bawaan PDF membuat bullet terbaca \\x7f).

Dicari berurutan: Liberation (Linux), Times New Roman + Arial (Windows), DejaVu. Kalau tidak ada, pakai font bawaan reportlab.
"""
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FAMILIES = {
    "serif": [
        ("/usr/share/fonts/truetype/liberation2", ["LiberationSerif-Regular.ttf", "LiberationSerif-Bold.ttf", "LiberationSerif-Italic.ttf"]),
        ("/usr/share/fonts/truetype/liberation", ["LiberationSerif-Regular.ttf", "LiberationSerif-Bold.ttf", "LiberationSerif-Italic.ttf"]),
        ("C:/Windows/Fonts", ["times.ttf", "timesbd.ttf", "timesi.ttf"]),
        ("/usr/share/fonts/truetype/dejavu", ["DejaVuSerif.ttf", "DejaVuSerif-Bold.ttf", "DejaVuSerif.ttf"]),
    ],
    "sans": [
        ("/usr/share/fonts/truetype/liberation2", ["LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf", "LiberationSans-Italic.ttf"]),
        ("/usr/share/fonts/truetype/liberation", ["LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf", "LiberationSans-Italic.ttf"]),
        ("C:/Windows/Fonts", ["arial.ttf", "arialbd.ttf", "ariali.ttf"]),
        ("/usr/share/fonts/truetype/dejavu", ["DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans-Oblique.ttf"]),
    ],
}
FALLBACK = {"serif": ("Times-Roman", "Times-Bold", "Times-Italic"), "sans": ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique")}


def _register(kind):
    for folder, files in FAMILIES[kind]:
        paths = [Path(folder) / f for f in files]
        if all(p.exists() for p in paths):
            names = tuple(f"CV{kind.title()}{s}" for s in ("", "-Bold", "-Italic"))
            for n, p in zip(names, paths):
                pdfmetrics.registerFont(TTFont(n, str(p)))
            return names
    print(f"PERINGATAN: font TrueType {kind} tidak ketemu, pakai font bawaan (bullet bisa terbaca aneh saat ekstraksi teks)")
    return FALLBACK[kind]


SERIF, SERIF_B, SERIF_I = _register("serif")
SANS, SANS_B, SANS_I = _register("sans")
