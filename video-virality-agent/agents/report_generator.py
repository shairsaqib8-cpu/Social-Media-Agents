"""
DOCX report generator for the Video Virality Analyzer.
Produces a formatted Word document suitable for sharing with a content creation team.
"""

import io
from datetime import datetime
from docx import Document
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


# ── Color palette ──────────────────────────────────────────────────────────────
C_PURPLE  = RGBColor(108, 99, 255)
C_RED     = RGBColor(255, 71, 87)
C_GREEN   = RGBColor(67, 233, 123)
C_YELLOW  = RGBColor(249, 202, 36)
C_CYAN    = RGBColor(0, 206, 201)
C_DARK    = RGBColor(30, 30, 46)
C_MUTED   = RGBColor(140, 140, 160)
C_WHITE   = RGBColor(255, 255, 255)


def _set_cell_bg(cell, hex_color: str):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_color)
    tcPr.append(shd)


def _grade_color(score: int) -> RGBColor:
    if score >= 70: return C_GREEN
    if score >= 50: return C_YELLOW
    if score >= 35: return RGBColor(255, 150, 0)
    return C_RED


def _add_heading(doc: Document, text: str, level: int = 1):
    p = doc.add_heading(text, level=level)
    run = p.runs[0] if p.runs else p.add_run(text)
    if level == 1:
        run.font.color.rgb = C_PURPLE
        run.font.size = Pt(16)
    elif level == 2:
        run.font.color.rgb = C_CYAN
        run.font.size = Pt(13)
    else:
        run.font.color.rgb = C_MUTED
        run.font.size = Pt(11)
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(4)
    return p


def _add_bullet(doc: Document, text: str, color: RGBColor = None, prefix: str = "•"):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.3)
    p.paragraph_format.space_after = Pt(3)
    run = p.add_run(f"{prefix}  {text}")
    run.font.size = Pt(10)
    if color:
        run.font.color.rgb = color


