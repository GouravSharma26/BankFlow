-- SECURE PASSWORD PROVISIONING:
-- Passwords must never be hardcoded or checked into version control.
-- After running this script, set or rotate the reporting user password securely out-of-band:
--
-- Local Setup (Interactive psql - recommended):
--   Connect interactively via psql and set password without command-line echoing:
--     \password bankflow_reporting_user
--
-- Automated Deployments:
--   Retrieve credentials securely from a secret manager or CI secret store (e.g. AWS Secrets
--   Manager, GCP Secret Manager, HashiCorp Vault) and provision using a non-echoing approach
--   appropriate to the deployment environment (e.g. deployment runner stdin pipe, Vault database
--   secrets engine, or managed cloud IAM). Never expose passwords via command-line flags (-v, -c)
--   that appear in system process listings.
--
-- Application Runtime Configuration (.env):
--   Both credentials must be configured together (never partially supplied):
--     BANKFLOW_REPORTING_DB_USER=bankflow_reporting_user
--     BANKFLOW_REPORTING_DB_PASSWORD=<secure_password>

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bankflow_reporting_user') THEN
        CREATE ROLE bankflow_reporting_user WITH LOGIN;
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
