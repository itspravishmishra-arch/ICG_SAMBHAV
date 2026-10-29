"""OKF generator.

Reads the structure of a SQL database and writes an OKF "bundle": a folder with
one markdown file per table (plus an index.md). Each file has a YAML header
(name, description, tags, trust level, keys, relationships) and a readable body
(columns table, relationships with links to other tables, a notes section).

Usage:
    python okf_generator.py --database-url sqlite:///sample_shop.db --output okf_bundle_sample

Environment (or a .env file):
    DATABASE_URL     SQLAlchemy URL of the database
    LLM_PROVIDER     optional: openai (default), gemini or ollama
    plus that provider's key (see .env.example); an AI then writes first-draft
    descriptions. Without one, plain descriptions are written (or use --no-enrich).

Re-running is safe: descriptions you have reviewed (trust_tier changed away from
"unverified") and anything written under "## Notes" are kept.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.output_parsers import StrOutputParser
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

import providers
from okf_utils import iter_table_concepts, load_env, render_concept, split_frontmatter
from providers import ProviderError

GENERATOR_ID = "text2sql-okf-chatbot/1.0"
OKF_VERSION = "0.2"
NOTES_HEADING = "## Notes"
NOTES_PLACEHOLDER = (
    "_Add business notes here (valid values, units, gotchas). "
    "Text under this heading is kept when the generator is re-run._"
)


# --------------------------------------------------------------------------- #
# Reading the database structure
# --------------------------------------------------------------------------- #
def introspect(engine: Engine) -> dict[str, dict]:
    """Return {table_name: {columns, primary_key, foreign_keys, referenced_by}}."""
    inspector = inspect(engine)
    tables: dict[str, dict] = {}

    for name in sorted(inspector.get_table_names()):
        columns = [
            {
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": bool(col.get("nullable", True)),
            }
            for col in inspector.get_columns(name)
        ]
        primary_key = list(
            inspector.get_pk_constraint(name).get("constrained_columns") or []
        )
        foreign_keys = []
        for fk in inspector.get_foreign_keys(name):
            # A foreign key can span several columns; store one entry per pair.
            for local_col, remote_col in zip(
                fk["constrained_columns"], fk["referred_columns"]
            ):
                foreign_keys.append(
                    {
                        "column": local_col,
                        "references_table": fk["referred_table"],
                        "references_column": remote_col,
                    }
                )
        tables[name] = {
            "columns": columns,
            "primary_key": primary_key,
            "foreign_keys": foreign_keys,
            "referenced_by": [],
        }

    # Reverse links: which tables point at this one?
    for name, info in tables.items():
        for fk in info["foreign_keys"]:
            target = tables.get(fk["references_table"])
            if target is not None:
                target["referenced_by"].append(
                    {
                        "table": name,
                        "column": fk["column"],
                        "references_column": fk["references_column"],
                    }
                )
    return tables


def fetch_sample_rows(engine: Engine, table: str, n: int) -> str | None:
    """Return up to n rows as pipe-separated text, or None."""
    if n <= 0:
        return None
    quoted = engine.dialect.identifier_preparer.quote(table)
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT * FROM {quoted} LIMIT {int(n)}"))
            columns = list(result.keys())
            rows = result.fetchall()
    except Exception:
        return None
    if not rows:
        return None
    lines = [" | ".join(columns)]
    lines += [" | ".join("NULL" if v is None else str(v) for v in row) for row in rows]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Descriptions (AI first draft, or a plain fallback)
# --------------------------------------------------------------------------- #
def make_describer(provider: str, model: str | None):
    """Return a chat model for drafting descriptions, or None if it cannot be set up."""
    try:
        return providers.make_llm(provider, providers.describe_model_name(provider, model))
    except ProviderError as err:
        print(f"Note: {err}\n      Using plain descriptions instead (add --no-enrich to hide this note).")
        return None


def fallback_description(table: str, info: dict) -> tuple[str, list[str]]:
    names = ", ".join(col["name"] for col in info["columns"])
    return f"Table `{table}` with columns: {names}.", []


_DESCRIBE_PROMPT = """You are documenting a database table for a data catalog that an AI assistant will read in order to write SQL.

