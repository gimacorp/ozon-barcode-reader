"""Проверка кода, Jupyter Notebook и PDF с автоматическим журналом среды."""

import collections
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))
from barcode_reader.engineering import load_config
from barcode_reader.provenance import metadata


def run() -> dict:
    start = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    print(result.stdout)
    collect = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    groups = collections.Counter(
        line.split("::")[0] for line in collect.stdout.splitlines() if "::" in line
    )
    from scripts.execute_notebook import run as notebook

    count = notebook()
    from pypdf import PdfReader

    pdf = PdfReader(ROOT / "output/pdf/ozon_cv2_report_ru.pdf")
    assert len(pdf.pages) == len(pdf.outline)
    assert len(pdf.pages[1].get("/Annots", [])) >= len(pdf.pages) - 2
    for page in pdf.pages:
        assert len(page.extract_text()) > 300
    output = {
        "metadata": metadata(load_config()),
        "test_result": result.stdout.strip(),
        "groups": dict(groups),
        "jupyter_code_cells_executed": count,
        "pdf_pages": len(pdf.pages),
        "pdf_bookmarks": len(pdf.outline),
        "elapsed_s": time.perf_counter() - start,
        "scope": "Программная проверка; визуальная проверка PDF выполняется по рендерам отдельно.",
    }
    (ROOT / "results/verification.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    )
    return output


if __name__ == "__main__":
    print(run()["elapsed_s"])
