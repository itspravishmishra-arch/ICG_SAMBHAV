---
type: table
title: products
description: 'Table `products` with columns: product_id, name, category_id, unit_price, stock_quantity.'
resource: sqlite://sample_shop.db/products
tags: []
trust_tier: unverified
generated:
  by: text2sql-okf-chatbot/1.0
  at: '2026-10-29T09:22:18+00:00'
sql:
  primary_key:
  - product_id
  foreign_keys:
  - column: category_id
    references_table: categories
    references_column: category_id
  referenced_by:
  - table: order_items
    column: product_id
    references_column: product_id
  - table: reviews
    column: product_id
    references_column: product_id
---

# products

Table `products` with columns: product_id, name, category_id, unit_price, stock_quantity.

## Columns

| Column | Type | Nullable | Notes |
|---|---|---|---|
| product_id | INTEGER | no | primary key |
| name | VARCHAR(100) | no |  |
| category_id | INTEGER | no | foreign key to categories.category_id |
| unit_price | NUMERIC(10, 2) | no |  |
| stock_quantity | INTEGER | no |  |

## Relationships

- `products.category_id` references [categories](categories.md) (join: `products.category_id = categories.category_id`)
- Referenced by [order_items](order_items.md) (join: `order_items.product_id = products.product_id`)
- Referenced by [reviews](reviews.md) (join: `reviews.product_id = products.product_id`)

## Notes

_Add business notes here (valid values, units, gotchas). Text under this heading is kept when the generator is re-run._
