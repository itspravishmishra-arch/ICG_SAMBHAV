---
type: table
title: order_items
description: 'Table `order_items` with columns: order_item_id, order_id, product_id, quantity, unit_price.'
resource: sqlite://sample_shop.db/order_items
tags: []
trust_tier: unverified
generated:
  by: text2sql-okf-chatbot/1.0
  at: '2026-10-29T09:22:18+00:00'
sql:
  primary_key:
  - order_item_id
  foreign_keys:
  - column: product_id
    references_table: products
    references_column: product_id
  - column: order_id
    references_table: orders
    references_column: order_id
  referenced_by: []
---

# order_items

Table `order_items` with columns: order_item_id, order_id, product_id, quantity, unit_price.

## Columns

| Column | Type | Nullable | Notes |
|---|---|---|---|
| order_item_id | INTEGER | no | primary key |
| order_id | INTEGER | no | foreign key to orders.order_id |
| product_id | INTEGER | no | foreign key to products.product_id |
| quantity | INTEGER | no |  |
| unit_price | NUMERIC(10, 2) | no |  |

## Relationships

- `order_items.product_id` references [products](products.md) (join: `order_items.product_id = products.product_id`)
- `order_items.order_id` references [orders](orders.md) (join: `order_items.order_id = orders.order_id`)

## Notes

_Add business notes here (valid values, units, gotchas). Text under this heading is kept when the generator is re-run._
