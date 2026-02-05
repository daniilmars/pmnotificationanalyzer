-- SAP Plant Maintenance Data Model (PostgreSQL)
-- Fully Localized Version

-- 1. QMEL: Notification Header (Technical Data Only)
CREATE TABLE IF NOT EXISTS QMEL (
    QMNUM TEXT PRIMARY KEY,
    QMART TEXT NOT NULL,
    EQUNR TEXT,
    TPLNR TEXT,
    PRIOK TEXT,
    QMNAM TEXT,
    ERDAT TEXT,
    MZEIT TEXT,
    STRMN TEXT,
    LTRMN TEXT
);

-- 2. NOTIF_CONTENT: Notification Header Texts (Multi-Language)
CREATE TABLE IF NOT EXISTS NOTIF_CONTENT (
    QMNUM TEXT,
    SPRAS TEXT,
    QMTXT TEXT,
    TDLINE TEXT,
    PRIMARY KEY (QMNUM, SPRAS),
    FOREIGN KEY(QMNUM) REFERENCES QMEL(QMNUM)
);

-- 3. QMFE: Notification Items (Codes Only)
CREATE TABLE IF NOT EXISTS QMFE (
    QMNUM TEXT,
    FENUM TEXT,
    OTGRP TEXT,
    OTEIL TEXT,
    FEGRP TEXT,
    FECOD TEXT,
    PRIMARY KEY (QMNUM, FENUM),
    FOREIGN KEY(QMNUM) REFERENCES QMEL(QMNUM)
);

-- 3b. QMFE_TEXT: Notification Item Texts (Multi-Language)
CREATE TABLE IF NOT EXISTS QMFE_TEXT (
    QMNUM TEXT,
    FENUM TEXT,
    SPRAS TEXT,
    FETXT TEXT,
    PRIMARY KEY (QMNUM, FENUM, SPRAS),
    FOREIGN KEY(QMNUM, FENUM) REFERENCES QMFE(QMNUM, FENUM)
);

-- 4. QMUR: Notification Causes (Codes Only)
CREATE TABLE IF NOT EXISTS QMUR (
    QMNUM TEXT,
    FENUM TEXT,
    URNUM TEXT,
    URGRP TEXT,
    URCOD TEXT,
    PRIMARY KEY (QMNUM, FENUM, URNUM),
    FOREIGN KEY(QMNUM, FENUM) REFERENCES QMFE(QMNUM, FENUM)
);

-- 4b. QMUR_TEXT: Notification Cause Texts (Multi-Language)
CREATE TABLE IF NOT EXISTS QMUR_TEXT (
    QMNUM TEXT,
    FENUM TEXT,
    URNUM TEXT,
    SPRAS TEXT,
    URTXT TEXT,
    PRIMARY KEY (QMNUM, FENUM, URNUM, SPRAS),
    FOREIGN KEY(QMNUM, FENUM, URNUM) REFERENCES QMUR(QMNUM, FENUM, URNUM)
);

-- 5. QMAK: Notification Activities
CREATE TABLE IF NOT EXISTS QMAK (
    QMNUM TEXT,
    MANUM TEXT,
    MNGRP TEXT,
    MNCOD TEXT,
    MATXT TEXT,
    PRIMARY KEY (QMNUM, MANUM),
    FOREIGN KEY(QMNUM) REFERENCES QMEL(QMNUM)
);

-- 6. AUFK: Order Header
CREATE TABLE IF NOT EXISTS AUFK (
    AUFNR TEXT PRIMARY KEY,
    QMNUM TEXT,
    AUART TEXT NOT NULL,
    KTEXT TEXT,
    GLTRP TEXT,
    GLTRS TEXT,
    FOREIGN KEY(QMNUM) REFERENCES QMEL(QMNUM)
);

-- 7. AFVC: Order Operations (Technical)
CREATE TABLE IF NOT EXISTS AFVC (
    AUFNR TEXT,
    VORNR TEXT,
    ARBPL TEXT,
    STEUS TEXT,
    DAUER TEXT,
    DAUERE TEXT,
    PRIMARY KEY (AUFNR, VORNR),
    FOREIGN KEY(AUFNR) REFERENCES AUFK(AUFNR)
);

