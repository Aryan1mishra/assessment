# AI Resume Screening & Ranking System

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


```

The report contains `batch_summary`, `ranked_eligible_candidates`, and `rejected_candidates`. Each eligible candidate includes the score breakdown, matched skills, evidence snippets, project summary, strengths/concerns, and GitHub enrichment status. Failed files are recorded without aborting the batch.


## Scoring model

| Category | Maximum |
|---|---:|
| AI / agentic / RAG project depth | 40 |
| Python & backend engineering | 30 |
| Cloud / deployment / full stack | 15 |
| GitHub activity and relevant repositories | 10 |
| Engineering depth signals | 5 |
| **Total** | **100** |



## Deployed link

https://kasparroassessment.streamlit.app/
