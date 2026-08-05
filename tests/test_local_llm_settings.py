import json
from pathlib import Path

import pytest
from django.test import Client


@pytest.fixture
def client() -> Client:
    return Client()


def test_settings_accept_local_llm_without_api_key(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    settings_file = tmp_path / "settings.json"
    rag_config_file = tmp_path / "rag_config.json"
    monkeypatch.setattr(
        "django_app.views.helpers.SETTINGS_FILE",
        settings_file,
    )
    monkeypatch.setattr(
        "django_app.views.helpers.RAG_CONFIG_FILE",
        rag_config_file,
    )
    monkeypatch.setattr(
        "django_app.views.rag._load_persisted_settings",
        lambda: {},
    )

    response = client.post(
        "/api/settings",
        data=json.dumps(
            {
                "provider": "local_llm",
                "model": "Qwen/Qwen2.5-3B-Instruct-GGUF:Q4_K_M",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert json.loads(settings_file.read_text(encoding="utf-8")) == {
        "provider": "local_llm",
        "model": "Qwen/Qwen2.5-3B-Instruct-GGUF:Q4_K_M",
        "api_key": None,
    }
    assert (
        json.loads(rag_config_file.read_text(encoding="utf-8"))["llm_model"]
        == "Qwen/Qwen2.5-3B-Instruct-GGUF:Q4_K_M"
    )


def test_settings_clear_api_key_when_switching_to_local_llm(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    settings_file = tmp_path / "settings.json"
    rag_config_file = tmp_path / "rag_config.json"
    monkeypatch.setattr("django_app.views.helpers.SETTINGS_FILE", settings_file)
    monkeypatch.setattr(
        "django_app.views.helpers.RAG_CONFIG_FILE",
        rag_config_file,
    )
    monkeypatch.setattr(
        "django_app.views.rag._load_persisted_settings",
        lambda: {"api_key": "cloud-secret"},
    )

    response = client.post(
        "/api/settings",
        data=json.dumps(
            {
                "provider": "local_llm",
                "model": "local-model",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert json.loads(settings_file.read_text(encoding="utf-8"))["api_key"] is None
    assert (
        json.loads(rag_config_file.read_text(encoding="utf-8"))["llm_model"]
        == "local-model"
    )


def test_settings_reject_removed_local_qwen_provider(
    client: Client,
):
    response = client.post(
        "/api/settings",
        data=json.dumps(
            {
                "provider": "local_qwen",
                "model": "qwen2.5:3b",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 400


def test_removed_ask_qwen_route_returns_not_found(client: Client):
    response = client.post(
        "/api/ask_qwen",
        data=json.dumps({"query": "test"}),
        content_type="application/json",
    )

    assert response.status_code == 404
