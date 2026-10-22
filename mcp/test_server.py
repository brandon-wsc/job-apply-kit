"""Tests for mcp/server.py — no live Dify needed; HTTP goes through MockTransport."""

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent))

import server

EXAMPLE_SSOT = json.loads(
    (Path(__file__).parent.parent / "examples" / "ssot.example.json").read_text()
)


@pytest.fixture()
def cfg_env(tmp_path, monkeypatch):
    ssot = tmp_path / "ssot.json"
    ssot.write_text(json.dumps(EXAMPLE_SSOT))
    monkeypatch.setenv("SSOT_PATH", str(ssot))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("DIFY_BASE_URL", "http://dify.test/v1")
    monkeypatch.setenv("DIFY_API_KEY", "app-test")
    return tmp_path


def _mock_client(payloads, handler=None):
    def _handler(request):
        payloads.append(json.loads(request.content))
        if handler:
            return handler(request)
        return httpx.Response(
            200,
            json={
                "workflow_run_id": "run-1",
                "data": {
                    "id": "run-1",
                    "status": "succeeded",
                    "elapsed_time": 12.3,
                    "outputs": {
                        "cv_md": "# CV\nAlex Demo <alex.demo@example.com>",
                        "cover_letter_md": "Dear hiring team…",
                        "interview_prep_md": None,
                    },
                },
            },
        )

    return httpx.Client(
        transport=httpx.MockTransport(_handler), base_url="http://dify.test/v1"
    )


def test_check_ssot_ok(cfg_env):
    result = server.check_ssot()
    assert result["ok"]
    assert result["sections"]["experience"] == "2 entries"
    assert result["sections"]["identity"] == "present"
    assert "alex.demo@example.com" not in json.dumps(result)


def test_check_ssot_missing_file(tmp_path, monkeypatch):
    monkeypatch.setenv("SSOT_PATH", str(tmp_path / "nope.json"))
    result = server.check_ssot()
    assert not result["ok"]
    assert result["warnings"]


def test_check_ssot_warns_without_pii(tmp_path, monkeypatch):
    bare = {k: v for k, v in EXAMPLE_SSOT.items() if k != "_comment"}
    bare["identity"] = {"id": "x", "public": {}}
    f = tmp_path / "ssot.json"
    f.write_text(json.dumps(bare))
    monkeypatch.setenv("SSOT_PATH", str(f))
    result = server.check_ssot()
    assert any("identity.pii" in w for w in result["warnings"])


def test_draft_application_writes_files(cfg_env, monkeypatch):
    payloads = []
    monkeypatch.setattr(server, "_dify_client", lambda cfg: _mock_client(payloads))
    result = server.draft_application("We are hiring a platform engineer…", prep_interview=True)

    sent = payloads[0]["inputs"]
    assert sent["prep_interview"] == "yes"
    assert sent["job_ad"].startswith("We are hiring")
    assert json.loads(sent["ssot_json"])["identity"]["pii"]["full_name"] == "Alex Demo"
    assert payloads[0]["response_mode"] == "blocking"

    assert Path(result["files"]["cv_md"]).read_text().startswith("# CV")
    assert Path(result["files"]["cover_letter_md"]).exists()
    assert "interview_prep_md" not in result["files"]
    # PII-bearing document contents are written to disk, not returned
    assert "alex.demo@example.com" not in json.dumps(result)


def test_draft_application_workflow_failed(cfg_env, monkeypatch):
    def handler(_request):
        return httpx.Response(
            200, json={"data": {"status": "failed", "error": "LLM exploded"}}
        )

    monkeypatch.setattr(server, "_dify_client", lambda cfg: _mock_client([], handler))
    with pytest.raises(RuntimeError, match="status='failed'"):
        server.draft_application("some job ad")


def test_draft_application_requires_api_key(cfg_env, monkeypatch):
    monkeypatch.delenv("DIFY_API_KEY")
    with pytest.raises(RuntimeError, match="DIFY_API_KEY"):
        server.draft_application("some job ad")


def test_draft_application_rejects_empty_ad(cfg_env):
    with pytest.raises(ValueError, match="empty"):
        server.draft_application("   ")
