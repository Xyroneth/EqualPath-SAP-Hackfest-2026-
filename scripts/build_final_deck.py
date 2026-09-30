"""Apply the Round 2 presentation corrections to a copy of the team deck.

Usage: backend/.venv/bin/python scripts/build_final_deck.py [architecture.png]
Reads  EQUALPATH_SAP_Hackfest_2026.pptx (unchanged) and writes EQUALPATH_SAP_Hackfest_2026_Final.pptx.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "EQUALPATH_SAP_Hackfest_2026.pptx"
OUT = ROOT / "EQUALPATH_SAP_Hackfest_2026_Final.pptx"
ARCH = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "architecture-diagram.png"

prs = Presentation(SRC)


def shape(slide_no: int, shape_id: int):
    return next(s for s in prs.slides[slide_no - 1].shapes if s.shape_id == shape_id)


def set_text(slide_no: int, shape_id: int, *lines: str) -> None:
    """Replace the text of a single-paragraph shape, keeping its paragraph formatting."""
    p = shape(slide_no, shape_id).text_frame.paragraphs[0]._p
    for child in list(p):
        if child.tag in (qn("a:r"), qn("a:br"), qn("a:fld")):
            p.remove(child)
    end = p.find(qn("a:endParaRPr"))
    for i, line in enumerate(lines):
        if i:
            br = p.makeelement(qn("a:br"), {})
            p.insert(list(p).index(end), br) if end is not None else p.append(br)
        r = p.makeelement(qn("a:r"), {})
        t = r.makeelement(qn("a:t"), {})
        t.text = line
        r.append(t)
        p.insert(list(p).index(end), r) if end is not None else p.append(r)


def set_paragraphs(slide_no: int, shape_id: int, lines: list[str]) -> None:
    paras = shape(slide_no, shape_id).text_frame.paragraphs
    for para, line in zip(paras, lines):
        runs = para.runs
        runs[0].text = line
        for r in runs[1:]:
            r._r.getparent().remove(r._r)


def add_note(slide_no: int, left, top, width, height, text: str, size=9, color="475569", bold=False) -> None:
    tb = prs.slides[slide_no - 1].shapes.add_textbox(Emu(left), Emu(top), Emu(width), Emu(height))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, line in enumerate(text.split("\n")):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        run = para.add_run()
        run.text = line
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.name = "Aptos"
        run.font.color.rgb = RGBColor.from_string(color)


def set_notes(slide_no: int, text: str) -> None:
    prs.slides[slide_no - 1].notes_slide.notes_text_frame.text = text


# ---------------------------------------------------------------- Slide 4: evidence levels per passport section
set_text(4, 12, "Self-declared / source-supported / assessed")
set_text(4, 17, "Verified / developing / missing")
set_text(4, 22, "Candidate-controlled constraints")
set_text(4, 27, "Declared / document-verified / experience-validated")

# ---------------------------------------------------------------- Slide 5: six agents + one human layer
set_text(5, 8, "Six Specialized AI Agents and One Human Approval Layer")
set_text(5, 28, "\U0001F512  Human approval layer (not an AI agent)   —   Priya approves her profile • Counsellor / HR approve the outcome")
set_text(5, 41, "Human approval layer (accountable)")

# ---------------------------------------------------------------- Slide 6: flags and classifies, not certifies
set_text(6, 22, "“We do not lower standards. We remove accidental barriers that are not actual job requirements.”",
         "The agent flags and classifies evidence; it does not independently certify that an employer is inclusive.")
add_note(6, 457200, 5120640, 11274552, 400000,
         "Employer claims are graded: declared → document-verified → experience-validated (3+ consented reports); conflicts go to human review. "
         "Demo uses a seeded job description and simulated employer data.", size=9)

# ---------------------------------------------------------------- Slide 7: complete persona + two human pauses
set_text(7, 12, "Priya Sharma, 31, Lucknow (tier-2 city)  •  Former junior software tester (3 yrs)  •  Four-year caregiving break  •  "
                "Goal: stable tech role  •  Hybrid/remote, cannot relocate")
set_text(7, 21, "Manual testing, bug reports, Python", "⏸ Pause 1: Priya approves")
set_text(7, 36, "6 Human approval")
set_text(7, 37, "⏸ Pause 2: counsellor approves", "→ passport issued")
set_text(7, 38, "Pain points: dated-looking experience • career break penalised • informal learning not comparable • JDs hide work mode.   "
                "Behaviour: short evening learning sessions • bilingual explanations • approves anything shared.")
set_text(7, 39, "Result: Ready with Learning Milestone + Employer Action Required — not a promise of a job, a better and transparent decision.")

# ---------------------------------------------------------------- Slide 8: used in prototype vs enterprise roadmap
set_text(8, 8, "SAP in EQUALPATH: Used in the Prototype vs. Enterprise Roadmap")
set_text(8, 10, "SAP TECHNOLOGY")
set_text(8, 11, "✓ USED IN THE PROTOTYPE   ·   ◇ ENTERPRISE ROADMAP (not integrated)")
rows = [
    ("✓  SAP UI5 Web Components", "✓  Used: accessible Fiori-style UI for all 13 prototype screens"),
    ("✓  SAP Learning Hub (student ed.)", "✓  Used: curated catalog, deep links, milestones, evidence upload + human review (no progress-sync API)"),
    ("✓  SAP AI Core · SAP Build · SAP BTP", "✓  Adapters: gen AI hub provider, Build Process Automation approval, CF/MTA deploy — live when bound"),
    ("◇  Talent Intelligence Hub", "◇  Roadmap: map normalised skills to the SAP skills ontology"),
    ("◇  SuccessFactors · Joule", "◇  Roadmap: publish approved JDs; conversational recruiter access"),
    ("◇  People Intelligence / Data Cloud", "◇  Roadmap: privacy-protected fairness monitoring at scale"),
]
for (left_id, right_id), (l, r) in zip([(12, 13), (15, 16), (18, 19), (21, 22), (24, 25), (27, 28)], rows):
    set_text(8, left_id, l)
    set_text(8, right_id, r)
set_text(8, 29, "SAP identifies skills. EQUALPATH helps enterprises act on them — and the live demo states exactly which SAP services are connected.")

# ---------------------------------------------------------------- Backup slide: business model (copied from slide 9 before editing)
src = prs.slides[8]
backup = prs.slides.add_slide(prs.slide_layouts[6])
for el in list(backup.shapes._spTree):
    if el.tag in (qn("p:sp"), qn("p:pic"), qn("p:grpSp"), qn("p:graphicFrame"), qn("p:cxnSp")):
        backup.shapes._spTree.remove(el)
for el in src.shapes._spTree:
    if el.tag in (qn("p:sp"), qn("p:pic"), qn("p:grpSp"), qn("p:graphicFrame"), qn("p:cxnSp")):
        backup.shapes._spTree.append(copy.deepcopy(el))
bg = src._element.find(qn("p:cSld")).find(qn("p:bg"))
if bg is not None:
    backup._element.find(qn("p:cSld")).insert(0, copy.deepcopy(bg))
for s in list(backup.shapes):
    if s.shape_id in (9, 10, 11):  # functional-prototype box stays on slide 9
        s._element.getparent().remove(s._element)
for s in backup.shapes:
    if s.has_text_frame and s.text_frame.text.startswith("A Practical Final Prototype"):
        s.text_frame.paragraphs[0].runs[0].text = "Backup: Business Value and Revenue Model"
    if s.has_text_frame and s.text_frame.text.startswith("SAP Hackfest 2026  •  Slide 9"):
        s.text_frame.paragraphs[0].runs[0].text = "SAP Hackfest 2026  •  Backup"
    if s.has_text_frame and s.text_frame.text.startswith("Live demo:"):
        s.text_frame.paragraphs[0].runs[0].text = "Moved to backup to leave time for the live demo."
backup.notes_slide.notes_text_frame.text = "Backup for Q&A: value for candidates, employers, HR teams and universities; revenue from enterprise subscription, employer-readiness analytics and university/workforce partnerships."

# ---------------------------------------------------------------- Slide 9: present tense + architecture proof
set_text(9, 8, "The Live Prototype Demonstrates the Full Career Orchestrator")
set_text(9, 10, "⚙  WORKING TODAY")
set_paragraphs(9, 11, [
    "✓  Skills Discovery Agent: functional core (LLM + validator)",
    "✓  LangGraph orchestration of 6 agents, parallel steps",
    "✓  Two human interrupts; no passport before approval",
    "✓  SAP UI5 UI; SAP Learning Hub catalog; SAP AI Core provider",
    "✓  Employer JD scan + counterfactual bias audit",
    "✓  Mutual Readiness Passport (print / download)",
])
slide9 = prs.slides[8]
for s in list(slide9.shapes):
    if 12 <= s.shape_id <= 31:
        s._element.getparent().remove(s._element)
if ARCH.exists():
    area_left, area_top, area_w, area_h = 4297680, 1783080, 7434072, 3246120
    from PIL import Image  # noqa: WPS433 - optional, only for aspect ratio

    with Image.open(ARCH) as im:
        ratio = im.width / im.height
    w = min(area_w, int(area_h * ratio))
    h = int(w / ratio)
    pic = slide9.shapes.add_picture(str(ARCH), Emu(area_left + (area_w - w) // 2), Emu(area_top + (area_h - h) // 2), Emu(w), Emu(h))
    pic.line.color.rgb = RGBColor(0xD6, 0xDE, 0xE8)
    pic.line.width = Pt(0.75)
add_note(9, 4297680, 5080000, 7434072, 300000,
         "Screenshot of the prototype's Architecture screen. Deterministic demo mode is shown when no SAP AI Core key is bound.", size=8)

# ---------------------------------------------------------------- Speaker notes: ~5.5-6 min of slides + 4-4.5 min live demo
NOTES = {
    1: "(25 s) Good morning. We are Team Blitzkrieg and this is EQUALPATH, the Capability Confidence Engine for Inclusive Hiring. Many candidates are not rejected for lack of ability, but because employers lack fast, comparable, job-relevant evidence. EQUALPATH closes that confidence gap.",
    2: "(35 s) Recruiters cannot quickly verify non-traditional evidence, so they fall back on shortcuts like degree filters and gap penalties. Candidates cannot see whether a role's work mode, interviews or return-to-work support fit them. A hiring decision fails when either capability evidence or workplace readiness is missing.",
    3: "(30 s) We don't ask employers to take a chance. We give them evidence: an evidence-backed profile, job-relevant proof with a validation status, a check on the employer side too, and milestones instead of generic course lists. Together they form a Mutual Readiness Passport.",
    4: "(35 s) Four sections, each with an honest status. Capability evidence is self-declared, source-supported or assessed. The gap map is verified, developing or missing. Work conditions are candidate-controlled constraints. Employer claims are declared, document-verified or experience-validated. The decision is one of four outcomes.",
    5: "(45 s) Six specialised AI agents and one human approval layer. Skills Discovery builds evidence; Market Intelligence finds realistic roles; Learning Pathway builds evidence bridges; Inclusive Matching and Employer Readiness assess mutual fit; Bias Audit tests the outcome. Humans are not an agent: Priya approves what is said about her, and a counsellor or HR reviewer owns the decision.",
    6: "(40 s) Our differentiator: we also optimise the role for capable candidates. The Employer Readiness Agent flags degree filters, uninterrupted-experience rules, vague wording and missing work-mode or accommodation information. It flags and classifies evidence; it does not certify an employer as inclusive. Conflicting claims go to a human, and every rewrite needs HR approval.",
    7: "(40 s) Priya is 31 and lives in Lucknow, a tier-2 city. She was a tester for three years, then took four years off for caregiving. She wants a stable tech role, can't relocate, learns in short evening sessions, and wants to approve anything that is shared. EQUALPATH finds her real evidence and pauses for her approval. It maps her to QA Automation with three milestones, flags the employer's uninterrupted-experience rule and missing hybrid policy, and pauses again for a counsellor before the passport is issued.",
    8: "(35 s) We separate what is used from what is roadmap. The prototype uses SAP UI5 Web Components and a curated SAP Learning Hub student-edition catalog with deep links and evidence upload. It also ships adapters for the SAP AI Core generative AI hub, SAP Build Process Automation and SAP BTP, which are live when credentials are bound. SuccessFactors, Talent Intelligence Hub, Joule and Data Cloud are roadmap items; the demo does not call them.",
    9: "(35 s) The live prototype demonstrates it end to end. The Skills Discovery Agent is our functional core: it calls an LLM, validates the schema, and checks every quote against the source. LangGraph orchestrates six agents with two human interrupts, and the passport is blocked until approval. The architecture screen shows which SAP service is active. Let's see it live. [Switch to demo: 4 to 4.5 minutes, see DEMO_SCRIPT.md]",
    10: "(15 s) Potential should not be rejected because it is unfamiliar, and employers should not hire blindly. EQUALPATH creates a better decision for both sides. Thank you. We welcome your questions. [Total: about 5.5 min of slides plus a 4 to 4.5 min demo. Keep the prerecorded fallback video ready.]",
}
for n, text in NOTES.items():
    set_notes(n, text)

prs.save(OUT)
print(f"wrote {OUT}")
