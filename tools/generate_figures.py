from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Patch, Polygon


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "figures"

BLUE = "#2166AC"
BLUE_DARK = "#163A5F"
BLUE_LIGHT = "#EAF2F8"
ORANGE = "#D6604D"
ORANGE_LIGHT = "#FAECE8"
GREEN = "#1B8062"
GREEN_LIGHT = "#EAF6F2"
GRAY = "#687580"
GRAY_DARK = "#2F3E4A"
GRAY_LIGHT = "#F3F6F8"
GRID = "#D8DEE4"


def configure() -> None:
    candidates = [
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "Lantinghei SC",
        "Hiragino Sans GB",
        "Microsoft YaHei",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    available = {f.name for f in mpl.font_manager.fontManager.ttflist}
    family = next((name for name in candidates if name in available), "DejaVu Sans")
    mpl.rcParams.update(
        {
            "font.family": family,
            "font.size": 10.5,
            "axes.titlesize": 14,
            "axes.titleweight": "semibold",
            "axes.labelsize": 11,
            "axes.edgecolor": GRAY_DARK,
            "axes.linewidth": 0.9,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.7,
            "grid.alpha": 0.8,
            "legend.frameon": False,
            "xtick.color": GRAY_DARK,
            "ytick.color": GRAY_DARK,
            "text.color": GRAY_DARK,
            "axes.labelcolor": GRAY_DARK,
            "axes.titlecolor": BLUE_DARK,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "svg.fonttype": "path",
            "svg.hashsalt": "memweave-figures-v1",
            "axes.unicode_minus": False,
        }
    )


def save(fig: plt.Figure, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    fig.savefig(
        path,
        format="svg",
        bbox_inches="tight",
        pad_inches=0.08,
        metadata={"Date": None, "Creator": "Matplotlib"},
    )
    plt.close(fig)
    clean = "\n".join(line.rstrip() for line in path.read_text(encoding="utf-8").splitlines()) + "\n"
    path.write_text(clean, encoding="utf-8")


def diagram(title: str, height: float = 5.4, width: float = 11.2) -> tuple[plt.Figure, plt.Axes]:
    fig, ax = plt.subplots(figsize=(width, height), dpi=120)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0.02, 0.965, title, ha="left", va="top", fontsize=15, weight="semibold", color=BLUE_DARK)
    return fig, ax


def box(
    ax: plt.Axes,
    x: float,
    y: float,
    w: float,
    h: float,
    text: str,
    *,
    face: str = GRAY_LIGHT,
    edge: str = GRAY,
    fontsize: float = 10.3,
    weight: str = "normal",
) -> None:
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.008,rounding_size=0.008",
        linewidth=1.25,
        edgecolor=edge,
        facecolor=face,
    )
    ax.add_patch(patch)
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        weight=weight,
        linespacing=1.32,
    )


def arrow(ax: plt.Axes, start: tuple[float, float], end: tuple[float, float], *, dashed: bool = False) -> None:
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops={
            "arrowstyle": "-|>",
            "lw": 1.35,
            "color": GRAY_DARK,
            "linestyle": "--" if dashed else "-",
            "shrinkA": 2,
            "shrinkB": 2,
        },
    )


