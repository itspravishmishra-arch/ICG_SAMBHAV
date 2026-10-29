---
type: table
title: categories
description: 'Table `categories` with columns: category_id, name.'
resource: sqlite://sample_shop.db/categories
tags: []
trust_tier: unverified
generated:
  by: text2sql-okf-chatbot/1.0
  at: '2026-10-29T09:22:18+00:00'
sql:
  primary_key:
  - category_id
  foreign_keys: []
  referenced_by:
  - table: products
    column: category_id
    references_column: category_id
---

# categories

Table `categories` with columns: category_id, name.

## Columns

| Column | Type | Nullable | Notes |
|---|---|---|---|
| category_id | INTEGER | no | primary key |
| name | VARCHAR(60) | no |  |

## Relationships

- Referenced by [products](products.md) (join: `products.category_id = categories.category_id`)

## Notes

_Add business notes here (valid values, units, gotchas). Text under this heading is kept when the generator is re-run._
