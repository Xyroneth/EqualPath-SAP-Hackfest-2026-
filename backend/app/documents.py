"""Evidence documents: upload validation, text extraction and safe viewers.

Supported uploads: PDF, Word (.docx), PowerPoint (.pptx), Excel (.xlsx), CSV, TXT/Markdown/JSON, source code
(.py .js .ts .java) and images (.png .jpg). Text is extracted so the Skills Discovery Agent can read it. Viewers are
generated server-side as script-free HTML (or raw PDF/image), so a file can never run code in the reviewer's browser.
"""
from __future__ import annotations

import html
import io
import math
import re
import zipfile
from pathlib import PurePath
from xml.etree import ElementTree as ET

MAX_BYTES = 8 * 1024 * 1024
MAX_TEXT = 60_000
MAX_PDF_PAGES = 60

EXT_INFO: dict[str, tuple[str, str]] = {  # extension -> (mime, kind)
    ".pdf": ("application/pdf", "pdf"),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
    ".pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", "pptx"),
    ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
    ".csv": ("text/csv", "csv"),
    ".txt": ("text/plain", "text"),
    ".md": ("text/markdown", "text"),
    ".json": ("application/json", "text"),
    ".py": ("text/x-python", "code"),
    ".js": ("text/javascript", "code"),
    ".ts": ("text/typescript", "code"),
    ".java": ("text/x-java", "code"),
    ".png": ("image/png", "image"),
    ".jpg": ("image/jpeg", "image"),
    ".jpeg": ("image/jpeg", "image"),
}
ACCEPT = ",".join(sorted(EXT_INFO))
LEGACY = {".doc": ".docx", ".xls": ".xlsx", ".ppt": ".pptx"}


class DocumentError(ValueError):
    """Raised with a message that is safe to show to the user."""


def safe_name(name: str) -> str:
    base = PurePath(name.replace("\\", "/")).name
    base = re.sub(r"[^\w.\- ()]", "_", base).strip(" .") or "document"
    return base[:100]


def ext_of(name: str) -> str:
    return PurePath(name).suffix.lower()