def figure_critical_points() -> None:
    fig, ax = plt.subplots(figsize=(10.8, 5.3), dpi=120, layout="constrained")
    x = np.array([1.0, 3.0, 3.0, 6.0, 6.0, 9.0])
    existing = np.array([42, 50, 30, 42, 24, 33])
    new_request = 12 + (x - 1.0 + 1.0)
    total = existing + new_request
    critical_x = np.array([3.0, 6.0, 9.0])
    critical_y = np.array([65, 60, 54])
    boundaries = np.array([1.0, 3.0, 6.0, 9.0])

    ax.axvspan(1.0, 9.0, color=BLUE, alpha=0.045)
    ax.axhline(72, color=ORANGE, lw=1.8, ls=(0, (5, 3)), label="GPU 容量 M[k]")
    for xpos in boundaries:
        ax.axvline(xpos, color=GRAY, lw=0.8, ls=(0, (3, 4)), alpha=0.8)

    ax.plot(x, existing, color=GRAY, lw=2.3, label="已有负载")
    ax.plot(x, total, color=BLUE, lw=2.8, label="加入新请求后的总显存")
    ax.scatter(critical_x, critical_y, s=58, facecolor="white", edgecolor=BLUE, linewidth=2.0, zorder=5)
    ax.annotate(
        "事件之间单调增加",
        xy=(2.5, 61),
        xytext=(1.25, 68),
        arrowprops={"arrowstyle": "->", "color": GRAY_DARK, "lw": 1.0},
        color=GRAY_DARK,
    )
    ax.annotate(
        "只检查关键点",
        xy=(6.0, 60),
        xytext=(6.35, 66),
        arrowprops={"arrowstyle": "->", "color": BLUE, "lw": 1.1},
        color=BLUE,
        weight="semibold",
    )

    ax.set_title("关键点检查替代逐时刻扫描", loc="left", pad=10)
    ax.set_xlabel("时间 t")
    ax.set_ylabel("显存占用（示意单位）")
    ax.set_xlim(0.4, 9.6)
    ax.set_ylim(0, 82)
    ax.set_xticks(boundaries, ["s=1\n并发边界", "C1=3", "C2=6", "e=9"])
    ax.legend(loc="lower center", ncol=1, fontsize=8.8, frameon=True, facecolor="white", edgecolor="none", framealpha=0.94)
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, "fig01-critical-points.svg")


def figure_check_count() -> None:
    fig, ax = plt.subplots(figsize=(10.3, 5.1), dpi=120, layout="constrained")
    lout = np.arange(1, 2049)
    ax.plot(lout, lout, color=GRAY_DARK, lw=2.2, label="逐时刻扫描：Lout")
    for b, color in [(8, GREEN), (32, BLUE), (128, ORANGE)]:
        checks = np.where(lout == 1, 1, b)
        ax.plot(lout, checks, lw=2.0, color=color, label=f"活动完成项检查上界：B={b}")
    ax.set_yscale("log")
    ax.set_title("逐时刻扫描与活动完成项检查的理论上界", loc="left", pad=10)
    ax.set_xlabel("请求输出长度 Lout")
    ax.set_ylabel("单次放置的显存检查点数（对数轴）")
    ax.set_xlim(1, 2048)
    ax.set_ylim(1, 4096)
    yticks = [1, 8, 32, 128, 512, 2048]
    ax.set_yticks(yticks, [str(value) for value in yticks])
    ax.legend(loc="upper left", ncol=1, fontsize=8.9, frameon=True, facecolor="white", edgecolor="none", framealpha=0.94)
    ax.spines[["top", "right"]].set_visible(False)
    ax.text(
        2048,
        1.35,
        "源码逐项检查活动请求的完成时刻，再检查新请求结束点；不含开始时刻的并发检查。",
        ha="right",
        va="bottom",
        color=GRAY,
        fontsize=9.4,
    )
    save(fig, "fig02-check-count.svg")