-- 7b. AFVC_TEXT: Order Operation Texts (Multi-Language)
CREATE TABLE IF NOT EXISTS AFVC_TEXT (
    AUFNR TEXT,
    VORNR TEXT,
    SPRAS TEXT,
    LTXA1 TEXT,
    PRIMARY KEY (AUFNR, VORNR, SPRAS),
    FOREIGN KEY(AUFNR, VORNR) REFERENCES AFVC(AUFNR, VORNR)
);

-- 8. RESB: Order Components (Materials - Technical)
CREATE TABLE IF NOT EXISTS RESB (
    AUFNR TEXT,
    VORNR TEXT,
    MATNR TEXT,
    MENGE REAL,
    MEINS TEXT,
    PRIMARY KEY (AUFNR, VORNR, MATNR),
    FOREIGN KEY(AUFNR, VORNR) REFERENCES AFVC(AUFNR, VORNR)
);

-- 8b. MAKT: Material Descriptions (Master Data Pattern)
CREATE TABLE IF NOT EXISTS MAKT (
    MATNR TEXT,
    SPRAS TEXT,
    MAKTX TEXT,
    PRIMARY KEY (MATNR, SPRAS)
);

-- ============================================================
-- SAP COMPLIANCE ENHANCEMENTS (FDA 21 CFR Part 11 Support)
-- ============================================================

-- 9. CDHDR: Change Document Header (Audit Trail)
CREATE TABLE IF NOT EXISTS CDHDR (
    CHANGENR TEXT PRIMARY KEY,
    OBJECTCLAS TEXT NOT NULL,
    OBJECTID TEXT NOT NULL,
    USERNAME TEXT NOT NULL,
    UDATE TEXT NOT NULL,
    UTIME TEXT NOT NULL,
    TCODE TEXT,
    CHANGE_IND TEXT,
    LANGU TEXT DEFAULT 'en'
);

-- 10. CDPOS: Change Document Items (Field-Level Changes)
CREATE TABLE IF NOT EXISTS CDPOS (
    CHANGENR TEXT,
    TABNAME TEXT NOT NULL,
    TABKEY TEXT NOT NULL,
    FNAME TEXT NOT NULL,
    VALUE_NEW TEXT,
    VALUE_OLD TEXT,
    CHNGIND TEXT,
    PRIMARY KEY (CHANGENR, TABNAME, TABKEY, FNAME),
    FOREIGN KEY(CHANGENR) REFERENCES CDHDR(CHANGENR)
);

-- 11. JEST: Object Status (System/User Status Management)
CREATE TABLE IF NOT EXISTS JEST (
    OBJNR TEXT,
    STAT TEXT,
    INACT TEXT DEFAULT '',
    CHGNR TEXT,
    PRIMARY KEY (OBJNR, STAT)
);

-- 11b. TJ02T: Status Texts (Multi-Language)
CREATE TABLE IF NOT EXISTS TJ02T (
    ISTAT TEXT,
    SPRAS TEXT,
    TXT04 TEXT,
    TXT30 TEXT,
    PRIMARY KEY (ISTAT, SPRAS)
);

-- 12. AFRU: Order Confirmations (Time Recording)
CREATE TABLE IF NOT EXISTS AFRU (
    RUESSION TEXT PRIMARY KEY,
    AUFNR TEXT NOT NULL,
    VORNR TEXT,
    ARBID TEXT,
    WERKS TEXT,
    BUDAT TEXT,
    ISDD TEXT,
    ISDZ TEXT,
    IEDD TEXT,
    IEDZ TEXT,
    ARBEI REAL,
    ISMNW REAL,
    ISMNE TEXT,
    AUFPL TEXT,
    APLZL TEXT,
    STOKZ TEXT,
    STEFB TEXT,
    LTXA1 TEXT,
    AUERU TEXT,
    ERNAM TEXT,
    ERDAT TEXT,
    ERZET TEXT,
    FOREIGN KEY(AUFNR) REFERENCES AUFK(AUFNR)
);

-- 13. QMIH: Notification History (Version Tracking)
CREATE TABLE IF NOT EXISTS QMIH (
    QMNUM TEXT,
    HESSION TEXT,
    ERDAT TEXT,
    ERZET TEXT,
    ERNAM TEXT,
    QMART TEXT,
    PRIESSION TEXT,
    STAT TEXT,
    OTGRP TEXT,
    FESSION TEXT,
    URGRP TEXT,
    MESSION TEXT,
    CHANGE_REASON TEXT,
    PRIMARY KEY (QMNUM, HESSION),
    FOREIGN KEY(QMNUM) REFERENCES QMEL(QMNUM)
);

