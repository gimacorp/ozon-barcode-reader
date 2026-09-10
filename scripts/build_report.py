"""Сборка русского отчёта и иллюстраций из фактических результатов эксперимента."""

import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(__file__).resolve().parents[1] / ".cache/matplotlib")
)
import matplotlib

matplotlib.use("Agg")
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from barcode_reader.materials import load_materials
from scripts.report_content import make_pages

BLUE = "#005BFF"
DARK = "#122441"
CYAN = "#00A6B8"


def build():
    bundle, manifest = load_materials(ROOT)
    (ROOT / "results/report_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    calc = json.loads((ROOT / "results/calculations.json").read_text())
    bench = json.loads((ROOT / "results/benchmark.json").read_text())
    from scripts.figures_review import run as review_figures

    review_figures()
    fontroot = Path(matplotlib.get_data_path()) / "fonts/ttf"
    for name, file in [("DV", "DejaVuSans.ttf"), ("DV-B", "DejaVuSans-Bold.ttf")]:
        pdfmetrics.registerFont(TTFont(name, str(fontroot / file)))
    pdfmetrics.registerFontFamily(
        "DV", normal="DV", bold="DV-B", italic="DV", boldItalic="DV-B"
    )
    styles = {
        "title": ParagraphStyle(
            "title",
            fontName="DV-B",
            fontSize=27,
            leading=33,
            textColor=colors.HexColor(DARK),
            spaceAfter=20,
        ),
        "h1": ParagraphStyle(
            "h1",
            fontName="DV-B",
            fontSize=19,
            leading=24,
            textColor=colors.HexColor(DARK),
            spaceAfter=15,
        ),
        "h2": ParagraphStyle(
            "h2",
            fontName="DV-B",
            fontSize=11,
            leading=15,
            textColor=colors.HexColor(BLUE),
            spaceBefore=10,
            spaceAfter=7,
        ),
        "p": ParagraphStyle(
            "p",
            fontName="DV",
            fontSize=10,
            leading=14.7,
            textColor=colors.HexColor(DARK),
            spaceAfter=9,
        ),
        "small": ParagraphStyle(
            "small",
            fontName="DV",
            fontSize=8.1,
            leading=11.7,
            textColor=colors.HexColor(DARK),
            spaceAfter=7,
        ),
        "cell": ParagraphStyle(
            "cell",
            fontName="DV",
            fontSize=8.2,
            leading=11.5,
            textColor=colors.HexColor(DARK),
        ),
    }
    native = json.loads((ROOT / "results/native_resolution.json").read_text())
    pages = make_pages(calc, bench, native, bundle=bundle)

    class ReportDoc(SimpleDocTemplate):
        def afterFlowable(self, flowable):
            if hasattr(flowable, "bookmark_key"):
                self.canv.bookmarkPage(flowable.bookmark_key)
                self.canv.addOutlineEntry(
                    flowable.getPlainText(), flowable.bookmark_key, 0, False
                )

    story = []
    markdown = [
        "# Шестистороннее чтение штрихкодов\n\nКарим Гимадиев · CV, вариант 2 · 10 сентября 2026\n"
    ]
    for i, page in enumerate(pages):
        if i:
            story.append(PageBreak())
        if i == 0:
            story.extend(
                [
                    Spacer(1, 34),
                    Paragraph("ТЕСТОВОЕ ЗАДАНИЕ · OZON · CV / 02", styles["h2"]),
                    Spacer(1, 20),
                ]
            )
        title = Paragraph(page["title"], styles["title"] if i == 0 else styles["h1"])
        title.bookmark_key = f"p{i}"
        story.append(title)
        markdown.append("\n## " + page["title"] + "\n")
        for block in page["blocks"]:
            kind = block[0]
            if kind in ("p", "h2", "small"):
                story.append(Paragraph(block[1], styles[kind]))
                raw = re.sub(
                    r'<link href="([^"]+)">([^<]+)</link>', r"[\2](\1)", block[1]
                )
                raw = (
                    raw.replace("<b>", "**")
                    .replace("</b>", "**")
                    .replace("<br/>", "\n")
                )
                markdown.append(("### " if kind == "h2" else "") + raw + "\n")
            elif kind == "toc":
                for j, entry in enumerate(pages):
                    if j > 1:
                        story.append(
                            Paragraph(
                                f'<link href="#p{j}">{entry["title"]}</link> … {j + 1}',
                                styles["p"],
                            )
                        )
            elif kind == "code":
                style = ParagraphStyle(
                    "code",
                    fontName="DV",
                    fontSize=8,
                    leading=11,
                    backColor=colors.HexColor("#F5F7FB"),
                    borderPadding=8,
                    spaceAfter=12,
                )
                story.append(Preformatted(block[1], style))
                markdown.append("```\n" + block[1] + "\n```\n")
            elif kind == "figure":
                path = ROOT / "docs/figures" / block[1]
                from PIL import Image as PILImage

                w, h = PILImage.open(path).size
                width = 475
                story.append(Image(str(path), width=width, height=width * h / w))
                story.append(Paragraph(block[2], styles["small"]))
                story.append(Spacer(1, 7))
                markdown.append(f"![{block[2]}](figures/{block[1]})\n")
            elif kind == "table":
                rows, widths = block[1], block[2]
                cells = [
                    [Paragraph(str(s), styles["cell"]) for s in row] for row in rows
                ]
                table = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
                table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E3EDFF")),
                            (
                                "ROWBACKGROUNDS",
                                (0, 1),
                                (-1, -1),
                                [colors.white, colors.HexColor("#F5F7FB")],
                            ),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 8),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                            ("TOPPADDING", (0, 0), (-1, -1), 8),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                            ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor(BLUE)),
                        ]
                    )
                )
                story.extend([table, Spacer(1, 10)])
                markdown.append(
                    "| "
                    + " | ".join(map(str, rows[0]))
                    + " |\n|"
                    + " --- |" * len(rows[0])
                )
                markdown.extend(
                    "| " + " | ".join(map(str, row)) + " |" for row in rows[1:]
                )
                markdown.append("\n")
    out = ROOT / "output/pdf/ozon_cv2_report_ru.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)

    def footer(c, doc):
        c.setStrokeColor(colors.HexColor(BLUE))
        c.setLineWidth(2)
        c.line(48, 798, 547, 798)
        c.setFont("DV", 8)
        c.setFillColor(colors.HexColor("#62728A"))
        c.drawString(48, 29, "КАРИМ ГИМАДИЕВ  /  OZON · CV, ВАРИАНТ 2")
        c.drawRightString(547, 29, f"{doc.page}")

    doc = ReportDoc(
        str(out),
        pagesize=(595.28, 841.89),
        leftMargin=54,
        rightMargin=54,
        topMargin=60,
        bottomMargin=55,
        title="Шестистороннее чтение штрихкодов | Ozon CV-2",
        author="Карим Гимадиев",
        subject="Инженерное решение и воспроизводимый прототип",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    (ROOT / "docs/report.md").write_text(
        "\n".join(markdown).rstrip() + "\n", encoding="utf-8"
    )
    print(out)


if __name__ == "__main__":
    build()
