"""Generate Priya's seed evidence as real files (PDFs + an Excel workbook).

Run from backend/:   .venv/bin/python scripts/generate_evidence.py
Output:              app/data/evidence/*.pdf|xlsx   (committed; the app never needs reportlab at runtime)

Everything here is FICTIONAL demo content. Dev-only dependencies: reportlab, openpyxl, Pillow.
"""
from __future__ import annotations

import random
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from PIL import Image, ImageDraw, ImageFont
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (Image as RLImage, KeepTogether, PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle)

OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "evidence"
TMP = Path(__file__).resolve().parent / ".tmp"
OUT.mkdir(parents=True, exist_ok=True)
TMP.mkdir(exist_ok=True)

NAVY, BLUE, TEAL = colors.HexColor("#0A1F44"), colors.HexColor("#0A6ED1"), colors.HexColor("#008A8A")
INK, MUTED, LINE, PALE = colors.HexColor("#1F2937"), colors.HexColor("#526071"), colors.HexColor("#D6DEE8"), colors.HexColor("#F4F8FC")
RED, GREEN, AMBER = colors.HexColor("#B42318"), colors.HexColor("#188038"), colors.HexColor("#F59E0B")

base = getSampleStyleSheet()
S = {
    "body": ParagraphStyle("body", parent=base["Normal"], fontName="Helvetica", fontSize=9.5, leading=13.5, textColor=INK),
    "small": ParagraphStyle("small", parent=base["Normal"], fontName="Helvetica", fontSize=8.2, leading=11, textColor=MUTED),
    "h1": ParagraphStyle("h1", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=NAVY, spaceAfter=4),
    "h2": ParagraphStyle("h2", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=10.5, leading=14, textColor=BLUE, spaceBefore=10, spaceAfter=3),
    "h3": ParagraphStyle("h3", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=NAVY, spaceBefore=6),
    "bullet": ParagraphStyle("bullet", parent=base["Normal"], fontName="Helvetica", fontSize=9.5, leading=13.5, textColor=INK, leftIndent=14, firstLineIndent=-10),
    "cell": ParagraphStyle("cell", parent=base["Normal"], fontName="Helvetica", fontSize=8.2, leading=10.5, textColor=INK),
    "code": ParagraphStyle("code", parent=base["Code"], fontName="Courier", fontSize=8, leading=10.2, textColor=INK, backColor=PALE, borderPadding=6, borderColor=LINE, borderWidth=0.5),
}


def P(text, style="body"):
    return Paragraph(text, S[style])


def bullets(items):
    return [Paragraph(t, S["bullet"], bulletText="•") for t in items]


def rule(width=1, color=LINE):
    t = Table([[""]], colWidths=["100%"], rowHeights=[width])
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), width, color)]))
    return t


def page_deco(title):
    def deco(canvas, doc):
        canvas.saveState()
        w, h = doc.pagesize
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 10 * mm, f"{title}  •  Fictional demo document created for EQUALPATH (SAP Hackfest 2026)")
        canvas.drawRightString(w - 18 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()
    return deco


def build(path, story, title, pagesize=A4, margins=(18, 16, 18, 16)):
    doc = SimpleDocTemplate(str(path), pagesize=pagesize, leftMargin=margins[0] * mm, topMargin=margins[1] * mm,
                            rightMargin=margins[2] * mm, bottomMargin=margins[3] * mm, title=title, author="Priya Sharma (fictional)")
    doc.build(story, onFirstPage=page_deco(title), onLaterPages=page_deco(title))


def band(title, subtitle, width):
    big = ParagraphStyle("bandtitle", parent=S["body"], leading=26)
    small = ParagraphStyle("bandsub", parent=S["body"], leading=13)
    t = Table([[Paragraph(f'<font color="white" size="20"><b>{title}</b></font>', big)],
               [Paragraph(f'<font color="#C7D5EA" size="9">{subtitle}</font>', small)]], colWidths=[width])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY), ("LEFTPADDING", (0, 0), (-1, -1), 14), ("TOPPADDING", (0, 0), (0, 0), 14),
                           ("BOTTOMPADDING", (0, -1), (-1, -1), 12), ("LINEBELOW", (0, -1), (-1, -1), 3, TEAL)]))
    return t


# ---------------------------------------------------------------------------------------------------- fonts / images
def font(size, bold=False, mono=False):
    candidates = []
    if mono:
        candidates = ["/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Monaco.ttf"]
    import reportlab
    fdir = Path(reportlab.__file__).parent / "fonts"
    candidates += [str(fdir / ("VeraBd.ttf" if bold else "Vera.ttf"))]
    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except OSError:
            continue
    return ImageFont.load_default()


