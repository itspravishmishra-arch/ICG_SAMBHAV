---
type: table
title: customers
description: 'Table `customers` with columns: customer_id, full_name, email, city, country, signup_date.'
resource: sqlite://sample_shop.db/customers
tags: []
trust_tier: unverified
generated:
  by: text2sql-okf-chatbot/1.0
  at: '2026-10-29T09:22:18+00:00'
sql:
  primary_key:
  - customer_id
  foreign_keys: []
  referenced_by:
  - table: orders
    column: customer_id
    references_column: customer_id
  - table: reviews
    column: customer_id
    references_column: customer_id
---

# customers

Table `customers` with columns: customer_id, full_name, email, city, country, signup_date.

## Columns

| Column | Type | Nullable | Notes |
|---|---|---|---|
| customer_id | INTEGER | no | primary key |
| full_name | VARCHAR(100) | no |  |
| email | VARCHAR(120) | no |  |
| city | VARCHAR(60) | yes |  |
| country | VARCHAR(60) | yes |  |
| signup_date | DATE | no |  |

## Relationships

- Referenced by [orders](orders.md) (join: `orders.customer_id = customers.customer_id`)
- Referenced by [reviews](reviews.md) (join: `reviews.customer_id = customers.customer_id`)

## Notes

_Add business notes here (valid values, units, gotchas). Text under this heading is kept when the generator is re-run._