def validate_upload(filename: str, data: bytes) -> tuple[str, str, str]:
    """Return (safe filename, mime, kind) or raise DocumentError."""
    name = safe_name(filename)
    ext = ext_of(name)
    if ext in LEGACY:
        raise DocumentError(f"Old {ext} files are not supported. Please save it as {LEGACY[ext]} and upload again.")
    if ext not in EXT_INFO:
        raise DocumentError("This file type is not supported. Use PDF, Word, PowerPoint, Excel, CSV, text, code or an image (PNG/JPG).")
    if not data:
        raise DocumentError("The file is empty.")
    if len(data) > MAX_BYTES:
        raise DocumentError(f"The file is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    mime, kind = EXT_INFO[ext]
    head = data[:8]
    if kind == "pdf" and not data.lstrip()[:5] == b"%PDF-":
        raise DocumentError("This does not look like a valid PDF.")
    if kind in ("docx", "pptx", "xlsx"):
        if head[:2] != b"PK":
            raise DocumentError(f"This does not look like a valid {ext} file.")
        _check_zip(data)
    if ext == ".png" and head[:4] != b"\x89PNG":
        raise DocumentError("This does not look like a valid PNG image.")
    if ext in (".jpg", ".jpeg") and head[:3] != b"\xff\xd8\xff":
        raise DocumentError("This does not look like a valid JPG image.")
    return name, mime, kind


def _check_zip(data: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if sum(i.file_size for i in z.infolist()) > 60 * 1024 * 1024:
                raise DocumentError("The file expands to an unreasonable size.")
    except zipfile.BadZipFile as exc:
        raise DocumentError("The file is damaged or not a real Office document.") from exc


# ------------------------------------------------------------------------------------------------ text extraction

_BULLET = re.compile(r"^(?:[•▪·\-\*]|\d{1,2}[.)])\s+")
_LABEL = re.compile(r"^[A-Z][A-Za-z' ]{2,28}:\s")
_ID_ROW = re.compile(r"^(?:[A-Z]{2,5}-\d+|\d{4}-\d{2}-\d{2}|Sheet\b|Workbook\b|Page\b)")


_BULLET_GLYPHS = str.maketrans({c: "\u2022" for c in "\x7f\uf0b7\uf0a7\uf0d8\uf076\u25aa\u25cf\u2023\u25e6\u2043\uf0fc"})


def reflow(text: str) -> str:
    """Undo hard line wraps from PDF text: join a line to the previous one unless it clearly starts a new item."""
    text = text.translate(_BULLET_GLYPHS)
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            out.append("")
            continue
        if line in ("•", "-", "▪"):
            out.append(line + " ")
            continue
        prev = out[-1] if out else ""
        heading = len(line) > 2 and line == line.upper() and not any(c.islower() for c in line) and len(line) < 60
        starts_new = bool(_BULLET.match(line) or _LABEL.match(line) or _ID_ROW.match(line) or heading)
        if prev and (prev.endswith(" ") and prev.strip() in ("•", "-", "▪")):
            out[-1] = prev + line
        elif not prev or starts_new or prev[-1] in ".!?:" or (prev == prev.upper() and len(prev) < 60 and not any(c.islower() for c in prev)):
            out.append(line)
        else:
            out[-1] = prev + " " + line
    return "\n".join(out).strip()


def extract_text(filename: str, data: bytes) -> tuple[str, str]:
    """Return (text, kind). Images return empty text; the caller must supply a description."""
    ext = ext_of(filename)
    mime, kind = EXT_INFO[ext]
    try:
        if kind == "pdf":
            text = _pdf_text(data)
        elif kind == "docx":
            text = _docx_text(data)
        elif kind == "pptx":
            text = _pptx_text(data)
        elif kind == "xlsx":
            text = xlsx_description(data, filename)
        elif kind in ("csv", "text", "code"):
            text = data.decode("utf-8", errors="replace").replace("\x00", "")
        else:
            text = ""
    except DocumentError:
        raise
    except Exception as exc:  # noqa: BLE001 - corrupt file; report a friendly error
        raise DocumentError(f"Could not read this {ext} file ({type(exc).__name__}). Is it damaged or password-protected?") from exc
    return text[:MAX_TEXT], kind


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        raise DocumentError("This PDF is password-protected. Please upload an unlocked copy.")
    pages = [(p.extract_text() or "") for p in reader.pages[:MAX_PDF_PAGES]]
    text = reflow("\n".join(pages))
    if len(text.strip()) < 20:
        raise DocumentError("No readable text was found in this PDF (it may be a scan). Upload a text PDF, or add the content as a description.")
    return text


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def _docx_blocks(data: bytes) -> list[tuple[str, object]]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    body = root.find(f"{_W}body")
    blocks: list[tuple[str, object]] = []
    for el in list(body) if body is not None else []:
        if el.tag == f"{_W}p":
            txt = "".join(t.text or "" for t in el.iter(f"{_W}t"))
            style = el.find(f"{_W}pPr/{_W}pStyle")
            head = style is not None and str(style.get(f"{_W}val", "")).lower().startswith(("heading", "title"))
            if txt.strip():
                blocks.append(("h" if head else "p", txt.strip()))
        elif el.tag == f"{_W}tbl":
            rows = []
            for tr in el.iter(f"{_W}tr"):
                rows.append(["".join(t.text or "" for t in tc.iter(f"{_W}t")).strip() for tc in tr.iter(f"{_W}tc")])
            blocks.append(("table", rows))
    return blocks


def _docx_text(data: bytes) -> str:
    lines = []
    for kind, val in _docx_blocks(data):
        lines.extend([" | ".join(r) for r in val] if kind == "table" else [val])  # type: ignore[union-attr]
    return "\n".join(lines)


def _pptx_slides(data: bytes) -> list[list[str]]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = sorted((n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)), key=lambda n: int(re.findall(r"\d+", n)[0]))
        slides = []
        for n in names:
            root = ET.fromstring(z.read(n))
            slides.append([t for t in ("".join(x.text or "" for x in p.iter(f"{_A}t")).strip() for p in root.iter(f"{_A}p")) if t])
    return slides


def _pptx_text(data: bytes) -> str:
    return "\n".join(f"Slide {i}: " + " / ".join(s) for i, s in enumerate(_pptx_slides(data), 1))


# ------------------------------------------------------------------------------------------------ xlsx helpers

def _load_xlsx(data: bytes):
    from openpyxl import load_workbook

    return load_workbook(io.BytesIO(data), data_only=True)


def _chart_title(chart) -> str:
    try:
        return "".join(r.t for p in chart.title.tx.rich.p for r in (p.r or []))
    except Exception:  # noqa: BLE001
        return ""


def xlsx_description(data: bytes, filename: str) -> str:
    """A factual, text description of a workbook: sheets, headers, charts, formatting rules and long notes."""
    wb = _load_xlsx(data)
    out = [f"Workbook: {filename} ({len(wb.sheetnames)} sheets: {', '.join(wb.sheetnames)})"]
    for ws in wb.worksheets:
        rows = [r for r in ws.iter_rows(values_only=True) if any(v not in (None, "") for v in r)]
        header = next((r for r in rows if sum(isinstance(v, str) for v in r) >= 3), None)
        line = f"Sheet '{ws.title}': {max(len(rows) - 1, 0)} data rows"
        if header:
            line += "; columns: " + ", ".join(str(v) for v in header if v not in (None, ""))
        out.append(line + ".")
        charts = getattr(ws, "_charts", [])
        if charts:
            out.append(f"Sheet '{ws.title}' has {len(charts)} {'charts' if len(charts) > 1 else 'chart'}: " + "; ".join(t for t in (_chart_title(c) for c in charts) if t) + ".")
        cf = [str(rng.sqref) for rng in ws.conditional_formatting]
        if cf:
            out.append(f"Sheet '{ws.title}' uses conditional formatting rules on {', '.join(cf)}.")
        for r in rows[:60]:
            for v in r:
                if isinstance(v, str) and len(v) >= 40:
                    out.append(v.strip())
    return "\n".join(out)


def _cell_value(wb, ref: str) -> list:
    m = re.match(r"^'?(.+?)'?!\$?([A-Z]+)\$?(\d+)(?::\$?([A-Z]+)\$?(\d+))?$", ref)
    if not m:
        return []
    sheet, c1, r1, c2, r2 = m.groups()
    ws = wb[sheet]
    cells = ws[f"{c1}{r1}:{c2 or c1}{r2 or r1}"]
    return [c.value for row in cells for c in row]


PALETTE = ["#0A6ED1", "#008A8A", "#F59E0B", "#B42318", "#6B3FA0", "#188038", "#526071"]


def _chart_svg(wb, chart) -> str:
    kind = type(chart).__name__
    title = html.escape(_chart_title(chart))
    series = []
    for s in chart.series:
        vals = _cell_value(wb, s.val.numRef.f) if s.val and s.val.numRef else []
        cats = []
        if s.cat is not None:
            ref = (s.cat.strRef or s.cat.numRef)
            cats = [str(v) for v in _cell_value(wb, ref.f)] if ref else []
        series.append(([float(v or 0) for v in vals], cats))
    if not series or not series[0][0]:
        return ""
    vals, cats = series[0]
    w, h = 520, 280
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-label="{title}" class="chart">',
           f'<text x="{w / 2}" y="20" text-anchor="middle" class="ct">{title}</text>']
    if kind == "PieChart":
        total = sum(vals) or 1
        cx, cy, r, ang = 150, 150, 92, -math.pi / 2
        for i, v in enumerate(vals):
            a2 = ang + 2 * math.pi * v / total
            x1, y1, x2, y2 = cx + r * math.cos(ang), cy + r * math.sin(ang), cx + r * math.cos(a2), cy + r * math.sin(a2)
            svg.append(f'<path d="M{cx},{cy} L{x1:.1f},{y1:.1f} A{r},{r} 0 {1 if a2 - ang > math.pi else 0} 1 {x2:.1f},{y2:.1f} Z" fill="{PALETTE[i % len(PALETTE)]}"/>')
            svg.append(f'<rect x="300" y="{70 + i * 24}" width="12" height="12" fill="{PALETTE[i % len(PALETTE)]}"/>'
                       f'<text x="320" y="{81 + i * 24}" class="cl">{html.escape(cats[i] if i < len(cats) else str(i + 1))}: {int(v) if v == int(v) else v}</text>')
            ang = a2
    else:
        horizontal = getattr(chart, "type", "col") == "bar"
        top, left, bottom, right = 40, 110 if horizontal else 44, 44, 20
        pw, ph = w - left - right, h - top - bottom
        mx = max(max(v) for v, _ in series) or 1
        n = len(vals)
        svg.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + ph}" class="ax"/><line x1="{left}" y1="{top + ph}" x2="{left + pw}" y2="{top + ph}" class="ax"/>')
        if horizontal:
            slot = ph / n
            for i, v in enumerate(vals):
                bw = pw * v / mx
                y = top + i * slot + slot * 0.18
                svg.append(f'<rect x="{left}" y="{y:.1f}" width="{bw:.1f}" height="{slot * 0.64:.1f}" fill="{PALETTE[0]}" rx="3"/>'
                           f'<text x="{left + bw + 6:.1f}" y="{y + slot * 0.4:.1f}" class="cl">{int(v)}</text>'
                           f'<text x="{left - 8}" y="{y + slot * 0.4:.1f}" text-anchor="end" class="cl">{html.escape(cats[i] if i < len(cats) else "")}</text>')
        else:
            slot = pw / n
            for i, v in enumerate(vals):
                bh = ph * v / mx
                x = left + i * slot + slot * 0.18
                svg.append(f'<rect x="{x:.1f}" y="{top + ph - bh:.1f}" width="{slot * 0.64:.1f}" height="{bh:.1f}" fill="{PALETTE[0]}" rx="3"/>'
                           f'<text x="{x + slot * 0.32:.1f}" y="{top + ph - bh - 6:.1f}" text-anchor="middle" class="cl">{int(v)}</text>'
                           f'<text x="{x + slot * 0.32:.1f}" y="{top + ph + 18}" text-anchor="middle" class="cl">{html.escape(cats[i] if i < len(cats) else "")}</text>')
    svg.append("</svg>")
    return "".join(svg)


