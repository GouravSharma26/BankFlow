-- BankFlow Phase 5: Dedicated Read-Only Reporting Role Setup
-- Grants least-privilege read-only access strictly to the `reporting` schema.
-- Prevents access to raw staging payloads, monitoring mutations, or warehouse base tables.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bankflow_reporting_user') THEN
        CREATE ROLE bankflow_reporting_user WITH LOGIN PASSWORD 'reporting_password_placeholder';
    END IF;
END $$;

-- Revoke all default privileges on application schemas
REVOKE ALL ON SCHEMA public FROM bankflow_reporting_user;
REVOKE ALL ON SCHEMA staging FROM bankflow_reporting_user;
REVOKE ALL ON SCHEMA monitoring FROM bankflow_reporting_user;
REVOKE ALL ON SCHEMA quarantine FROM bankflow_reporting_user;
REVOKE ALL ON SCHEMA warehouse FROM bankflow_reporting_user;

-- Grant USAGE strictly on reporting schema
GRANT USAGE ON SCHEMA reporting TO bankflow_reporting_user;

-- Grant SELECT only on views in reporting schema
GRANT SELECT ON ALL TABLES IN SCHEMA reporting TO bankflow_reporting_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA reporting GRANT SELECT ON TABLES TO bankflow_reporting_user;

-- Defense in depth: enforce read-only transaction mode and statement timeout for this role
ALTER ROLE bankflow_reporting_user SET default_transaction_read_only = on;
ALTER ROLE bankflow_reporting_user SET statement_timeout = '5000ms';