-- 14. QMCATALOG: Catalog Code Master (Validation)
CREATE TABLE IF NOT EXISTS QMCATALOG (
    KATESSION TEXT,
    CODEGRUPPE TEXT,
    CODE TEXT,
    SPRAS TEXT,
    KUESSION TEXT,
    ACTIVE TEXT DEFAULT 'X',
    VALID_FROM TEXT,
    VALID_TO TEXT,
    PRIMARY KEY (KATESSION, CODEGRUPPE, CODE, SPRAS)
);

-- 15. EQUI: Equipment Master (Basic)
CREATE TABLE IF NOT EXISTS EQUI (
    EQUNR TEXT PRIMARY KEY,
    EQART TEXT,
    EQTYP TEXT,
    ERDAT TEXT,
    ERNAM TEXT,
    HERST TEXT,
    TYPBZ TEXT,
    BAESSION TEXT,
    GEWRK TEXT,
    TPLNR TEXT,
    INBDT TEXT,
    ANSDT TEXT,
    ACTIVE TEXT DEFAULT 'X'
);

-- 15b. EQKT: Equipment Texts (Multi-Language)
CREATE TABLE IF NOT EXISTS EQKT (
    EQUNR TEXT,
    SPRAS TEXT,
    EQKTX TEXT,
    PRIMARY KEY (EQUNR, SPRAS),
    FOREIGN KEY(EQUNR) REFERENCES EQUI(EQUNR)
);

-- 16. IFLOT: Functional Location Master (Basic)
CREATE TABLE IF NOT EXISTS IFLOT (
    TPLNR TEXT PRIMARY KEY,
    FLESSION TEXT,
    ERDAT TEXT,
    ERNAM TEXT,
    IESSION TEXT,
    PESSION TEXT,
    ACTIVE TEXT DEFAULT 'X'
);

-- 16b. IFLOTX: Functional Location Texts (Multi-Language)
CREATE TABLE IF NOT EXISTS IFLOTX (
    TPLNR TEXT,
    SPRAS TEXT,
    PLTXT TEXT,
    PRIMARY KEY (TPLNR, SPRAS),
    FOREIGN KEY(TPLNR) REFERENCES IFLOT(TPLNR)
);

-- ============================================================
-- Multi-Tenancy Support
-- ============================================================