def terminal_image(path, title, lines, highlight=(), width=1200):
    f = font(20, mono=True)
    lh, pad = 30, 22
    h = 46 + pad * 2 + lh * len(lines)
    im = Image.new("RGB", (width, h), "#0F172A")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, width, 40], fill="#1E293B")
    for i, c in enumerate(["#EF4444", "#F59E0B", "#22C55E"]):
        d.ellipse([16 + i * 26, 12, 30 + i * 26, 26], fill=c)
    d.text((width // 2, 20), title, font=font(16, bold=True), fill="#94A3B8", anchor="mm")
    y = 46 + pad
    for i, line in enumerate(lines):
        if i in highlight:
            d.rectangle([8, y - 4, width - 8, y + lh - 6], fill="#4C1D1D")
        color = "#FCA5A5" if i in highlight else ("#86EFAC" if "PASSED" in line or "passed" in line else "#E2E8F0")
        d.text((pad, y), line, font=f, fill=color)
        y += lh
    im.save(path)


def checkout_screenshot(path):
    w, h = 1200, 720
    im = Image.new("RGB", (w, h), "#EEF2F7")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w, 44], fill="#E2E8F0")
    for i, c in enumerate(["#EF4444", "#F59E0B", "#22C55E"]):
        d.ellipse([16 + i * 26, 15, 30 + i * 26, 29], fill=c)
    d.rounded_rectangle([130, 8, w - 60, 36], radius=12, fill="#FFFFFF")
    d.text((150, 22), "https://staging.brightline-shop.example/checkout/payment", font=font(15), fill="#475569", anchor="lm")
    d.rectangle([0, 44, w, 100], fill="#0A1F44")
    d.text((40, 72), "BRIGHTLINE SHOP", font=font(24, bold=True), fill="#FFFFFF", anchor="lm")
    d.text((w - 40, 72), "Cart (2)   |   Account", font=font(16), fill="#C7D5EA", anchor="rm")
    d.rounded_rectangle([40, 130, 740, 660], radius=14, fill="#FFFFFF", outline="#D6DEE8")
    d.text((70, 165), "Payment", font=font(26, bold=True), fill="#0A1F44", anchor="lm")
    d.rounded_rectangle([70, 200, 710, 268], radius=8, fill="#FEF3C7", outline="#F59E0B")
    d.text((90, 234), "Gateway timeout. Please click Retry to complete your payment.", font=font(16), fill="#92400E", anchor="lm")
    d.text((70, 305), "Card ending 4242", font=font(18), fill="#1F2937", anchor="lm")
    d.text((70, 345), "Amount payable", font=font(16), fill="#526071", anchor="lm")
    d.text((710, 345), "Rs. 1,200.00", font=font(20, bold=True), fill="#1F2937", anchor="rm")
    d.rounded_rectangle([70, 400, 250, 452], radius=8, fill="#0A6ED1")
    d.text((160, 426), "Retry payment", font=font(17, bold=True), fill="#FFFFFF", anchor="mm")
    d.rounded_rectangle([70, 500, 710, 620], radius=10, fill="#FDE2E2", outline="#B42318")
    d.text((90, 535), "Order ORD-88213 shows status: PAID", font=font(18, bold=True), fill="#7F1D1D", anchor="lm")
    d.text((90, 575), "Payment log: 2 charges of Rs. 1,200.00 recorded (expected 1)", font=font(16), fill="#7F1D1D", anchor="lm")
    d.rounded_rectangle([780, 130, 1160, 400], radius=14, fill="#FFFFFF", outline="#D6DEE8")
    d.text((805, 165), "Order summary", font=font(20, bold=True), fill="#0A1F44", anchor="lm")
    for i, (a, b) in enumerate([("Notebook x2", "800.00"), ("Pen set x1", "400.00"), ("Delivery", "0.00")]):
        d.text((805, 215 + i * 40), a, font=font(16), fill="#475569", anchor="lm")
        d.text((1135, 215 + i * 40), b, font=font(16), fill="#1F2937", anchor="rm")
    d.line([805, 335, 1135, 335], fill="#D6DEE8")
    d.text((805, 365), "Total", font=font(18, bold=True), fill="#0A1F44", anchor="lm")
    d.text((1135, 365), "1,200.00", font=font(18, bold=True), fill="#0A1F44", anchor="rm")
    im.save(path)


# ---------------------------------------------------------------------------------------------------- 1. resume.pdf
def make_resume():
    W = A4[0] - 36 * mm
    story = [band("PRIYA SHARMA", "Lucknow, Uttar Pradesh  |  priya.sharma.qa@example.com  |  +91 98765 43210  |  github.com/priya-sharma-demo", W), Spacer(1, 8)]
    story += [P("SUMMARY", "h2"), P("Software tester with three years of experience in manual and regression testing of web applications. Returning to work after a four-year career break (2022-2026) for family caregiving. Recently refreshed my skills through Python practice and an online testing course.")]
    story += [P("EXPERIENCE", "h2"), P("<b>Junior Software Tester</b>, Brightline Softech Pvt Ltd (fictional), Noida &nbsp;&nbsp;<font color='#526071'>January 2019 to March 2022</font>")]
    story += bullets(["Tested the checkout, payments and order-history modules of an e-commerce web application.",
                      "Wrote and executed regression test cases for every fortnightly release.",
                      "Logged and tracked defects and verified fixes with developers.",
                      "Participated in daily stand-ups and sprint reviews in a Scrum team."])
    story += [P("SKILLS", "h2")]
    story += bullets(["Manual testing, regression testing, smoke testing",
                      "Test case design using boundary value analysis and equivalence partitioning",
                      "Defect reporting and tracking",
                      "Proficient in Selenium WebDriver automation",
                      "Basic SQL queries for test data validation",
                      "Python (beginner), Git and GitHub",
                      "MS Excel (pivot tables, conditional formatting)",
                      "Languages: Hindi (native), English (professional)"])
    story += [P("EDUCATION", "h2"), P("B.Sc. (Computer Science), 2018")]
    story += [P("CERTIFICATION", "h2"), P("Software Testing Fundamentals - online course, completed June 2026")]
    build(OUT / "resume.pdf", story, "Resume - Priya Sharma")