def figure_event_loop() -> None:
    fig, ax = diagram("事件驱动构造器", 6.3, 12.5)
    xs = [0.03, 0.265, 0.50, 0.735]
    labels = [
        "取下一事件 t\nmin(到达时刻,\n完成时刻)",
        "清理已完成请求\n移动 GPU 的\nhead",
        "合并本时刻\n新到达请求",
        "整理 pending\n保持稳定的\n优先级顺序",
    ]
    for x, label in zip(xs, labels):
        box(ax, x, 0.69, 0.205, 0.18, label, face=BLUE_LIGHT if x == xs[0] else GRAY_LIGHT, edge=BLUE if x == xs[0] else GRAY, fontsize=8.9)
    for x in xs[:-1]:
        arrow(ax, (x + 0.205, 0.78), (x + 0.235, 0.78))

    box(ax, 0.365, 0.51, 0.27, 0.12, "遍历 pending，尝试放置\ns = t + 1", face=BLUE_LIGHT, edge=BLUE)
    arrow(ax, (0.837, 0.69), (0.635, 0.57))

    diamond = Polygon([[0.50, 0.45], [0.61, 0.34], [0.50, 0.23], [0.39, 0.34]], closed=True, facecolor="white", edgecolor=BLUE, linewidth=1.6)
    ax.add_patch(diamond)
    ax.text(0.50, 0.365, "存在可行 GPU？", ha="center", va="center", weight="semibold")
    ax.text(0.50, 0.305, "完整显存 + 并发检查", ha="center", va="center", fontsize=8.9, color=GRAY)
    arrow(ax, (0.50, 0.51), (0.50, 0.45))

    box(ax, 0.67, 0.075, 0.27, 0.13, "提交并更新状态\n写入 end/v 与完成事件", face=GREEN_LIGHT, edge=GREEN)
    box(ax, 0.06, 0.075, 0.27, 0.13, "保留在 pending\n等待后续事件", face=ORANGE_LIGHT, edge=ORANGE)
    arrow(ax, (0.61, 0.34), (0.67, 0.16))
    arrow(ax, (0.39, 0.34), (0.33, 0.16))
    ax.text(0.645, 0.29, "是", color=GREEN, weight="semibold", ha="center")
    ax.text(0.355, 0.29, "否", color=ORANGE, weight="semibold", ha="center")

    ax.text(0.50, 0.028, "继续扫描本轮 pending；本轮结束后回到下一事件。\nearlyStop 只截断本轮，不绕过合法性检查。", ha="center", va="bottom", fontsize=8.8, color=GRAY, linespacing=1.35)
    save(fig, "fig03-event-loop.svg")


def figure_priority_grid() -> None:
    grid = np.array(
        [
            (8, 0), (8, 2), (8, 4), (8, 5), (8, 6), (8, 7), (8, 8), (8, 10), (8, 12), (8, 16), (8, 24),
            (4, 4), (4, 8), (4, 16), (4, 32),
            (2, 2), (2, 8), (2, 24), (2, 48),
            (0, 8), (16, 4),
        ],
        dtype=float,
    )
    groups = np.array(["a=8"] * 11 + ["a=4"] * 4 + ["a=2"] * 4 + ["边界"] * 2)
    palette = {"a=8": BLUE, "a=4": GREEN, "a=2": ORANGE, "边界": GRAY_DARK}
    markers = {"a=8": "o", "a=4": "s", "a=2": "^", "边界": "D"}

    fig, ax = plt.subplots(figsize=(9.8, 5.6), dpi=120, layout="constrained")
    for group in ["a=8", "a=4", "a=2", "边界"]:
        mask = groups == group
        ax.scatter(grid[mask, 0], grid[mask, 1], s=68, color=palette[group], marker=markers[group], label=group, zorder=3)
    for x, y in [(8, 0), (8, 24), (4, 32), (2, 48), (0, 8), (16, 4)]:
        ax.annotate(f"({int(x)},{int(y)})", (x, y), xytext=(5, 6), textcoords="offset points", fontsize=8.8, color=GRAY_DARK)
    ax.set_title("离散优先级权重网格", loc="left", pad=10)
    ax.set_xlabel("输入—输出乘积权重 a")
    ax.set_ylabel("输出平方权重 b")
    ax.set_xlim(-0.8, 17.2)
    ax.set_ylim(-2, 52)
    ax.legend(loc="upper right", ncol=4)
    ax.spines[["top", "right"]].set_visible(False)
    ax.text(0.0, -0.18, "图中为源码系数同时除以 125 后的等价整数比。", transform=ax.transAxes, color=GRAY, fontsize=9.2)
    save(fig, "fig04-priority-grid.svg")


