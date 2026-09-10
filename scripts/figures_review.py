"""Итоговые схемы с размерами, подписями и раздельными фазами движения."""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle

B = "#005BFF"
C = "#00A6B8"
D = "#122441"
E = "#EF6C4D"


def run():
    dest = ROOT / "docs/figures"
    dest.mkdir(exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 14,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    fig, axes = plt.subplots(2, 1, figsize=(11, 6.5), layout="constrained")
    for ax, rear, label in [
        (axes[0], 656, "Фаза А: передний торец x = 1256 мм"),
        (axes[1], 1256, "Фаза Б: задний торец x = 1256 мм"),
    ]:
        ax.add_patch(Rectangle((0, -30), 3000, 30, color="#DDE6F4"))
        ax.add_patch(Rectangle((rear, 0), 600, 400, fc="#EEDBC4", ec=D))
        x = 2513 if rear == 656 else 0
        ax.scatter([x], [550], s=100, marker="s", color=B)
        ax.fill([x, 1256, 1256], [550, -75, 475], alpha=0.12, color=B)
        ax.axvspan(1210, 1302, alpha=0.2, color=C)
        ax.text(1500, 540, "Зона фокуса показана\nдля центра торца", fontsize=13)
        for xx, zz, t in [(650, 850, "Верх"), (750, 450, "Бока"), (900, -220, "Дно")]:
            ax.scatter(xx, zz, s=40, marker="s", color=C)
            ax.text(xx + 25, zz + 15, t, fontsize=13)
        ax.scatter(0, 100, s=40, color=E)
        ax.text(40, 100, "Фотофронт", fontsize=14)
        ax.scatter(400, -60, s=40, color=E)
        ax.text(400, -140, "Энкодер", fontsize=14)
        ax.axvline(3000, color=E)
        ax.text(2990, 250, "Сортировка", rotation=90, ha="right")
        ax.annotate(
            "1 м/с", xy=(2400, 800), xytext=(2100, 800), arrowprops={"arrowstyle": "->"}
        )
        ax.set(xlim=(-100, 3100), ylim=(-260, 950), ylabel="z, мм", title=label)
        ax.grid(alpha=0.12)
    axes[-1].set_xlabel("x, мм; символы линейных камер условны по высоте")
    fig.savefig(dest / "layout.png", dpi=180)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 4.4), layout="constrained")
    ax.add_patch(Rectangle((-325, -20), 650, 20, fc="#DDE6F4", ec=D))
    ax.add_patch(Rectangle((-200, 0), 400, 400, fc="#EEDBC4", ec=D))
    for y, z in [(-667, 200), (667, 200), (0, 1112), (0, -712)]:
        ax.scatter(y, z, color=B, s=70, marker="s")
        if y:
            ax.fill(
                [y, 200 * np.sign(y), 200 * np.sign(y)],
                [z, -25, 425],
                color=B,
                alpha=0.12,
            )
        else:
            ax.fill(
                [0, -350, 350],
                [z, 400 if z > 0 else 0, 400 if z > 0 else 0],
                color=C,
                alpha=0.12,
            )
    ax.text(260, 600, "Бока: FOV 450 мм\nWD ≈ 0,47 м")
    ax.text(-600, 800, "Верх / дно:\nFOV 700 мм\nWD ≈ 0,71 м")
    ax.text(-200, 170, "400 × 400 мм")
    ax.set(
        xlim=(-850, 850),
        ylim=(-800, 1200),
        xlabel="y, мм",
        ylabel="z, мм",
        title="Поперечные проекции каналов (их x различается)",
    )
    fig.savefig(dest / "cross_section.png", dpi=180)
    plt.close(fig)
    fig, axes = plt.subplots(
        1,
        2,
        figsize=(11, 4.8),
        gridspec_kw={"width_ratios": [1, 1.2]},
        layout="constrained",
    )
    ax = axes[0]
    for x in [-10, 10]:
        ax.add_patch(Circle((x, -3), 3, fc="#526783"))
    ax.plot([-55, -10], [0, 0], color=D, lw=3)
    ax.plot([10, 55], [0, 0], color=D, lw=3)
    ax.plot([-50, -10, 0, 10, 50], [1, 1, -2, 1, 1], color="#AC8250", lw=4)
    for sx in [-67.5, -42.5, 42.5, 67.5]:
        ax.plot([sx, 0], [-180, -2], color=E, lw=1)
    ax.fill([-1.75, 1.75, 0], [-712, -712, -2], color=B, alpha=0.4)
    ax.annotate(
        "20 мм по касательным",
        xy=(0, 0),
        xytext=(-45, 19),
        arrowprops={"arrowstyle": "->"},
        fontsize=13,
    )
    ax.annotate(
        "Прогиб ≤ 2 мм",
        xy=(0, -2),
        xytext=(-50, -23),
        arrowprops={"arrowstyle": "->"},
        fontsize=13,
    )
    ax.set(
        xlim=(-60, 60),
        ylim=(-32, 30),
        xlabel="x относительно щели, мм",
        ylabel="z, мм",
        title="Носики R = 3 мм; просвет ≥ 14 мм",
    )
    ax.set_aspect("equal")
    ax = axes[1]
    ax.plot([-100, -10], [0, 0], color=D, lw=3)
    ax.plot([10, 100], [0, 0], color=D, lw=3)
    ax.plot([-25, 25], [-30, -30], color=C, lw=4)
    ax.text(28, -35, "Окно 50 × 700 мм", fontsize=13)
    for x in [-55, 55]:
        ax.add_patch(Rectangle((x - 12.5, -185), 25, 10, fc=E))
        for edge in [x - 12.5, x + 12.5]:
            ax.plot([edge, 0], [-180, -2], color=E, lw=1)
    ax.plot([0, 0], [-712, 0], color=B, lw=2)
    ax.scatter(0, -712, s=100, marker="s", color=B)
    ax.text(8, -640, "Камера\nWD ≈ 0,71 м", fontsize=13)
    ax.text(
        -145,
        -250,
        "2 × CCS LNSP2-700SW\nсветящаяся ширина 25 мм\nцентры x = ±55, z = −180",
        fontsize=13,
    )
    ax.set(
        xlim=(-160, 170),
        ylim=(-760, 60),
        xlabel="x, мм",
        title="Освещение и наблюдение проходят щель",
    )
    fig.savefig(dest / "bottom_section.png", dpi=180)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(11, 4.5), layout="constrained")
    ax.axis("off")
    ax.set(xlim=(0, 11), ylim=(0, 5))
    nodes = [
        (0.1, 3.5, 2.3, 0.9, "DFS60 A/B\nRS-422 · 2400 имп/об"),
        (0.1, 1.7, 2.3, 0.9, "WL12 фотофронт\nPNP · 24 В"),
        (
            3.3,
            2.6,
            3,
            1.3,
            "VCL-1 · FPGA\nквадратура ×4 → ÷4\nсчётчик позиции / box_id",
        ),
        (7.4, 3.8, 3.2, 0.8, "CC1 → 4 линейные камеры\n12 кГц · выдержка 40 мкс"),
        (7.4, 2.3, 3.2, 0.9, "VCL-2 ← TTL line / reset\nединые номера строк"),
        (
            7.4,
            0.6,
            3.2,
            1.1,
            "Opto Trigger 5 · 24 В\n2 торца / 2 группы света\n16 Гц · серия 5 кадров",
        ),
    ]
    for x, y, w, h, t in nodes:
        ax.add_patch(
            FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.06", fc="#E3EDFF", ec=B)
        )
        ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=13)
    for a, b in [
        ((2.4, 4), (3.3, 3.5)),
        ((2.4, 2.2), (3.3, 2.9)),
        ((6.3, 3.5), (7.4, 4.1)),
        ((6.3, 3.2), (7.4, 2.8)),
        ((6.3, 2.8), (7.4, 1.3)),
    ]:
        ax.annotate("", xy=b, xytext=a, arrowprops={"arrowstyle": "->", "color": D})
    ax.text(
        0.1,
        0.5,
        "Кадр / DMA: camera_id, frame_id, encoder_start/end, boot_id, timestamps",
        fontsize=13,
    )
    fig.savefig(dest / "synchronization.png", dpi=180)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 3.3), layout="constrained")
    values = [80, 420, 50, 85, 250, 100]
    names = [
        "Приём\n80",
        "Очередь + декодирование\n420",
        "ACK\n50",
        "Запас\n85",
        "Резерв\n250",
        "ПЛК\n100",
    ]
    left = 0
    for v, n, col in zip(values, names, [C, B, C, "#B2D4FF", "#DDE6F4", "#EEDBC4"]):
        ax.barh(0, v, left=left, color=col, edgecolor="white")
        ax.text(
            left + v / 2,
            0,
            n,
            ha="center",
            va="center",
            fontsize=13,
            color="white" if col == B else D,
        )
        left += v
    ax.set(
        xlim=(0, 985),
        yticks=[],
        xlabel="мс после конца последней экспозиции",
        title="985 мс до сортировки; 635 мс после резервов",
    )
    ax.text(
        0,
        0.65,
        "Экспозиция 0,04 мс предшествует t = 0; приём включает readout + передачу",
        fontsize=13,
    )
    ax.set_ylim(-0.6, 1)
    fig.savefig(dest / "deadline.png", dpi=180)
    plt.close(fig)
    data = json.loads((ROOT / "results/ablation.json").read_text())
    ms = [
        m
        for m in data["summary"]
        if m["mode"] == "code128_45" and m["policy"] == "one" and m["level"] != "all"
    ]
    fig, ax = plt.subplots(figsize=(10, 4), layout="constrained")
    x = np.arange(3)
    for off, key, col, lab in [
        (-0.18, "exact", B, "Полное множество коробки"),
        (0.18, "tp", C, "Полнота значений"),
    ]:
        vals = [
            m[key] / (m["boxes"] if key == "exact" else m["tp"] + m["fn"]) * 100
            for m in ms
        ]
        bars = ax.bar(x + off, vals, 0.36, color=col, label=lab)
        for b, v in zip(bars, vals):
            ax.text(
                b.get_x() + b.get_width() / 2,
                v - 7,
                f"{v:.1f}%".replace(".", ","),
                ha="center",
                color="white",
                fontsize=14,
            )
    ax.set(
        ylim=(0, 100),
        xticks=x,
        xticklabels=[
            f"{name} · n={m['boxes']}"
            for name, m in zip(["Чистые", "Умеренные", "Сложные"], ms)
        ],
        ylabel="%",
        title="Стресс-набор: Code 128 + 45°",
    )
    ax.legend(loc="lower left", fontsize=13)
    fig.savefig(dest / "benchmark.png", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    run()