# ---------------------------------------------------------------------------------------------------- 2. test-cases.pdf
TEST_CASES = [
    ("001", "Add single item to cart", "Checkout", "Pass", ""), ("002", "Add multiple items to cart", "Checkout", "Pass", ""),
    ("003", "Update item quantity in cart", "Checkout", "Pass", ""), ("004", "Remove item from cart", "Checkout", "Pass", ""),
    ("005", "Proceed to checkout as logged-in user", "Checkout", "Pass", ""), ("006", "Guest checkout redirects to login", "Checkout", "Pass", ""),
    ("007", "Shipping address required fields", "Checkout", "Pass", ""), ("008", "PIN code format validation", "Checkout", "Pass", ""),
    ("009", "Select delivery slot", "Checkout", "Pass", ""), ("010", "Order summary totals match cart", "Checkout", "Pass", ""),
    ("011", "Coupon amount 0 rejected (boundary)", "Coupon", "Pass", ""), ("012", "Coupon amount 1 accepted (boundary)", "Coupon", "Pass", ""),
    ("013", "Coupon amount 499 accepted (boundary)", "Coupon", "Pass", ""), ("014", "Coupon amount 500 accepted (boundary)", "Coupon", "Pass", ""),
    ("015", "Coupon amount 501 rejected (boundary)", "Coupon", "Pass", ""), ("016", "Apply valid percentage coupon", "Coupon", "Pass", ""),
    ("017", "Apply expired coupon", "Coupon", "Pass", ""), ("018", "Payment retry after timeout", "Payment retry", "Fail", "BUG-231"),
    ("019", "Retry payment after card decline", "Payment retry", "Pass", ""), ("020", "Retry payment after network drop", "Payment retry", "Pass", ""),
    ("021", "Payment page reload keeps order intact", "Payment retry", "Pass", ""), ("022", "Card format: 16-digit Visa (partition)", "Payment retry", "Pass", ""),
    ("023", "Card format: 16-digit Mastercard (partition)", "Payment retry", "Pass", ""), ("024", "Card format: 15-digit Amex (partition)", "Payment retry", "Pass", ""),
    ("025", "Card format: 13-digit number rejected (partition)", "Payment retry", "Pass", ""), ("026", "Coupon stacking with a second coupon", "Coupon", "Fail", "BUG-236"),
    ("027", "Remove coupon restores total", "Coupon", "Pass", ""), ("028", "Coupon not applicable to sale items", "Coupon", "Pass", ""),
    ("029", "Coupon works in Firefox", "Coupon", "Pass", ""), ("030", "Checkout works in Firefox", "Checkout", "Pass", ""),
    ("031", "Checkout works in Chrome", "Checkout", "Pass", ""), ("032", "Payment success shows receipt", "Payment retry", "Pass", ""),
    ("033", "Double-click on Pay does not double charge", "Payment retry", "Pass", ""), ("034", "Session expiry during payment", "Payment retry", "Pass", ""),
    ("035", "Refund status shown for cancelled order", "Payment retry", "Pass", ""), ("036", "Cancel order before dispatch", "Checkout", "Pass", ""),
    ("037", "Order confirmation e-mail content", "Checkout", "Pass", ""), ("038", "Order confirmation total matches payment", "Checkout", "Pass", ""),
    ("039", "Order history date shown in IST format", "Checkout", "Fail", "BUG-244"), ("040", "Order confirmation print layout", "Checkout", "Pass", ""),
    ("041", "Invoice download after payment", "Payment retry", "Pass", ""), ("042", "Payment retry limit (3 attempts)", "Payment retry", "Pass", ""),
]
assert len(TEST_CASES) == 42 and sum(1 for t in TEST_CASES if t[3] == "Fail") == 3


