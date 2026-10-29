"""Choose which AI service powers the project.

Three services are supported:

    openai   OpenAI (needs an API key with credit)
    gemini   Google Gemini (has a free tier; needs a free API key)
    ollama   Ollama (models run on your own computer; free, no key)

Everything else in the project only asks this module for "a chat model" and
"an embeddings model", so the rest of the code does not care which one is used.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

DEFAULT_OLLAMA_URL = "http://localhost:11434"


class ProviderError(Exception):
    """A problem with the chosen AI service that the user can fix (missing key, package...)."""


@dataclass(frozen=True)
class Provider:
    name: str
    chat_model: str          # writes SQL and answers
    describe_model: str      # drafts table descriptions (can be cheaper)
    embedding_model: str     # turns text into numbers for searching the notes
    key_names: tuple         # environment variables that may hold the API key (empty: none needed)
    key_help: str
    install_hint: str
    privacy_note: str


REGISTRY = {
    "openai": Provider(
        name="openai",
        chat_model="gpt-4o",
        describe_model="gpt-4o-mini",
        embedding_model="text-embedding-3-small",
        key_names=("OPENAI_API_KEY",),
        key_help="Create a key at https://platform.openai.com/api-keys (the account needs credit).",
        install_hint="pip install langchain-openai",
        privacy_note="",
    ),
    "gemini": Provider(
        name="gemini",
        chat_model="gemini-flash-latest",
        describe_model="gemini-flash-latest",
        embedding_model="gemini-embedding-001",
        key_names=("GOOGLE_API_KEY", "GEMINI_API_KEY"),
        key_help="Create a free key in Google AI Studio: https://aistudio.google.com/apikey",
        install_hint="pip install langchain-google-genai",
        privacy_note=(
            "On Google's free tier, prompts and answers may be used by Google to improve its "
            "products. Do not use confidential or client data."
        ),
    ),
    "ollama": Provider(
        name="ollama",
        chat_model="qwen2.5-coder:7b",
        describe_model="qwen2.5-coder:7b",
        embedding_model="nomic-embed-text",
        key_names=(),
        key_help="",
        install_hint="pip install langchain-ollama",
        privacy_note="",
    ),
}

PROVIDERS = tuple(REGISTRY)


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #
def resolve_provider(name: str | None = None) -> str:
    """Pick the provider: command-line value, else LLM_PROVIDER, else openai."""
    value = (name or os.environ.get("LLM_PROVIDER") or "openai").strip().lower()
    if value not in REGISTRY:
        raise ProviderError(f"Unknown provider '{value}'. Choose one of: {', '.join(PROVIDERS)}.")
    return value


def get_api_key(provider: str) -> str | None:
    """Return the API key, or None if this provider needs none. Raise if it is missing."""
    info = REGISTRY[provider]
    if not info.key_names:
        return None
    for env_name in info.key_names:
        value = os.environ.get(env_name, "").strip()
        if value:
            return value
    raise ProviderError(
        f"No API key found for '{provider}'. Set {info.key_names[0]} in your .env file. {info.key_help}".strip()
    )


def ollama_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_URL


def chat_model_name(provider: str, override: str | None = None) -> str:
    return override or os.environ.get("CHAT_MODEL") or REGISTRY[provider].chat_model


def embedding_model_name(provider: str, override: str | None = None) -> str:
    return override or os.environ.get("EMBEDDING_MODEL") or REGISTRY[provider].embedding_model


def describe_model_name(provider: str, override: str | None = None) -> str:
    return override or os.environ.get("OKF_MODEL") or REGISTRY[provider].describe_model


# --------------------------------------------------------------------------- #
# Building the models (packages are imported only when needed)
# --------------------------------------------------------------------------- #
def make_llm(provider: str, model: str | None = None):
    """Return a LangChain chat model for the provider (temperature 0 for steady SQL)."""
    info = REGISTRY[provider]
    model = model or chat_model_name(provider)
    key = get_api_key(provider)
    try:
        if provider == "openai":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(model=model, temperature=0, api_key=key)
        if provider == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI

            return ChatGoogleGenerativeAI(model=model, temperature=0, google_api_key=key)
        from langchain_ollama import ChatOllama

        return ChatOllama(model=model, temperature=0, base_url=ollama_url())
    except ImportError as exc:
        raise ProviderError(
            f"The package for '{provider}' is not installed. Run: {info.install_hint}"
        ) from exc


def make_embeddings(provider: str, model: str | None = None):
    """Return a LangChain embeddings model for the provider."""
    info = REGISTRY[provider]
    model = model or embedding_model_name(provider)
    key = get_api_key(provider)
    try:
        if provider == "openai":
            from langchain_openai import OpenAIEmbeddings

            return OpenAIEmbeddings(model=model, api_key=key)
        if provider == "gemini":
            from langchain_google_genai import GoogleGenerativeAIEmbeddings

            return GoogleGenerativeAIEmbeddings(model=model, google_api_key=key)
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(model=model, base_url=ollama_url())
    except ImportError as exc:
        raise ProviderError(
            f"The package for '{provider}' is not installed. Run: {info.install_hint}"
        ) from exc


# --------------------------------------------------------------------------- #
# Listing the models you can use
# --------------------------------------------------------------------------- #
def _http_get_json(url: str, headers: dict | None = None) -> dict:
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def list_models(provider: str) -> dict[str, list[str]]:
    """Ask the service which models this account can use: {'chat': [...], 'embedding': [...]}."""
    try:
        if provider == "gemini":
            data = _http_get_json(
                "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000",
                {"x-goog-api-key": get_api_key(provider)},
            )
            chat, embedding = [], []
            for item in data.get("models", []):
                name = str(item.get("name", "")).removeprefix("models/")
                methods = item.get("supportedGenerationMethods") or []
                if "embedContent" in methods:
                    embedding.append(name)
                elif "generateContent" in methods:
                    chat.append(name)
            return {"chat": sorted(chat), "embedding": sorted(embedding)}

        if provider == "ollama":
            data = _http_get_json(ollama_url().rstrip("/") + "/api/tags")
            names = sorted(str(m.get("name", "")) for m in data.get("models", []))
            return {
                "chat": [n for n in names if "embed" not in n],
                "embedding": [n for n in names if "embed" in n],
            }

        data = _http_get_json(
            "https://api.openai.com/v1/models",
            {"Authorization": f"Bearer {get_api_key(provider)}"},
        )
        ids = sorted(str(m.get("id", "")) for m in data.get("data", []))
        skip = ("embedding", "audio", "image", "realtime", "tts", "transcribe", "search", "moderation")
        return {
            "chat": [i for i in ids
                     if i.startswith(("gpt", "o1", "o3", "o4", "chatgpt")) and not any(w in i for w in skip)],
            "embedding": [i for i in ids if "embedding" in i],
        }
    except urllib.error.HTTPError as exc:
        raise ProviderError(
            f"{provider} answered with an error ({exc.code}). Check your key and its permissions."
        ) from exc
    except (urllib.error.URLError, OSError) as exc:
        if provider == "ollama":
            raise ProviderError(
                f"Could not reach Ollama at {ollama_url()}. Is it running? Start it with: ollama serve"
            ) from exc
        raise ProviderError(f"Could not reach {provider}. Check your internet connection.") from exc


def model_list_text(provider: str) -> str:
    """Human-readable list of usable models, for --list-models."""
    models = list_models(provider)
    lines = [f"Models available for '{provider}':", "", "Chat models (use with --chat-model):"]
    lines += [f"  {name}" for name in models["chat"]] or ["  (none found)"]
    lines += ["", "Embedding models (use with --embedding-model):"]
    lines += [f"  {name}" for name in models["embedding"]] or ["  (none found)"]
    if provider == "openai":
        lines += ["", "(This list can include models your account is not allowed to use.)"]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Friendlier error messages
# --------------------------------------------------------------------------- #
def explain_error(provider: str, message: str) -> str:
    """A short suggestion for a common provider error message ('' if there is none)."""
    text = message.lower()
    if provider == "ollama" and any(
        w in text for w in ("connection refused", "failed to connect", "connect call failed", "connecterror")
    ):
        return "Is Ollama running? Start it with: ollama serve"
    if any(w in text for w in ("429", "quota", "rate limit", "resource_exhausted", "insufficient")):
        return ("You may be out of credit or have hit the rate limit. Wait a minute and try again, "
                "or check your billing and limits.")
    if any(w in text for w in ("not found", "404", "does not exist", "no such model")):
        extra = " For Ollama, download the model first with: ollama pull <model>." if provider == "ollama" else ""
        return ("That model may not exist for your account. Run with --list-models to see the usable "
                f"names, then pass one with --chat-model or --embedding-model.{extra}")
    if any(w in text for w in ("401", "403", "api key", "api_key", "authentication", "unauthorized",
                               "permission denied")):
        return "Your API key may be wrong or missing permissions. Check the key in .env."
    return ""