def figure_priority_surfaces() -> None:
    lin = np.linspace(0, 2048, 160)
    lout = np.linspace(0, 2048, 160)
    xx, yy = np.meshgrid(lin / 2048.0, lout / 2048.0)
    weights = [(8, 2), (8, 8), (2, 24)]
    fig, axes = plt.subplots(1, 3, figsize=(12.4, 4.3), dpi=120, layout="constrained", sharex=True, sharey=True)
    mappable = None
    for ax, (a, b) in zip(axes, weights):
        score = a * xx * yy + b * yy * yy
        score /= score.max()
        mappable = ax.contourf(lin, lout, score, levels=np.linspace(0, 1, 11), cmap="Blues", vmin=0, vmax=1)
        ax.contour(lin, lout, score, levels=[0.25, 0.5, 0.75], colors=[GRAY_DARK], linewidths=0.65, alpha=0.75)
        ax.set_title(f"(a,b)=({a},{b})")
        ax.set_xlabel("Lin")
        ax.set_aspect("equal")
    axes[0].set_ylabel("Lout")
    fig.suptitle("优先级函数对请求形状的响应", x=0.02, ha="left", fontsize=14, weight="semibold", color=BLUE_DARK)
    cbar = fig.colorbar(mappable, ax=axes, shrink=0.82, pad=0.035, fraction=0.032, aspect=28)
    cbar.ax.set_title("归一化 P", pad=8, fontsize=9.5)
    save(fig, "fig05-priority-surfaces.svg")


def grid_size(per_es: np.ndarray) -> np.ndarray:
    return np.where(per_es >= 21, 21, np.where(per_es >= 14, 10, np.where(per_es >= 8, 5, 3)))


def figure_budget_grid() -> None:
    x = np.arange(0, 31)
    size = grid_size(x)
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.7), dpi=120)
    fig.subplots_adjust(left=0.08, right=0.98, top=0.88, bottom=0.22, wspace=0.25)
    axes[0].step(x, size, where="post", color=BLUE, lw=2.4)
    axes[0].scatter([7, 8, 13, 14, 20, 21], grid_size(np.array([7, 8, 13, 14, 20, 21])), color=BLUE, s=30, zorder=3)
    axes[0].set_title("每个 earlyStop 可承担的网格规模", loc="left")
    axes[0].set_xlabel("perEs：每个 earlyStop 可负担的完整构造次数")
    axes[0].set_ylabel("权重对数量")
    axes[0].set_yticks([3, 5, 10, 21])
    for boundary in [8, 14, 21]:
        axes[0].axvline(boundary, color=GRAY, lw=0.8, ls=(0, (3, 3)))

    axes[1].step(x, size * 8, where="post", color=GREEN, lw=2.2, label="全量首帧：8 个 earlyStop")
    axes[1].step(x, size * 6, where="post", color=ORANGE, lw=2.2, label="最终残余：6 个 earlyStop")
    axes[1].set_title("主网格的候选构造数上界", loc="left")
    axes[1].set_xlabel("perEs")
    axes[1].set_ylabel("权重 × earlyStop 组合数")
    axes[1].legend(loc="upper left")
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    fig.text(0.08, 0.055, "不计基线、线性键和网格结束后的 GPU 模式复试；数据直接来自源码阈值。", fontsize=9.1, color=GRAY)
    save(fig, "fig06-budget-grid.svg")