def make_test_cases():
    W = A4[0] - 36 * mm
    story = [band("Regression Test Suite - Checkout Module", "Release 4.7  |  Prepared by: Priya Sharma  |  Reviewed by QA Lead", W), Spacer(1, 8)]
    story += [P("SCOPE", "h2"), P("Created and executed 42 regression test cases for the checkout, coupon and payment-retry flows across Chrome and Firefox.")]
    story += [P("TECHNIQUE", "h2"), P("Boundary value analysis was applied to coupon amounts (0, 1, 499, 500, 501) and equivalence partitioning to card-number formats.")]
    story += [P("RESULTS", "h2"), P("39 passed, 3 failed. All failures linked to defect IDs and retested after fixes.")]
    flows = ["Checkout", "Coupon", "Payment retry"]
    passed = [sum(1 for t in TEST_CASES if t[2] == f and t[3] == "Pass") for f in flows]
    failed = [sum(1 for t in TEST_CASES if t[2] == f and t[3] == "Fail") for f in flows]
    d = Drawing(W, 150)
    bc = VerticalBarChart()
    bc.x, bc.y, bc.width, bc.height = 40, 22, W - 150, 105
    bc.data = [passed, failed]
    bc.categoryAxis.categoryNames = flows
    bc.categoryAxis.labels.fontSize = 8
    bc.valueAxis.valueMin, bc.valueAxis.valueMax = 0, 20
    bc.valueAxis.valueStep = 5
    bc.valueAxis.labels.fontSize = 8
    bc.bars[0].fillColor, bc.bars[1].fillColor = GREEN, RED
    bc.barLabelFormat = "%d"
    bc.barLabels.fontSize = 8
    bc.barLabels.nudge = 7
    d.add(bc)
    d.add(String(40, 137, "Test results by flow (42 cases)", fontSize=9, fontName="Helvetica-Bold", fillColor=NAVY))
    lg = Legend()
    lg.x, lg.y, lg.fontSize, lg.alignment = W - 95, 110, 8, "right"
    lg.colorNamePairs = [(GREEN, "Passed (39)"), (RED, "Failed (3)")]
    d.add(lg)
    story += [d]
    story += [P("TEST CASE LOG", "h2")]
    rows = [[P("<b>ID</b>", "cell"), P("<b>Test case</b>", "cell"), P("<b>Flow</b>", "cell"), P("<b>Result</b>", "cell"), P("<b>Defect</b>", "cell")]]
    for tid, title, flow, res, bug in TEST_CASES:
        col = "#188038" if res == "Pass" else "#B42318"
        rows.append([P(f"TC-{tid}", "cell"), P(title, "cell"), P(flow, "cell"), P(f'<font color="{col}"><b>{res}</b></font>', "cell"), P(bug or "-", "cell")])
    t = Table(rows, colWidths=[16 * mm, 84 * mm, 30 * mm, 18 * mm, 22 * mm], repeatRows=1)
    style = [("BACKGROUND", (0, 0), (-1, 0), PALE), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    for i, r in enumerate(TEST_CASES, start=1):
        if r[3] == "Fail":
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FDF2F2")))
    t.setStyle(TableStyle(style))
    story += [t, PageBreak(), P("DETAILED TEST CASES", "h2")]
    detail = lambda tid, title, pre, steps, exp, res: KeepTogether([
        P(f"<b>TC-{tid}</b> &nbsp; {title}", "h3"),
        Table([[P("<b>Preconditions</b>", "cell"), P(pre, "cell")], [P("<b>Steps</b>", "cell"), P(steps, "cell")],
               [P("<b>Expected</b>", "cell"), P(exp, "cell")], [P("<b>Result</b>", "cell"), P(res, "cell")]],
              colWidths=[28 * mm, W - 28 * mm], style=TableStyle([("GRID", (0, 0), (-1, -1), 0.4, LINE), ("BACKGROUND", (0, 0), (0, -1), PALE), ("VALIGN", (0, 0), (-1, -1), "TOP")])),
        Spacer(1, 6)])
    story += [detail("017", "Apply expired coupon", "User logged in, cart value 1200", "1) open cart 2) enter coupon EXPIRED10 3) click Apply",
                     "Error message 'Coupon expired' and total unchanged", '<font color="#188038"><b>Pass</b></font>'),
              detail("018", "Payment retry after timeout", "User logged in, order placed, gateway timeout simulated", "1) place order 2) simulate gateway timeout 3) click Retry",
                     "Single charge, order status 'Paid'", '<font color="#B42318"><b>Fail</b></font> - duplicate charge, see BUG-231 (attachments in bug-reports.pdf)')]
    build(OUT / "test-cases.pdf", story, "Regression Test Suite - Checkout Module (Release 4.7)")


# ---------------------------------------------------------------------------------------------------- 3. bug-reports.pdf
def make_bug_reports():
    W = A4[0] - 36 * mm
    log = TMP / "attachment-a-log.png"
    ui = TMP / "attachment-b-ui.png"
    terminal_image(log, "payment-service.log (excerpt)", [
        "2022-02-08 11:42:07 INFO  payment-service order=ORD-88213 gateway=PAYX attempt=1 TIMEOUT",
        "2022-02-08 11:42:09 INFO  payment-service order=ORD-88213 user clicked Retry",
        "2022-02-08 11:42:10 INFO  gateway         charge created id=CH-1001 amount=1200.00 INR",
        "2022-02-08 11:42:11 INFO  gateway         charge created id=CH-1002 amount=1200.00 INR",
        "2022-02-08 11:42:11 ERROR payment-service duplicate charge: order=ORD-88213 charges=2",
    ], highlight=(3, 4))
    checkout_screenshot(ui)

    def card(bid, sev, prio, title, env, steps, expected, actual, history, extra=""):
        head = Table([[P(f"<b>{bid}</b>", "h3"), P(f"Severity: <b>{sev}</b> &nbsp;|&nbsp; Priority: <b>{prio}</b>", "body")]], colWidths=[28 * mm, W - 28 * mm])
        head.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE), ("BOX", (0, 0), (-1, -1), 0.5, LINE), ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
        return [head, P(f"<b>Title:</b> {title}"), P(f"<b>Environment:</b> {env}."), P("<b>Steps to reproduce:</b>")] + bullets(steps) + [
            P(f"<b>Expected:</b> {expected}. <b>Actual:</b> {actual}."), P(f"<b>Status history:</b> {history}."), P(extra) if extra else Spacer(1, 1), Spacer(1, 8)]

    story = [band("Defect Reports - Release 4.7", "Raised by: Priya Sharma  |  Brightline Softech (fictional)  |  Tracker export", W), Spacer(1, 8)]
    story += card("BUG-231", "Critical", "P1", "Duplicate charge when payment retry is clicked after gateway timeout", "Staging, Chrome 97, build 4.7.2",
                  ["Add item to cart", "Proceed to payment", "Simulate gateway timeout", "Click Retry"], "One charge", "Two charges recorded in the payment log",
                  "Open &rarr; In Progress &rarr; Fixed &rarr; Verified by tester on build 4.7.3",
                  "<b>Attachments:</b> Attachment A (payment log excerpt) and Attachment B (checkout screen at failure) on the following pages; screen recording kept in the tracker.")
    story += [rule(), Spacer(1, 6)]
    story += card("BUG-244", "Major", "P2", "Order history shows wrong date format for IST users", "Staging, Firefox 96, build 4.7.3",
                  ["Log in as a user with IST time zone", "Open Order history", "Compare displayed dates with order confirmation e-mails"],
                  "Dates shown as DD-MM-YYYY in IST", "Dates shown in the MM/DD/YYYY US format",
                  "Open &rarr; In Progress &rarr; Fixed &rarr; Closed",
                  "Steps to reproduce and root-cause notes written by the tester; verified the fix after deployment and closed the defect.")
    story += [P("<i>Root cause:</i> the date formatter used the browser locale instead of the account time zone setting. Fix verified on build 4.7.4 in Chrome and Firefox.", "small"),
              PageBreak(), P("ATTACHMENT A - Payment log excerpt (BUG-231)", "h2"), RLImage(str(log), width=W, height=W * 0.28),
              P("Lines 4 and 5 show the second charge created by the retry request.", "small"), Spacer(1, 12),
              P("ATTACHMENT B - Checkout screen at failure (BUG-231)", "h2"), RLImage(str(ui), width=W * 0.9, height=W * 0.9 * 0.6),
              P("The order shows PAID while the payment log records two charges.", "small")]
    build(OUT / "bug-reports.pdf", story, "Defect Reports - Release 4.7")