-- Tenant registry for SaaS multi-tenancy
CREATE TABLE IF NOT EXISTS tenants (
    tenant_id TEXT PRIMARY KEY,
    subdomain TEXT UNIQUE NOT NULL,
    display_name TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    plan TEXT NOT NULL DEFAULT 'basic',
    max_users INTEGER DEFAULT 10,
    max_notifications INTEGER DEFAULT 5000,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Tenant usage metering
CREATE TABLE IF NOT EXISTS tenant_usage (
    id SERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
    metric TEXT NOT NULL,
    value REAL NOT NULL DEFAULT 0,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- Security Infrastructure Tables
-- ============================================================

-- API keys
CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    scopes TEXT DEFAULT '[]',
    created_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    last_used_at TIMESTAMP,
    enabled BOOLEAN DEFAULT TRUE,
    request_count INTEGER DEFAULT 0
);

-- Security audit log
CREATE TABLE IF NOT EXISTS security_audit_log (
    id SERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    user_id TEXT,
    ip_address TEXT,
    resource TEXT,
    action TEXT,
    details JSONB DEFAULT '{}',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Alert rules
CREATE TABLE IF NOT EXISTS alert_rules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    config JSONB NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_triggered TIMESTAMP,
    trigger_count INTEGER DEFAULT 0
);

-- Alert subscriptions
CREATE TABLE IF NOT EXISTS subscriptions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    email TEXT NOT NULL,
    config JSONB NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Alert log
CREATE TABLE IF NOT EXISTS alert_log (
    id SERIAL PRIMARY KEY,
    rule_id TEXT,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT,
    recipients TEXT,
    triggered_at TIMESTAMP NOT NULL,
    data JSONB
);

-- ============================================================
-- Indexes for query optimization
-- ============================================================

-- Primary lookup indexes
CREATE INDEX IF NOT EXISTS idx_qmel_equnr ON QMEL(EQUNR);
CREATE INDEX IF NOT EXISTS idx_qmel_tplnr ON QMEL(TPLNR);
CREATE INDEX IF NOT EXISTS idx_qmel_erdat ON QMEL(ERDAT DESC);

-- Foreign key indexes for JOIN performance
CREATE INDEX IF NOT EXISTS idx_aufk_qmnum ON AUFK(QMNUM);
CREATE INDEX IF NOT EXISTS idx_notif_content_qmnum ON NOTIF_CONTENT(QMNUM);
CREATE INDEX IF NOT EXISTS idx_qmfe_qmnum ON QMFE(QMNUM);
CREATE INDEX IF NOT EXISTS idx_qmfe_text_qmnum ON QMFE_TEXT(QMNUM);
CREATE INDEX IF NOT EXISTS idx_qmur_qmnum ON QMUR(QMNUM);
CREATE INDEX IF NOT EXISTS idx_qmur_text_qmnum ON QMUR_TEXT(QMNUM);
CREATE INDEX IF NOT EXISTS idx_qmak_qmnum ON QMAK(QMNUM);
CREATE INDEX IF NOT EXISTS idx_afvc_aufnr ON AFVC(AUFNR);
CREATE INDEX IF NOT EXISTS idx_afvc_text_aufnr ON AFVC_TEXT(AUFNR);
CREATE INDEX IF NOT EXISTS idx_resb_aufnr ON RESB(AUFNR);
CREATE INDEX IF NOT EXISTS idx_resb_aufnr_vornr ON RESB(AUFNR, VORNR);
CREATE INDEX IF NOT EXISTS idx_makt_matnr ON MAKT(MATNR);

-- Change Document indexes (Audit Trail)
CREATE INDEX IF NOT EXISTS idx_cdhdr_objectid ON CDHDR(OBJECTID);
CREATE INDEX IF NOT EXISTS idx_cdhdr_objectclas ON CDHDR(OBJECTCLAS);
CREATE INDEX IF NOT EXISTS idx_cdhdr_username ON CDHDR(USERNAME);
CREATE INDEX IF NOT EXISTS idx_cdhdr_udate ON CDHDR(UDATE DESC);
CREATE INDEX IF NOT EXISTS idx_cdpos_changenr ON CDPOS(CHANGENR);
CREATE INDEX IF NOT EXISTS idx_cdpos_tabname ON CDPOS(TABNAME);

-- Status management indexes
CREATE INDEX IF NOT EXISTS idx_jest_objnr ON JEST(OBJNR);
CREATE INDEX IF NOT EXISTS idx_jest_stat ON JEST(STAT);

-- Time confirmation indexes
CREATE INDEX IF NOT EXISTS idx_afru_aufnr ON AFRU(AUFNR);
CREATE INDEX IF NOT EXISTS idx_afru_budat ON AFRU(BUDAT DESC);
CREATE INDEX IF NOT EXISTS idx_afru_ernam ON AFRU(ERNAM);

-- Notification history indexes
CREATE INDEX IF NOT EXISTS idx_qmih_qmnum ON QMIH(QMNUM);
CREATE INDEX IF NOT EXISTS idx_qmih_erdat ON QMIH(ERDAT DESC);

-- Catalog code indexes
CREATE INDEX IF NOT EXISTS idx_qmcatalog_katalogart ON QMCATALOG(KATESSION);
CREATE INDEX IF NOT EXISTS idx_qmcatalog_codegruppe ON QMCATALOG(CODEGRUPPE);

-- Equipment master indexes
CREATE INDEX IF NOT EXISTS idx_equi_tplnr ON EQUI(TPLNR);
CREATE INDEX IF NOT EXISTS idx_equi_eqart ON EQUI(EQART);

-- Functional location indexes
CREATE INDEX IF NOT EXISTS idx_iflot_parent ON IFLOT(PESSION);

-- Multi-tenancy indexes
CREATE INDEX IF NOT EXISTS idx_tenant_usage_tenant ON tenant_usage(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_usage_metric ON tenant_usage(metric);
CREATE INDEX IF NOT EXISTS idx_tenant_usage_recorded ON tenant_usage(recorded_at DESC);

-- Security indexes
CREATE INDEX IF NOT EXISTS idx_security_audit_event ON security_audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_security_audit_user ON security_audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_security_audit_ts ON security_audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
