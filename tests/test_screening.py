from main import score_candidate, extract_github, unique_terms

def test_github_url_extraction():
    url, username = extract_github('GitHub: https://github.com/octocat')
    assert url == 'https://github.com/octocat'
    assert username == 'octocat'

def test_python_only_does_not_imply_ai():
    text = 'Python developer built a Django backend and PostgreSQL API.'
    assert unique_terms(text, ['python']) == ['python']
    assert unique_terms(text, ['langchain', 'rag', 'llm']) == []

def test_score_caps_and_breakdown():
    text = ('Built a stateful RAG pipeline with LangGraph agent orchestration, embeddings, vector search, '
            'FastAPI async backend, PostgreSQL, Redis, Docker, GCP, unit testing, caching and retries.')
    breakdown, strengths, concerns, summary, ai = score_candidate(text, 12)
    assert breakdown['github'] == 10
    assert breakdown['ai_project_depth'] <= 40
    assert breakdown['python_backend'] <= 30
    assert sum(breakdown.values()) <= 100
