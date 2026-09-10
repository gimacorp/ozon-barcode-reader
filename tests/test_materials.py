import json
from copy import deepcopy
from pathlib import Path

import pytest

from barcode_reader.materials import RESULT_NAMES, load_materials
from scripts.report_content import make_pages

ROOT = Path(__file__).resolve().parents[1]


def test_report_numbers_and_conclusions_follow_modified_results():
    bundle = {
        name: json.loads((ROOT / "results" / f"{name}.json").read_text())
        for name in RESULT_NAMES
    }
    changed = deepcopy(bundle)
    load = changed["load_replay"]
    load["boxes"] = 7
    load["outcomes"] = [{"late": True}] * 7
    load["measurements"] = [{}] * 123
    load["p95_ms"] = 987.6
    load["p99_ms"] = 999.8
    load["all_decodes_correct"] = False
    model = next(
        r for r in load["models"] if r["workers"] == 4 and r["service_multiplier"] == 1
    )
    model["max_queue"] = 63
    model["p95_success_ms"] = 876.5
    legacy = next(
        r
        for r in changed["ablation"]["summary"]
        if (r["mode"], r["policy"], r["level"]) == ("legacy_enhanced", "one", "all")
    )
    legacy["tp"] = 111
    legacy["fp"] = 9
    pages = make_pages(changed["calculations"], {}, {}, bundle=changed)
    rendered = json.dumps(pages, ensure_ascii=False)
    for text in (
        "7 коробок, 123 заданий",
        "просрочек 7/7",
        "987,6",
        "999,8",
        "63 / 876,5",
        "111 TP / 9 FP",
        "Нагрузочная серия выявила просрочки",
    ):
        assert text in rendered
    assert (
        "просрочек 0/12" not in rendered and "Все задания восстановили" not in rendered
    )


def test_materials_reject_mixed_config(tmp_path):
    (tmp_path / "results").mkdir()
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs/conveyor.json").write_text(
        (ROOT / "configs/conveyor.json").read_text()
    )
    for name in RESULT_NAMES:
        (tmp_path / "results" / f"{name}.json").write_text("{}")
    with pytest.raises(ValueError, match="конфигом"):
        load_materials(tmp_path)
