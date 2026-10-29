"""Helpers shared by okf_generator.py and rag_sql_chatbot.py.

An OKF "concept" is one markdown file: a YAML header between two `---` lines,
followed by a free-form markdown body. These helpers read and write that shape.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

import yaml

_FRONTMATTER = re.compile(
    r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)(.*)\Z", re.DOTALL
)


def load_env() -> None:
    """Load variables from a local .env file if python-dotenv is installed."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Split a concept file into (header dict, body text).

    If the file has no valid header, returns ({}, whole text).
    """
    match = _FRONTMATTER.match(text)
    if not match:
        return {}, text
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}, text
    if not isinstance(meta, dict):
        return {}, text
    return meta, match.group(2).lstrip("\n")


def render_concept(meta: dict, body: str) -> str:
    """Build the text of a concept file from a header dict and a body."""
    header = yaml.safe_dump(
        meta, sort_keys=False, allow_unicode=True, width=100
    ).rstrip()
    return f"---\n{header}\n---\n\n{body.strip()}\n"


def iter_table_concepts(bundle_dir: str | Path) -> Iterator[tuple[Path, dict, str]]:
    """Yield (path, header, body) for every table concept in a bundle folder.

    index.md and any file whose `type` is not "table" are skipped.
    """
    for path in sorted(Path(bundle_dir).glob("*.md")):
        if path.name.lower() == "index.md":
            continue
        meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
        if meta.get("type") != "table":
            continue
        yield path, meta, body
