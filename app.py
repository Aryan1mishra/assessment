from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import streamlit as st

from main import screen_file, WEIGHTS

st.set_page_config(page_title="AI Resume Screening", page_icon="📄", layout="wide")

st.markdown("""
<style>
.block-container {max-width: 1180px; padding-top: 2rem; padding-bottom: 3rem;}
.hero {padding: 1.5rem 1.7rem; border: 1px solid #e5e7eb; border-radius: 16px; background: linear-gradient(120deg,#f8fafc,#eef5ff); margin-bottom: 1.2rem;}
.hero h1 {margin: 0 0 .35rem 0; font-size: 2rem; color: #0f172a;}
.hero p {margin: 0; color: #475569; font-size: 1rem;}
.metric-label {color:#64748b;font-size:.85rem;}
.candidate {border:1px solid #e2e8f0;border-radius:12px;padding:1rem 1.1rem;margin:.6rem 0;background:#fff;}
.small-note {font-size:.86rem;color:#64748b;}
</style>
<div class="hero">
  <h1>AI Resume Screening &amp; Ranking</h1>
  <p>Upload a batch of resumes, review evidence-based candidate rankings, and export a JSON or text report.</p>
</div>
""", unsafe_allow_html=True)

st.warning("Hiring decision support only: scores are heuristic, can miss context, and must be reviewed by a human. Upload resumes only if you are authorized to process them.")

with st.sidebar:
    st.header("Screening settings")
    enrich_github = st.checkbox("Enrich public GitHub profiles", value=False, help="Uses the public GitHub API. Can be slower and may be rate-limited. No token is required.")
    st.caption("Scoring weights")
    for category, points in WEIGHTS.items():
        st.write(f"**{points}/100** · {category.replace('_', ' ').title()}")
    st.divider()
    st.caption("Supported formats: PDF, DOCX, TXT. Scanned/image-only PDFs may need OCR.")

st.subheader("1. Upload resumes")
files_tab, folder_tab = st.tabs(["Choose files", "Choose a folder"])
with files_tab:
    uploaded_files = st.file_uploader(
        "Select one or more resume files",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        key="resume_files_upload",
        help="Select multiple PDFs, DOCX, or TXT files at once.",
    )
with folder_tab:
    folder_files = st.file_uploader(
        "Select a folder containing resumes (supported browsers)",
        type=["pdf", "docx", "txt"],
        accept_multiple_files="directory",
        key="resume_folder_upload",
        help="Folder selection depends on browser support. If unavailable, use the Choose files tab and select all resume files.",
    )
uploaded_files = uploaded_files or folder_files

if uploaded_files and folder_files:
    uploaded_files = uploaded_files + folder_files
    # Avoid accidentally processing the same selected file twice.
    seen = set()
    uploaded_files = [f for f in uploaded_files if not (f.name, f.size) in seen and not seen.add((f.name, f.size))]

if uploaded_files:
    st.success(f"{len(uploaded_files)} file(s) selected")
    with st.expander("Review selected files"):
        for f in uploaded_files:
            st.write(f" {f.name} · {f.size:,} bytes")

