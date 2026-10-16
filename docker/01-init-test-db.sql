-- BankFlow Local Docker Initialization
-- Executed on initial container startup by postgres docker-entrypoint

-- Create dedicated test database for automated integration tests
CREATE DATABASE bankflow_test;