def _add_info_row(doc: Document, label: str, value: str, value_color: RGBColor = None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    lbl = p.add_run(f"{label}: ")
    lbl.bold = True
    lbl.font.size = Pt(10)
    lbl.font.color.rgb = C_MUTED
    val = p.add_run(str(value))
    val.font.size = Pt(10)
    if value_color:
        val.font.color.rgb = value_color


def _score_bar_table(doc: Document, breakdown: dict):
    """Render score breakdown as a simple table."""
    labels = {
        "hook_strength":      "Hook Strength",
        "visual_quality":     "Visual Quality",
        "title_power":        "Title Power",
        "seo_strength":       "SEO Strength",
        "engagement_signals": "Engagement",
        "pacing":             "Edit Pacing",
        "content_depth":      "Content Depth",
    }
    rows = [(labels.get(k, k.replace("_"," ").title()), v)
            for k, v in breakdown.items() if isinstance(v, (int, float))]
    if not rows:
        return

    table = doc.add_table(rows=1 + len(rows), cols=3)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.LEFT

    # Header
    hdr = table.rows[0].cells
    for cell, txt in zip(hdr, ["Metric", "Score", "Rating"]):
        cell.text = txt
        cell.paragraphs[0].runs[0].bold = True
        cell.paragraphs[0].runs[0].font.size = Pt(9)
        _set_cell_bg(cell, "1E1E2E")
        cell.paragraphs[0].runs[0].font.color.rgb = C_WHITE

    for i, (label, score) in enumerate(rows):
        row = table.rows[i + 1].cells
        row[0].text = label
        row[0].paragraphs[0].runs[0].font.size = Pt(9)
        row[1].text = f"{score}/100"
        row[1].paragraphs[0].runs[0].font.size = Pt(9)
        row[1].paragraphs[0].runs[0].bold = True
        row[1].paragraphs[0].runs[0].font.color.rgb = _grade_color(int(score))
        grade = ("Excellent" if score >= 70 else "Average" if score >= 50
                 else "Weak" if score >= 35 else "Poor")
        row[2].text = grade
        row[2].paragraphs[0].runs[0].font.size = Pt(9)
        row[2].paragraphs[0].runs[0].font.color.rgb = _grade_color(int(score))

    doc.add_paragraph()


def generate_report(data: dict, mode: str = "url") -> bytes:
    """
    Generate a formatted DOCX report.
    mode: 'url' | 'upload' | 'thumbnail' | 'full'
    Returns bytes of the .docx file.
    """
    doc = Document()

    # ── Page margins ──
    for section in doc.sections:
        section.top_margin    = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin   = Cm(2.5)
        section.right_margin  = Cm(2.5)

    # ── Default font ──
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10)

    meta      = data.get("metadata", {})
    ca        = data.get("content_analysis") or data.get("video_analysis") or {}
    ta        = data.get("thumbnail_analysis", {})
    comp      = data.get("competitor_analysis", {})
    comps     = data.get("competitors", [])

    # For video upload the result IS the top-level dict
    if not ca and data.get("virality_score") is not None:
        ca = data

    score = ca.get("virality_score") or ta.get("score") or 0
    grade = ca.get("grade") or ta.get("grade") or "F"
    title = meta.get("title") or "Uploaded Video"

    # ════════════════════════════════════════════════════════════
    # COVER
    # ════════════════════════════════════════════════════════════
    cover = doc.add_paragraph()
    cover.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = cover.add_run("VIDEO VIRALITY ANALYSIS REPORT")
    r.bold = True
    r.font.size = Pt(22)
    r.font.color.rgb = C_PURPLE

    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run(title).font.size = Pt(14)

    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = p2.add_run(f"Virality Score:  {score}/100  |  Grade {grade}")
    r2.bold = True
    r2.font.size = Pt(13)
    r2.font.color.rgb = _grade_color(int(score))

    p3 = doc.add_paragraph()
    p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p3.add_run(f"Report generated: {datetime.now().strftime('%B %d, %Y  %H:%M')}").font.color.rgb = C_MUTED

    doc.add_page_break()

    # ════════════════════════════════════════════════════════════
    # 1. EXECUTIVE SUMMARY
    # ════════════════════════════════════════════════════════════
    _add_heading(doc, "1. Executive Summary")

    if meta:
        _add_info_row(doc, "Channel",   meta.get("channel", "—"))
        _add_info_row(doc, "Views",     f"{meta.get('view_count',0):,}")
        _add_info_row(doc, "Likes",     f"{meta.get('like_count',0):,}")
        _add_info_row(doc, "Comments",  f"{meta.get('comment_count',0):,}")
        doc.add_paragraph()

    if ca.get("performance_verdict"):
        p = doc.add_paragraph()
        p.add_run("Performance Verdict: ").bold = True
        p.add_run(ca["performance_verdict"]).font.color.rgb = C_RED

    if ca.get("biggest_mistake"):
        p = doc.add_paragraph()
        p.add_run("Biggest Mistake: ").bold = True
        r = p.add_run(ca["biggest_mistake"])
        r.font.color.rgb = C_RED
        r.bold = True

    if ca.get("first_impression"):
        p = doc.add_paragraph()
        p.add_run("First Impression (0-3s): ").bold = True
        p.add_run(ca["first_impression"])

    if ca.get("viral_potential"):
        p = doc.add_paragraph()
        p.add_run("Viral Potential: ").bold = True
        vp = ca["viral_potential"]
        color = C_GREEN if "high" in vp.lower() else C_YELLOW if "medium" in vp.lower() else C_RED
        p.add_run(vp).font.color.rgb = color

    if ca.get("if_reshot_today") or ca.get("estimated_improvement"):
        p = doc.add_paragraph()
        p.add_run("If Fixed Today: ").bold = True
        p.add_run(ca.get("if_reshot_today") or ca.get("estimated_improvement", ""))

    # ════════════════════════════════════════════════════════════
    # 2. SCORE BREAKDOWN
    # ════════════════════════════════════════════════════════════
    _add_heading(doc, "2. Score Breakdown")
    if ca.get("breakdown"):
        _score_bar_table(doc, ca["breakdown"])

    # Video stats
    vs = ca.get("video_stats")
    if vs:
        _add_heading(doc, "Video Technical Stats", level=2)
        _add_info_row(doc, "Duration",        f"{vs.get('duration_sec','?')}s")
        _add_info_row(doc, "Frames analyzed", vs.get("frames_analyzed", "?"))
        _add_info_row(doc, "Scene cuts",      vs.get("scene_cuts", "?"))
        _add_info_row(doc, "Cuts per minute", vs.get("cuts_per_min", "?"))
        _add_info_row(doc, "A/V Sync",        vs.get("av_sync", "?"))
        if vs.get("high_risk_moments"):
            _add_bullet(doc, "Drop-off risk: " + ", ".join(vs["high_risk_moments"]), C_RED, "⚠")

    # ════════════════════════════════════════════════════════════
    # 3. FRAME-BY-FRAME WATCH REPORT
    # ════════════════════════════════════════════════════════════
    vwr = ca.get("video_watch_report")
    if vwr:
        _add_heading(doc, "3. Frame-by-Frame Watch Report")
        _add_info_row(doc, "A/V Sync Overall", vwr.get("av_sync_verdict", "—"))
        _add_info_row(doc, "Edit Pacing",      vwr.get("edit_pacing_verdict", "—"))
        if vwr.get("retention_curve"):
            p = doc.add_paragraph()
            p.add_run("Retention Curve Forecast: ").bold = True
            p.add_run(vwr["retention_curve"]).font.color.rgb = C_YELLOW
        if vwr.get("segment_verdicts"):
            _add_heading(doc, "Segment Issues", level=2)
            for sv in vwr["segment_verdicts"]:
                _add_bullet(doc, f"[{sv.get('label','?')}] {sv.get('problem','')}", C_RED, "🔴")

    # ════════════════════════════════════════════════════════════
    # 4. HOOK ANALYSIS
    # ════════════════════════════════════════════════════════════
    ha = ca.get("hook_analysis", {})
    if ha:
        _add_heading(doc, "4. Hook Analysis")
        if ha.get("verdict"):
            _add_bullet(doc, ha["verdict"], C_RED, "❌")
        if ha.get("what_top_creators_do_instead") or ha.get("what_creator_actually_said"):
            _add_heading(doc, "What Top Creators Do Instead", level=2)
            _add_bullet(doc, ha.get("what_top_creators_do_instead",""), C_CYAN, "✅")
        if ha.get("rewritten_opening") or ha.get("rewritten_hook"):
            _add_heading(doc, "Rewritten Hook Script", level=2)
            rw = ha.get("rewritten_opening") or ha.get("rewritten_hook","")
            p = doc.add_paragraph(rw)
            p.paragraph_format.left_indent = Inches(0.3)
            p.runs[0].font.color.rgb = C_GREEN
            p.runs[0].italic = True
        if ha.get("why_viewers_left"):
            _add_bullet(doc, "Why viewers left: " + ha["why_viewers_left"], C_RED, "📉")

    # ════════════════════════════════════════════════════════════
    # 5. AUDIO ANALYSIS
    # ════════════════════════════════════════════════════════════
    aa = ca.get("audio_analysis", {})
    if aa:
        _add_heading(doc, "5. Audio Analysis")
        for key, label, color in [
            ("verdict",             "Overall Verdict",      C_RED),
            ("transcript_summary",  "What Was Said",        None),
            ("filler_word_problem", "Filler Word Problem",  C_YELLOW),
            ("pacing_verdict",      "Pacing",               C_CYAN),
            ("audio_visual_sync",   "A/V Sync",             C_YELLOW),
            ("script_quality",      "Script Quality",       C_MUTED),
        ]:
            if aa.get(key):
                _add_info_row(doc, label, aa[key], color)

    # ════════════════════════════════════════════════════════════
    # 6. TITLE & SEO ANALYSIS
    # ════════════════════════════════════════════════════════════
    title_a = ca.get("title_analysis", {})
    seo_a   = ca.get("seo_analysis", {})
    if title_a or seo_a:
        _add_heading(doc, "6. Title & SEO Analysis")
        if title_a.get("verdict"):
            _add_info_row(doc, "Title Verdict", title_a["verdict"], C_RED)
        if title_a.get("issues"):
            _add_heading(doc, "Title Issues", level=2)
            for i in title_a["issues"]:
                _add_bullet(doc, i, C_RED, "⚠")
        if title_a.get("alternative_titles"):
            _add_heading(doc, "Alternative Titles to Test", level=2)
            for t in title_a["alternative_titles"]:
                _add_bullet(doc, t, C_GREEN, "✅")
        if seo_a.get("suggested_tags"):
            _add_heading(doc, "Suggested Tags", level=2)
            _add_bullet(doc, "  ".join(f"#{t}" for t in seo_a["suggested_tags"]), C_CYAN, "🏷")
        if seo_a.get("description_rewrite"):
            _add_heading(doc, "Description Rewrite", level=2)
            p = doc.add_paragraph(seo_a["description_rewrite"])
            p.runs[0].italic = True
            p.runs[0].font.color.rgb = C_GREEN

    # ════════════════════════════════════════════════════════════
    # 7. PRODUCTION SCRIPT NOTES
    # ════════════════════════════════════════════════════════════
    psn = ca.get("production_script_notes", [])
    if psn:
        _add_heading(doc, "7. Production Script Notes")
        doc.add_paragraph("Hand these directly to your scriptwriter and video editor:").runs[0].font.color.rgb = C_MUTED
        for note in psn:
            _add_bullet(doc, note, C_CYAN, "📝")

    # ════════════════════════════════════════════════════════════
    # 8. OPTIMIZATION ROADMAP
    # ════════════════════════════════════════════════════════════
    tips = ca.get("optimization_tips", [])
    if tips:
        _add_heading(doc, "8. Optimization Roadmap")
        doc.add_paragraph("Priority order — fix these before re-uploading:").runs[0].font.color.rgb = C_MUTED
        doc.add_paragraph()
        for i, tip in enumerate(tips, 1):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.2)
            p.paragraph_format.space_after = Pt(6)
            lbl = p.add_run(f"  {i}.  ")
            lbl.bold = True
            lbl.font.color.rgb = C_PURPLE
            lbl.font.size = Pt(11)
            body = p.add_run(tip)
            body.font.size = Pt(10)
        doc.add_paragraph()

    # ════════════════════════════════════════════════════════════
    # 9. THUMBNAIL ANALYSIS
    # ════════════════════════════════════════════════════════════
    if ta:
        _add_heading(doc, "9. Thumbnail Analysis")
        _add_info_row(doc, "Thumbnail Score",  f"{ta.get('score','?')}/72", _grade_color(int(ta.get('score',0))))
        _add_info_row(doc, "CTR Potential",    ta.get("ctr_potential","?"))
        _add_info_row(doc, "CTR Verdict",      ta.get("ctr_verdict",""))
        if ta.get("weaknesses"):
            _add_heading(doc, "Weaknesses", level=2)
            for w in ta["weaknesses"]:
                _add_bullet(doc, w, C_RED, "❌")
        if ta.get("improvements"):
            _add_heading(doc, "Thumbnail Fixes", level=2)
            for w in ta["improvements"]:
                _add_bullet(doc, w, C_GREEN, "✅")

    # ════════════════════════════════════════════════════════════
    # 10. COMPETITOR ANALYSIS
    # ════════════════════════════════════════════════════════════
    if comp and comp.get("summary"):
        _add_heading(doc, "10. Competitor Analysis")
        _add_info_row(doc, "Head-to-Head Verdict", comp.get("head_to_head_verdict",""))
        if comp.get("summary"):
            doc.add_paragraph(comp["summary"])
        if comp.get("what_competitors_do_better"):
            _add_heading(doc, "What Competitors Do Better", level=2)
            for c in comp["what_competitors_do_better"]:
                _add_bullet(doc, c, C_RED, "⚠")
        if comp.get("gaps_to_exploit"):
            _add_heading(doc, "Gaps to Exploit", level=2)
            for g in comp["gaps_to_exploit"]:
                _add_bullet(doc, g, C_GREEN, "🎯")
        if comp.get("positioning_advice"):
            _add_heading(doc, "Positioning Strategy", level=2)
            p = doc.add_paragraph(comp["positioning_advice"])
            p.runs[0].font.color.rgb = C_CYAN

    if comps:
        _add_heading(doc, "Top Competing Videos", level=2)
        for i, c in enumerate(comps, 1):
            _add_bullet(doc, f"{c.get('title','')} — {c.get('channel','')}", None, f"{i}.")

    # ════════════════════════════════════════════════════════════
    # FOOTER NOTE
    # ════════════════════════════════════════════════════════════
    doc.add_page_break()
    footer = doc.add_paragraph()
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = footer.add_run("Generated by Video Virality Analyzer · AI-powered content audit · " + datetime.now().strftime("%Y"))
    r.font.color.rgb = C_MUTED
    r.font.size = Pt(8)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()
