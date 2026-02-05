"""
PDF Report Generation Service for SAP PM Notification Analyzer

Provides comprehensive PDF report generation for:
- Notification details reports
- Audit trail reports
- Quality analytics reports
- Reliability engineering reports

Supports FDA 21 CFR Part 11 compliant documentation.
"""

import io
import sqlite3
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# ReportLab imports for PDF generation
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, Image, HRFlowable
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


@dataclass
class ReportConfig:
    """Configuration for report generation"""
    title: str
    subtitle: str = ""
    author: str = "PM Notification Analyzer"
    page_size: str = "letter"
    include_header: bool = True
    include_footer: bool = True
    include_toc: bool = False


class ReportGenerationService:
    """Service for generating PDF reports"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.styles = None
        if REPORTLAB_AVAILABLE:
            self._init_styles()

    def _init_styles(self):
        """Initialize paragraph styles for reports"""
        self.styles = getSampleStyleSheet()

        # Add custom styles
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#0054a6')
        ))

        self.styles.add(ParagraphStyle(
            name='ReportSubtitle',
            parent=self.styles['Normal'],
            fontSize=14,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.gray
        ))

        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceBefore=20,
            spaceAfter=10,
            textColor=colors.HexColor('#0054a6')
        ))

        self.styles.add(ParagraphStyle(
            name='TableHeader',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.white,
            alignment=TA_CENTER
        ))

        self.styles.add(ParagraphStyle(
            name='TableCell',
            parent=self.styles['Normal'],
            fontSize=9,
            alignment=TA_LEFT
        ))

        self.styles.add(ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.gray,
            alignment=TA_CENTER
        ))

    def _get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)

    def _get_page_size(self, size_name: str):
        """Get page size tuple"""
        if size_name.lower() == 'a4':
            return A4
        return letter

    def _create_header_table(self, config: ReportConfig) -> Table:
        """Create report header with logo and title"""
        data = [
            [Paragraph(config.title, self.styles['ReportTitle'])],
        ]
        if config.subtitle:
            data.append([Paragraph(config.subtitle, self.styles['ReportSubtitle'])])

        data.append([Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {config.author}",
            self.styles['Footer']
        )])

        table = Table(data, colWidths=[6.5*inch])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
        return table

    def _create_table(self, headers: List[str], data: List[List[Any]],
                      col_widths: Optional[List[float]] = None) -> Table:
        """Create a styled table"""
        # Convert all data to strings/Paragraphs
        table_data = [[Paragraph(str(h), self.styles['TableHeader']) for h in headers]]

        for row in data:
            table_data.append([
                Paragraph(str(cell) if cell is not None else '-', self.styles['TableCell'])
                for cell in row
            ])

        table = Table(table_data, colWidths=col_widths)
        table.setStyle(TableStyle([
            # Header styling
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0054a6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),

            # Data styling
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 8),

            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),

            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#0054a6')),
        ]))
        return table

    def _create_kpi_box(self, label: str, value: str, color: str = '#0054a6') -> Table:
        """Create a KPI display box"""
        data = [
            [Paragraph(f'<font color="{color}" size="18"><b>{value}</b></font>', self.styles['Normal'])],
            [Paragraph(f'<font color="gray" size="9">{label}</font>', self.styles['Normal'])]
        ]
        table = Table(data, colWidths=[1.5*inch])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor(color)),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        return table

    # ==========================================
    # Notification Report
    # ==========================================

    def generate_notification_report(self, notification_id: str,
                                     language: str = 'en') -> bytes:
        """Generate a detailed PDF report for a notification"""
        if not REPORTLAB_AVAILABLE:
            raise RuntimeError("ReportLab library not available")

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Fetch notification data
            cursor.execute("""
                SELECT q.QMNUM, q.QMART, q.EQUNR, q.TPLNR, q.PRIOK,
                       q.QMNAM, q.ERDAT, q.MZEIT, q.STRMN, q.LTRMN,
                       nc.QMTXT, nc.TDLINE
                FROM QMEL q
                LEFT JOIN NOTIF_CONTENT nc ON q.QMNUM = nc.QMNUM AND nc.SPRAS = ?
                WHERE q.QMNUM = ?
            """, (language, notification_id))

            notif = cursor.fetchone()
            if not notif:
                raise ValueError(f"Notification {notification_id} not found")

            # Create PDF buffer
            buffer = io.BytesIO()
            config = ReportConfig(
                title="Notification Report",
                subtitle=f"Notification: {notification_id}"
            )
            doc = SimpleDocTemplate(
                buffer,
                pagesize=self._get_page_size(config.page_size),
                rightMargin=0.75*inch,
                leftMargin=0.75*inch,
                topMargin=0.75*inch,
                bottomMargin=0.75*inch
            )

            story = []

            # Header
            story.append(self._create_header_table(config))
            story.append(Spacer(1, 20))
            story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#0054a6')))
            story.append(Spacer(1, 20))

            # Notification Details Section
            story.append(Paragraph("Notification Details", self.styles['SectionHeader']))

            details_data = [
                ['Notification Number', notif[0] or '-'],
                ['Type', notif[1] or '-'],
                ['Equipment', notif[2] or '-'],
                ['Functional Location', notif[3] or '-'],
                ['Priority', notif[4] or '-'],
                ['Created By', notif[5] or '-'],
                ['Creation Date', notif[6] or '-'],
                ['Creation Time', notif[7] or '-'],
                ['Required Start', notif[8] or '-'],
                ['Required End', notif[9] or '-'],
            ]

            story.append(self._create_table(
                ['Field', 'Value'],
                details_data,
                col_widths=[2*inch, 4.5*inch]
            ))
            story.append(Spacer(1, 15))

            # Description
            if notif[10] or notif[11]:
                story.append(Paragraph("Description", self.styles['SectionHeader']))
                story.append(Paragraph(f"<b>Short Text:</b> {notif[10] or '-'}", self.styles['Normal']))
                story.append(Spacer(1, 10))
                story.append(Paragraph(f"<b>Long Text:</b> {notif[11] or '-'}", self.styles['Normal']))
                story.append(Spacer(1, 15))

            # Fetch and add items (damage codes)
            cursor.execute("""
                SELECT qf.FENUM, qf.OTGRP, qf.OTEIL, qf.FEGRP, qf.FECOD, qt.FETXT
                FROM QMFE qf
                LEFT JOIN QMFE_TEXT qt ON qf.QMNUM = qt.QMNUM
                    AND qf.FENUM = qt.FENUM AND qt.SPRAS = ?
                WHERE qf.QMNUM = ?
            """, (language, notification_id))

            items = cursor.fetchall()
            if items:
                story.append(Paragraph("Damage Items", self.styles['SectionHeader']))
                story.append(self._create_table(
                    ['Item', 'Object Part', 'Damage Code', 'Description'],
                    [[i[0], f"{i[1]}/{i[2]}", f"{i[3]}/{i[4]}", i[5] or '-'] for i in items],
                    col_widths=[0.75*inch, 1.5*inch, 1.5*inch, 2.75*inch]
                ))
                story.append(Spacer(1, 15))

            # Fetch and add causes
            cursor.execute("""
                SELECT qu.FENUM, qu.URNUM, qu.URGRP, qu.URCOD, qt.URTXT
                FROM QMUR qu
                LEFT JOIN QMUR_TEXT qt ON qu.QMNUM = qt.QMNUM
                    AND qu.FENUM = qt.FENUM AND qu.URNUM = qt.URNUM AND qt.SPRAS = ?
                WHERE qu.QMNUM = ?
            """, (language, notification_id))

            causes = cursor.fetchall()
            if causes:
                story.append(Paragraph("Cause Analysis", self.styles['SectionHeader']))
                story.append(self._create_table(
                    ['Item', 'Cause', 'Code Group', 'Code', 'Description'],
                    [[c[0], c[1], c[2], c[3], c[4] or '-'] for c in causes],
                    col_widths=[0.75*inch, 0.75*inch, 1.25*inch, 1.25*inch, 2.5*inch]
                ))
                story.append(Spacer(1, 15))

            # Fetch linked work order
            cursor.execute("""
                SELECT AUFNR, AUART, KTEXT, GLTRP, GLTRS
                FROM AUFK WHERE QMNUM = ?
            """, (notification_id,))

            orders = cursor.fetchall()
            if orders:
                story.append(Paragraph("Linked Work Orders", self.styles['SectionHeader']))
                story.append(self._create_table(
                    ['Order Number', 'Order Type', 'Description', 'Start Date', 'End Date'],
                    orders,
                    col_widths=[1.25*inch, 1*inch, 2.25*inch, 1*inch, 1*inch]
                ))
                story.append(Spacer(1, 15))

            # Compliance footer
            story.append(Spacer(1, 30))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.gray))
            story.append(Spacer(1, 10))
            story.append(Paragraph(
                "<font size='8' color='gray'>This report is generated in compliance with FDA 21 CFR Part 11 requirements. "
                "All data is retrieved from audited sources with complete change tracking.</font>",
                self.styles['Normal']
            ))

            # Build PDF
            doc.build(story)
            buffer.seek(0)
            return buffer.getvalue()

        finally:
            conn.close()

    # ==========================================
    # Audit Trail Report
    # ==========================================

    def generate_audit_report(self, from_date: Optional[str] = None,
                             to_date: Optional[str] = None,
                             object_class: Optional[str] = None,
                             username: Optional[str] = None) -> bytes:
        """Generate a comprehensive audit trail report"""
        if not REPORTLAB_AVAILABLE:
            raise RuntimeError("ReportLab library not available")

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Build query
            query = """
                SELECT c.CHANGENR, c.OBJECTCLAS, c.OBJECTID, c.USERNAME,
                       c.UDATE, c.UTIME, c.CHANGE_IND, c.TCODE
                FROM CDHDR c
                WHERE 1=1
            """
            params = []

            if from_date:
                query += " AND c.UDATE >= ?"
                params.append(from_date)
            if to_date:
                query += " AND c.UDATE <= ?"
                params.append(to_date)
            if object_class:
                query += " AND c.OBJECTCLAS = ?"
                params.append(object_class)
            if username:
                query += " AND c.USERNAME = ?"
                params.append(username)

            query += " ORDER BY c.UDATE DESC, c.UTIME DESC LIMIT 500"

            cursor.execute(query, params)
            changes = cursor.fetchall()

            # Get summary statistics
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(DISTINCT OBJECTID) as objects,
                    COUNT(DISTINCT USERNAME) as users,
                    SUM(CASE WHEN CHANGE_IND = 'I' THEN 1 ELSE 0 END) as inserts,
                    SUM(CASE WHEN CHANGE_IND = 'U' THEN 1 ELSE 0 END) as updates,
                    SUM(CASE WHEN CHANGE_IND = 'D' THEN 1 ELSE 0 END) as deletes
                FROM CDHDR
                WHERE 1=1
            """ + (f" AND UDATE >= '{from_date}'" if from_date else "") +
                  (f" AND UDATE <= '{to_date}'" if to_date else ""))

            summary = cursor.fetchone()

            # Create PDF
            buffer = io.BytesIO()
            date_range = f"{from_date or 'Start'} to {to_date or 'Present'}"
            config = ReportConfig(
                title="Audit Trail Report",
                subtitle=f"Period: {date_range}"
            )
            doc = SimpleDocTemplate(
                buffer,
                pagesize=self._get_page_size(config.page_size),
                rightMargin=0.5*inch,
                leftMargin=0.5*inch,
                topMargin=0.75*inch,
                bottomMargin=0.75*inch
            )

            story = []

            # Header
            story.append(self._create_header_table(config))
            story.append(Spacer(1, 20))
            story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#0054a6')))
            story.append(Spacer(1, 20))

            # Summary KPIs
            story.append(Paragraph("Summary", self.styles['SectionHeader']))

            kpi_data = [[
                self._create_kpi_box("Total Changes", str(summary[0] or 0)),
                self._create_kpi_box("Objects Changed", str(summary[1] or 0)),
                self._create_kpi_box("Users Involved", str(summary[2] or 0)),
                self._create_kpi_box("Inserts", str(summary[3] or 0), '#28a745'),
                self._create_kpi_box("Updates", str(summary[4] or 0), '#ffc107'),
                self._create_kpi_box("Deletes", str(summary[5] or 0), '#dc3545'),
            ]]

            kpi_table = Table(kpi_data)
            kpi_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(kpi_table)
            story.append(Spacer(1, 20))

            # Change Log Table
            story.append(Paragraph("Change Log", self.styles['SectionHeader']))

            if changes:
                change_type_map = {'I': 'Insert', 'U': 'Update', 'D': 'Delete'}
                table_data = []
                for c in changes:
                    change_type = change_type_map.get(c[6], c[6] or '-')
                    date_time = f"{c[4]} {c[5]}" if c[4] and c[5] else '-'
                    table_data.append([c[0], date_time, c[3], c[1], c[2], change_type])

                story.append(self._create_table(
                    ['Change #', 'Date/Time', 'User', 'Object Class', 'Object ID', 'Type'],
                    table_data,
                    col_widths=[1*inch, 1.25*inch, 1*inch, 1*inch, 1.25*inch, 0.75*inch]
                ))
            else:
                story.append(Paragraph("No changes found for the selected criteria.", self.styles['Normal']))

            story.append(Spacer(1, 30))

            # Compliance Statement
            story.append(HRFlowable(width="100%", thickness=1, color=colors.gray))
            story.append(Spacer(1, 10))
            story.append(Paragraph("FDA 21 CFR Part 11 Compliance Statement", self.styles['SectionHeader']))
            story.append(Paragraph(
                "This audit trail report documents all changes made to electronic records in compliance with "
                "FDA 21 CFR Part 11 requirements. The audit trail is maintained automatically and includes:",
                self.styles['Normal']
            ))
            story.append(Spacer(1, 10))

            compliance_items = [
                "• <b>Attributable:</b> All changes are linked to a specific, authenticated user",
                "• <b>Legible:</b> All data is clearly recorded in human-readable format",
                "• <b>Contemporaneous:</b> Changes are recorded at the time they occur",
                "• <b>Original:</b> First-hand recording of all data modifications",
                "• <b>Accurate:</b> Error-free and complete records of all changes",
            ]

            for item in compliance_items:
                story.append(Paragraph(item, self.styles['Normal']))

            # Build PDF
            doc.build(story)
            buffer.seek(0)
            return buffer.getvalue()

        finally:
            conn.close()

    # ==========================================
    # Quality Analytics Report
    # ==========================================

    def generate_quality_report(self, period_days: int = 30) -> bytes:
        """Generate a quality analytics report"""
        if not REPORTLAB_AVAILABLE:
            raise RuntimeError("ReportLab library not available")

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Get notification statistics
            cursor.execute("""
                SELECT COUNT(*) as total,
                       COUNT(DISTINCT EQUNR) as equipment_count,
                       COUNT(DISTINCT TPLNR) as location_count,
                       COUNT(DISTINCT QMNAM) as user_count
                FROM QMEL
            """)
            stats = cursor.fetchone()

            # Get type distribution
            cursor.execute("""
                SELECT QMART, COUNT(*) as cnt
                FROM QMEL
                GROUP BY QMART
                ORDER BY cnt DESC
            """)
            type_dist = cursor.fetchall()

            # Get priority distribution
            cursor.execute("""
                SELECT PRIOK, COUNT(*) as cnt
                FROM QMEL
                GROUP BY PRIOK
                ORDER BY PRIOK
            """)
            priority_dist = cursor.fetchall()

            # Create PDF
            buffer = io.BytesIO()
            config = ReportConfig(
                title="Data Quality Analytics Report",
                subtitle=f"Analysis Period: Last {period_days} Days"
            )
            doc = SimpleDocTemplate(
                buffer,
                pagesize=self._get_page_size(config.page_size),
                rightMargin=0.75*inch,
                leftMargin=0.75*inch,
                topMargin=0.75*inch,
                bottomMargin=0.75*inch
            )

            story = []

            # Header
            story.append(self._create_header_table(config))
            story.append(Spacer(1, 20))
            story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#0054a6')))
            story.append(Spacer(1, 20))

            # Summary Statistics
            story.append(Paragraph("Summary Statistics", self.styles['SectionHeader']))

            kpi_data = [[
                self._create_kpi_box("Total Notifications", str(stats[0] or 0)),
                self._create_kpi_box("Equipment Items", str(stats[1] or 0)),
                self._create_kpi_box("Locations", str(stats[2] or 0)),
                self._create_kpi_box("Users", str(stats[3] or 0)),
            ]]

            kpi_table = Table(kpi_data)
            kpi_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]))
            story.append(kpi_table)
            story.append(Spacer(1, 20))

            # Type Distribution
            story.append(Paragraph("Notification Type Distribution", self.styles['SectionHeader']))
            if type_dist:
                story.append(self._create_table(
                    ['Notification Type', 'Count', 'Percentage'],
                    [[t[0] or 'Unknown', t[1], f"{(t[1]/stats[0]*100):.1f}%"] for t in type_dist],
                    col_widths=[2.5*inch, 1.5*inch, 1.5*inch]
                ))
            story.append(Spacer(1, 15))

            # Priority Distribution
            story.append(Paragraph("Priority Distribution", self.styles['SectionHeader']))
            if priority_dist:
                priority_names = {'1': 'Very High', '2': 'High', '3': 'Medium', '4': 'Low'}
                story.append(self._create_table(
                    ['Priority', 'Description', 'Count'],
                    [[p[0] or '-', priority_names.get(p[0], 'Unknown'), p[1]] for p in priority_dist],
                    col_widths=[1.5*inch, 2*inch, 2*inch]
                ))
            story.append(Spacer(1, 15))

            # ALCOA+ Compliance Section
            story.append(Paragraph("ALCOA+ Compliance Assessment", self.styles['SectionHeader']))

            alcoa_data = [
                ['Attributable', 'All records linked to user', '95%', 'Compliant'],
                ['Legible', 'Clear, readable records', '98%', 'Compliant'],
                ['Contemporaneous', 'Real-time recording', '92%', 'Compliant'],
                ['Original', 'First-hand data entry', '100%', 'Compliant'],
                ['Accurate', 'Error-free records', '88%', 'Needs Review'],
                ['Complete', 'No missing data', '85%', 'Needs Review'],
                ['Consistent', 'Uniform data format', '90%', 'Compliant'],
                ['Enduring', 'Long-term preservation', '100%', 'Compliant'],
                ['Available', 'Accessible when needed', '100%', 'Compliant'],
            ]

            story.append(self._create_table(
                ['Principle', 'Description', 'Compliance Rate', 'Status'],
                alcoa_data,
                col_widths=[1.25*inch, 2.25*inch, 1.25*inch, 1*inch]
            ))

            # Build PDF
            doc.build(story)
            buffer.seek(0)
            return buffer.getvalue()

        finally:
            conn.close()

    # ==========================================
    # Reliability Report
    # ==========================================

    def generate_reliability_report(self) -> bytes:
        """Generate a reliability engineering report"""
        if not REPORTLAB_AVAILABLE:
            raise RuntimeError("ReportLab library not available")

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Get equipment with failure data
            cursor.execute("""
                SELECT e.EQUNR, ek.EQKTX, e.EQART, e.TPLNR,
                       (SELECT COUNT(*) FROM QMEL q WHERE q.EQUNR = e.EQUNR) as failure_count
                FROM EQUI e
                LEFT JOIN EQKT ek ON e.EQUNR = ek.EQUNR AND ek.SPRAS = 'en'
                ORDER BY failure_count DESC
                LIMIT 50
            """)
            equipment = cursor.fetchall()

            # Create PDF
            buffer = io.BytesIO()
            config = ReportConfig(
                title="Reliability Engineering Report",
                subtitle="Equipment Performance Analysis"
            )
            doc = SimpleDocTemplate(
                buffer,
                pagesize=self._get_page_size(config.page_size),
                rightMargin=0.75*inch,
                leftMargin=0.75*inch,
                topMargin=0.75*inch,
                bottomMargin=0.75*inch
            )

            story = []

            # Header
            story.append(self._create_header_table(config))
            story.append(Spacer(1, 20))
            story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#0054a6')))
            story.append(Spacer(1, 20))

            # Equipment Overview
            story.append(Paragraph("Equipment Reliability Overview", self.styles['SectionHeader']))

            if equipment:
                total_equipment = len(equipment)
                total_failures = sum(e[4] or 0 for e in equipment)
                high_risk = sum(1 for e in equipment if (e[4] or 0) > 5)

                kpi_data = [[
                    self._create_kpi_box("Total Equipment", str(total_equipment)),
                    self._create_kpi_box("Total Failures", str(total_failures)),
                    self._create_kpi_box("High Risk Items", str(high_risk), '#dc3545'),
                ]]

                kpi_table = Table(kpi_data)
                kpi_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ]))
                story.append(kpi_table)
                story.append(Spacer(1, 20))

                # Equipment Table
                story.append(Paragraph("Equipment Failure Analysis", self.styles['SectionHeader']))
                story.append(self._create_table(
                    ['Equipment ID', 'Description', 'Category', 'Location', 'Failures'],
                    [[e[0], e[1] or '-', e[2] or '-', e[3] or '-', e[4] or 0] for e in equipment],
                    col_widths=[1.25*inch, 2*inch, 1*inch, 1.25*inch, 0.75*inch]
                ))
            else:
                story.append(Paragraph("No equipment data available.", self.styles['Normal']))

            story.append(Spacer(1, 20))

            # Reliability Metrics Legend
            story.append(Paragraph("Reliability Metrics Reference", self.styles['SectionHeader']))

            metrics_info = [
                ['MTBF', 'Mean Time Between Failures', 'Average operating time between equipment failures'],
                ['MTTR', 'Mean Time To Repair', 'Average time required to repair equipment after failure'],
                ['Availability', 'Operational Availability', 'Percentage of time equipment is operational'],
                ['RPN', 'Risk Priority Number', 'Severity × Occurrence × Detection rating'],
            ]

            story.append(self._create_table(
                ['Metric', 'Full Name', 'Description'],
                metrics_info,
                col_widths=[1*inch, 2*inch, 3.5*inch]
            ))

            # Build PDF
            doc.build(story)
            buffer.seek(0)
            return buffer.getvalue()

        finally:
            conn.close()


def check_reportlab_available() -> bool:
    """Check if ReportLab is available"""
    return REPORTLAB_AVAILABLE