def figure_search_pipeline() -> None:
    fig, ax = diagram("常规离线搜索与完整 V 的使用边界", 6.5, 12.0)
    top = [
        (0.05, "基线 + 线性键"),
        (0.375, "量化网格 × earlyStop\nGPU 模式 0"),
        (0.70, "当前最佳键 / ES\n复试 GPU 模式\n1 和 2"),
    ]
    for idx, (x, label) in enumerate(top):
        box(ax, x, 0.685, 0.25, 0.16, label, face=BLUE_LIGHT if idx else GRAY_LIGHT, edge=BLUE if idx else GRAY, fontsize=9.2)
        if idx:
            arrow(ax, (top[idx - 1][0] + 0.25, 0.765), (x, 0.765))

    bottom = [
        (0.70, "regret bootstrap"),
        (0.375, "局部搜索\n检查点恢复"),
        (0.05, "返回当前最好解\n并计算完整 V"),
    ]
    arrow(ax, (0.825, 0.685), (0.825, 0.57))
    for idx, (x, label) in enumerate(bottom):
        box(ax, x, 0.44, 0.25, 0.13, label, face=BLUE_LIGHT if idx < 2 else GRAY_LIGHT, edge=BLUE if idx < 2 else GRAY)
        if idx:
            arrow(ax, (bottom[idx - 1][0], 0.505), (x + 0.25, 0.505))
    ax.text(0.50, 0.89, "常规候选统一按 sumD 选优", ha="center", color=BLUE_DARK, weight="semibold")

    ax.plot([0.04, 0.96], [0.35, 0.35], color=GRID, lw=1.2)
    ax.text(0.50, 0.30, "完整 V 只在两个结构性分支中直接决定取舍", ha="center", color=GREEN, weight="semibold")
    box(ax, 0.10, 0.085, 0.34, 0.16, "全量小规模\n分支定界解\nvs 启发式解", face=GREEN_LIGHT, edge=GREEN, fontsize=9.0)
    box(ax, 0.56, 0.085, 0.34, 0.16, "最终残余\n残余优化解\nvs 继续贪心", face=GREEN_LIGHT, edge=GREEN, fontsize=9.0)
    ax.text(0.50, 0.025, "执行哪些候选只由算法阶段和墙钟预算决定，不根据输入统计分类。", ha="center", fontsize=9.3, color=GRAY)
    save(fig, "fig07-search-pipeline.svg")


def figure_regret_update() -> None:
    x = np.linspace(0, 1, 200)
    alpha = 0.025
    y = -alpha * x
    examples = np.array([0.05, 0.20, 0.40, 0.65, 0.85, 1.00])
    fig, ax = plt.subplots(figsize=(9.7, 4.8), dpi=120, layout="constrained")
    ax.plot(x, y, color=BLUE, lw=2.5, label="ΔP / kmax = -0.025 × D / maxD")
    ax.scatter(examples, -alpha * examples, s=55, color=ORANGE, edgecolor="white", linewidth=0.8, zorder=3, label="示例请求")
    for idx, value in enumerate(examples, 1):
        ax.annotate(str(idx), (value, -alpha * value), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=8.5)
    ax.axhline(0, color=GRAY_DARK, lw=0.8)
    ax.set_title("单轮 regret 更新：等待越久，优先级前移越多", loc="left", pad=10)
    ax.set_xlabel("归一化等待 D / maxD")
    ax.set_ylabel("归一化优先级变化 ΔP / kmax")
    ax.set_xlim(0, 1.02)
    ax.set_ylim(-0.027, 0.0015)
    ax.legend(loc="lower left")
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, "fig08-regret-update.svg")