Table: {table}
Columns:
{columns}
Foreign keys:
{fks}
Referenced by:
{refs}

Return only a JSON object (no other text) with exactly two keys:
  "description": 1-2 plain-English sentences saying what one row of this table represents. Use only what the names imply; do not invent business rules.
  "tags": a list of 1-4 short lowercase topic words (for example "sales", "customers", "inventory").
"""


def extract_json(text_value: str) -> dict:
    """Pull the first {...} object out of model output (it may be wrapped in fences or chatter)."""
    start, end = text_value.find("{"), text_value.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found")
    return json.loads(text_value[start:end + 1])


def describe_with_llm(llm, table: str, info: dict) -> tuple[str, list[str]]:
    """Ask the model for a short description and tags. Falls back on any problem."""
    prompt = _DESCRIBE_PROMPT.format(
        table=table,
        columns="\n".join(f"- {c['name']} ({c['type']})" for c in info["columns"]),
        fks="\n".join(
            f"- {fk['column']} -> {fk['references_table']}.{fk['references_column']}"
            for fk in info["foreign_keys"]
        )
        or "none",
        refs="\n".join(
            f"- {r['table']}.{r['column']}" for r in info["referenced_by"]
        )
        or "none",
    )
    try:
        reply = (llm | StrOutputParser()).invoke(prompt)
        data = extract_json(reply)
        description = " ".join(str(data["description"]).split())
        tags = [
            re.sub(r"[^a-z0-9_-]", "", str(t).lower().replace(" ", "-"))
            for t in data.get("tags", [])
        ]
        tags = [t for t in tags if t][:4]
        if not description:
            raise ValueError("empty description")
        return description, tags
    except Exception as exc:  # network problems, bad JSON, rate limits...
        print(f"  (AI description failed for {table}: {str(exc).splitlines()[0][:120]}; using a plain one)")
        return fallback_description(table, info)


# --------------------------------------------------------------------------- #
# Writing the files
# --------------------------------------------------------------------------- #
def file_name(table: str) -> str:
    return re.sub(r"[^\w.-]", "_", table) + ".md"


def _cell(value: str) -> str:
    return str(value).replace("|", "\\|")


def build_body(table: str, info: dict, description: str, samples: str | None, notes: str) -> str:
    fk_by_column = {fk["column"]: fk for fk in info["foreign_keys"]}
    lines = [
        f"# {table}",
        "",
        description,
        "",
        "## Columns",
        "",
        "| Column | Type | Nullable | Notes |",
        "|---|---|---|---|",
    ]
    for col in info["columns"]:
        bits = []
        if col["name"] in info["primary_key"]:
            bits.append("primary key")
        fk = fk_by_column.get(col["name"])
        if fk:
            bits.append(
                f"foreign key to {fk['references_table']}.{fk['references_column']}"
            )
        lines.append(
            f"| {_cell(col['name'])} | {_cell(col['type'])} | "
            f"{'yes' if col['nullable'] and col['name'] not in info['primary_key'] else 'no'} | {'; '.join(bits)} |"
        )

    if info["foreign_keys"] or info["referenced_by"]:
        lines += ["", "## Relationships", ""]
        for fk in info["foreign_keys"]:
            other = fk["references_table"]
            lines.append(
                f"- `{table}.{fk['column']}` references [{other}]({file_name(other)}) "
                f"(join: `{table}.{fk['column']} = {other}.{fk['references_column']}`)"
            )
        for ref in info["referenced_by"]:
            other = ref["table"]
            lines.append(
                f"- Referenced by [{other}]({file_name(other)}) "
                f"(join: `{other}.{ref['column']} = {table}.{ref['references_column']}`)"
            )

    if samples:
        lines += ["", "## Sample rows", "", "```", samples, "```"]

    lines += ["", NOTES_HEADING, "", notes]
    return "\n".join(lines)


def extract_notes(body: str) -> str | None:
    """Return the text under the Notes heading of an existing file, if any."""
    index = body.find(NOTES_HEADING)
    if index == -1:
        return None
    notes = body[index + len(NOTES_HEADING):].strip()
    return notes or None


def build_bundle(
    database_url: str,
    output_dir: str,
    sample_rows: int = 0,
    enrich: bool = True,
    provider: str | None = None,
    model: str | None = None,
    llm=None,
) -> dict[str, dict]:
    """Write the whole bundle. Returns the introspected table info.

    `llm` lets a caller (or a test) supply the chat model directly.
    """
    engine = create_engine(database_url)
    tables = introspect(engine)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    describer = llm
    if describer is None and enrich:
        describer = make_describer(providers.resolve_provider(provider), model)

    db_label = f"{engine.dialect.name}://{engine.url.database or 'db'}"
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"Found {len(tables)} tables. Writing bundle to '{out}'...")

    summaries: dict[str, str] = {}
    for table, info in tables.items():
        path = out / file_name(table)

        previous_meta: dict = {}
        notes = NOTES_PLACEHOLDER
        if path.exists():
            previous_meta, previous_body = split_frontmatter(path.read_text(encoding="utf-8"))
            notes = extract_notes(previous_body) or NOTES_PLACEHOLDER

        previous_trust = previous_meta.get("trust_tier") or "unverified"
        if previous_trust != "unverified" and previous_meta.get("description"):
            # A person has reviewed this file: keep their wording.
            description = str(previous_meta["description"])
            tags = list(previous_meta.get("tags") or [])
            trust_tier = previous_trust
            source = "kept (reviewed)"
        else:
            if describer is not None:
                description, tags = describe_with_llm(describer, table, info)
            else:
                description, tags = fallback_description(table, info)
            trust_tier = "unverified"
            source = "AI draft" if describer is not None else "plain"

        meta = {
            "type": "table",
            "title": table,
            "description": description,
            "resource": f"{db_label}/{table}",
            "tags": tags,
            "trust_tier": trust_tier,
            "generated": {"by": GENERATOR_ID, "at": now},
            # Fields below are specific to this project (OKF allows extra keys).
            "sql": {
                "primary_key": info["primary_key"],
                "foreign_keys": info["foreign_keys"],
                "referenced_by": info["referenced_by"],
            },
        }
        samples = fetch_sample_rows(engine, table, sample_rows)
        body = build_body(table, info, description, samples, notes)
        path.write_text(render_concept(meta, body), encoding="utf-8")
        summaries[table] = description
        print(f"  {path.name}  [{source}]")

    index_lines = [
        "# Knowledge bundle",
        "",
        f"Tables in `{db_label}`. Generated by {GENERATOR_ID}.",
        "",
    ]
    for table, description in summaries.items():
        index_lines.append(f"- [{table}]({file_name(table)}): {description}")
    (out / "index.md").write_text(
        render_concept({"okf_version": OKF_VERSION}, "\n".join(index_lines)),
        encoding="utf-8",
    )

    # Warn about files for tables that no longer exist in the database.
    for path, meta, _ in iter_table_concepts(out):
        if meta.get("title") not in tables:
            print(f"  WARNING: {path.name} describes a table that is not in the database any more.")

    print("Done. Review the descriptions, then change trust_tier to 'human-reviewed' to keep your edits.")
    return tables


def main() -> None:
    load_env()
    parser = argparse.ArgumentParser(description="Generate an OKF bundle from a SQL database.")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"),
                        help="SQLAlchemy URL (or set DATABASE_URL)")
    parser.add_argument("--output", default="okf_bundle", help="Folder to write the bundle to")
    parser.add_argument("--sample-rows", type=int, default=0,
                        help="Rows of real data to copy into each file (default 0: none, for privacy)")
    parser.add_argument("--no-enrich", action="store_true",
                        help="Do not use an AI service; write plain descriptions")
    parser.add_argument("--provider", default=None,
                        help="AI service for descriptions: openai, gemini or ollama "
                             "(default: LLM_PROVIDER from .env, else openai)")
    parser.add_argument("--model", default=None,
                        help="Model for descriptions (default depends on the provider)")
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("Set DATABASE_URL (in .env or the environment) or pass --database-url.")

    try:
        build_bundle(args.database_url, args.output, args.sample_rows,
                     not args.no_enrich, args.provider, args.model)
    except ProviderError as err:
        raise SystemExit(str(err))


if __name__ == "__main__":
    main()
