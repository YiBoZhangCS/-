"""Build the course DOCX from the retained template and completed real run data."""
import argparse
from datetime import datetime, timezone
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import zipfile

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "roleplay/report"
TEMPLATE = ROOT / "报告模板.docx"
TEMPLATE_SHA = "4f27a22424bd7c94cdcfd1ef14ce06c2ff12d0ca5ff1748ea0407cda9a5bfa01"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def replace_text(paragraph, text):
    properties = deepcopy(paragraph.runs[0]._r.rPr) if paragraph.runs and paragraph.runs[0]._r.rPr is not None else None
    paragraph.text = text
    if properties is not None:
        paragraph.runs[0]._r.insert(0, properties)


def table(doc, caption, headers, rows, widths):
    p = doc.add_paragraph(caption, "Caption")
    p.paragraph_format.keep_with_next = True
    t = doc.add_table(rows=1, cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for column, width in zip(t.columns, widths):
        column.width = Cm(width)
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement("w:" + edge)
        for k, v in {"val": "single", "sz": "4", "color": "D9D9D9"}.items():
            e.set(qn("w:" + k), v)
        borders.append(e)
    t._tbl.tblPr.append(borders)
    for cell, value in zip(t.rows[0].cells, headers):
        cell.text = str(value)
    repeat = OxmlElement("w:tblHeader")
    t.rows[0]._tr.get_or_add_trPr().append(repeat)
    for row in rows:
        for cell, value in zip(t.add_row().cells, row):
            cell.text = str(value)
    for i, row in enumerate(t.rows):
        row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        for j, cell in enumerate(row.cells):
            cell.width = Cm(widths[j])
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            margins = OxmlElement("w:tcMar")
            for name in ("top", "bottom", "left", "right"):
                m = OxmlElement("w:" + name)
                m.set(qn("w:w"), "85")
                m.set(qn("w:type"), "dxa")
                margins.append(m)
            cell._tc.get_or_add_tcPr().append(margins)
            if i == 0:
                shade = OxmlElement("w:shd")
                shade.set(qn("w:fill"), "EDEDED")
                cell._tc.get_or_add_tcPr().append(shade)
            for p in cell.paragraphs:
                p.paragraph_format.first_line_indent = Pt(0)
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.line_spacing = 1.15
                p.paragraph_format.keep_with_next = i < len(t.rows) - 1
                for r in p.runs:
                    r.font.name = "Times New Roman"
                    r.font.size = Pt(10.5)
                    r.font.bold = i == 0
                    r._r.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "宋体")
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--identity", type=Path, help="Optional private JSON with 学院/专业/班级/姓名/学号/组员/联系方式/序号")
    args = parser.parse_args()
    if hashlib.sha256(TEMPLATE.read_bytes()).hexdigest() != TEMPLATE_SHA:
        raise SystemExit("Retained template changed; inspect again before building")
    summary = read(ROOT / "roleplay/results/experiment_summary.json")
    runs = {r["run_id"]: r for r in summary["runs"]}
    final = runs["final_v2"]
    if final["completed_samples"] != 571 or final.get("submission_validation", {}).get("unique_ids") != 571:
        raise SystemExit("Final 571-record validated run is required; no fabricated report results")
    verify = read(ROOT / "roleplay/audit/offline_verification.json")
    if not verify["all_passed"]:
        raise SystemExit("Offline acceptance tests must pass")
    totals = summary["totals"]
    values = {
        "final_records": "571", "final_bytes": str(final["submission_validation"]["bytes"]),
        "final_input_tokens": f"{final['delivered_input_tokens']:,}", "final_output_tokens": f"{final['delivered_output_tokens']:,}",
        "final_cost": f"{final['submission_attributed_usd']:.6f}", "total_cost": f"{totals['provider_billed_usd']:.6f}",
        "test_count": str(verify["results"][0]["test_count"]),
        "model_distribution": "、".join(f"{k} {v} 条" for k,v in final["model_distribution"].items()),
        "inference_requests": str(totals["inference_requests"]),
        "responses_with_usage": str(totals["responses_with_usage"]),
        "unknown_reserve": f"{totals['unknown_reserved_usd']:.2f}",
        "budget_remaining": f"{totals['budget_remaining_after_reservations_usd']:.6f}",
        "python_version": verify["python"], "openai_version": verify["packages"]["openai"],
        "httpx_version": verify["packages"]["httpx"],
    }
    content = (REPORT / "content.md").read_text(encoding="utf-8")
    content = re.sub(r"\{\{(\w+)\}\}", lambda m: values[m.group(1)], content)
    # Markdown permits a heading immediately followed by a body line.
    # Keep these as separate Word paragraphs rather than making the body a heading.
    content = re.sub(r"(?m)^(# [^\n]+)\n", r"\1\n\n", content)
    if "{{" in content:
        raise SystemExit("Unresolved report placeholders")
    doc = Document(TEMPLATE)
    update = OxmlElement("w:updateFields")
    update.set(qn("w:val"), "true")
    doc.settings.element.append(update)
    body = doc.element.body
    original_children = list(body)
    first_heading = next(i for i, e in enumerate(original_children) if e.xpath('./w:pPr/w:pStyle[@w:val="1"]'))
    section_paragraphs = [e for e in original_children if e.xpath("./w:pPr/w:sectPr")]
    body_section = deepcopy(section_paragraphs[1].find(qn("w:pPr")))
    for e in original_children[:first_heading]:
        if e.xpath(".//w:txbxContent"):
            body.remove(e)
    for p in doc.paragraphs:
        if p.text.startswith("题目："):
            replace_text(p, "题目：基于大模型的中文角色扮演对话生成")
    identity = read(args.identity) if args.identity else {}
    doc.core_properties.author = str(identity.get("姓名", ""))
    doc.core_properties.last_modified_by = ""
    doc.core_properties.title = "基于大模型的中文角色扮演对话生成"
    doc.core_properties.subject = "信息检索课程角色扮演大作业"
    doc.core_properties.created = datetime.now(timezone.utc)
    doc.core_properties.modified = datetime.now(timezone.utc)
    replace_text(doc.tables[0].rows[1].cells[0].paragraphs[0], str(identity.get("序号", "")))
    for row in doc.tables[1].rows:
        label = row.cells[0].text.rstrip("：:")
        replace_text(row.cells[1].paragraphs[0], str(identity.get(label, "2026年11月18日" if label == "日期" else "")))
    for e in original_children[first_heading:]:
        if e.tag != qn("w:sectPr"):
            body.remove(e)
    source_rows = {r["id"]: r for r in read(ROOT / "基于大模型的角色扮演/test_data.jsonl")}
    final_outputs = {r["id"]: r["model_output"] for r in read(ROOT / "roleplay/runs/final_v1/submission.json")}
    refs = False
    for block in content.split("\n\n"):
        block = " ".join(block.splitlines()).strip()
        if not block:
            continue
        if block == "@abstract":
            p = doc.add_paragraph("摘要", "新正文")
            p.runs[0].bold = True
        elif block == "@references":
            p = doc.add_paragraph()
            p._p.append(deepcopy(body_section))
            doc.add_paragraph("参 考 文 献", "参考文献标题")
            refs = True
        elif block.startswith("# "):
            doc.add_paragraph(block[2:], "Heading 1")
        elif block == "[[TABLE_MODELS]]":
            names = [("GLM 5.3 Flash", "cmp_glm_low_structured40_v1"),
                     ("Qwen 3.8 Max", "cmp_qwen_low_structured40_v1"),
                     ("GPT 6 Astra", "cmp_gpt_structured40_v1")]
            table(doc, "表1 固定40条样本的模型比较", ["模型", "输入token", "输出token", "平均字数", "实收美元"],
                  [[label, runs[k]["input_tokens"], runs[k]["output_tokens"], f"{runs[k]['length_chars']['mean']:.2f}",
                    f"{runs[k]['provider_billed_usd']:.6f}"] for label, k in names], [3.6, 2.6, 2.6, 2.6, 3.2])
        elif block == "[[TABLE_ABLATIONS]]":
            names = [("No Profile", "ablation_gpt_no_profile40_v1"), ("Baseline", "ablation_gpt_baseline40_v1"),
                     ("Structured", "cmp_gpt_structured40_v1")]
            table(doc, "表2 GPT候选的画像与提示词消融", ["条件", "有效条数", "平均字数", "实收美元"],
                  [[label, runs[k]["completed_samples"], f"{runs[k]['length_chars']['mean']:.3f}",
                    f"{runs[k]['provider_billed_usd']:.6f}"] for label, k in names], [4.0, 3.0, 3.5, 4.1])
        elif block == "[[TABLE_FINAL]]":
            table(doc, "表3 全量最终回答的长度分布", ["回答字符区间", "条数"],
                  list(final["length_histogram"].items()), [8.0, 6.6])
        elif block.startswith("[[CASE_"):
            rid = int(re.search(r"CASE_(\d+)", block).group(1))
            row = source_rows[rid]
            p = doc.add_paragraph(f"案例 {rid}  {row['role']}", "新正文")
            p.runs[0].bold = True
            p.paragraph_format.keep_with_next = True
            lines = row["context"].splitlines()
            excerpt = ("……" if len(lines) > 3 else "") + " ".join(lines[-3:])
            p = doc.add_paragraph("历史节选：“" + excerpt + "”", "新正文")
            p.paragraph_format.keep_with_next = True
            doc.add_paragraph("最终回复：“" + final_outputs[rid] + "”", "新正文")
        else:
            doc.add_paragraph(block, "参考文献正文" if refs else "新正文")
    for paragraph in doc.paragraphs:
        if paragraph.style.name == "新正文":
            paragraph.paragraph_format.widow_control = True
    path = REPORT / "角色扮演实验报告.docx"
    working = REPORT / ".report-working.docx"
    doc.save(working)
    # python-docx reserializes untouched XML parts. Retain the original package
    # bytes and replace only the intentionally edited body/settings parts.
    with zipfile.ZipFile(TEMPLATE) as source, zipfile.ZipFile(working) as modified, \
            zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as output:
        if set(modified.namelist()) - set(source.namelist()):
            raise SystemExit("Unexpected package parts; inspect relationships")
        for item in source.infolist():
            data = modified.read(item.filename) if item.filename in ("word/document.xml", "word/settings.xml", "docProps/core.xml") else source.read(item.filename)
            output.writestr(item, data)
    working.unlink()
    with zipfile.ZipFile(TEMPLATE) as source, zipfile.ZipFile(path) as output:
        inventory = {name: {"bytes": len(source.read(name)), "sha256": hashlib.sha256(source.read(name)).hexdigest()}
                     for name in source.namelist()}
        preserve = [name for name in inventory if name not in ("word/document.xml", "[Content_Types].xml",
                    "word/_rels/document.xml.rels", "word/settings.xml", "docProps/core.xml", "docProps/app.xml")]
        changed = [name for name in preserve if name not in output.namelist() or source.read(name) != output.read(name)]
        write_json(REPORT / "template_inventory.json", inventory)
        write_json(REPORT / "preservation_check.json", {"template_sha256": TEMPLATE_SHA,
                   "preserve_only_parts": preserve, "changed_preserve_only_parts": changed,
                   "sections": len(doc.sections), "identity_fields_blank": not bool(identity)})
        if changed or len(doc.sections) != 3:
            raise SystemExit("Template preservation mismatch: " + repr(changed))
    print(path)


if __name__ == "__main__":
    main()
