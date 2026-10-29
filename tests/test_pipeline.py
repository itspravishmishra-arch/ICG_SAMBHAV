"""End-to-end tests. A fake LLM and fake embeddings stand in for OpenAI,
so these run offline and cost nothing."""

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.runnables import RunnableLambda
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from create_sample_db import create_database
from okf_generator import build_bundle
from okf_utils import render_concept, split_frontmatter
from rag_sql_chatbot import Text2SQLBot, make_engine


@pytest.fixture()
def db_url(tmp_path):
    url = f"sqlite:///{tmp_path / 'shop.db'}"
    counts = create_database(url)
    assert counts["customers"] == 60
    return url


@pytest.fixture()
def bundle(db_url, tmp_path):
    out = tmp_path / "bundle"
    build_bundle(db_url, str(out), sample_rows=0, enrich=False)
    return out


def scripted_llm(sql_answers, answer="Done.", condensed="How many customers are there?"):
    """A fake chat model. Returns the given SQL strings one after another."""
    queue = list(sql_answers)

    def respond(prompt_value):
        prompt = prompt_value.to_string()
        if "Standalone question:" in prompt:
            return condensed
        if "SQL query:" in prompt:  # covers both the first attempt and the repair prompt
            return queue.pop(0) if len(queue) > 1 else queue[0]
        return answer

    return RunnableLambda(respond)


def make_bot(db_url, bundle, llm, **kwargs):
    return Text2SQLBot(
        engine=make_engine(db_url),
        llm=llm,
        embeddings=DeterministicFakeEmbedding(size=32),
        bundle_dir=str(bundle),
        **kwargs,
    )


# ----------------------------- sample database ------------------------------ #
def test_sample_db_refuses_to_overwrite_without_force(db_url):
    with pytest.raises(SystemExit):
        create_database(db_url)
    create_database(db_url, force=True)


# ------------------------------- OKF bundle --------------------------------- #
def test_bundle_has_one_file_per_table_plus_index(bundle):
    names = {p.name for p in bundle.glob("*.md")}
    assert names == {
        "index.md", "categories.md", "customers.md", "products.md",
        "orders.md", "order_items.md", "reviews.md",
    }
    meta, _ = split_frontmatter((bundle / "index.md").read_text())
    assert meta == {"okf_version": "0.2"}


def test_table_file_has_header_links_and_join_hints(bundle):
    meta, body = split_frontmatter((bundle / "orders.md").read_text())
    assert meta["type"] == "table" and meta["title"] == "orders"
    assert meta["trust_tier"] == "unverified"
    assert {"column": "customer_id", "references_table": "customers",
            "references_column": "customer_id"} in meta["sql"]["foreign_keys"]
    assert [r["table"] for r in meta["sql"]["referenced_by"]] == ["order_items"]
    assert "[customers](customers.md)" in body
    assert "orders.customer_id = customers.customer_id" in body
    assert "## Notes" in body


def test_no_sample_rows_by_default(bundle):
    assert "Sample rows" not in (bundle / "customers.md").read_text()


def test_sample_rows_only_when_asked(db_url, tmp_path):
    out = tmp_path / "with_samples"
    build_bundle(db_url, str(out), sample_rows=2, enrich=False)
    assert "## Sample rows" in (out / "customers.md").read_text()


def test_regenerating_keeps_reviewed_description_and_notes(db_url, bundle):
    path = bundle / "orders.md"
    meta, body = split_frontmatter(path.read_text())
    meta["description"] = "One row per customer order (reviewed by a person)."
    meta["trust_tier"] = "human-reviewed"
    body = body.replace(
        "_Add business notes here (valid values, units, gotchas). "
        "Text under this heading is kept when the generator is re-run._",
        "status is one of pending, shipped, delivered, cancelled.",
    )
    path.write_text(render_concept(meta, body))

    build_bundle(db_url, str(bundle), sample_rows=0, enrich=False)

    meta2, body2 = split_frontmatter(path.read_text())
    assert meta2["description"] == "One row per customer order (reviewed by a person)."
    assert meta2["trust_tier"] == "human-reviewed"
    assert "status is one of pending, shipped, delivered, cancelled." in body2
    # Unreviewed files are still refreshed and stay unverified.
    assert split_frontmatter((bundle / "customers.md").read_text())[0]["trust_tier"] == "unverified"


# --------------------------------- chatbot ---------------------------------- #
def test_happy_path_returns_rows_and_answer(db_url, bundle):
    bot = make_bot(db_url, bundle, scripted_llm(["```sql\nSELECT COUNT(*) AS n FROM customers;\n```"],
                                                answer="There are 60 customers."))
    reply = bot.ask("How many customers do we have?")
    assert reply.rows == [(60,)]
    assert reply.answer == "There are 60 customers."
    assert "LIMIT" in reply.sql.upper()
    assert not reply.error


def test_row_limit_is_enforced(db_url, bundle):
    bot = make_bot(db_url, bundle, scripted_llm(["SELECT order_id FROM orders"]), max_rows=7)
    reply = bot.ask("List orders")
    assert len(reply.rows) == 7


def test_colons_in_sql_do_not_break_execution(db_url, bundle):
    bot = make_bot(db_url, bundle, scripted_llm(["SELECT '10:30' AS t FROM customers LIMIT 1"]))
    assert bot.ask("time?").rows == [("10:30",)]


def test_failed_query_is_repaired(db_url, bundle):
    bot = make_bot(db_url, bundle, scripted_llm(
        ["SELECT * FROM does_not_exist", "SELECT COUNT(*) FROM orders"]))
    reply = bot.ask("How many orders?")
    assert reply.rows == [(400,)]
    assert not reply.error


def test_gives_up_after_retries_with_a_friendly_message(db_url, bundle):
    bot = make_bot(db_url, bundle, scripted_llm(["SELECT * FROM does_not_exist"]), max_retries=1)
    reply = bot.ask("Anything")
    assert reply.error and "Unknown table" in reply.error
    assert "couldn't build a query" in reply.answer


def test_cannot_answer_is_handled(db_url, bundle):
    bot = make_bot(db_url, bundle, scripted_llm(["CANNOT_ANSWER"]))
    reply = bot.ask("What is the weather?")
    assert "can't answer" in reply.answer and not reply.sql


def test_destructive_sql_never_runs(db_url, bundle):
    bot = make_bot(db_url, bundle, scripted_llm(["DELETE FROM customers"]), max_retries=1)
    reply = bot.ask("Delete everyone")
    assert reply.error
    with create_engine(db_url).connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM customers")).scalar() == 60


def test_connection_itself_is_read_only(db_url):
    engine = make_engine(db_url)
    with pytest.raises(SQLAlchemyError):
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM customers"))
    with create_engine(db_url).connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM customers")).scalar() == 60


def test_followup_uses_history(db_url, bundle):
    bot = make_bot(db_url, bundle, scripted_llm(["SELECT COUNT(*) FROM customers"],
                                                condensed="How many customers are in India?"))
    bot.ask("How many customers?")
    reply = bot.ask("and in India?")
    assert reply.standalone_question == "How many customers are in India?"
    assert len(bot.history) == 2
    bot.reset()
    assert bot.history == []


def test_retrieval_adds_foreign_key_neighbours(db_url, bundle):
    bot = make_bot(db_url, bundle, scripted_llm(["SELECT 1 FROM customers"]), top_k=1)
    names = bot.retrieve("anything at all")
    first = bot.tables[names[0]]
    for neighbour in first.references + first.referenced_by:
        assert neighbour in names
    assert len(names) <= bot.max_tables