def _xlsx_sheet_html(wb, ws, idx: int) -> str:
    from openpyxl.utils import get_column_letter

    max_r, max_c = min(ws.max_row, 300), min(ws.max_column, 26)
    from openpyxl.utils.cell import range_boundaries

    rules = []
    for cf in ws.conditional_formatting:
        for r in cf.rules:
            if r.type == "cellIs" and r.formula:
                try:
                    rules.append(([range_boundaries(part) for part in str(cf.sqref).split()], r.operator, float(r.formula[0])))
                except (ValueError, TypeError):
                    continue

    def rule_style(cell) -> str:
        v = cell.value
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            return ""
        for boxes, op, lim in rules:
            if any(c1 <= cell.column <= c2 and r1 <= cell.row <= r2 for c1, r1, c2, r2 in boxes):
                if (op == "greaterThan" and v > lim) or (op == "lessThan" and v < lim) or (op == "equal" and v == lim) \
                        or (op == "greaterThanOrEqual" and v >= lim) or (op == "lessThanOrEqual" and v <= lim):
                    return "background:#FDE2E2;color:#B42318;font-weight:700;"
        return ""

    head = "<tr><th class='corner'></th>" + "".join(f"<th>{get_column_letter(c)}</th>" for c in range(1, max_c + 1)) + "</tr>"
    body = []
    sticky_rows = 1 if (ws.freeze_panes and ws.freeze_panes.endswith("2")) else 0
    for r in range(1, max_r + 1):
        cells = []
        for c in range(1, max_c + 1):
            cell = ws.cell(r, c)
            v = cell.value
            style = ""
            if cell.fill and cell.fill.fill_type == "solid" and cell.fill.fgColor and isinstance(cell.fill.fgColor.rgb, str) and len(cell.fill.fgColor.rgb) == 8:
                style += f"background:#{cell.fill.fgColor.rgb[2:]};"
            if cell.font:
                if cell.font.bold:
                    style += "font-weight:700;"
                if cell.font.italic:
                    style += "font-style:italic;"
                if cell.font.color is not None and isinstance(cell.font.color.rgb, str) and len(cell.font.color.rgb) == 8:
                    style += f"color:#{cell.font.color.rgb[2:]};"
                if cell.font.sz and cell.font.sz >= 13:
                    style += f"font-size:{min(cell.font.sz, 20)}px;"
            style += rule_style(cell)
            num = isinstance(v, (int, float)) and not isinstance(v, bool)
            text = "" if v is None else (f"{v:,.2f}" if isinstance(v, float) and not v.is_integer() else f"{int(v)}" if num else str(v))
            cells.append(f"<td class='{'n' if num else ''}' style=\"{style}\">{html.escape(text)}</td>")
        cls = " class='frozen'" if r <= sticky_rows else ""
        body.append(f"<tr{cls}><th class='rn'>{r}</th>{''.join(cells)}</tr>")
    widths = "".join(f"<col style='width:{min(max((ws.column_dimensions[get_column_letter(c)].width or 10) * 7.2, 46), 420):.0f}px'>" for c in range(1, max_c + 1))
    note = f"<p class='note'>Showing the first {max_r} rows.</p>" if ws.max_row > max_r else ""
    charts = "".join(f"<figure>{_chart_svg(wb, ch)}</figure>" for ch in getattr(ws, "_charts", []))
    return (f"<input type='radio' name='sheet' id='s{idx}' {'checked' if idx == 0 else ''}><label for='s{idx}'>{html.escape(ws.title)}</label>"
            f"<section class='panel'><div class='grid'><table><colgroup><col style='width:44px'>{widths}</colgroup><thead>{head}</thead><tbody>{''.join(body)}</tbody></table></div>{note}"
            f"<div class='charts'>{charts}</div></section>")


