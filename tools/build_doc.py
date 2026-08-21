from __future__ import annotations

import hashlib
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "GPU显存约束调度_通用385版.docx"
SOURCE = ROOT / "src" / "Solution.cpp"

NAVY = "17365D"
BLUE = "2E74B5"
BLUE_DARK = "1F4D78"
BLUE_LIGHT = "E8EEF5"
CYAN_LIGHT = "EAF5F8"
GRAY_LIGHT = "F3F5F7"
GRAY_MID = "D9E1E8"
GRAY_TEXT = "5B6573"
ORANGE = "C55A11"
WHITE = "FFFFFF"
BLACK = "1A1A1A"


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=80, start=120, bottom=80, end=120) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for name, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{name}"))
        if node is None:
            node = OxmlElement(f"w:{name}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_cell_width(cell, width_twips: int) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.find(qn("w:tcW"))
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(width_twips))
    tc_w.set(qn("w:type"), "dxa")


def set_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def set_run_font(run, size=None, bold=None, italic=None, color=None, code=False) -> None:
    name = "Consolas" if code else "Noto Sans CJK SC"
    east = "Noto Sans CJK SC"
    run.font.name = name
    r_pr = run._element.get_or_add_rPr()
    r_fonts = r_pr.rFonts
    if r_fonts is None:
        r_fonts = OxmlElement("w:rFonts")
        r_pr.insert(0, r_fonts)
    r_fonts.set(qn("w:ascii"), name)
    r_fonts.set(qn("w:hAnsi"), name)
    r_fonts.set(qn("w:eastAsia"), east)
    r_fonts.set(qn("w:cs"), east)
    lang = r_pr.find(qn("w:lang"))
    if lang is None:
        lang = OxmlElement("w:lang")
        r_pr.append(lang)
    lang.set(qn("w:val"), "zh-CN")
    lang.set(qn("w:eastAsia"), "zh-CN")
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color is not None:
        run.font.color.rgb = RGBColor.from_string(color)


def add_page_number(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run("第 ")
    set_run_font(run, 8.5, color=GRAY_TEXT)
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    fld_text = OxmlElement("w:t")
    fld_text.text = "1"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.extend([fld_begin, instr, fld_sep, fld_text, fld_end])
    run2 = paragraph.add_run(" 页")
    set_run_font(run2, 8.5, color=GRAY_TEXT)


def add_bottom_border(paragraph, color=GRAY_MID, size=6) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    p_bdr = p_pr.find(qn("w:pBdr"))
    if p_bdr is None:
        p_bdr = OxmlElement("w:pBdr")
        p_pr.append(p_bdr)
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(size))
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), color)
    p_bdr.append(bottom)


def set_keep_with_next(paragraph, value=True) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    node = p_pr.find(qn("w:keepNext"))
    if value and node is None:
        p_pr.append(OxmlElement("w:keepNext"))
    elif not value and node is not None:
        p_pr.remove(node)


def set_cant_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tr_pr.append(OxmlElement("w:cantSplit"))


def add_inline(paragraph, segments) -> None:
    for text, opts in segments:
        run = paragraph.add_run(text)
        set_run_font(
            run,
            opts.get("size"),
            opts.get("bold"),
            opts.get("italic"),
            opts.get("color"),
            opts.get("code", False),
        )


def add_body(doc, text: str, *, bold_lead: str | None = None, keep=False):
    p = doc.add_paragraph(style="Body Text")
    if bold_lead and text.startswith(bold_lead):
        r1 = p.add_run(bold_lead)
        set_run_font(r1, 10.5, bold=True, color=BLACK)
        r2 = p.add_run(text[len(bold_lead):])
        set_run_font(r2, 10.5, color=BLACK)
    else:
        r = p.add_run(text)
        set_run_font(r, 10.5, color=BLACK)
    if keep:
        set_keep_with_next(p)
    return p


def add_bullet(doc, text: str, level=0):
    style = "List Bullet" if level == 0 else "List Bullet 2"
    p = doc.add_paragraph(style=style)
    r = p.add_run(text)
    set_run_font(r, 10.2, color=BLACK)
    return p


def add_number(doc, text: str, level=0, restart=False):
    if restart or not hasattr(doc, "_manual_list_number"):
        doc._manual_list_number = 1
    else:
        doc._manual_list_number += 1
    p = doc.add_paragraph(style="Body Text")
    p.paragraph_format.left_indent = Inches(0.22 + level * 0.22)
    p.paragraph_format.first_line_indent = Inches(-0.22)
    r0 = p.add_run(f"{doc._manual_list_number}.  ")
    set_run_font(r0, 10.2, color=BLACK)
    r = p.add_run(text)
    set_run_font(r, 10.2, color=BLACK)
    return p


def add_formula(doc, text: str, note: str | None = None):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    cell = table.cell(0, 0)
    set_cell_width(cell, 9000)
    set_cell_margins(cell, 100, 180, 100, 180)
    set_cell_shading(cell, CYAN_LIGHT)
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    set_run_font(r, 12, color=NAVY)
    r.font.name = "Cambria Math"
    if note:
        p2 = cell.add_paragraph()
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r2 = p2.add_run(note)
        set_run_font(r2, 8.6, color=GRAY_TEXT)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)
    return table


