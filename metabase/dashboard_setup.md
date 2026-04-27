# Metabase Starter Setup

1. Open Metabase at your configured `METABASE_DOMAIN`.
2. Add a new PostgreSQL database with a read-only user.
3. Run SQL from `metabase/starter_queries.sql` to create saved questions:
   - Daily trend by cat
   - 7-day moving average
   - 30-day moving average
   - Min/Max/Median by week
   - Time-of-day pattern distribution
4. Create a dashboard named `Cat Glucose Overview`.
5. Add the saved questions and expose dashboard filters:
   - Cat name
   - Date range

## Read-Only Role SQL

Use the SQL from `/api/metabase/bootstrap` to provision a least-privilege user.