# ------------------------------------------------------------------------------------------------ viewers

VIEWER_CSS = """
:root{--bg:#F4F8FC;--card:#fff;--ink:#1F2937;--muted:#526071;--line:#D6DEE8;--navy:#0A1F44;--blue:#0A6ED1;--teal:#008A8A}
@media (prefers-color-scheme:dark){:root{--bg:#0B1220;--card:#111B2E;--ink:#E6EDF7;--muted:#9FB0C8;--line:#22314D;--navy:#0F2A57;--blue:#4DA3FF;--teal:#2CC5C5}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
header.bar{position:sticky;top:0;z-index:5;background:var(--navy);color:#fff;padding:12px 22px;display:flex;gap:16px;align-items:center;flex-wrap:wrap;border-bottom:3px solid var(--teal)}
header.bar b{letter-spacing:.08em}header.bar span{opacity:.85}header.bar a{margin-left:auto;color:#fff;border:1px solid #ffffff66;border-radius:8px;padding:6px 12px;text-decoration:none}
header.bar a:hover{background:#ffffff1f}main{max-width:1180px;margin:22px auto;padding:0 18px}
.doc{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:26px 30px}h1,h2,h3{color:var(--blue)}pre{background:var(--bg);padding:16px;border-radius:10px;overflow:auto;font:13px/1.5 ui-monospace,Menlo,monospace;white-space:pre-wrap;word-break:break-word}
table.t{border-collapse:collapse;width:100%}table.t td,table.t th{border:1px solid var(--line);padding:6px 10px;text-align:left}table.t th{background:var(--bg)}
.slide{border:1px solid var(--line);border-radius:12px;padding:20px 24px;margin:0 0 14px;background:var(--card)}.slide h3{margin:0 0 8px}.slide span{color:var(--muted);font-size:12px}
input[type=radio]{position:absolute;opacity:0;pointer-events:none}label{display:inline-block;padding:9px 18px;margin-right:4px;border:1px solid var(--line);border-bottom:0;border-radius:10px 10px 0 0;background:var(--bg);color:var(--muted);cursor:pointer;font-weight:600}
input:checked+label{background:var(--card);color:var(--blue);box-shadow:inset 0 3px 0 var(--teal)}input:focus-visible+label{outline:3px solid #F59E0B}
.sheets{display:flex;flex-wrap:wrap;align-items:flex-end}.panel{display:none;order:10;flex:0 0 100%;background:var(--card);border:1px solid var(--line);border-radius:0 12px 12px 12px;padding:14px;margin-top:-1px}
""" + "".join(f"input#s{i}:checked~section.panel.p{i}{{display:block}}" for i in range(12)) + """
.grid{overflow:auto;max-height:70vh;border:1px solid var(--line);border-radius:8px}.grid table{border-collapse:collapse;table-layout:fixed;font-size:13px;background:var(--card)}
.grid th,.grid td{border:1px solid var(--line);padding:4px 8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.grid thead th{position:sticky;top:0;background:var(--bg);z-index:2;color:var(--muted);font-weight:600;text-align:center}
.grid th.rn{background:var(--bg);color:var(--muted);text-align:center;position:sticky;left:0;z-index:1}.grid tr.frozen td{position:sticky;top:26px;z-index:1}.grid td.n{text-align:right;font-variant-numeric:tabular-nums}
.charts{display:flex;flex-wrap:wrap;gap:16px;margin-top:16px}.charts figure{margin:0;border:1px solid var(--line);border-radius:10px;padding:8px;background:var(--card)}
svg.chart{width:min(520px,90vw);height:auto}svg .ct{font:700 14px sans-serif;fill:var(--ink)}svg .cl{font:12px sans-serif;fill:var(--ink)}svg .ax{stroke:var(--muted);stroke-width:1}.note{color:var(--muted);font-size:13px}
"""