def add_callout(doc, title: str, text: str, kind="note"):
    fill = BLUE_LIGHT if kind == "note" else "FCE4D6"
    accent = BLUE if kind == "note" else ORANGE
    table = doc.add_table(rows=1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    left, right = table.rows[0].cells
    set_cell_width(left, 120)
    set_cell_width(right, 8880)
    set_cell_shading(left, accent)
    set_cell_shading(right, fill)
    set_cell_margins(left, 40, 0, 40, 0)
    set_cell_margins(right, 100, 180, 100, 180)
    p = right.paragraphs[0]
    r = p.add_run(title)
    set_run_font(r, 10.2, bold=True, color=NAVY if kind == "note" else ORANGE)
    p2 = right.add_paragraph()
    r2 = p2.add_run(text)
    set_run_font(r2, 9.5, color=BLACK)
    set_cant_split(table.rows[0])
    doc.add_paragraph().paragraph_format.space_after = Pt(0)
    return table


def add_code(doc, code: str, caption: str | None = None):
    if caption:
        p0 = doc.add_paragraph()
        p0.paragraph_format.space_before = Pt(4)
        p0.paragraph_format.space_after = Pt(3)
        r0 = p0.add_run(caption)
        set_run_font(r0, 8.8, bold=True, color=GRAY_TEXT)
        set_keep_with_next(p0)
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    cell = table.cell(0, 0)
    set_cell_width(cell, 9000)
    set_cell_margins(cell, 110, 160, 110, 160)
    set_cell_shading(cell, GRAY_LIGHT)
    p = cell.paragraphs[0]
    p.paragraph_format.line_spacing = 1.0
    p.paragraph_format.space_after = Pt(0)
    lines = code.splitlines()
    for idx, line in enumerate(lines):
        r = p.add_run(line)
        set_run_font(r, 8.2, color="243447", code=True)
        if idx != len(lines) - 1:
            r.add_break()
    set_cant_split(table.rows[0])
    doc.add_paragraph().paragraph_format.space_after = Pt(0)
    return table


def add_table(doc, headers, rows, widths, caption=None):
    if caption:
        p0 = doc.add_paragraph()
        p0.paragraph_format.space_before = Pt(5)
        p0.paragraph_format.space_after = Pt(4)
        r0 = p0.add_run(caption)
        set_run_font(r0, 8.8, bold=True, color=GRAY_TEXT)
        set_keep_with_next(p0)
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    header = table.rows[0]
    set_repeat_table_header(header)
    for i, h in enumerate(headers):
        cell = header.cells[i]
        set_cell_width(cell, widths[i])
        set_cell_shading(cell, BLUE_DARK)
        set_cell_margins(cell)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        r = p.add_run(str(h))
        set_run_font(r, 9.2, bold=True, color=WHITE)
    for ridx, row in enumerate(rows):
        tr = table.add_row()
        set_cant_split(tr)
        for i, value in enumerate(row):
            cell = tr.cells[i]
            set_cell_width(cell, widths[i])
            set_cell_margins(cell)
            if ridx % 2:
                set_cell_shading(cell, "F8FAFC")
            p = cell.paragraphs[0]
            r = p.add_run(str(value))
            set_run_font(r, 8.9, color=BLACK, code=("Solution.cpp" in str(value) or str(value).startswith("O(")))
    doc.add_paragraph().paragraph_format.space_after = Pt(0)
    return table


def h1(doc, text, page_break=False):
    p = doc.add_paragraph(text, style="Heading 1")
    p.paragraph_format.page_break_before = page_break
    return p


def h2(doc, text):
    return doc.add_paragraph(text, style="Heading 2")


def h3(doc, text):
    return doc.add_paragraph(text, style="Heading 3")


def configure_document(doc: Document) -> None:
    sec = doc.sections[0]
    sec.page_width = Inches(8.5)
    sec.page_height = Inches(11)
    sec.top_margin = Inches(0.78)
    sec.bottom_margin = Inches(0.72)
    sec.left_margin = Inches(0.92)
    sec.right_margin = Inches(0.92)
    sec.header_distance = Inches(0.35)
    sec.footer_distance = Inches(0.35)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Noto Sans CJK SC"
    normal.font.size = Pt(10.5)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Noto Sans CJK SC")
    normal.paragraph_format.line_spacing = 1.25
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.widow_control = True

    body = styles["Body Text"]
    body.font.name = "Noto Sans CJK SC"
    body.font.size = Pt(10.5)
    body._element.rPr.rFonts.set(qn("w:eastAsia"), "Noto Sans CJK SC")
    body.paragraph_format.line_spacing = 1.25
    body.paragraph_format.space_after = Pt(6)
    body.paragraph_format.widow_control = True

    for style_name in ["List Bullet", "List Bullet 2", "List Number", "List Number 2"]:
        st = styles[style_name]
        st.font.name = "Noto Sans CJK SC"
        st.font.size = Pt(10.2)
        st._element.rPr.rFonts.set(qn("w:eastAsia"), "Noto Sans CJK SC")
        st.paragraph_format.line_spacing = 1.18
        st.paragraph_format.space_after = Pt(3.5)

    h1s = styles["Heading 1"]
    h1s.font.name = "Noto Sans CJK SC"
    h1s._element.rPr.rFonts.set(qn("w:eastAsia"), "Noto Sans CJK SC")
    h1s.font.size = Pt(16)
    h1s.font.bold = True
    h1s.font.color.rgb = RGBColor.from_string(BLUE)
    h1s.paragraph_format.space_before = Pt(18)
    h1s.paragraph_format.space_after = Pt(10)
    h1s.paragraph_format.keep_with_next = True

    h2s = styles["Heading 2"]
    h2s.font.name = "Noto Sans CJK SC"
    h2s._element.rPr.rFonts.set(qn("w:eastAsia"), "Noto Sans CJK SC")
    h2s.font.size = Pt(13)
    h2s.font.bold = True
    h2s.font.color.rgb = RGBColor.from_string(BLUE_DARK)
    h2s.paragraph_format.space_before = Pt(14)
    h2s.paragraph_format.space_after = Pt(7)
    h2s.paragraph_format.keep_with_next = True

    h3s = styles["Heading 3"]
    h3s.font.name = "Noto Sans CJK SC"
    h3s._element.rPr.rFonts.set(qn("w:eastAsia"), "Noto Sans CJK SC")
    h3s.font.size = Pt(11.5)
    h3s.font.bold = True
    h3s.font.color.rgb = RGBColor.from_string(BLUE_DARK)
    h3s.paragraph_format.space_before = Pt(10)
    h3s.paragraph_format.space_after = Pt(5)
    h3s.paragraph_format.keep_with_next = True

    header = sec.header
    hp = header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    hr = hp.add_run("GPU 显存约束调度  ·  通用 385 版")
    set_run_font(hr, 8.2, bold=True, color=GRAY_TEXT)
    add_bottom_border(hp, GRAY_MID, 6)

    footer = sec.footer
    fp = footer.paragraphs[0]
    add_page_number(fp)

    props = doc.core_properties
    props.title = "GPU 显存约束调度：通用 385 版"
    props.subject = "华为算法挑战赛赛后开源说明"
    props.author = "Competition solution authors"
    props.keywords = "GPU scheduling, memory constraint, quantization, local search"


def build() -> None:
    source_bytes = SOURCE.read_bytes()
    source_lines = source_bytes.count(b"\n") + (0 if source_bytes.endswith(b"\n") else 1)
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()

    doc = Document()
    configure_document(doc)

    # Cover: editorial cover pattern.
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(74)
    p.paragraph_format.space_after = Pt(12)
    r = p.add_run("赛后公开整理")
    set_run_font(r, 10.5, bold=True, color=BLUE)

    title = doc.add_paragraph()
    title.paragraph_format.space_after = Pt(6)
    r = title.add_run("GPU 显存约束调度")
    set_run_font(r, 30, bold=True, color=NAVY)

    subtitle = doc.add_paragraph()
    subtitle.paragraph_format.space_after = Pt(24)
    r = subtitle.add_run("源自 385.03 代码谱系的通用量化实现")
    set_run_font(r, 18, bold=False, color=BLUE_DARK)

    add_callout(
        doc,
        "版本定位",
        "本实现由比赛期间约 385 分的代码谱系整理而来。公开源码采用固定、透明的候选集合；当前派生版未回到原赛场重新计分。",
    )

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(26)
    p.paragraph_format.space_after = Pt(5)
    r = p.add_run("从精确显存检查，到有限墙钟内的多起点搜索")
    set_run_font(r, 11.5, bold=True, color=BLACK)
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(30)
    r = p.add_run("GCC 17 · C++17 · 单文件交互式程序 · 2026 年 8 月")
    set_run_font(r, 9.5, color=GRAY_TEXT)

    add_body(
        doc,
        "本文重点：事件驱动模拟、优先级网格、regret、局部搜索、无损 int16 预筛和残余重优化。所有实例使用同一候选集合；385 只表示原始代码谱系的历史量级。",
    )

    doc.add_page_break()

    h1(doc, "摘要")
    add_body(
        doc,
        "这道题的难点并不只在优先级公式。真正耗时的是：给定一个顺序以后，如何反复、快速地判断请求能否放到某张 GPU，并构造一份完整、合法的调度。我们的做法是先把显存曲线改写成分段线性形式，只检查少量关键时刻；模拟器足够快以后，再在多个简单顺序之间做 best-of，并用严格改进的局部搜索继续压缩等待时间。",
    )
    add_body(
        doc,
        "公开代码保留了两条路径。若所有请求在首帧到齐，就在固定墙钟内做离线搜索；若请求持续到达，则先在线贪心，待全部请求到齐后，把尚未启动的部分连同 GPU 当前占用一起重建为残余子问题。这样既保持因果性，也能在流式输入的尾部利用一次全知优化。",
    )
    add_callout(
        doc,
        "一句话概括",
        "先把合法性判断做快，再把搜索预算花在顺序上。量化只用于无损预筛，最终放置仍由完整检查确认。",
    )

    h2(doc, "阅读路线")
    add_number(doc, "先看第 2 章：显存关键点检查，这是整份实现的基础。", restart=True)
    add_number(doc, "再看第 3、4 章：事件构造器怎样使用优先级与 earlyStop。")
    add_number(doc, "第 5、6 章说明如何在有限时间内搜索，以及 int16 预筛为何不损失正确性。")
    add_number(doc, "最后看第 7 章：全量到达和流式到达如何共用同一套离线内核。")

    h2(doc, "代码版本")
    add_body(
        doc,
        "公开源码是从 385.03 历史代码谱系整理出的通用派生版，当前版本未重新计分。",
    )
    add_code(
        doc,
        f"src/Solution.cpp\n{source_lines} lines, {len(source_bytes)} bytes\nSHA-256 {source_sha256}",
        "公开源码校验信息",
    )

    h1(doc, "1  题目模型", page_break=True)
    add_body(
        doc,
        "共有 N 个推理请求和 K 张 GPU。请求 i 在时刻 Aᵢ 到达，输入长度为 Linᵢ，输出长度为 Loutᵢ。调度器需要选择开始时刻 Sᵢ 和 GPU 编号 kᵢ。题面要求 Sᵢ > Aᵢ，请求活跃区间是 [Sᵢ, Sᵢ + Loutᵢ − 1]。",
    )
    add_formula(doc, "mᵢ(t) = Linᵢ + (t − Sᵢ + 1)", "请求 i 在活跃时刻 t 的显存占用")
    add_body(
        doc,
        "每张 GPU 在任意时刻最多同时运行 B 个请求，活跃请求的显存之和不能超过该 GPU 的容量 Mₖ。输出一旦提交就不能撤回，因此流式到达时还要满足在线因果性。",
    )

    h2(doc, "1.1 目标函数")
    add_formula(
        doc,
        "V = Σᵢ(Sᵢ − Aᵢ) + maxᵢ(Sᵢ + Loutᵢ) + maxᵢ(Sᵢ − Aᵢ)",
        "依次是总等待、全局完成项和最大等待；完成项按题面使用 Sᵢ + Loutᵢ",
    )
    add_body(
        doc,
        "第一项通常占比最大，所以搜索内层主要使用 sumD = Σ(Sᵢ−Aᵢ) 作为快速代理；跨策略比较和最终输出前再计算完整 V。这个取舍很实用，但要说清楚：局部搜索中的每一步并不是直接优化三项之和。",
    )
    add_formula(
        doc,
        "score = max(1 + (Vbase − Vans) / ΣᵢLoutᵢ, 0)",
        "单测相对分数；385.03 是原始分支的历史记录，当前派生版未单独评测",
    )

    h2(doc, "1.2 约束规模带来的直接结论")
    add_bullet(doc, "N ≤ 2000、K ≤ 64、B ≤ 128，不能对每个候选顺序做逐时刻全量扫描。")
    add_bullet(doc, "Lin、Lout ≤ 2048，Lin + Lout ≤ 4096，为 int16 无损窄化留下了空间。")
    add_bullet(doc, "到达时间可很大，流式路径不能把每个整数时刻都当作一次重搜索。")
    add_bullet(doc, "单次搜索只有有限墙钟，任何加速最终都要换算成“多跑几次完整构造”。")

    h1(doc, "2  关键化简：只检查显存曲线的关键点")
    add_body(
        doc,
        "这是整份代码最重要的推导。对已经安排在某张 GPU 上的请求 j，记完成时刻 Cⱼ = Sⱼ + Loutⱼ − 1，并把与开始时刻有关的常数收进 vⱼ：",
    )
    add_formula(doc, "vⱼ = Linⱼ − Sⱼ + 1， mⱼ(t) = vⱼ + t")
    add_body(
        doc,
        "在一段没有任务完成的时间里，活跃集合不变。设活跃请求数为 cnt，则该 GPU 的已有显存可以写成：",
    )
    add_formula(doc, "Mem(t) = Σⱼ vⱼ + t · cnt")
    add_body(
        doc,
        "它随 t 单调增加。把新请求 i 放到 [s,e] 后，新请求本身也以斜率 1 增长。因此，在两个完成事件之间，总显存仍单调增加，峰值只可能出现在区间右端。完整逐时刻检查可以精确缩成以下几类点：",
    )
    add_number(doc, "开始时刻 s 的并发数；", restart=True)
    add_number(doc, "落在 [s,e) 内的已有任务完成时刻 C；")
    add_number(doc, "新请求自己的结束时刻 e = s + Loutᵢ − 1。")

    add_code(
        doc,
        "canPlace(i, k, s):\n"
        "    e = s + Lout[i] - 1\n"
        "    if Lin[i] + Lout[i] > M[k]: return false\n"
        "    if activeCount[k] + 1 > B: return false\n"
        "    for C in existing completion times with s <= C < e:\n"
        "        check Mem_k(C) + Lin[i] + C - s + 1 <= M[k]\n"
        "    check Mem_k(e) + Lin[i] + Lout[i] <= M[k]\n"
        "    return true",
        "伪代码 1  单张 GPU 的精确可行性检查",
    )

    h2(doc, "2.1 一个小例子")
    add_body(
        doc,
        "设 GPU 容量为 14，并发上限为 2。已有请求 j：Sⱼ=1、Linⱼ=4、Loutⱼ=4，因此它在 [1,4] 活跃，显存依次为 5、6、7、8。现在尝试让新请求 i 在 s=3 启动，Linᵢ=3、Loutᵢ=3，结束时刻 e=5。",
    )
    add_table(
        doc,
        ["检查时刻", "已有请求", "新请求", "合计", "结论"],
        [
            ("t=4（已有完成点）", "8", "5", "13", "≤14"),
            ("t=5（新请求结束）", "0", "6", "6", "≤14"),
        ],
        [1800, 1600, 1600, 1400, 2600],
        "表 1  只检查两个关键点即可",
    )
    add_body(
        doc,
        "t=3 的总显存是 11，低于 t=4 的 13，不需要单独检查。并发数在 s=3 时达到 2，之后只会因已有任务完成而下降。这个例子也说明了为何并发约束只需在放置开始时检查。",
    )

    h2(doc, "2.2 数据结构")
    add_bullet(doc, "每张 GPU 保存按完成时刻升序排列的 end[]。")
    add_bullet(doc, "并行保存 v[]，维护活动窗口 head、tail、sumV 和 count。")
    add_bullet(doc, "时间前进时只移动 head 删除过期请求，不做 vector 头部擦除。")
    add_bullet(doc, "可行性扫描遇到完成点后，从 sumV 和 count 中扣掉对应请求，再继续检查下一段。")
    add_callout(doc, "对应源码", "src/Solution.cpp:67–100 与 292–322。在线构造和离线模拟器使用同一套关键点数学模型。")

    h1(doc, "3  事件驱动的构造器")
    add_body(
        doc,
        "有了快速可行性检查，下一步是把一个优先级顺序变成完整调度。构造器只在到达事件和完成事件上工作，不按时间逐格推进。对当前事件时刻 t，所有新放置请求的开始时刻统一取 s=t+1。",
    )

    h2(doc, "3.1 主循环")
    add_code(
        doc,
        "while unscheduled jobs remain:\n"
        "    t = min(next arrival, next completion)\n"
        "    add newly arrived jobs into pending\n"
        "    remove completed jobs from each GPU\n"
        "    sort pending by priority\n"
        "    for job in pending:\n"
        "        k = best feasible GPU at s = t + 1\n"
        "        if k exists: place(job, k, s)\n"
        "        else: keep job for a later event",
        "伪代码 2  事件驱动构造",
    )
    add_body(
        doc,
        "GPU 的默认选择更接近 worst-fit：在所有可行 GPU 中，倾向选择新请求区间内已有显存峰值较低的一张。这样能避免某一张卡过早形成高峰，同时保留其他卡的装箱空间。代码还保留了少量 GPU 选择模式，用于离线 best-of。",
    )

    h2(doc, "3.2 earlyStop 的作用")
    add_body(
        doc,
        "pending 已按优先级排序。如果前面的高优先级请求连续多次放不下，继续扫描很深往往只会用低优先级请求填掉零碎空间，反而让重要请求等得更久。earlyStop 记录连续失败次数，达到阈值就结束本轮扫描，等下一个完成事件释放显存后再试。",
    )
    add_callout(
        doc,
        "它不是合法性捷径",
        "earlyStop 只决定“本轮还要不要继续看后面的请求”。任何真正放置的请求仍经过完整检查；被跳过的请求只是推迟，不会因此得到非法安排。",
    )

    h2(doc, "3.3 一个需要诚实说明的局限")
    add_body(
        doc,
        "这份构造器只在到达或完成事件之后尝试启动请求。它不是对每个请求求全局最早可行开始时刻的算法，也不会主动枚举两个事件之间的整数时刻。选择它的原因是稳定、容易验证，而且能让同一秒内跑更多候选顺序。一个自然改进方向是更精细的启动时刻搜索，本文实现未覆盖。",
    )
    add_callout(doc, "对应源码", "src/Solution.cpp:257–624。向量化路径与标量路径最终都会调用同一个 feasible/chooseGpu 逻辑。")

    h1(doc, "4  优先级：从面积直觉到量化小网格")
    add_body(
        doc,
        "单靠一种排序很难覆盖所有输入。短请求适合尽快释放并发名额，大输入请求又会长期抬高显存基线。我们先从请求生命周期的显存—时间面积出发：",
    )
    add_formula(doc, "Areaᵢ = Linᵢ·Loutᵢ + Loutᵢ(Loutᵢ+1)/2")
    add_body(
        doc,
        "实现里的主优先级族省略了不影响主要尺度的线性小项，写成乘积项与平方项的组合。值越小，越靠前尝试：",
    )
    add_formula(doc, "Pᵢ = a·Linᵢ·Loutᵢ + b·Loutᵢ² = Loutᵢ(a·Linᵢ + b·Loutᵢ)")

    h2(doc, "4.1 为什么称为量化网格")
    add_body(
        doc,
        "比赛代码只试少量离散系数，而不是连续调参。原表的系数都是 125 的整数倍；整体除以 125 不改变排序，可以等价写成小整数对。下面列出主网格，便于读者直接移植：",
    )
    add_table(
        doc,
        ["组", "(qₐ, qᵦ) 整数权重"],
        [
            ("qₐ=8", "(8,0), (8,2), (8,4), (8,5), (8,6), (8,7), (8,8), (8,10), (8,12), (8,16), (8,24)"),
            ("qₐ=4", "(4,4), (4,8), (4,16), (4,32)"),
            ("qₐ=2", "(2,2), (2,8), (2,24), (2,48)"),
            ("边界", "(0,8), (16,4)"),
        ],
        [1500, 7500],
        "表 2  与源码浮点系数排序等价的 Q3 整数表示",
    )
    add_body(
        doc,
        "每个权重还会搭配少量 earlyStop 值和 GPU 选择模式。搜索先用一次构造估计耗时，再按剩余墙钟决定跑完整网格、缩减网格还是最小网格。这里的重点不是某个神奇系数，而是：用几个互补但便宜的起点，最后按实际结果保留更好的一个。",
    )

    h2(doc, "4.2 线性补充顺序")
    add_body(
        doc,
        "乘积—平方族对大 Lout 的惩罚较强，但不能表达 a·Lin + Lout 这类“按持续时间近似 SPT，同时给输入长度加权”的顺序。公开代码把一个线性键放进统一候选集合；每个实例都在同一墙钟规则下尝试，并仍以严格 best-of 方式采用。",
    )
    add_callout(doc, "对应源码", "src/Solution.cpp:641–731 为优先级、earlyStop 与 GPU 选择方式的统一搜索。")

    h1(doc, "5  有限墙钟内的搜索")
    add_body(
        doc,
        "网格只能给出几个不错的起点。剩余时间主要用来调整请求顺序。代码不直接修改开始时刻，而是修改优先级，再调用同一个构造器重建完整方案。这样所有候选天然经过同一套合法性逻辑，搜索层不需要维护复杂的增量约束。",
    )

    h2(doc, "5.1 regret bootstrap")
    add_body(
        doc,
        "先运行当前最好顺序，得到每个请求的实际等待 Dᵢ=Sᵢ−Aᵢ。等待越久的请求，下一轮越向前提升：",
    )
    add_formula(doc, "Pᵢ ← Pᵢ − η · (Dᵢ / maxⱼDⱼ) · scale")
    add_body(
        doc,
        "这一步会把搜索从“面积排序”的盆地推向“照顾长等待请求”的盆地。每一轮都重新构造完整解，只在代理目标更好时更新全局最优；即使当前轮没有改进，更新后的优先级仍可继续作为下一轮起点。",
    )

    h2(doc, "5.2 严格改进局部搜索")
    add_body(doc, "局部搜索混合四类邻域，比例会随预计可运行次数调整：")
    add_bullet(doc, "局部交换：交换顺序相近的两个请求；")
    add_bullet(doc, "向前插入：把一个请求插到更早位置；")
    add_bullet(doc, "regret promote：把当前等待较久的请求前移；")
    add_bullet(doc, "regret demote：把前部占用面积较大的请求后移。")
    add_body(
        doc,
        "接受规则保持简单：候选的 sumD 必须严格下降。代码保留固定随机种子，使同一机器、相近负载下的搜索更容易复现。完整 V 主要用于外层候选比较；因此“严格改进”是对内层代理目标而言，不应解释成对所有三项逐步单调。",
    )

    h2(doc, "5.3 后缀检查点")
    add_body(
        doc,
        "若一次交换只影响调度后半段，前面的到达处理、GPU 活跃集合和累计等待都没有必要重算。全量首帧路径会周期性保存检查点：当前事件、每张卡的活动窗口、pending 队列、累计 sumD 和已启动数量。局搜从变化位置之前最近的检查点恢复，再只重放后缀。",
    )
    add_code(
        doc,
        "candidate order changes near position p\n"
        "checkpoint = latest saved state before p\n"
        "restore(checkpoint)\n"
        "replay only the affected suffix\n"
        "accept iff candidate sumD < incumbent sumD",
        "伪代码 3  后缀恢复",
    )
    add_callout(doc, "对应源码", "regret bootstrap：733–747；局部搜索：754–947；检查点结构和恢复：422–469。")

    h1(doc, "6  无损 int16 量化与候选掩码")
    add_body(
        doc,
        "一次构造会反复判断某个请求是否在所有 GPU 上都放不下。若逐个调用完整可行性检查，成本仍然偏高。代码先计算一个便宜的必要条件，批量排除已经能证明不可行的请求。",
    )

    h2(doc, "6.1 第一完成点的必要条件")
    add_body(
        doc,
        "设当前尝试开始时刻为 s，GPU 上最早完成的活动请求在 C₀ 结束，cm=C₀−s+1。若新请求的 Loutᵢ>cm，它会跨过 C₀，那么在 C₀ 必须满足：",
    )
    add_formula(doc, "Linᵢ ≤ Mₖ − sumVₖ − C₀·cntₖ − cm = thresholdₖ")
    add_body(
        doc,
        "此外，单个请求自身峰值必须满足 Linᵢ+Loutᵢ≤Mₖ。把两条条件组合起来，就得到一个非常便宜的掩码判断。对多张 GPU 的结果做 OR：只要有一张卡没有被证明不可行，就保留该请求。",
    )
    add_code(
        doc,
        "candidate_on_gpu =\n"
        "    (Lin + Lout <= cap) and\n"
        "    ((Lin <= threshold) or (Lout <= cm))\n\n"
        "candidate[j] = OR over all non-full GPUs\n"
        "candidate[j] == 0  => safely skip exact check\n"
        "candidate[j] == 1  => call full chooseGpu/feasible",
        "伪代码 4  只产生假阳性、不产生假阴性的预筛",
    )

    h2(doc, "6.2 为什么 int16 是无损的")
    add_bullet(doc, "题目约束给出 Lin、Lout ≤ 2048，因此两者都可精确存入有符号 16 位整数。")
    add_bullet(doc, "Lin + Lout ≤ 4096，也不会越过 int16 正上界 32767。")
    add_bullet(doc, "容量和阈值在写入 short 前向“保留候选”的方向夹紧；夹紧只会增加假阳性，不会误删可行请求。")
    add_bullet(doc, "掩码为 1 后仍执行完整 64 位解析式检查，最终合法性不依赖 short 近似。")
    add_callout(
        doc,
        "术语建议",
        "更准确的叫法是“无损窄化”或“无损量化预筛”。它减少内存带宽并便于 SIMD，但不改变可行集合。",
    )

    h2(doc, "6.3 SoA、分块与 AVX2")
    add_body(
        doc,
        "pending 的 Lin、Lout 被拆成连续数组，候选掩码按块懒计算。放置一个请求以后，GPU 状态会收紧；代码只重算尚未扫描的必要区间。x86 且支持 AVX2 时使用带 target 属性的向量化函数，否则走同逻辑的标量版本。两条路径的差别只在吞吐，不在调度规则。",
    )
    add_callout(doc, "对应源码", "普通/int16 内核：190–255；SoA、阈值夹紧与分块掩码：348–420、510–620。")

    h1(doc, "7  全量到达与流式到达")
    add_body(
        doc,
        "交互题最容易出错的地方，是把离线算法直接套到尚未到达的请求上。公开版把流程明确分成两条路径，但共用同一个快速模拟器。",
    )

    add_table(
        doc,
        ["路径", "触发条件", "主要动作", "合法性边界"],
        [
            ("全量首帧", "t=0 且首帧已包含全部 N 个请求", "约 900ms 的离线多起点搜索，一次性输出", "所有请求已经可见"),
            ("流式在线", "请求分批到达", "在线贪心逐步提交", "只使用已经到达的请求"),
            ("最终残余", "全部请求到齐但仍有 backlog", "以当前 GPU 占用为种子，重解未启动请求", "残余请求统一设 Arr=t，保证 S≥t+1"),
        ],
        [1500, 2300, 3000, 2200],
        "表 3  两条主路径与一个汇合点",
    )

    h2(doc, "7.1 全量首帧")
    add_body(
        doc,
        "若第一帧已经给出全部请求，代码直接构造 Test，运行 solveOffline，然后输出全部 (S,id,k)。墙钟被切成网格、bootstrap 和局搜三段；任何阶段都保留当前最好可行解，预算不足时可以提前收尾。小规模 K=1、N≤16 另有分支定界兜底。",
    )

    h2(doc, "7.2 流式在线与最终残余")
    add_body(
        doc,
        "流式阶段由轻量 Sched 维护环形时间表、活动完成事件和 pending。全部请求到齐后，代码收集尚未启动请求，并把已经提交且仍在运行的请求转换成每张 GPU 的 seedE/seedV。残余问题中的到达时刻统一设为当前 t，因此离线构造器输出的开始时间自然满足 S>t。",
    )
    add_body(
        doc,
        "残余解不会直接覆盖在线方案。实现还会模拟“继续原贪心”的保底方案，并用完整实例的 V 比较；只有严格更优的残余安排才会采用。这个 best-of 很重要，因为残余搜索受墙钟影响，不能假定每次都优于简单延续。",
    )
    add_code(
        doc,
        "live job j on GPU k:\n"
        "    seedE[k].push(Cj)\n"
        "    seedV[k].push(Lin[j] - S[j] + 1)\n\n"
        "residual jobs:\n"
        "    Arr'[i] = current_time\n"
        "    solve with the same event simulator\n"
        "    compare full V against greedy continuation",
        "伪代码 5  把在线状态接到离线模拟器",
    )
    add_callout(doc, "对应源码", "全量首帧入口：1203–1240；残余建模、求解和严格比较：1268–1362。")

    h1(doc, "8  正确性、复杂度与墙钟")
    h2(doc, "8.1 正确性边界")
    add_number(doc, "关键点检查是精确化简：固定活跃集合内显存单调递增，峰值出现在完成事件或新请求结束点。", restart=True)
    add_number(doc, "任何真正放置都经过完整并发与显存检查；掩码只跳过已证明在所有 GPU 上不可行的候选。")
    add_number(doc, "earlyStop 只延迟请求，不修改约束，也不绕过检查。")
    add_number(doc, "流式阶段不读取未来请求；最终残余只在全部请求已经到达后一次性提交。")
    add_number(doc, "外层 best-of 在同一次运行内按完整 V 比较；受墙钟影响的不同机器运行之间没有理论上的分数单调保证。")

    h2(doc, "8.2 复杂度")
    add_table(
        doc,
        ["操作", "上界", "实际减负手段"],
        [
            ("单 GPU 可行性", "O(B)", "完成点扫描；head 单向移动"),
            ("选择 GPU", "O(KB)", "int16 掩码先跳过明显不可行请求"),
            ("一次完整构造", "宽松上界 O(N²KB)", "事件驱动、earlyStop、SoA 分块"),
            ("局搜候选", "一次构造或一个后缀", "检查点恢复，受硬墙钟截止"),
            ("离线空间", "O(K(N+B)+N)", "每张 GPU 保存活动 end/v 数组"),
        ],
        [2300, 2400, 4300],
        "表 4  复杂度和实际优化点",
    )
    add_body(
        doc,
        "最坏复杂度看起来仍然很高，但比赛规模下的关键是常数和平均扫描深度。预筛、earlyStop、活动头指针和后缀恢复并不改变理论最坏阶，却直接决定固定 900ms 里能跑几份候选。",
    )

    h2(doc, "8.3 墙钟治理")
    add_bullet(doc, "先跑一份基准构造，估计单次模拟耗时。")
    add_bullet(doc, "按可负担次数选择完整网格、缩减网格或最小网格。")
    add_bullet(doc, "搜索阶段预留至少一次模拟的收尾时间，避免拿到半份候选。")
    add_bullet(doc, "流式残余预算会扣除前面已经消耗的在线时间。")
    add_bullet(doc, "任何额外候选都以当前可行解为保底，不依赖搜索一定收敛。")

    h1(doc, "9  代码导航与使用")
    add_table(
        doc,
        ["源码位置", "内容"],
        [
            ("src/Solution.cpp:21–170", "流式在线调度器 Sched"),
            ("src/Solution.cpp:190–255", "普通/int16 掩码内核与 AVX2 运行时分派"),
            ("src/Solution.cpp:257–624", "事件驱动快速模拟器 Sim"),
            ("src/Solution.cpp:626–632", "完整目标函数 computeV"),
            ("src/Solution.cpp:634–952", "网格、regret、局部搜索和后缀恢复"),
            ("src/Solution.cpp:954–1123", "K=1、N≤16 的精确求解"),
            ("src/Solution.cpp:1203–1240", "全量首帧入口"),
            ("src/Solution.cpp:1268–1362", "最终残余重优化"),
        ],
        [3400, 5600],
        "表 5  建议阅读顺序",
    )

    h2(doc, "9.1 编译")
    add_code(doc, "g++ -std=c++17 -O2 -pipe src/Solution.cpp -o solution")
    add_body(
        doc,
        "推荐 Linux + GCC 17。程序依赖 GNU C++ 的 bits/stdc++.h、unistd.h 和函数 target 属性。x86 平台会在运行时检查 AVX2；不支持时使用标量内核。",
    )

    h2(doc, "9.2 交互运行")
    add_body(
        doc,
        "这不是普通离线程序。每个时间步读入 t、到达请求数及请求信息，随后输出本轮决策数量和若干行三元组 (S,id,k)，并立即写出。要在本地复现，需要交互器负责逐帧喂入、检查 S 的未来性、统计显存/并发并计算 V。直接把完整数据一次重定向到 stdin，未必等价于正式交互环境。",
    )

    h2(doc, "9.3 建议的独立校验")
    add_number(doc, "检查每个请求只被调度一次，且 Sᵢ>Aᵢ、1≤kᵢ≤K。", restart=True)
    add_number(doc, "按开始和结束事件重放每张 GPU，检查任意时刻并发≤B。")
    add_number(doc, "重放 mᵢ(t)=Linᵢ+t−Sᵢ+1，检查总显存≤Mₖ。")
    add_number(doc, "独立计算 sumD、maxC、maxD 和完整 V，不复用求解器内部状态。")
    add_number(doc, "至少覆盖全量首帧、稀疏到达、K=1、小容量、高并发上限和最大 N。")

    h1(doc, "10  版本边界与可继续改进的方向")
    add_body(
        doc,
        "这份公开稿来自约 385 分的代码谱系，整理目标是给出一套完整、可读、便于迁移的方法。候选集合和搜索规则在源码中固定给出；385 只表示历史量级，当前派生版没有直接评测成绩。",
    )

    h2(doc, "10.1 这份实现的已知局限")
    add_bullet(doc, "构造器只在到达/完成事件后启动请求，未枚举事件之间更细的可行时刻。")
    add_bullet(doc, "局搜内层主要优化 sumD，maxC 和 maxD 依靠外层比较补偿。")
    add_bullet(doc, "候选数量由剩余墙钟决定，不同机器上的实际搜索深度可能不同。")
    add_bullet(doc, "固定墙钟会让不同 CPU 或系统负载下的迭代次数略有变化。")
    add_bullet(doc, "源码保留单文件程序形态，便于编译复现，但不等同于生产级库接口。")

    h2(doc, "10.2 更通用的改进顺序")
    add_number(doc, "先写独立 checker 和可重复的基准集，保证每次优化都有合法性护栏。", restart=True)
    add_number(doc, "把优先级、GPU 选择和启动时刻搜索拆成可替换策略，保留同一模拟内核。")
    add_number(doc, "若要进一步提分，优先研究更精细的最早可行时刻，而不是继续堆权重表。")
    add_number(doc, "让局搜直接比较完整 V，或用增量方式维护 maxC/maxD 的变化。")
    add_number(doc, "用确定的迭代预算补充墙钟预算，降低跨机器波动。")

    add_callout(
        doc,
        "最后的判断",
        "这份方案真正可复用的不是某组常数，而是三件事：精确关键点检查、快速完整构造、用保底解约束搜索风险。",
    )

    h1(doc, "附录 A  核心流程速查")
    add_table(
        doc,
        ["阶段", "输入", "输出", "保底"],
        [
            ("关键点检查", "请求 i、GPU k、开始 s", "可行/不可行、已有峰值", "完整 64 位计算"),
            ("事件构造", "优先级向量", "一份合法 S/K", "pending 延后而非强放"),
            ("网格搜索", "若干权重/earlyStop", "较好初始顺序", "始终保留当前 best"),
            ("regret + LS", "当前最好优先级", "更低 sumD 的候选", "只接受严格下降"),
            ("最终残余", "在线状态 + 未启动请求", "一次性尾部计划", "与原贪心按完整 V 比较"),
        ],
        [1900, 2800, 2500, 1800],
    )

    h2(doc, "核心不变量")
    add_bullet(doc, "活动请求按完成时刻有序；head 之前全部过期。")
    add_bullet(doc, "sumV 等于活动窗口中所有 v 的和，count 等于活动请求数。")
    add_bullet(doc, "候选掩码为 0 才允许跳过；掩码为 1 必须精确复核。")
    add_bullet(doc, "bestS/bestK 始终对应一份已经完整构造的可行方案。")
    add_bullet(doc, "在线输出只包含已经到达的请求，开始时间严格晚于当前时刻。")

    h2(doc, "发布文件")
    add_table(
        doc,
        ["文件", "用途"],
        [
            ("README.md", "项目边界、编译和复现说明"),
            ("LICENSE", "MIT License"),
            (".gitignore", "本地编译与文档预览产物忽略规则"),
            ("src/Solution.cpp", "通用化派生版单文件源码"),
            ("docs/GPU显存约束调度_通用385版.docx", "本文档"),
            ("tools/build_doc.py", "本文档的可重复生成脚本"),
            ("SHA256SUMS.txt", "发布文件校验清单"),
        ],
        [3900, 5100],
    )

    h2(doc, "版本说明")
    add_body(
        doc,
        "历史成绩只用于说明代码谱系。发布包还保留本文档的生成脚本与 SHA-256 校验清单，便于复核和继续维护。",
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build()
