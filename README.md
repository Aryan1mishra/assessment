# AI Resume Screening & Ranking System

A Python CLI that batch-processes PDF resumes (plus optional DOCX/TXT), applies explicit Python + AI eligibility gates, ranks eligible candidates out of 100, enriches public GitHub profiles where possible, and emits an auditable JSON report.

## Requirements

Python 3.10+ recommended.

```bash
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python main.py --input ./resumes --output ./output/results.json

# Offline/reproducible run without GitHub network calls
python main.py --input ./resumes --output ./output/results.json --skip-github
```

The report contains `batch_summary`, `ranked_eligible_candidates`, and `rejected_candidates`. Each eligible candidate includes the score breakdown, matched skills, evidence snippets, project summary, strengths/concerns, and GitHub enrichment status. Failed files are recorded without aborting the batch.

Optional GitHub token: copy `.env.example` to `.env` for reference and set `GITHUB_TOKEN` in your shell. The app does not automatically load `.env`; this avoids an extra dependency and keeps secret handling explicit. Public GitHub enrichment is best-effort, time-bounded, cached per username during the run, and never a hard eligibility gate.

## Scoring model

| Category | Maximum |
|---|---:|
| AI / agentic / RAG project depth | 40 |
| Python & backend engineering | 30 |
| Cloud / deployment / full stack | 15 |
| GitHub activity and relevant repositories | 10 |
| Engineering depth signals | 5 |
| **Total** | **100** |

The implementation uses deterministic keyword/evidence heuristics to keep the assignment runnable without a paid model/API key. It rewards multiple technical signals and implementation verbs, and applies a 10-point AI-depth penalty when AI appears to be a thin API wrapper without retrieval, agents, workflows, orchestration, evaluation, or tool calling. GitHub points are based on non-fork repositories pushed in the last 180 days and public Python/AI-relevant repositories, each capped at five points. API failures are recorded and do not interrupt screening.

Eligibility is checked before scoring: Python evidence and AI/LLM/RAG/agentic evidence must both exist. JavaScript/Java/React are not disqualifiers. The current eligibility and scoring approach is a transparent heuristic, not a semantic model; false positives/negatives are possible and evidence snippets are included to support human review.

## Design Decisions

- **Batch reliability:** each resume is parsed independently; a malformed or image-only PDF is recorded as failed rather than terminating the run.
- **Eligibility before ranking:** candidates missing Python or AI evidence are rejected and are not assigned a competitive score.
- **Explainability:** category-level points, matched skills, extracted evidence, strengths, concerns, and rejection reasons are output as JSON.
- **LLM strategy:** no LLM is required for the baseline. In a follow-up iteration, a provider adapter could return a validated Pydantic schema for project ownership/depth; deterministic hard filters should remain outside the model and model failures should fall back to this scorer.
- **GitHub strategy:** only public unauthenticated API endpoints are used by default. A `GITHUB_TOKEN` environment variable is optional. Results are cached by username for the duration of a batch, and enrichment errors never fail the resume pipeline.
- **Trade-offs:** rule-based extraction is cheap, repeatable, and easy to test within the 2–3 hour scope, but is less robust than semantic extraction for varied resume layouts and nuanced project quality.

## Tests

```bash
pytest -q
```

Tests cover GitHub URL extraction, eligibility signal distinction, and score caps. Add more synthetic resume fixtures before using this for real hiring decisions.

## If I Had More Time

1. Add OCR fallback for scanned PDFs and more robust section-aware resume parsing.
2. Add an optional structured LLM adapter with Pydantic validation and deterministic fallback.
3. Improve GitHub signals using recent public events/commit activity, pagination, and stronger repository relevance checks.
4. Expand tests with malformed files, duplicate content, edge-case eligibility, and calibrated score fixtures.

## Responsible use

This tool is decision support, not an automated hiring decision-maker. Resume parsing can miss context and the heuristic may reflect keyword density rather than ability. Review evidence manually and avoid using protected or sensitive personal attributes in scoring.

## Web app (deployment)

This repository also includes `app.py`, a Streamlit web interface. A recruiter can upload multiple PDF/DOCX/TXT files (or choose a folder in browsers that support directory selection), run screening, inspect ranked/rejected candidates, and download `results.json` and `results.txt`.

### Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Streamlit will print a local URL, usually `http://localhost:8501`.

### Deploy on Streamlit Community Cloud

1. Push this project to a GitHub repository. Include `app.py`, `main.py`, `requirements.txt`, and `README.md`; do not upload `.venv`, `.env`, private resumes, or generated candidate reports to a public repository.
2. Sign in to Streamlit Community Cloud and choose **Create app**.
3. Select the repository, branch, and `app.py` as the main file path.
4. Deploy. The platform will install dependencies from `requirements.txt` and provide a public app URL.
5. Test with synthetic/sample resumes first, including malformed and image-only PDFs, before handling real candidate data.

### Privacy and production considerations

- Uploaded files are written to a temporary directory and removed when processing finishes; do not assume hosting infrastructure or platform logs provide a legally sufficient privacy guarantee.
- Use private hosting and access controls for actual company hiring data. Confirm the company's data-processing, retention, and candidate-consent requirements before uploading resumes to a third-party host.
- Avoid storing reports in a public repository. Reports contain candidate names and evidence extracted from resumes.
- GitHub enrichment is off by default in the web UI to keep runs predictable. Enable it in the sidebar only when external API calls are acceptable.
- This prototype is not production-hardened. Before production, add authentication/authorization, request/file-size limits, rate limiting, audit logging, malware scanning, stronger parsing/OCR, and a retention policy. Do not make hiring decisions solely from heuristic scores.
