# Database checklist (SQL, NoSQL, any ORM: Prisma, TypeORM, Sequelize, Mongoose, Eloquent, Django ORM, SQLAlchemy)

Load when the project has queries, models or migrations. Apply `general.md`
first; stack files cover framework syntax, this file covers the data layer.
Quality items (migrations, N+1) are `low`/`medium` unless they cause data loss,
exposure or an easy denial of service; say so in the finding.

## Wildcard reads and writes (mass assignment, A01/A04)

- `SELECT *`, `.find()` / `.findMany()` / `Model::all()` / `.objects.all()`
  with no column list, returned to a client: leaks hashes, tokens and internal
  flags added later. Select the columns the response needs.
- `INSERT`/`UPDATE` fed the whole request: `update(req.body)`,
  `create({ data: body })`, `Model::create($request->all())`,
  `Model(**request.data)`, `UPDATE ... SET` built from every key of the body.
  The client can set `role`, `isAdmin`, `ownerId`, `price`, `deletedAt`.
  Require an explicit field allowlist (DTO/schema/`$fillable`/`fields = [...]`).
- Update/delete whose `WHERE` is built from user input and can end up empty
  (`where: {}` when the filter is missing) - updates every row.
- Returning the saved row straight back (`RETURNING *`, `save()` result) - the
  same exposure as a wildcard read.

## Query safety (A03)

- String-built SQL or filters (see the stack file); `ORDER BY` / column / table
  names taken from the client without an allowlist.
- App connects as the DB owner/superuser; one account for app, migrations and
  reporting. The runtime user should lack DDL and access to other schemas.
- Multi-step writes (balance, stock, coupon) without a transaction, row lock
  or unique constraint - the race is in the data layer, not the handler.
- Multi-tenant tables queried without the tenant column in `WHERE`.

## Migration quality

- Foreign key missing where a column references another table (orphans,
  broken cascades); `ON DELETE` left at the default without a decision
  (`CASCADE` on user-owned data is a deletion bomb, `SET NULL` on a required
  field breaks reads).
- No index on foreign keys, on columns used in `WHERE`/`JOIN`/`ORDER BY`, or
  a unique index where the rule is "one per user" (enforced only in code).
- Nullability: a column the code treats as required declared `NULL`able, or
  `NOT NULL` added to a populated table with no default/backfill (the
  migration fails or locks the table).
- Destructive or lock-heavy changes with no plan: dropping a column the
  running version still reads, a type change that rewrites a large table,
  index creation without `CONCURRENTLY` (Postgres) on a hot table.
- No `down`/rollback, or a migration that mixes schema change and data
  backfill in one transaction; edited after it already ran (check history).
- Sensitive column (token, card, national id) stored as plain text; passwords
  not hashed; no soft-delete/retention decision for personal data.
- Seeds or fixtures with real credentials, default admin passwords, or data
  that run in production.

## N+1 and unbounded queries (A04, availability)

- A query inside a loop or `.map`/`forEach`/serializer/template that runs once
  per row (lazy relation access, `await` in a loop, a resolver per item).
  Use eager loading / a join / `IN (...)` batch / DataLoader.
- Listing endpoints with no `LIMIT`/pagination, or a client-set `limit` with
  no maximum; `COUNT(*)` on every request of a large table.
- Filtering or sorting in application memory after loading the whole table.
- Search with leading wildcard `LIKE '%x%'` on a large unindexed column.
- Report the real cost: "GET /orders runs 1 + N queries, N = rows per page".
