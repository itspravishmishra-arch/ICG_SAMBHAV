---
type: table
title: reviews
description: 'Table `reviews` with columns: review_id, product_id, customer_id, rating, comment, created_at.'
resource: sqlite://sample_shop.db/reviews
tags: []
trust_tier: unverified
generated:
  by: text2sql-okf-chatbot/1.0
  at: '2026-10-29T09:22:18+00:00'
sql:
  primary_key:
  - review_id
  foreign_keys:
  - column: customer_id
    references_table: customers
    references_column: customer_id
  - column: product_id
    references_table: products
    references_column: product_id
  referenced_by: []
---

# reviews

Table `reviews` with columns: review_id, product_id, customer_id, rating, comment, created_at.

## Columns

| Column | Type | Nullable | Notes |
|---|---|---|---|
| review_id | INTEGER | no | primary key |
| product_id | INTEGER | no | foreign key to products.product_id |
| customer_id | INTEGER | no | foreign key to customers.customer_id |
| rating | INTEGER | no |  |
| comment | VARCHAR(255) | yes |  |
| created_at | DATE | no |  |

## Relationships

- `reviews.customer_id` references [customers](customers.md) (join: `reviews.customer_id = customers.customer_id`)
- `reviews.product_id` references [products](products.md) (join: `reviews.product_id = products.product_id`)

## Notes

_Add business notes here (valid values, units, gotchas). Text under this heading is kept when the generator is re-run._