def _shell(title: str, subtitle: str, body: str, download_url: str | None) -> str:
    dl = f"<a href='{html.escape(download_url)}'>Download original</a>" if download_url else ""
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)} - EQUALPATH</title><style>{VIEWER_CSS}</style></head><body><header class='bar'><b>EQUALPATH</b><span>Evidence viewer</span>"
            f"<span>{html.escape(title)}</span><span style='opacity:.6'>{html.escape(subtitle)}</span>{dl}</header><main>{body}</main></body></html>")


def render_view(filename: str, data: bytes, title: str, download_url: str | None = None) -> tuple[bytes, str]:
    """Return (content, content_type) to display the file in a browser tab."""
    ext = ext_of(filename)
    mime, kind = EXT_INFO[ext]
    if kind in ("pdf", "image"):
        return data, mime
    if kind == "xlsx":
        wb = _load_xlsx(data)
        tabs = "".join(_xlsx_sheet_html(wb, ws, i).replace("<section class='panel'>", f"<section class='panel p{i}'>") for i, ws in enumerate(wb.worksheets[:12]))
        body = f"<div class='sheets'>{tabs}</div>"
        return _shell(title, f"Excel workbook - {filename}", body, download_url).encode(), "text/html; charset=utf-8"
    if kind == "csv":
        import csv

        rows = list(csv.reader(io.StringIO(data.decode("utf-8", errors="replace"))))[:500]
        tr = "".join("<tr>" + "".join(f"<{'th' if i == 0 else 'td'}>{html.escape(c)}</{'th' if i == 0 else 'td'}>" for c in r) + "</tr>" for i, r in enumerate(rows))
        return _shell(title, f"CSV - {filename}", f"<div class='doc'><table class='t'>{tr}</table></div>", download_url).encode(), "text/html; charset=utf-8"
    if kind == "docx":
        parts = []
        for k, v in _docx_blocks(data):
            if k == "h":
                parts.append(f"<h2>{html.escape(str(v))}</h2>")
            elif k == "p":
                parts.append(f"<p>{html.escape(str(v))}</p>")
            else:
                parts.append("<table class='t'>" + "".join("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>" for r in v) + "</table>")  # type: ignore[union-attr]
        return _shell(title, f"Word document - {filename}", f"<div class='doc'>{''.join(parts)}</div>", download_url).encode(), "text/html; charset=utf-8"
    if kind == "pptx":
        slides = "".join(f"<div class='slide'><span>Slide {i}</span><h3>{html.escape(s[0]) if s else ''}</h3>" + "".join(f"<p>{html.escape(x)}</p>" for x in s[1:]) + "</div>"
                         for i, s in enumerate(_pptx_slides(data), 1))
        return _shell(title, f"PowerPoint - {filename}", slides or "<p>No text found on the slides.</p>", download_url).encode(), "text/html; charset=utf-8"
    text = data.decode("utf-8", errors="replace")[:MAX_TEXT]
    return _shell(title, filename, f"<div class='doc'><pre>{html.escape(text)}</pre></div>", download_url).encode(), "text/html; charset=utf-8"
