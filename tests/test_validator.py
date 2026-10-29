import pytest

from rag_sql_chatbot import UnsafeQuery, apply_row_limit, clean_sql, validate_sql

ALLOWED = {"customers", "orders", "order_items", "products"}


def check(sql, dialect="sqlite"):
    return validate_sql(sql, ALLOWED, dialect)


def test_plain_select_is_allowed():
    check("SELECT COUNT(*) FROM customers")


def test_columns_containing_write_words_are_allowed():
    # The old keyword check wrongly rejected these ("created_at" contains "create").
    check("SELECT created_at, updated_at, last_update FROM orders")


def test_joins_and_aliases_are_allowed():
    check("SELECT c.full_name, o.order_id FROM customers c JOIN orders o ON o.customer_id = c.customer_id")


def test_cte_names_are_not_treated_as_unknown_tables():
    check("WITH big AS (SELECT * FROM orders) SELECT COUNT(*) FROM big")


def test_union_is_allowed():
    check("SELECT customer_id FROM orders UNION SELECT customer_id FROM customers")


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM customers",
        "UPDATE customers SET city = 'x'",
        "INSERT INTO customers (customer_id) VALUES (1)",
        "DROP TABLE customers",
        "ALTER TABLE customers ADD COLUMN x INT",
        "CREATE TABLE t (a INT)",
        "TRUNCATE TABLE customers",
    ],
)
def test_write_statements_are_rejected(sql):
    with pytest.raises(UnsafeQuery):
        check(sql, dialect="postgres")


def test_write_hidden_inside_a_cte_is_rejected():
    sql = "WITH gone AS (DELETE FROM customers RETURNING *) SELECT * FROM gone"
    with pytest.raises(UnsafeQuery):
        check(sql, dialect="postgres")


def test_select_into_is_rejected():
    with pytest.raises(UnsafeQuery):
        check("SELECT * INTO backup FROM customers", dialect="postgres")


def test_two_statements_are_rejected():
    with pytest.raises(UnsafeQuery):
        check("SELECT 1 FROM customers; DROP TABLE customers")


def test_unknown_table_is_rejected():
    with pytest.raises(UnsafeQuery, match="secrets"):
        check("SELECT * FROM secrets")


def test_garbage_is_rejected():
    with pytest.raises(UnsafeQuery):
        check("this is not sql")


def test_empty_is_rejected():
    with pytest.raises(UnsafeQuery):
        check("")


def test_limit_is_added_when_missing():
    tree = check("SELECT * FROM customers")
    assert "LIMIT 50" in apply_row_limit(tree, 50, "sqlite")


def test_existing_limit_is_kept():
    tree = check("SELECT * FROM customers LIMIT 3")
    sql = apply_row_limit(tree, 50, "sqlite")
    assert "LIMIT 3" in sql and "LIMIT 50" not in sql


def test_clean_sql_removes_fences_and_semicolon():
    assert clean_sql("```sql\nSELECT 1;\n```") == "SELECT 1"
    assert clean_sql("  SELECT 1 ;  ") == "SELECT 1"
    assert clean_sql("Here you go:\n```\nSELECT 2\n```") == "SELECT 2"
