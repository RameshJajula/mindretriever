from pathlib import Path

from fastapi.testclient import TestClient

from graphmind.api import app


def test_health() -> None:
    client = TestClient(app)
    res = client.get('/health')
    assert res.status_code == 200
    assert res.json()['status'] == 'ok'


def test_upload_and_run(tmp_path: Path) -> None:
    client = TestClient(app)

    md_path = tmp_path / 'notes.md'
    md_path.write_text('# Intro\n\n## Goals\n', encoding='utf-8')

    with md_path.open('rb') as f:
        upload = client.post(
            '/api/upload',
            files=[('files', ('notes.md', f.read(), 'text/markdown'))],
        )
    assert upload.status_code == 200
    up = upload.json()
    assert len(up['files_saved']) == 1

    py_file = tmp_path / 'app.py'
    py_file.write_text('def ping():\n    return 1\n', encoding='utf-8')

    run = client.post('/api/run', json={'path': str(tmp_path), 'full': True})
    assert run.status_code == 200
    payload = run.json()
    assert payload['run_id'] > 0
    assert payload['files'] >= 1

    runs = client.get('/api/runs')
    assert runs.status_code == 200
    assert len(runs.json()) >= 1

    graph = client.get(f"/api/runs/{payload['run_id']}/graph")
    assert graph.status_code == 200
    graph_payload = graph.json()
    assert graph_payload['nodes'] >= 1


def test_upload_single_file_field_alias(tmp_path: Path) -> None:
    client = TestClient(app)

    md_path = tmp_path / 'single.md'
    md_path.write_text('# Single Upload\n', encoding='utf-8')

    with md_path.open('rb') as f:
        upload = client.post(
            '/api/upload',
            files=[('file', ('single.md', f.read(), 'text/markdown'))],
        )

    assert upload.status_code == 200
    payload = upload.json()
    assert len(payload['files_saved']) == 1


def test_upload_rejects_unsupported_extension(tmp_path: Path) -> None:
    client = TestClient(app)

    pdf_path = tmp_path / 'paper.pdf'
    pdf_path.write_bytes(b'%PDF-1.4')

    with pdf_path.open('rb') as f:
        upload = client.post(
            '/api/upload',
            files=[('files', ('paper.pdf', f.read(), 'application/pdf'))],
        )

    assert upload.status_code == 400
    assert 'Allowed: .md, .docx, .sql' in upload.json()['detail']