def make_text_report(result: dict) -> str:
    summary = result["batch_summary"]
    lines = [
        "AI RESUME SCREENING & RANKING REPORT",
        "=" * 42,
        f"Generated (UTC): {result['metadata'].get('generated_at_utc', 'N/A')}",
        "",
        "BATCH SUMMARY",
        "-" * 42,
        f"Total resumes:       {summary['total_resumes']}",
        f"Successfully parsed: {summary['successfully_parsed']}",
        f"Eligible:            {summary['eligible']}",
        f"Rejected:            {summary['rejected']}",
        f"Failed/unreadable:   {summary['failed_unreadable']}",
        "",
        "RANKED ELIGIBLE CANDIDATES",
        "=" * 42,
    ]
    eligible = result.get("ranked_eligible_candidates", [])
    if not eligible:
        lines.append("No candidates met the eligibility requirements.")
    for c in eligible:
        lines += [
            "",
            f"#{c.get('rank')}  {c.get('candidate_name', 'Unknown')} — {c.get('total_score', 0)}/100",
            f"Source file: {c.get('source_file', 'N/A')}",
            f"Project summary: {c.get('project_summary', 'N/A')}",
            "Score breakdown:",
        ]
        for key, score in c.get("score_breakdown", {}).items():
            lines.append(f"  - {key.replace('_', ' ').title()}: {score}")
        lines.append("Matched skills: " + (", ".join(c.get("matched_skills", [])) or "None extracted"))
        lines.append("Evidence:")
        lines.extend([f"  - {e}" for e in c.get("evidence", [])] or ["  - No evidence snippets extracted"])
        lines.append("Strengths:")
        lines.extend([f"  - {s}" for s in c.get("strengths", [])] or ["  - None recorded"])
        lines.append("Concerns:")
        lines.extend([f"  - {s}" for s in c.get("concerns", [])] or ["  - None recorded"])
        gh = c.get("github_enrichment", {})
        lines.append(f"GitHub: {c.get('github_url') or 'Not found'} ({gh.get('status', 'not checked')})")
        lines.append(f"GitHub details: {gh.get('summary', 'N/A')}")
    lines += ["", "REJECTED CANDIDATES", "=" * 42]
    rejected = result.get("rejected_candidates", [])
    if not rejected:
        lines.append("No rejected candidates.")
    for c in rejected:
        lines += [
            "",
            f"{c.get('candidate_name', 'Unknown')} — NOT ELIGIBLE",
            f"Source file: {c.get('source_file', 'N/A')}",
            "Reasons: " + ("; ".join(c.get("rejection_reasons", [])) or "Eligibility requirements not met"),
            "Evidence: " + (" | ".join(c.get("evidence", [])) or "No evidence extracted"),
        ]
        if c.get("error"):
            lines.append(f"Parsing error: {c['error']}")
    lines += ["", "IMPORTANT: This report is decision support, not an automated hiring decision. Review resumes and evidence manually.", ""]
    return "\n".join(lines)


run_clicked = st.button("Screen resumes", type="primary", disabled=not uploaded_files, use_container_width=False)

if run_clicked and uploaded_files:
    progress = st.progress(0, text="Preparing files…")
    status = st.empty()
    candidates = []
    github_cache = {}
    allowed = {".pdf", ".docx", ".txt"}
    try:
        with tempfile.TemporaryDirectory(prefix="resume_screening_") as temp:
            temp_path = Path(temp)
            valid_files = []
            for index, uploaded in enumerate(uploaded_files):
                original_name = Path(uploaded.name).name
                if Path(original_name).suffix.lower() not in allowed:
                    continue
                # Prefix to prevent duplicate filenames overwriting one another.
                target_dir = temp_path / f"upload_{index:04d}"
                target_dir.mkdir(parents=True, exist_ok=True)
                target = target_dir / original_name
                target.write_bytes(uploaded.getvalue())
                valid_files.append(target)
            if not valid_files:
                st.error("No supported PDF, DOCX, or TXT files were uploaded.")
                st.stop()
            for i, path in enumerate(valid_files, start=1):
                status.write(f"Screening {i} of {len(valid_files)}: {path.name}")
                candidates.append(screen_file(path, github_cache, enrich_github=enrich_github))
                progress.progress(i / len(valid_files), text=f"Processed {i} of {len(valid_files)}")

        eligible = [c for c in candidates if c.get("eligible")]
        eligible.sort(key=lambda c: (-c.get("total_score", 0), c.get("candidate_name", "").lower(), c.get("source_file", "")))
        for rank, candidate in enumerate(eligible, 1):
            candidate["rank"] = rank
        rejected = [c for c in candidates if not c.get("eligible")]
        rejected.sort(key=lambda c: c.get("source_file", ""))
        for candidate in rejected:
            candidate["rank"] = None
        parsed = sum(1 for c in candidates if c.get("parse_status") != "failed")
        result = {
            "metadata": {
                "system": "AI Resume Screening & Ranking System",
                "scoring_weights": WEIGHTS,
                "scoring_method": "Deterministic evidence-based heuristic; optional public GitHub API enrichment",
                "generated_at_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                "human_review_required": True,
            },
            "batch_summary": {
                "total_resumes": len(candidates),
                "successfully_parsed": parsed,
                "eligible": len(eligible),
                "rejected": len(rejected),
                "failed_unreadable": len(candidates) - parsed,
            },
            "ranked_eligible_candidates": eligible,
            "rejected_candidates": rejected,
        }
        st.session_state["screening_result"] = result
        st.session_state["screening_json"] = json.dumps(result, indent=2, ensure_ascii=False)
        st.session_state["screening_txt"] = make_text_report(result)
        status.empty()
        progress.empty()
        st.success("Screening completed. Review the results and download your reports below.")
    except Exception as exc:
        st.error(f"Screening could not be completed: {type(exc).__name__}: {exc}")




