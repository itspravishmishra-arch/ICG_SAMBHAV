import sys

import pytest
from langchain_core.runnables import RunnableLambda

import providers
import rag_sql_chatbot
from create_sample_db import create_database
from okf_generator import build_bundle, extract_json
from okf_utils import split_frontmatter
from providers import ProviderError

KEY_VARS = ["OPENAI_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY", "LLM_PROVIDER",
            "CHAT_MODEL", "EMBEDDING_MODEL", "OKF_MODEL", "OLLAMA_BASE_URL"]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in KEY_VARS:
        monkeypatch.delenv(name, raising=False)


# ------------------------------ choosing a provider -------------------------- #
def test_default_provider_is_openai():
    assert providers.resolve_provider() == "openai"


def test_provider_from_environment_and_flag(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "Gemini")
    assert providers.resolve_provider() == "gemini"
    assert providers.resolve_provider("ollama") == "ollama"  # the flag wins


def test_unknown_provider_is_rejected():
    with pytest.raises(ProviderError, match="openai, gemini, ollama"):
        providers.resolve_provider("skynet")


def test_model_names_follow_flag_then_environment_then_default(monkeypatch):
    assert providers.chat_model_name("gemini") == providers.REGISTRY["gemini"].chat_model
    monkeypatch.setenv("CHAT_MODEL", "from-env")
    assert providers.chat_model_name("gemini") == "from-env"
    assert providers.chat_model_name("gemini", "from-flag") == "from-flag"


# ------------------------------------ keys ----------------------------------- #
def test_missing_key_says_which_variable_to_set():
    with pytest.raises(ProviderError, match="OPENAI_API_KEY"):
        providers.make_llm("openai")
    with pytest.raises(ProviderError, match="GOOGLE_API_KEY"):
        providers.make_embeddings("gemini")


def test_gemini_accepts_either_key_name(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "abc")
    assert providers.get_api_key("gemini") == "abc"


def test_ollama_needs_no_key():
    assert providers.get_api_key("ollama") is None