# ---------------------------------------------------------------------------------------------------- 4. python repo snapshot
STRING_UTILS = '''"""Small string helpers used in my testing practice exercises."""
import re

EMAIL_RE = re.compile(r"^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$")


def trim_all(value: str) -> str:
    """Trim the ends and collapse internal whitespace."""
    return " ".join(value.split())


def is_valid_email(value: str) -> bool:
    return bool(EMAIL_RE.match(value))


def mask_card(number: str) -> str:
    """Mask all but the last four digits of a card number."""
    digits = number.replace(" ", "")
    if len(digits) < 12:
        raise ValueError("card number too short")
    return "*" * (len(digits) - 4) + digits[-4:]
'''
TEST_STRING_UTILS = '''import pytest
from string_utils import is_valid_email, mask_card, trim_all


def test_trim_all_basic():
    assert trim_all("  hello   world ") == "hello world"


def test_trim_all_empty():
    assert trim_all("   ") == ""


def test_trim_all_tabs():
    assert trim_all("a\\t\\tb") == "a b"


@pytest.mark.parametrize("email", ["a@b.co", "first.last@mail.example", "x+tag@site.org"])
def test_valid_emails(email):
    assert is_valid_email(email)


@pytest.mark.parametrize("email", ["", "no-at-sign", "two@@signs.com"])
def test_invalid_emails(email):
    assert not is_valid_email(email)


def test_mask_card_keeps_last_four():
    assert mask_card("4111111111111111") == "************1111"


def test_mask_card_ignores_spaces():
    assert mask_card("4111 1111 1111 1111") == "************1111"


def test_mask_card_short_number_raises():
    with pytest.raises(ValueError):
        mask_card("1234")
'''
CSV_COMPARE = '''"""Compare expected and actual CSV outputs and print the mismatched rows."""
import csv
import sys


def load(path):
    with open(path, newline="") as fh:
        return list(csv.reader(fh))


def compare(expected_path, actual_path):
    expected, actual = load(expected_path), load(actual_path)
    mismatches = []
    for i in range(max(len(expected), len(actual))):
        e = expected[i] if i < len(expected) else None
        a = actual[i] if i < len(actual) else None
        if e != a:
            mismatches.append((i + 1, e, a))
    return mismatches


if __name__ == "__main__":
    for row, e, a in compare(sys.argv[1], sys.argv[2]):
        print(f"row {row}: expected={e} actual={a}")
'''
COMMITS = [("2026-06-14", "Initial commit: README and project layout"), ("2026-06-15", "Add trim_all helper"), ("2026-06-17", "Add email validation"),
           ("2026-06-20", "Add pytest and first tests"), ("2026-06-24", "Parametrize email tests"), ("2026-06-28", "Merge PR #1: feature/email-validation"),
           ("2026-07-03", "Add mask_card helper"), ("2026-07-05", "Test mask_card edge cases"), ("2026-07-11", "Merge PR #2: feature/card-masking"),
           ("2026-07-19", "Add csv_compare script"), ("2026-07-26", "Merge PR #3: feature/csv-compare"), ("2026-08-04", "Add tab and empty-string tests"),
           ("2026-08-12", "Update README with run instructions"), ("2026-08-21", "Merge PR #4: chore/readme")]