def figure_prefilter_flow() -> None:
    fig, ax = diagram("无损 int16 预筛：只提前证明“不可能”", 6.2, 12.0)
    box(ax, 0.04, 0.70, 0.22, 0.14, "pending 批次\nLin / Lout 的 SoA", face=BLUE_LIGHT, edge=BLUE, fontsize=9.1)
    box(ax, 0.33, 0.66, 0.34, 0.22, "逐 GPU 必要条件\nLin + Lout ≤ M\nLin ≤ threshold 或 Lout ≤ cm", face=BLUE_LIGHT, edge=BLUE, fontsize=8.8)
    box(ax, 0.74, 0.70, 0.22, 0.14, "跨非满 GPU 做 OR\n得到 mask", face=BLUE_LIGHT, edge=BLUE, fontsize=9.1)
    arrow(ax, (0.26, 0.77), (0.33, 0.77))
    arrow(ax, (0.67, 0.77), (0.74, 0.77))

    diamond = Polygon([[0.50, 0.58], [0.62, 0.47], [0.50, 0.36], [0.38, 0.47]], closed=True, facecolor="white", edgecolor=BLUE, linewidth=1.5)
    ax.add_patch(diamond)
    ax.text(0.50, 0.47, "mask?", ha="center", va="center", weight="semibold")
    arrow(ax, (0.85, 0.70), (0.62, 0.49))

    box(ax, 0.06, 0.12, 0.34, 0.15, "进入 64 位整数精确检查\n再决定放置或延后", face=GREEN_LIGHT, edge=GREEN, fontsize=9.1)
    box(ax, 0.60, 0.12, 0.34, 0.15, "所有 GPU 已被必要条件排除\n安全跳过", face=ORANGE_LIGHT, edge=ORANGE, fontsize=9.1)
    arrow(ax, (0.38, 0.47), (0.23, 0.27))
    arrow(ax, (0.62, 0.47), (0.77, 0.27))
    ax.text(0.31, 0.35, "mask=1", color=GREEN, weight="semibold")
    ax.text(0.65, 0.35, "mask=0", color=ORANGE, weight="semibold")

    ax.text(0.50, 0.045, "mask=0 才跳过；mask=1 只表示尚未证明不可行。最终合法性始终由精确检查决定。", ha="center", fontsize=9.3, color=GRAY)
    save(fig, "fig09-prefilter-flow.svg")


def figure_prefilter_region() -> None:
    lin = np.linspace(0, 2048, 513)
    lout = np.linspace(0, 2048, 513)
    xx, yy = np.meshgrid(lin, lout)
    capacity = 3072
    threshold = 800
    cm = 512
    mask = (xx + yy <= capacity) & ((xx <= threshold) | (yy <= cm))

    fig, ax = plt.subplots(figsize=(10.2, 6.3), dpi=120)
    fig.subplots_adjust(left=0.09, right=0.72, top=0.90, bottom=0.18)
    cmap = mpl.colors.ListedColormap(["#F3F4F6", BLUE_LIGHT])
    ax.imshow(
        mask.astype(int),
        origin="lower",
        extent=(0, 2048, 0, 2048),
        interpolation="nearest",
        cmap=cmap,
        vmin=0,
        vmax=1,
        rasterized=True,
    )
    ax.plot(lin, capacity - lin, color=ORANGE, lw=2.0, label="Lin + Lout = M")
    ax.axvline(threshold, color=BLUE, lw=1.8, ls=(0, (4, 3)), label="Lin = threshold")
    ax.axhline(cm, color=GREEN, lw=1.8, ls=(0, (4, 3)), label="Lout = cm")
    ax.set_title("单张非满 GPU 上的必要条件候选区域", loc="left", pad=10)
    ax.set_xlabel("Lin")
    ax.set_ylabel("Lout")
    ax.set_xlim(0, 2048)
    ax.set_ylim(0, 2048)
    ax.set_aspect("equal")
    handles = [
        Patch(facecolor=BLUE_LIGHT, edgecolor=BLUE, label="mask=1：保留复核"),
        Patch(facecolor="#F3F4F6", edgecolor=GRAY, label="mask=0：本卡排除"),
        Line2D([0], [0], color=ORANGE, lw=2, label="Lin + Lout = M"),
        Line2D([0], [0], color=BLUE, lw=1.8, ls=(0, (4, 3)), label="Lin = threshold"),
        Line2D([0], [0], color=GREEN, lw=1.8, ls=(0, (4, 3)), label="Lout = cm"),
    ]
    fig.legend(
        handles=handles,
        loc="upper left",
        bbox_to_anchor=(0.73, 0.88),
        fontsize=9.2,
        frameon=True,
        facecolor="white",
        edgecolor=GRID,
        framealpha=1.0,
    )
    fig.text(0.09, 0.055, "示例状态：M=3072、threshold=800、cm=512；多 GPU 时对各卡结果取 OR。", fontsize=9.1, color=GRAY)
    save(fig, "fig10-prefilter-region.svg")


