CREATE INDEX sessions_tenant_expiry ON sessions(tenant_id,expires_at);
CREATE INDEX runs_tenant_created ON runs(tenant_id,created_at DESC);
CREATE INDEX runs_ticket_created ON runs(ticket_id,created_at DESC);
CREATE INDEX audit_tenant_created ON audit(tenant_id,id DESC);