def make_repo():
    W = A4[0] - 36 * mm
    shot = TMP / "pytest-run.png"
    names = ["test_trim_all_basic", "test_trim_all_empty", "test_trim_all_tabs", "test_valid_emails[a@b.co]", "test_valid_emails[first.last@mail.example]",
             "test_valid_emails[x+tag@site.org]", "test_invalid_emails[]", "test_invalid_emails[no-at-sign]", "test_invalid_emails[two@@signs.com]",
             "test_mask_card_keeps_last_four", "test_mask_card_ignores_spaces", "test_mask_card_short_number_raises"]
    lines = ["$ pytest -v", "==================== test session starts ====================", "collected 12 items", ""]
    for i, n in enumerate(names, 1):
        lines.append(f"test_string_utils.py::{n} PASSED".ljust(78) + f"[{round(i / 12 * 100):3d}%]")
    lines += ["", "==================== 12 passed in 0.08s ===================="]
    terminal_image(shot, "Terminal - qa-python-practice", lines, width=1300)
    story = [band("qa-python-practice", "Public repository  |  14 commits  |  4 merged pull requests  |  last commit August 2026", W), Spacer(1, 8)]
    story += [P("README.md", "h2"), P("Practice project I built while returning to work. It contains small Python scripts and unit tests."), Spacer(1, 3)]
    story += bullets(["string_utils.py: functions for trimming, validating email formats and masking card numbers.",
                      "test_string_utils.py: 12 unit tests written with pytest, including parametrized tests for edge cases.",
                      "csv_compare.py: script that compares expected and actual CSV test outputs and prints mismatched rows."])
    story += [P("How to run: <font face='Courier'>pip install pytest</font>, then run <font face='Courier'>pytest -v</font>. Latest run: 12 passed in 0.08s."),
              P("Commit history shows feature branches merged through pull requests.")]
    story += [P("FILES", "h2"), Preformatted("qa-python-practice/\n  README.md\n  string_utils.py\n  test_string_utils.py\n  csv_compare.py", S["code"])]
    story += [P("TEST RUN", "h2"), RLImage(str(shot), width=W, height=W * shot_ratio(shot))]
    story += [PageBreak(), P("string_utils.py", "h2"), Preformatted(STRING_UTILS, S["code"]), Spacer(1, 8), P("test_string_utils.py", "h2"), Preformatted(TEST_STRING_UTILS, S["code"])]
    story += [PageBreak(), P("csv_compare.py", "h2"), Preformatted(CSV_COMPARE, S["code"]), Spacer(1, 8), P("COMMIT HISTORY", "h2")]
    rows = [[P("<b>Date</b>", "cell"), P("<b>Message</b>", "cell")]] + [[P(d, "cell"), P(m, "cell")] for d, m in reversed(COMMITS)]
    t = Table(rows, colWidths=[28 * mm, W - 28 * mm], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), PALE), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    story += [t]
    build(OUT / "python-practice-repo.pdf", story, "Repository snapshot - qa-python-practice")


def shot_ratio(path):
    with Image.open(path) as im:
        return im.height / im.width


