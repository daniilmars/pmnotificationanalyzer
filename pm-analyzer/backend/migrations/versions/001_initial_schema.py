"""Initial schema baseline - SAP PM data model with FDA compliance tables.

Revision ID: 001_initial
Revises: None
Create Date: 2026-02-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all baseline tables for PM Notification Analyzer."""

    # SAP PM Core Tables
    op.create_table('QMEL',
        sa.Column('QMNUM', sa.Text(), primary_key=True),
        sa.Column('QMART', sa.Text(), nullable=False),
        sa.Column('EQUNR', sa.Text()),
        sa.Column('TPLNR', sa.Text()),
        sa.Column('PRIOK', sa.Text()),
        sa.Column('QMNAM', sa.Text()),
        sa.Column('ERDAT', sa.Text()),
        sa.Column('MZEIT', sa.Text()),
        sa.Column('STRMN', sa.Text()),
        sa.Column('LTRMN', sa.Text()),
    )

    op.create_table('NOTIF_CONTENT',
        sa.Column('QMNUM', sa.Text(), sa.ForeignKey('QMEL.QMNUM')),
        sa.Column('SPRAS', sa.Text()),
        sa.Column('QMTXT', sa.Text()),
        sa.Column('TDLINE', sa.Text()),
        sa.PrimaryKeyConstraint('QMNUM', 'SPRAS'),
    )

    op.create_table('QMFE',
        sa.Column('QMNUM', sa.Text(), sa.ForeignKey('QMEL.QMNUM')),
        sa.Column('FENUM', sa.Text()),
        sa.Column('OTGRP', sa.Text()),
        sa.Column('OTEIL', sa.Text()),
        sa.Column('FEGRP', sa.Text()),
        sa.Column('FECOD', sa.Text()),
        sa.PrimaryKeyConstraint('QMNUM', 'FENUM'),
    )

    op.create_table('QMFE_TEXT',
        sa.Column('QMNUM', sa.Text()),
        sa.Column('FENUM', sa.Text()),
        sa.Column('SPRAS', sa.Text()),
        sa.Column('FETXT', sa.Text()),
        sa.PrimaryKeyConstraint('QMNUM', 'FENUM', 'SPRAS'),
        sa.ForeignKeyConstraint(['QMNUM', 'FENUM'], ['QMFE.QMNUM', 'QMFE.FENUM']),
    )

    op.create_table('QMUR',
        sa.Column('QMNUM', sa.Text()),
        sa.Column('FENUM', sa.Text()),
        sa.Column('URNUM', sa.Text()),
        sa.Column('URGRP', sa.Text()),
        sa.Column('URCOD', sa.Text()),
        sa.PrimaryKeyConstraint('QMNUM', 'FENUM', 'URNUM'),
        sa.ForeignKeyConstraint(['QMNUM', 'FENUM'], ['QMFE.QMNUM', 'QMFE.FENUM']),
    )

    op.create_table('QMUR_TEXT',
        sa.Column('QMNUM', sa.Text()),
        sa.Column('FENUM', sa.Text()),
        sa.Column('URNUM', sa.Text()),
        sa.Column('SPRAS', sa.Text()),
        sa.Column('URTXT', sa.Text()),
        sa.PrimaryKeyConstraint('QMNUM', 'FENUM', 'URNUM', 'SPRAS'),
        sa.ForeignKeyConstraint(['QMNUM', 'FENUM', 'URNUM'], ['QMUR.QMNUM', 'QMUR.FENUM', 'QMUR.URNUM']),
    )

    op.create_table('QMAK',
        sa.Column('QMNUM', sa.Text(), sa.ForeignKey('QMEL.QMNUM')),
        sa.Column('MANUM', sa.Text()),
        sa.Column('MNGRP', sa.Text()),
        sa.Column('MNCOD', sa.Text()),
        sa.Column('MATXT', sa.Text()),
        sa.PrimaryKeyConstraint('QMNUM', 'MANUM'),
    )

    op.create_table('AUFK',
        sa.Column('AUFNR', sa.Text(), primary_key=True),
        sa.Column('QMNUM', sa.Text(), sa.ForeignKey('QMEL.QMNUM')),
        sa.Column('AUART', sa.Text(), nullable=False),
        sa.Column('KTEXT', sa.Text()),
        sa.Column('GLTRP', sa.Text()),
        sa.Column('GLTRS', sa.Text()),
    )

    op.create_table('AFVC',
        sa.Column('AUFNR', sa.Text(), sa.ForeignKey('AUFK.AUFNR')),
        sa.Column('VORNR', sa.Text()),
        sa.Column('ARBPL', sa.Text()),
        sa.Column('STEUS', sa.Text()),
        sa.Column('DAUER', sa.Text()),
        sa.Column('DAUERE', sa.Text()),
        sa.PrimaryKeyConstraint('AUFNR', 'VORNR'),
    )

    op.create_table('AFVC_TEXT',
        sa.Column('AUFNR', sa.Text()),
        sa.Column('VORNR', sa.Text()),
        sa.Column('SPRAS', sa.Text()),
        sa.Column('LTXA1', sa.Text()),
        sa.PrimaryKeyConstraint('AUFNR', 'VORNR', 'SPRAS'),
        sa.ForeignKeyConstraint(['AUFNR', 'VORNR'], ['AFVC.AUFNR', 'AFVC.VORNR']),
    )

    op.create_table('RESB',
        sa.Column('AUFNR', sa.Text()),
        sa.Column('VORNR', sa.Text()),
        sa.Column('MATNR', sa.Text()),
        sa.Column('MENGE', sa.Float()),
        sa.Column('MEINS', sa.Text()),
        sa.PrimaryKeyConstraint('AUFNR', 'VORNR', 'MATNR'),
        sa.ForeignKeyConstraint(['AUFNR', 'VORNR'], ['AFVC.AUFNR', 'AFVC.VORNR']),
    )

    op.create_table('MAKT',
        sa.Column('MATNR', sa.Text()),
        sa.Column('SPRAS', sa.Text()),
        sa.Column('MAKTX', sa.Text()),
        sa.PrimaryKeyConstraint('MATNR', 'SPRAS'),
    )

    op.create_table('EQUI',
        sa.Column('EQUNR', sa.Text(), primary_key=True),
        sa.Column('EQART', sa.Text()),
        sa.Column('EQTYP', sa.Text()),
        sa.Column('ERDAT', sa.Text()),
        sa.Column('ERNAM', sa.Text()),
        sa.Column('HERST', sa.Text()),
        sa.Column('TYPBZ', sa.Text()),
        sa.Column('BAESSION', sa.Text()),
        sa.Column('GEWRK', sa.Text()),
        sa.Column('TPLNR', sa.Text()),
        sa.Column('INBDT', sa.Text()),
        sa.Column('ANSDT', sa.Text()),
        sa.Column('ACTIVE', sa.Text(), server_default='X'),
    )

    op.create_table('EQKT',
        sa.Column('EQUNR', sa.Text(), sa.ForeignKey('EQUI.EQUNR')),
        sa.Column('SPRAS', sa.Text()),
        sa.Column('EQKTX', sa.Text()),
        sa.PrimaryKeyConstraint('EQUNR', 'SPRAS'),
    )

    op.create_table('IFLOT',
        sa.Column('TPLNR', sa.Text(), primary_key=True),
        sa.Column('FLESSION', sa.Text()),
        sa.Column('ERDAT', sa.Text()),
        sa.Column('ERNAM', sa.Text()),
        sa.Column('IESSION', sa.Text()),
        sa.Column('PESSION', sa.Text()),
        sa.Column('ACTIVE', sa.Text(), server_default='X'),
    )

    op.create_table('IFLOTX',
        sa.Column('TPLNR', sa.Text(), sa.ForeignKey('IFLOT.TPLNR')),
        sa.Column('SPRAS', sa.Text()),
        sa.Column('PLTXT', sa.Text()),
        sa.PrimaryKeyConstraint('TPLNR', 'SPRAS'),
    )

    # FDA Compliance Tables
    op.create_table('CDHDR',
        sa.Column('CHANGENR', sa.Text(), primary_key=True),
        sa.Column('OBJECTCLAS', sa.Text(), nullable=False),
        sa.Column('OBJECTID', sa.Text(), nullable=False),
        sa.Column('USERNAME', sa.Text(), nullable=False),
        sa.Column('UDATE', sa.Text(), nullable=False),
        sa.Column('UTIME', sa.Text(), nullable=False),
        sa.Column('TCODE', sa.Text()),
        sa.Column('CHANGE_IND', sa.Text()),
        sa.Column('LANGU', sa.Text(), server_default='en'),
    )

    op.create_table('CDPOS',
        sa.Column('CHANGENR', sa.Text(), sa.ForeignKey('CDHDR.CHANGENR')),
        sa.Column('TABNAME', sa.Text(), nullable=False),
        sa.Column('TABKEY', sa.Text(), nullable=False),
        sa.Column('FNAME', sa.Text(), nullable=False),
        sa.Column('VALUE_NEW', sa.Text()),
        sa.Column('VALUE_OLD', sa.Text()),
        sa.Column('CHNGIND', sa.Text()),
        sa.PrimaryKeyConstraint('CHANGENR', 'TABNAME', 'TABKEY', 'FNAME'),
    )

    op.create_table('JEST',
        sa.Column('OBJNR', sa.Text()),
        sa.Column('STAT', sa.Text()),
        sa.Column('INACT', sa.Text(), server_default=''),
        sa.Column('CHGNR', sa.Text()),
        sa.PrimaryKeyConstraint('OBJNR', 'STAT'),
    )

    op.create_table('TJ02T',
        sa.Column('ISTAT', sa.Text()),
        sa.Column('SPRAS', sa.Text()),
        sa.Column('TXT04', sa.Text()),
        sa.Column('TXT30', sa.Text()),
        sa.PrimaryKeyConstraint('ISTAT', 'SPRAS'),
    )

    op.create_table('AFRU',
        sa.Column('RUESSION', sa.Text(), primary_key=True),
        sa.Column('AUFNR', sa.Text(), sa.ForeignKey('AUFK.AUFNR'), nullable=False),
        sa.Column('VORNR', sa.Text()),
        sa.Column('ARBID', sa.Text()),
        sa.Column('WERKS', sa.Text()),
        sa.Column('BUDAT', sa.Text()),
        sa.Column('ISDD', sa.Text()),
        sa.Column('ISDZ', sa.Text()),
        sa.Column('IEDD', sa.Text()),
        sa.Column('IEDZ', sa.Text()),
        sa.Column('ARBEI', sa.Float()),
        sa.Column('ISMNW', sa.Float()),
        sa.Column('ISMNE', sa.Text()),
        sa.Column('AUFPL', sa.Text()),
        sa.Column('APLZL', sa.Text()),
        sa.Column('STOKZ', sa.Text()),
        sa.Column('STEFB', sa.Text()),
        sa.Column('LTXA1', sa.Text()),
        sa.Column('AUERU', sa.Text()),
        sa.Column('ERNAM', sa.Text()),
        sa.Column('ERDAT', sa.Text()),
        sa.Column('ERZET', sa.Text()),
    )

    op.create_table('QMIH',
        sa.Column('QMNUM', sa.Text(), sa.ForeignKey('QMEL.QMNUM')),
        sa.Column('HESSION', sa.Text()),
        sa.Column('ERDAT', sa.Text()),
        sa.Column('ERZET', sa.Text()),
        sa.Column('ERNAM', sa.Text()),
        sa.Column('QMART', sa.Text()),
        sa.Column('PRIESSION', sa.Text()),
        sa.Column('STAT', sa.Text()),
        sa.Column('OTGRP', sa.Text()),
        sa.Column('FESSION', sa.Text()),
        sa.Column('URGRP', sa.Text()),
        sa.Column('MESSION', sa.Text()),
        sa.Column('CHANGE_REASON', sa.Text()),
        sa.PrimaryKeyConstraint('QMNUM', 'HESSION'),
    )

    op.create_table('QMCATALOG',
        sa.Column('KATESSION', sa.Text()),
        sa.Column('CODEGRUPPE', sa.Text()),
        sa.Column('CODE', sa.Text()),
        sa.Column('SPRAS', sa.Text()),
        sa.Column('KUESSION', sa.Text()),
        sa.Column('ACTIVE', sa.Text(), server_default='X'),
        sa.Column('VALID_FROM', sa.Text()),
        sa.Column('VALID_TO', sa.Text()),
        sa.PrimaryKeyConstraint('KATESSION', 'CODEGRUPPE', 'CODE', 'SPRAS'),
    )

    # Indexes
    op.create_index('idx_qmel_equnr', 'QMEL', ['EQUNR'])
    op.create_index('idx_qmel_tplnr', 'QMEL', ['TPLNR'])
    op.create_index('idx_qmel_erdat', 'QMEL', ['ERDAT'])
    op.create_index('idx_aufk_qmnum', 'AUFK', ['QMNUM'])
    op.create_index('idx_notif_content_qmnum', 'NOTIF_CONTENT', ['QMNUM'])
    op.create_index('idx_qmfe_qmnum', 'QMFE', ['QMNUM'])
    op.create_index('idx_qmfe_text_qmnum', 'QMFE_TEXT', ['QMNUM'])
    op.create_index('idx_qmur_qmnum', 'QMUR', ['QMNUM'])
    op.create_index('idx_qmur_text_qmnum', 'QMUR_TEXT', ['QMNUM'])
    op.create_index('idx_qmak_qmnum', 'QMAK', ['QMNUM'])
    op.create_index('idx_afvc_aufnr', 'AFVC', ['AUFNR'])
    op.create_index('idx_afvc_text_aufnr', 'AFVC_TEXT', ['AUFNR'])
    op.create_index('idx_resb_aufnr', 'RESB', ['AUFNR'])
    op.create_index('idx_makt_matnr', 'MAKT', ['MATNR'])
    op.create_index('idx_cdhdr_objectid', 'CDHDR', ['OBJECTID'])
    op.create_index('idx_cdhdr_objectclas', 'CDHDR', ['OBJECTCLAS'])
    op.create_index('idx_cdhdr_username', 'CDHDR', ['USERNAME'])
    op.create_index('idx_cdhdr_udate', 'CDHDR', ['UDATE'])
    op.create_index('idx_cdpos_changenr', 'CDPOS', ['CHANGENR'])
    op.create_index('idx_jest_objnr', 'JEST', ['OBJNR'])
    op.create_index('idx_afru_aufnr', 'AFRU', ['AUFNR'])
    op.create_index('idx_afru_budat', 'AFRU', ['BUDAT'])
    op.create_index('idx_qmih_qmnum', 'QMIH', ['QMNUM'])
    op.create_index('idx_equi_tplnr', 'EQUI', ['TPLNR'])
    op.create_index('idx_iflot_parent', 'IFLOT', ['PESSION'])


def downgrade() -> None:
    """Drop all baseline tables."""
    tables = [
        'IFLOTX', 'IFLOT', 'EQKT', 'EQUI', 'QMCATALOG', 'QMIH',
        'AFRU', 'TJ02T', 'JEST', 'CDPOS', 'CDHDR',
        'MAKT', 'RESB', 'AFVC_TEXT', 'AFVC', 'AUFK',
        'QMAK', 'QMUR_TEXT', 'QMUR', 'QMFE_TEXT', 'QMFE',
        'NOTIF_CONTENT', 'QMEL',
    ]
    for table in tables:
        op.drop_table(table)
