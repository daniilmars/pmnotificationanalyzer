-- SAP Plant Maintenance Data Model (SQLite Compatible)
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
    MATXT TEXT, -- Keeping simple for now, focus was on Items/Causes
    PRIMARY KEY (QMNUM, MANUM),
    FOREIGN KEY(QMNUM) REFERENCES QMEL(QMNUM)
);

-- 6. AUFK: Order Header
CREATE TABLE IF NOT EXISTS AUFK (
    AUFNR TEXT PRIMARY KEY,
    QMNUM TEXT,
    AUART TEXT NOT NULL,
    KTEXT TEXT, -- Usually in AUFK, but could be text table. Keeping here for simplicity or we can move it.
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
-- In SAP, MAKT is linked to MARA (Material Master). Here we link via MATNR.
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
-- Tracks all changes to business objects for regulatory compliance
CREATE TABLE IF NOT EXISTS CDHDR (
    CHANGENR TEXT PRIMARY KEY,        -- Change document number
    OBJECTCLAS TEXT NOT NULL,         -- Object class (QMEL, AUFK, etc.)
    OBJECTID TEXT NOT NULL,           -- Object ID (QMNUM, AUFNR, etc.)
    USERNAME TEXT NOT NULL,           -- User who made the change
    UDATE TEXT NOT NULL,              -- Change date (YYYYMMDD)
    UTIME TEXT NOT NULL,              -- Change time (HHMMSS)
    TCODE TEXT,                       -- Transaction code
    CHANGE_IND TEXT,                  -- Change indicator (I=Insert, U=Update, D=Delete)
    LANGU TEXT DEFAULT 'en'           -- Language key
);

-- 10. CDPOS: Change Document Items (Field-Level Changes)
-- Records individual field changes for complete audit trail
CREATE TABLE IF NOT EXISTS CDPOS (
    CHANGENR TEXT,                    -- Reference to CDHDR
    TABNAME TEXT NOT NULL,            -- Table name
    TABKEY TEXT NOT NULL,             -- Table key (record identifier)
    FNAME TEXT NOT NULL,              -- Field name
    VALUE_NEW TEXT,                   -- New value
    VALUE_OLD TEXT,                   -- Old value
    CHNGIND TEXT,                     -- Change indicator (I/U/D/E)
    PRIMARY KEY (CHANGENR, TABNAME, TABKEY, FNAME),
    FOREIGN KEY(CHANGENR) REFERENCES CDHDR(CHANGENR)
);

-- 11. JEST: Object Status (System/User Status Management)
-- Manages lifecycle status of notifications and orders
CREATE TABLE IF NOT EXISTS JEST (
    OBJNR TEXT,                       -- Object number (internal)
    STAT TEXT,                        -- Status code
    INACT TEXT DEFAULT '',            -- Inactive flag
    CHGNR TEXT,                       -- Change number
    PRIMARY KEY (OBJNR, STAT)
);

-- 11b. TJ02T: Status Texts (Multi-Language)
CREATE TABLE IF NOT EXISTS TJ02T (
    ISTAT TEXT,                       -- Status code
    SPRAS TEXT,                       -- Language key
    TXT04 TEXT,                       -- Short text (4 chars)
    TXT30 TEXT,                       -- Medium text (30 chars)
    PRIMARY KEY (ISTAT, SPRAS)
);

-- 12. AFRU: Order Confirmations (Time Recording)
-- Records actual work performed on orders
CREATE TABLE IF NOT EXISTS AFRU (
    RUESSION TEXT PRIMARY KEY,        -- Confirmation counter
    AUFNR TEXT NOT NULL,              -- Order number
    VORNR TEXT,                       -- Operation number
    ARBID TEXT,                       -- Work center
    WERKS TEXT,                       -- Plant
    BUDAT TEXT,                       -- Posting date
    ISDD TEXT,                        -- Actual start date
    ISDZ TEXT,                        -- Actual start time
    IEDD TEXT,                        -- Actual end date
    IEDZ TEXT,                        -- Actual end time
    ARBEI REAL,                       -- Actual work (hours)
    ISMNW REAL,                       -- Actual machine time
    ISMNE TEXT,                       -- Machine time unit
    AUFPL TEXT,                       -- Routing number
    APLZL TEXT,                       -- General counter
    STOKZ TEXT,                       -- Reversal indicator
    STEFB TEXT,                       -- Error indicator
    LTXA1 TEXT,                       -- Confirmation text
    AUERU TEXT,                       -- Final confirmation flag
    ERNAM TEXT,                       -- Created by
    ERDAT TEXT,                       -- Creation date
    ERZET TEXT,                       -- Creation time
    FOREIGN KEY(AUFNR) REFERENCES AUFK(AUFNR)
);

-- 13. QMIH: Notification History (Version Tracking)
-- Tracks notification changes over time
CREATE TABLE IF NOT EXISTS QMIH (
    QMNUM TEXT,                       -- Notification number
    HESSION TEXT,                     -- History counter
    ERDAT TEXT,                       -- Change date
    ERZET TEXT,                       -- Change time
    ERNAM TEXT,                       -- Changed by
    QMART TEXT,                       -- Notification type
    PRIESSION TEXT,                   -- Priority (at time of change)
    STAT TEXT,                        -- Status (at time of change)
    OTGRP TEXT,                       -- Object part group
    FESSION TEXT,                     -- Damage code group
    URGRP TEXT,                       -- Cause code group
    MESSION TEXT,                     -- Activity code group
    CHANGE_REASON TEXT,               -- Reason for change
    PRIMARY KEY (QMNUM, HESSION),
    FOREIGN KEY(QMNUM) REFERENCES QMEL(QMNUM)
);

-- 14. QMCATALOG: Catalog Code Master (Validation)
-- Master data for damage/cause/activity codes
CREATE TABLE IF NOT EXISTS QMCATALOG (
    KATESSION TEXT,                   -- Catalog type (1=DamageCode, 2=CauseCode, 3=Activity)
    CODEGRUPPE TEXT,                  -- Code group
    CODE TEXT,                        -- Code
    SPRAS TEXT,                       -- Language
    KUESSION TEXT,                    -- Short text
    ACTIVE TEXT DEFAULT 'X',          -- Active flag
    VALID_FROM TEXT,                  -- Valid from date
    VALID_TO TEXT,                    -- Valid to date
    PRIMARY KEY (KATESSION, CODEGRUPPE, CODE, SPRAS)
);

-- 15. EQUI: Equipment Master (Basic)
-- Equipment master data for validation
CREATE TABLE IF NOT EXISTS EQUI (
    EQUNR TEXT PRIMARY KEY,           -- Equipment number
    EQART TEXT,                       -- Equipment category
    EQTYP TEXT,                       -- Equipment type
    ERDAT TEXT,                       -- Creation date
    ERNAM TEXT,                       -- Created by
    HERST TEXT,                       -- Manufacturer
    TYPBZ TEXT,                       -- Model number
    BAESSION TEXT,                    -- Construction year
    GEWRK TEXT,                       -- Warranty end
    TPLNR TEXT,                       -- Functional location
    INBDT TEXT,                       -- Startup date
    ANSDT TEXT,                       -- Acquisition date
    ACTIVE TEXT DEFAULT 'X'           -- Active flag
);

-- 15b. EQKT: Equipment Texts (Multi-Language)
CREATE TABLE IF NOT EXISTS EQKT (
    EQUNR TEXT,                       -- Equipment number
    SPRAS TEXT,                       -- Language
    EQKTX TEXT,                       -- Equipment description
    PRIMARY KEY (EQUNR, SPRAS),
    FOREIGN KEY(EQUNR) REFERENCES EQUI(EQUNR)
);

-- 16. IFLOT: Functional Location Master (Basic)
CREATE TABLE IF NOT EXISTS IFLOT (
    TPLNR TEXT PRIMARY KEY,           -- Functional location
    FLESSION TEXT,                    -- Functional location type
    ERDAT TEXT,                       -- Creation date
    ERNAM TEXT,                       -- Created by
    IESSION TEXT,                     -- Installation date
    PESSION TEXT,                     -- Superior functional location
    ACTIVE TEXT DEFAULT 'X'           -- Active flag
);

-- 16b. IFLOTX: Functional Location Texts (Multi-Language)
CREATE TABLE IF NOT EXISTS IFLOTX (
    TPLNR TEXT,                       -- Functional location
    SPRAS TEXT,                       -- Language
    PLTXT TEXT,                       -- Description
    PRIMARY KEY (TPLNR, SPRAS),
    FOREIGN KEY(TPLNR) REFERENCES IFLOT(TPLNR)
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