def figure_online_offline() -> None:
    fig, ax = diagram("全量首帧与流式到达的两条执行路径", 7.0, 13.2)
    ax.text(0.02, 0.79, "全量首帧", ha="left", va="center", weight="semibold", color=BLUE_DARK)
    ax.text(0.02, 0.40, "流式到达", ha="left", va="center", weight="semibold", color=BLUE_DARK)

    box(ax, 0.13, 0.70, 0.20, 0.15, "t=0\n全部 N 个请求可见", face=BLUE_LIGHT, edge=BLUE, fontsize=9.2)
    box(ax, 0.40, 0.70, 0.20, 0.15, "solv::Sim\n离线多起点搜索", face=BLUE_LIGHT, edge=BLUE, fontsize=9.2)
    box(ax, 0.67, 0.70, 0.20, 0.15, "输出全部\n(S,id,k)", face=GREEN_LIGHT, edge=GREEN, fontsize=9.2)
    arrow(ax, (0.33, 0.775), (0.40, 0.775))
    arrow(ax, (0.60, 0.775), (0.67, 0.775))

    box(ax, 0.12, 0.33, 0.15, 0.15, "逐帧到达\n仅用可见请求", face=GRAY_LIGHT, edge=GRAY, fontsize=9.0)
    box(ax, 0.31, 0.33, 0.13, 0.15, "Sched\n在线提交", face=BLUE_LIGHT, edge=BLUE, fontsize=9.0)
    box(ax, 0.48, 0.30, 0.18, 0.21, "全部到齐后\n建立残余问题\n运行中作 seed\n未启动作 backlog", face=BLUE_LIGHT, edge=BLUE, fontsize=8.3)
    arrow(ax, (0.27, 0.405), (0.31, 0.405))
    arrow(ax, (0.44, 0.405), (0.48, 0.405))

    box(ax, 0.70, 0.46, 0.15, 0.11, "solv::Sim\n残余优化", face=GREEN_LIGHT, edge=GREEN, fontsize=8.7)
    box(ax, 0.70, 0.25, 0.15, 0.11, "继续原贪心\n保底", face=ORANGE_LIGHT, edge=ORANGE, fontsize=8.7)
    arrow(ax, (0.66, 0.43), (0.70, 0.515))
    arrow(ax, (0.66, 0.37), (0.70, 0.305))

    diamond = Polygon([[0.91, 0.48], [0.985, 0.405], [0.91, 0.33], [0.835, 0.405]], closed=True, facecolor="white", edgecolor=GREEN, linewidth=1.4)
    ax.add_patch(diamond)
    ax.text(0.91, 0.405, "完整 V\n比较", ha="center", va="center", fontsize=8.7, weight="semibold", linespacing=1.3)
    arrow(ax, (0.85, 0.515), (0.875, 0.45))
    arrow(ax, (0.85, 0.305), (0.875, 0.36))
    box(ax, 0.77, 0.105, 0.20, 0.13, "采用更优尾部计划\n一次性输出残余", face=GREEN_LIGHT, edge=GREEN, fontsize=8.7)
    arrow(ax, (0.91, 0.33), (0.87, 0.235))

    ax.plot([0.10, 0.98], [0.61, 0.61], color=GRID, lw=1.2)
    ax.text(0.50, 0.57, "在线阶段不读取未来请求；全部到齐后才建立残余问题。", ha="center", fontsize=9.1, color=GRAY)
    save(fig, "fig11-online-offline.svg")


def main() -> None:
    configure()
    figure_critical_points()
    figure_check_count()
    figure_event_loop()
    figure_priority_grid()
    figure_priority_surfaces()
    figure_budget_grid()
    figure_search_pipeline()
    figure_regret_update()
    figure_prefilter_flow()
    figure_prefilter_region()
    figure_online_offline()


if __name__ == "__main__":
    main()