# ---------------------------------------------------------------------------------------------------- 5. defect-tracker.xlsx
def make_tracker():
    rnd = random.Random(2022)
    modules = ["Checkout", "Coupons", "Payments", "Orders", "Profile"]
    sev_w = [("Critical", 8), ("Major", 32), ("Minor", 56), ("Trivial", 22)]
    sevs = [s for s, n in sev_w for _ in range(n)]
    rnd.shuffle(sevs)
    owners = ["Rohan", "Meera", "Kabir", "Ananya", "Vikram"]
    builds = ["4.5.1", "4.5.2", "4.6.0", "4.6.1", "4.6.2", "4.7.0", "4.7.2", "4.7.3", "4.8.0"]
    titles = {"Checkout": ["Total not updated after quantity change", "Delivery slot not saved", "PIN code accepts letters", "Address form loses data on error"],
              "Coupons": ["Expired coupon message missing", "Coupon stacking allowed", "Percentage coupon rounds wrongly", "Coupon field accepts spaces"],
              "Payments": ["Duplicate charge on retry after timeout", "Receipt shows wrong amount", "Card error message unclear", "Payment page reload loses order"],
              "Orders": ["Order history date format wrong for IST", "Cancelled order still shows Dispatch", "Invoice link returns 404", "Order e-mail missing GST line"],
              "Profile": ["Saved card not listed", "Password rule message unclear", "Address book duplicates entry", "Logout keeps cart badge"]}
    rows = []
    for i in range(118):
        m = rnd.choice(modules)
        status = rnd.choices(["Open", "In Progress", "Fixed", "Verified", "Closed"], weights=[10, 8, 22, 30, 30])[0]
        found = rnd.choice(builds[:-1])
        fixed = rnd.choice(builds[builds.index(found) + 1:]) if status in ("Fixed", "Verified", "Closed") else ""
        age = rnd.randint(1, 26) if status in ("Open", "In Progress") else rnd.randint(1, 12)
        rows.append([f"DEF-{1001 + i}", m, sevs[i], {"Critical": "P1", "Major": "P2", "Minor": "P3", "Trivial": "P4"}[sevs[i]], status, rnd.choice(owners), found, fixed, age, rnd.choice(titles[m])])
    wb = Workbook()
    ws = wb.active
    ws.title = "Defects"
    hdr = ["ID", "Module", "Severity", "Priority", "Status", "Owner", "Found in build", "Fixed in build", "Age (days)", "Title"]
    hfill, hfont = PatternFill("solid", fgColor="0A1F44"), Font(bold=True, color="FFFFFF")
    thin = Side(style="thin", color="D6DEE8")
    ws.append(hdr)
    for r in rows:
        ws.append(r)
    for c in ws[1]:
        c.fill, c.font, c.alignment = hfill, hfont, Alignment(horizontal="center", vertical="center")
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.border = Border(bottom=thin)
    for i, w in enumerate([11, 12, 10, 9, 12, 10, 14, 14, 11, 44], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:J{len(rows) + 1}"
    ws.conditional_formatting.add(f"I2:I{len(rows) + 1}", CellIsRule(operator="greaterThan", formula=["7"], fill=PatternFill("solid", bgColor="FDE2E2", fgColor="FDE2E2"), font=Font(color="B42318", bold=True)))
    sev_fill = {"Critical": "FDE2E2", "Major": "FEF3C7"}
    for row in ws.iter_rows(min_row=2, min_col=3, max_col=3):
        for c in row:
            if c.value in sev_fill:
                c.fill = PatternFill("solid", fgColor=sev_fill[c.value])

    dash = wb.create_sheet("Dashboard")
    openrows = [r for r in rows if r[4] in ("Open", "In Progress")]
    dash["A1"], dash["A1"].font = "Release defect dashboard - open defects (Open + In Progress)", Font(bold=True, size=14, color="0A1F44")
    dash["A2"], dash["A2"].font = "Summary tables built from the Defects sheet. Red cells on the Defects sheet mark defects older than 7 days.", Font(italic=True, color="526071")
    dash.append([])
    dash["A4"], dash["B4"] = "Severity", "Open defects"
    dash["D4"], dash["E4"] = "Module", "Open defects"
    dash["G4"], dash["H4"] = "Status", "All defects"
    sev_counts = [(s, sum(1 for r in openrows if r[2] == s)) for s in ["Critical", "Major", "Minor", "Trivial"]]
    mod_counts = [(m, sum(1 for r in openrows if r[1] == m)) for m in modules]
    st_counts = [(s, sum(1 for r in rows if r[4] == s)) for s in ["Open", "In Progress", "Fixed", "Verified", "Closed"]]
    for i, (k, v) in enumerate(sev_counts, 5):
        dash.cell(i, 1, k), dash.cell(i, 2, v)
    for i, (k, v) in enumerate(mod_counts, 5):
        dash.cell(i, 4, k), dash.cell(i, 5, v)
    for i, (k, v) in enumerate(st_counts, 5):
        dash.cell(i, 7, k), dash.cell(i, 8, v)
    for cell in ("A4", "B4", "D4", "E4", "G4", "H4"):
        dash[cell].fill, dash[cell].font = hfill, hfont
    dash.cell(10, 1, "Total open"), dash.cell(10, 2, len(openrows))
    dash.cell(10, 1).font = dash.cell(10, 2).font = Font(bold=True)
    dash.cell(11, 1, "Older than 7 days"), dash.cell(11, 2, sum(1 for r in openrows if r[8] > 7))
    for col, w in zip("ABCDEFGH", [20, 14, 4, 16, 14, 4, 16, 12]):
        dash.column_dimensions[col].width = w
    c1 = BarChart(); c1.type, c1.style, c1.title = "col", 10, "Open defects by severity"
    c1.add_data(Reference(dash, min_col=2, min_row=4, max_row=8), titles_from_data=True); c1.set_categories(Reference(dash, min_col=1, min_row=5, max_row=8))
    c1.y_axis.title, c1.legend, c1.height, c1.width = "Defects", None, 7.5, 12
    c2 = BarChart(); c2.type, c2.style, c2.title = "bar", 12, "Open defects by module"
    c2.add_data(Reference(dash, min_col=5, min_row=4, max_row=9), titles_from_data=True); c2.set_categories(Reference(dash, min_col=4, min_row=5, max_row=9))
    c2.legend, c2.height, c2.width = None, 7.5, 12
    c3 = PieChart(); c3.title = "All defects by status"
    c3.add_data(Reference(dash, min_col=8, min_row=4, max_row=9), titles_from_data=True); c3.set_categories(Reference(dash, min_col=7, min_row=5, max_row=9)); c3.height, c3.width = 7.5, 12
    dash.add_chart(c1, "A13"); dash.add_chart(c2, "F13"); dash.add_chart(c3, "A29")

    tr = wb.create_sheet("Triage notes")
    tr["A1"], tr["A1"].font = "Weekly triage decisions agreed with the developer team (maintained weekly by Priya Sharma, releases 4.5 to 4.8)", Font(bold=True, size=12, color="0A1F44")
    tr.append([])
    tr.append(["Week", "Date", "Decision", "Owner", "Agreed with"])
    notes = ["Freeze new coupon rules until BUG-236 is fixed", "Retest payment retry flow on every build", "Downgrade cosmetic profile defects to P4",
             "Add IST date check to the regression suite", "Block release 4.7 until BUG-231 is verified", "Close defects older than 30 days after retest",
             "Run smoke tests after each hotfix", "Review Firefox-only defects every Friday", "Move invoice defects to Orders backlog", "Confirm GST line fix with finance",
             "Add duplicate-charge alert to staging", "Release 4.8 scope agreed"]
    for i, n in enumerate(notes, 1):
        tr.append([f"W{i:02d}", f"2022-{1 + (i - 1) // 4:02d}-{[7, 14, 21, 28][(i - 1) % 4]:02d}", n, rnd.choice(owners), "Developer team"])
    for c in tr[3]:
        c.fill, c.font = hfill, hfont
    for col, w in zip("ABCDE", [8, 12, 58, 12, 18]):
        tr.column_dimensions[col].width = w
    wb.properties.creator, wb.properties.title = "Priya Sharma (fictional)", "Release_Defect_Tracker"
    wb.save(OUT / "defect-tracker.xlsx")


# ---------------------------------------------------------------------------------------------------- 6. certificate
def make_certificate():
    from reportlab.pdfgen import canvas
    w, h = landscape(A4)
    c = canvas.Canvas(str(OUT / "course-certificate.pdf"), pagesize=(w, h))
    c.setTitle("Certificate - Software Testing Fundamentals")
    c.setStrokeColor(NAVY); c.setLineWidth(3); c.rect(12 * mm, 12 * mm, w - 24 * mm, h - 24 * mm)
    c.setStrokeColor(TEAL); c.setLineWidth(1); c.rect(16 * mm, 16 * mm, w - 32 * mm, h - 32 * mm)
    c.setFillColor(NAVY); c.rect(16 * mm, h - 46 * mm, w - 32 * mm, 30 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 30); c.drawCentredString(w / 2, h - 34 * mm, "Certificate of Completion")
    c.setFont("Helvetica", 10); c.setFillColor(colors.HexColor("#C7D5EA")); c.drawCentredString(w / 2, h - 41 * mm, "OpenLearn Academy (fictional issuer)")
    c.setFillColor(MUTED); c.setFont("Helvetica", 12); c.drawCentredString(w / 2, h - 70 * mm, "This certifies that")
    c.setFillColor(NAVY); c.setFont("Helvetica-Bold", 30); c.drawCentredString(w / 2, h - 88 * mm, "Priya Sharma")
    style = ParagraphStyle("c", parent=S["body"], alignment=TA_CENTER, fontSize=12.5, leading=19)
    p = Paragraph("has completed the online course <b>'Software Testing Fundamentals'</b> (20 hours), covering test levels, test design techniques, defect life cycle and an introduction to test automation concepts.", style)
    pw, ph = p.wrap(w - 90 * mm, 60 * mm)
    p.drawOn(c, (w - pw) / 2, h - 100 * mm - ph)
    c.setFillColor(INK); c.setFont("Helvetica", 11)
    c.drawString(38 * mm, 52 * mm, "Issued by: OpenLearn Academy")
    c.drawString(38 * mm, 45 * mm, "Completed: June 2026")
    c.drawString(38 * mm, 38 * mm, "Certificate ID: OLA-STF-2026-0613")
    c.setStrokeColor(INK); c.setLineWidth(0.6); c.line(w - 100 * mm, 48 * mm, w - 38 * mm, 48 * mm)
    c.setFont("Helvetica-Oblique", 10); c.setFillColor(MUTED); c.drawCentredString(w - 69 * mm, 42 * mm, "Director, OpenLearn Academy")
    c.setFillColor(TEAL); c.circle(w / 2, 46 * mm, 13 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 9); c.drawCentredString(w / 2, 48 * mm, "COMPLETED"); c.drawCentredString(w / 2, 43 * mm, "2026")
    c.setFont("Helvetica", 7.5); c.setFillColor(MUTED)
    c.drawCentredString(w / 2, 22 * mm, "Note: issuer verification is not connected in this prototype. Fictional demo document created for EQUALPATH (SAP Hackfest 2026).")
    c.showPage(); c.save()


if __name__ == "__main__":
    make_resume(); make_test_cases(); make_bug_reports(); make_repo(); make_tracker(); make_certificate()
    for f in sorted(OUT.iterdir()):
        print(f"{f.name:32} {f.stat().st_size / 1024:7.1f} KB")
