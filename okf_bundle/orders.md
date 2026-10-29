---
type: table
title: orders
description: 'Table `orders` with columns: order_id, customer_id, order_date, status.'
resource: sqlite://sample_shop.db/orders
tags: []
trust_tier: unverified
generated:
  by: text2sql-okf-chatbot/1.0
  at: '2026-10-29T09:22:18+00:00'
sql:
  primary_key:
  - order_id
  foreign_keys:
  - column: customer_id
    references_table: customers
    references_column: customer_id
  referenced_by:
  - table: order_items
    column: order_id
    references_column: order_id
---

# orders

Table `orders` with columns: order_id, customer_id, order_date, status.

## Columns

| Column | Type | Nullable | Notes |
|---|---|---|---|
| order_id | INTEGER | no | primary key |
| customer_id | INTEGER | no | foreign key to customers.customer_id |
| order_date | DATE | no |  |
| status | VARCHAR(20) | no |  |

## Relationships

- `orders.customer_id` references [customers](customers.md) (join: `orders.customer_id = customers.customer_id`)
- Referenced by [order_items](order_items.md) (join: `order_items.order_id = orders.order_id`)

## Notes

_Add business notes here (valid values, units, gotchas). Text under this heading is kept when the generator is re-run._
