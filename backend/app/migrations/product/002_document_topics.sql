ALTER TABLE documents ADD COLUMN family text NOT NULL DEFAULT 'shared'
    CHECK(family IN ('billing','integration','configuration','shared'));
UPDATE documents SET family=CASE source_key
    WHEN 'billing-recovery' THEN 'billing'
    WHEN 'delivery-recovery' THEN 'integration'
    WHEN 'webhook-settings' THEN 'configuration'
    ELSE 'shared' END;