# Render report after a successful run; keeping it in session state allows separate downloads.
if "screening_result" in st.session_state:
    result = st.session_state["screening_result"]
    summary = result["batch_summary"]
    st.subheader("2. Screening summary")
    cols = st.columns(5)
    metric_items = [
        ("Total resumes", summary["total_resumes"]),
        ("Parsed", summary["successfully_parsed"]),
        ("Eligible", summary["eligible"]),
        ("Rejected", summary["rejected"]),
        ("Unreadable", summary["failed_unreadable"]),
    ]
    for col, (label, value) in zip(cols, metric_items):
        col.metric(label, value)

    st.subheader("3. Ranked eligible candidates")
    if result["ranked_eligible_candidates"]:
        for c in result["ranked_eligible_candidates"]:
            with st.expander(f"#{c['rank']} · {c['candidate_name']} · {c['total_score']}/100"):
                st.write(c.get("project_summary", "No project summary extracted."))
                breakdown = c.get("score_breakdown", {})
                st.write("**Score breakdown**")
                st.json(breakdown)
                st.write("**Matched skills**")
                st.write(", ".join(c.get("matched_skills", [])) or "None extracted")
                st.write("**Evidence**")
                for evidence in c.get("evidence", []):
                    st.markdown(f"- {evidence}")
                st.write("**Strengths**")
                for item in c.get("strengths", []): st.markdown(f"- {item}")
                st.write("**Concerns**")
                for item in c.get("concerns", []): st.markdown(f"- {item}")
                st.caption(f"GitHub: {c.get('github_url') or 'Not found'} · {c.get('github_enrichment', {}).get('status', 'not checked')}")
    else:
        st.info("No candidates met both hard eligibility requirements (Python and AI/LLM/RAG/agentic evidence).")

    with st.expander(f"Rejected candidates ({len(result['rejected_candidates'])})"):
        for c in result["rejected_candidates"]:
            st.markdown(f"**{c.get('candidate_name', 'Unknown')}** · `{c.get('source_file', '')}`")
            for reason in c.get("rejection_reasons", []): st.markdown(f"- {reason}")
            if c.get("error"): st.caption(c["error"])
            st.divider()

    st.subheader("4. Download reports")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("Download JSON report", data=st.session_state["screening_json"], file_name="results.json", mime="application/json", type="primary", use_container_width=True)
    with c2:
        st.download_button("Download TXT report", data=st.session_state["screening_txt"], file_name="results.txt", mime="text/plain; charset=utf-8", use_container_width=True)
    st.caption("Uploaded resume contents are processed in temporary storage for this run. Reports may contain candidate names and resume evidence; store and share them securely.")