# --------------------------- building the models ---------------------------- #
def test_openai_models_build_without_network(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert providers.make_llm("openai", "gpt-test").model_name == "gpt-test"
    assert providers.make_embeddings("openai", "embed-test").model == "embed-test"


def test_gemini_models_build_without_network(monkeypatch):
    pytest.importorskip("langchain_google_genai")
    monkeypatch.setenv("GOOGLE_API_KEY", "test")
    assert providers.make_llm("gemini", "gemini-test").model == "gemini-test"
    assert "embed-test" in providers.make_embeddings("gemini", "embed-test").model


def test_ollama_models_build_without_network():
    pytest.importorskip("langchain_ollama")
    assert providers.make_llm("ollama", "llama-test").model == "llama-test"
    assert providers.make_embeddings("ollama", "embed-test").model == "embed-test"


def test_missing_package_gives_install_hint(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test")
    monkeypatch.setitem(sys.modules, "langchain_google_genai", None)  # makes the import fail
    with pytest.raises(ProviderError, match="pip install langchain-google-genai"):
        providers.make_llm("gemini")


# ------------------------------ listing models ------------------------------ #
def test_list_models_gemini(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test")
    seen = {}

    def fake_get(url, headers=None):
        seen["headers"] = headers
        return {"models": [
            {"name": "models/gemini-a", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/embed-b", "supportedGenerationMethods": ["embedContent"]},
            {"name": "models/other", "supportedGenerationMethods": ["countTokens"]},
        ]}

    monkeypatch.setattr(providers, "_http_get_json", fake_get)
    assert providers.list_models("gemini") == {"chat": ["gemini-a"], "embedding": ["embed-b"]}
    assert seen["headers"] == {"x-goog-api-key": "test"}


def test_list_models_ollama(monkeypatch):
    monkeypatch.setattr(providers, "_http_get_json", lambda url, headers=None: {
        "models": [{"name": "qwen2.5-coder:7b"}, {"name": "nomic-embed-text:latest"}]})
    assert providers.list_models("ollama") == {
        "chat": ["qwen2.5-coder:7b"], "embedding": ["nomic-embed-text:latest"]}


def test_list_models_openai_filters_non_chat(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(providers, "_http_get_json", lambda url, headers=None: {"data": [
        {"id": "gpt-4o"}, {"id": "text-embedding-3-small"}, {"id": "whisper-1"}, {"id": "gpt-4o-audio-preview"}]})
    models = providers.list_models("openai")
    assert models == {"chat": ["gpt-4o"], "embedding": ["text-embedding-3-small"]}


def test_unreachable_ollama_has_a_helpful_message(monkeypatch):
    import urllib.error

    def boom(url, headers=None):
        raise urllib.error.URLError("refused")

    monkeypatch.setattr(providers, "_http_get_json", boom)
    with pytest.raises(ProviderError, match="ollama serve"):
        providers.list_models("ollama")


def test_list_models_flag_prints_and_exits(monkeypatch, capsys):
    monkeypatch.setattr(providers, "_http_get_json", lambda url, headers=None: {"models": [{"name": "m1"}]})
    monkeypatch.setattr(sys, "argv", ["rag_sql_chatbot.py", "--provider", "ollama", "--list-models"])
    rag_sql_chatbot.main()
    assert "m1" in capsys.readouterr().out


def test_chatbot_exits_cleanly_when_key_is_missing(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["rag_sql_chatbot.py", "--provider", "gemini",
                                      "--database-url", "sqlite:///x.db"])
    with pytest.raises(SystemExit, match="GOOGLE_API_KEY"):
        rag_sql_chatbot.main()


# ------------------------------ friendly errors ------------------------------ #
@pytest.mark.parametrize("provider,message,expected", [
    ("openai", "Error code: 429 - insufficient_quota", "credit"),
    ("gemini", "429 RESOURCE_EXHAUSTED", "rate limit"),
    ("gemini", "404 models/foo is not found", "--list-models"),
    ("ollama", "model 'foo' not found", "ollama pull"),
    ("ollama", "[Errno 111] Connection refused", "ollama serve"),
    ("openai", "Error code: 401 - Incorrect API key provided", ".env"),
])
def test_explain_error(provider, message, expected):
    assert expected in providers.explain_error(provider, message)


def test_explain_error_is_quiet_for_unknown_problems():
    assert providers.explain_error("openai", "something odd happened") == ""


# --------------- descriptions drafted by any provider's model ---------------- #
def test_extract_json_handles_fences_and_chatter():
    assert extract_json('Sure!\n```json\n{"a": 1}\n```\nDone.') == {"a": 1}
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_generator_uses_the_model_for_descriptions_and_tags(tmp_path):
    url = f"sqlite:///{tmp_path / 'shop.db'}"
    create_database(url)
    reply = '```json\n{"description": "Customers who bought things.", "tags": ["Sales", "people here"]}\n```'
    build_bundle(url, str(tmp_path / "b"), enrich=True, llm=RunnableLambda(lambda _: reply))
    meta, _ = split_frontmatter((tmp_path / "b" / "customers.md").read_text())
    assert meta["description"] == "Customers who bought things."
    assert meta["tags"] == ["sales", "people-here"]
    assert meta["trust_tier"] == "unverified"


def test_generator_falls_back_when_the_model_misbehaves(tmp_path, capsys):
    url = f"sqlite:///{tmp_path / 'shop.db'}"
    create_database(url)
    build_bundle(url, str(tmp_path / "b"), enrich=True, llm=RunnableLambda(lambda _: "I cannot do that"))
    meta, _ = split_frontmatter((tmp_path / "b" / "orders.md").read_text())
    assert meta["description"].startswith("Table `orders` with columns")
    assert "AI description failed" in capsys.readouterr().out


def test_generator_without_a_key_still_works(tmp_path, capsys):
    url = f"sqlite:///{tmp_path / 'shop.db'}"
    create_database(url)
    build_bundle(url, str(tmp_path / "b"), enrich=True)  # no key set: plain descriptions
    out = capsys.readouterr().out
    assert "OPENAI_API_KEY" in out and "plain descriptions" in out
    assert (tmp_path / "b" / "orders.md").exists()
