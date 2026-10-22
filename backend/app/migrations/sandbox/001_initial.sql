CREATE TABLE accounts(id uuid PRIMARY KEY, tenant_id uuid NOT NULL, state jsonb NOT NULL, version integer NOT NULL DEFAULT 1);
CREATE INDEX accounts_tenant ON accounts(tenant_id);
CREATE TABLE receipts(operation_id uuid PRIMARY KEY, tenant_id uuid NOT NULL, account_id uuid NOT NULL REFERENCES accounts, payload_hash text NOT NULL, result jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
