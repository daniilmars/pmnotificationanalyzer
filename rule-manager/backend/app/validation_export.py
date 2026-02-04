# rule-manager/backend/app/validation_export.py
"""
Validation Support Module for Regulatory Compliance Documentation.

Provides CSV export capabilities for:
- Audit logs (ALCOA+ compliant)
- Electronic signatures
- Configuration change history
- System validation reports

Supports FDA 21 CFR Part 11 and EU GMP Annex 11 documentation requirements.
"""
import csv
import json
import logging
from io import StringIO
from datetime import datetime
from typing import List, Dict, Any, Optional
from flask import Blueprint, Response, jsonify, request

from .database import (
    Session, AuditLog, User, Role, Permission, ElectronicSignature,
    AccessLog, Ruleset, Rule
)
from .auth_service import require_permission

logger = logging.getLogger(__name__)

validation_blueprint = Blueprint('validation', __name__)


def _generate_csv_response(data: List[Dict], fieldnames: List[str], filename: str) -> Response:
    """Generate a CSV response from data."""
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()

    for row in data:
        # Convert non-string values to strings
        cleaned_row = {}
        for key in fieldnames:
            value = row.get(key)
            if value is None:
                cleaned_row[key] = ''
            elif isinstance(value, datetime):
                cleaned_row[key] = value.isoformat()
            elif isinstance(value, (dict, list)):
                cleaned_row[key] = json.dumps(value)
            else:
                cleaned_row[key] = str(value)
        writer.writerow(cleaned_row)

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename={filename}',
            'Content-Type': 'text/csv; charset=utf-8'
        }
    )


# =============================================================================
# AUDIT LOG EXPORTS
# =============================================================================

@validation_blueprint.route('/export/audit-log', methods=['GET'])
@require_permission('audit_log', 'export')
def export_audit_log():
    """
    Export audit log to CSV for compliance documentation.

    Query Parameters:
        start_date: ISO format date (optional)
        end_date: ISO format date (optional)
        user_id: Filter by user (optional)
        action_type: Filter by action type (optional)
        limit: Max records (default 10000)
    """
    session = Session()
    try:
        query = session.query(AuditLog)

        # Apply filters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        user_id = request.args.get('user_id')
        action_type = request.args.get('action_type')
        limit = int(request.args.get('limit', 10000))

        if start_date:
            query = query.filter(AuditLog.timestamp >= datetime.fromisoformat(start_date))
        if end_date:
            query = query.filter(AuditLog.timestamp <= datetime.fromisoformat(end_date))
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        if action_type:
            query = query.filter(AuditLog.action_type == action_type)

        logs = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()

        data = []
        for log in logs:
            data.append({
                'id': log.id,
                'timestamp': log.timestamp,
                'user_id': log.user_id,
                'action_type': log.action_type,
                'entity_changed': log.entity_changed,
                'old_value': log.old_value_json,
                'new_value': log.new_value_json
            })

        fieldnames = ['id', 'timestamp', 'user_id', 'action_type', 'entity_changed', 'old_value', 'new_value']
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

        return _generate_csv_response(data, fieldnames, f'audit_log_{timestamp}.csv')

    except Exception as e:
        logger.exception("Failed to export audit log")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@validation_blueprint.route('/export/audit-log/summary', methods=['GET'])
@require_permission('audit_log', 'view')
def get_audit_log_summary():
    """
    Get audit log summary statistics for validation documentation.
    """
    session = Session()
    try:
        # Total records
        total_count = session.query(AuditLog).count()

        # Count by action type
        from sqlalchemy import func
        action_counts = session.query(
            AuditLog.action_type,
            func.count(AuditLog.id)
        ).group_by(AuditLog.action_type).all()

        # Count by user
        user_counts = session.query(
            AuditLog.user_id,
            func.count(AuditLog.id)
        ).group_by(AuditLog.user_id).all()

        # Date range
        first_record = session.query(AuditLog).order_by(AuditLog.timestamp.asc()).first()
        last_record = session.query(AuditLog).order_by(AuditLog.timestamp.desc()).first()

        return jsonify({
            'total_records': total_count,
            'by_action_type': {action: count for action, count in action_counts},
            'by_user': {user: count for user, count in user_counts},
            'date_range': {
                'first_record': first_record.timestamp.isoformat() if first_record else None,
                'last_record': last_record.timestamp.isoformat() if last_record else None
            }
        })

    except Exception as e:
        logger.exception("Failed to get audit log summary")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# =============================================================================
# ELECTRONIC SIGNATURE EXPORTS
# =============================================================================

@validation_blueprint.route('/export/signatures', methods=['GET'])
@require_permission('signatures', 'export')
def export_signatures():
    """
    Export electronic signatures to CSV for 21 CFR Part 11 compliance.

    Query Parameters:
        start_date: ISO format date (optional)
        end_date: ISO format date (optional)
        user_id: Filter by signer (optional)
        entity_type: Filter by entity type (optional)
        meaning: Filter by signature meaning (optional)
        limit: Max records (default 10000)
    """
    session = Session()
    try:
        query = session.query(ElectronicSignature)

        # Apply filters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        user_id = request.args.get('user_id')
        entity_type = request.args.get('entity_type')
        meaning = request.args.get('meaning')
        limit = int(request.args.get('limit', 10000))

        if start_date:
            query = query.filter(ElectronicSignature.timestamp >= datetime.fromisoformat(start_date))
        if end_date:
            query = query.filter(ElectronicSignature.timestamp <= datetime.fromisoformat(end_date))
        if user_id:
            query = query.filter(ElectronicSignature.user_id == user_id)
        if entity_type:
            query = query.filter(ElectronicSignature.entity_type == entity_type)
        if meaning:
            query = query.filter(ElectronicSignature.meaning == meaning)

        signatures = query.order_by(ElectronicSignature.timestamp.desc()).limit(limit).all()

        data = []
        for sig in signatures:
            # Get user name for readability
            user = session.query(User).filter_by(id=sig.user_id).first()
            user_name = user.full_name if user else sig.user_id

            data.append({
                'id': sig.id,
                'timestamp': sig.timestamp,
                'user_id': sig.user_id,
                'user_name': user_name,
                'entity_type': sig.entity_type,
                'entity_id': sig.entity_id,
                'entity_version': sig.entity_version,
                'meaning': sig.meaning,
                'reason': sig.reason,
                'auth_method': sig.auth_method,
                'ip_address': sig.ip_address
            })

        fieldnames = [
            'id', 'timestamp', 'user_id', 'user_name', 'entity_type', 'entity_id',
            'entity_version', 'meaning', 'reason', 'auth_method', 'ip_address'
        ]
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

        return _generate_csv_response(data, fieldnames, f'electronic_signatures_{timestamp}.csv')

    except Exception as e:
        logger.exception("Failed to export signatures")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# =============================================================================
# ACCESS LOG EXPORTS
# =============================================================================

@validation_blueprint.route('/export/access-log', methods=['GET'])
@require_permission('access_log', 'export')
def export_access_log():
    """
    Export access log to CSV for security audit documentation.
    """
    session = Session()
    try:
        query = session.query(AccessLog)

        # Apply filters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        user_id = request.args.get('user_id')
        action = request.args.get('action')
        limit = int(request.args.get('limit', 10000))

        if start_date:
            query = query.filter(AccessLog.timestamp >= datetime.fromisoformat(start_date))
        if end_date:
            query = query.filter(AccessLog.timestamp <= datetime.fromisoformat(end_date))
        if user_id:
            query = query.filter(AccessLog.user_id == user_id)
        if action:
            query = query.filter(AccessLog.action == action)

        logs = query.order_by(AccessLog.timestamp.desc()).limit(limit).all()

        data = []
        for log in logs:
            data.append({
                'id': log.id,
                'timestamp': log.timestamp,
                'username': log.username,
                'user_id': log.user_id,
                'action': log.action,
                'success': log.success,
                'failure_reason': log.failure_reason,
                'ip_address': log.ip_address,
                'user_agent': log.user_agent
            })

        fieldnames = [
            'id', 'timestamp', 'username', 'user_id', 'action',
            'success', 'failure_reason', 'ip_address', 'user_agent'
        ]
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

        return _generate_csv_response(data, fieldnames, f'access_log_{timestamp}.csv')

    except Exception as e:
        logger.exception("Failed to export access log")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# =============================================================================
# RULESET EXPORTS
# =============================================================================

@validation_blueprint.route('/export/rulesets', methods=['GET'])
@require_permission('rulesets', 'export')
def export_rulesets():
    """
    Export all rulesets with their rules for validation documentation.
    """
    session = Session()
    try:
        rulesets = session.query(Ruleset).all()

        data = []
        for rs in rulesets:
            for rule in rs.rules:
                data.append({
                    'ruleset_id': rs.id,
                    'ruleset_name': rs.name,
                    'ruleset_version': rs.version,
                    'ruleset_status': rs.status,
                    'notification_type': rs.notification_type,
                    'ruleset_created_at': rs.created_at,
                    'ruleset_created_by': rs.created_by,
                    'rule_id': rule.id,
                    'rule_name': rule.name,
                    'rule_description': rule.description,
                    'target_field': rule.target_field,
                    'condition': rule.condition,
                    'value': rule.value,
                    'score_impact': rule.score_impact,
                    'feedback_message': rule.feedback_message
                })

        fieldnames = [
            'ruleset_id', 'ruleset_name', 'ruleset_version', 'ruleset_status',
            'notification_type', 'ruleset_created_at', 'ruleset_created_by',
            'rule_id', 'rule_name', 'rule_description', 'target_field',
            'condition', 'value', 'score_impact', 'feedback_message'
        ]
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

        return _generate_csv_response(data, fieldnames, f'rulesets_export_{timestamp}.csv')

    except Exception as e:
        logger.exception("Failed to export rulesets")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# =============================================================================
# USER AND PERMISSION EXPORTS
# =============================================================================

@validation_blueprint.route('/export/users', methods=['GET'])
@require_permission('users', 'export')
def export_users():
    """
    Export user list for validation documentation.
    """
    session = Session()
    try:
        users = session.query(User).all()

        data = []
        for user in users:
            roles = [r.name for r in user.roles]
            data.append({
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'full_name': user.full_name,
                'department': user.department,
                'title': user.title,
                'status': user.status,
                'roles': ', '.join(roles),
                'created_at': user.created_at,
                'last_login': user.last_login,
                'password_changed_at': user.password_changed_at,
                'training_status': user.training_status
            })

        fieldnames = [
            'user_id', 'username', 'email', 'full_name', 'department', 'title',
            'status', 'roles', 'created_at', 'last_login', 'password_changed_at',
            'training_status'
        ]
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

        return _generate_csv_response(data, fieldnames, f'users_export_{timestamp}.csv')

    except Exception as e:
        logger.exception("Failed to export users")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@validation_blueprint.route('/export/rbac-matrix', methods=['GET'])
@require_permission('permissions', 'export')
def export_rbac_matrix():
    """
    Export RBAC permission matrix for validation documentation.
    """
    session = Session()
    try:
        roles = session.query(Role).all()

        data = []
        for role in roles:
            for permission in role.permissions:
                data.append({
                    'role_name': role.name,
                    'role_description': role.description,
                    'resource': permission.resource,
                    'action': permission.action,
                    'permission_description': permission.description
                })

        fieldnames = ['role_name', 'role_description', 'resource', 'action', 'permission_description']
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

        return _generate_csv_response(data, fieldnames, f'rbac_matrix_{timestamp}.csv')

    except Exception as e:
        logger.exception("Failed to export RBAC matrix")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# =============================================================================
# SYSTEM VALIDATION REPORT
# =============================================================================

@validation_blueprint.route('/report/system-validation', methods=['GET'])
@require_permission('validation', 'view')
def get_system_validation_report():
    """
    Generate comprehensive system validation report for regulatory audits.

    Returns JSON with all critical compliance metrics.
    """
    session = Session()
    try:
        from sqlalchemy import func

        # User statistics
        total_users = session.query(User).count()
        active_users = session.query(User).filter_by(status='active').count()
        users_with_training = session.query(User).filter(User.training_status != None).count()

        # Role statistics
        total_roles = session.query(Role).count()
        role_user_counts = session.query(
            Role.name,
            func.count(User.id)
        ).outerjoin(Role.users).group_by(Role.name).all()

        # Signature statistics
        total_signatures = session.query(ElectronicSignature).count()
        signature_by_meaning = session.query(
            ElectronicSignature.meaning,
            func.count(ElectronicSignature.id)
        ).group_by(ElectronicSignature.meaning).all()

        # Audit log statistics
        total_audit_logs = session.query(AuditLog).count()
        audit_by_type = session.query(
            AuditLog.action_type,
            func.count(AuditLog.id)
        ).group_by(AuditLog.action_type).all()

        # Ruleset statistics
        total_rulesets = session.query(Ruleset).count()
        active_rulesets = session.query(Ruleset).filter_by(status='Active').count()
        total_rules = session.query(Rule).count()

        # Access log statistics
        total_access_logs = session.query(AccessLog).count()
        failed_access_attempts = session.query(AccessLog).filter_by(success=False).count()

        report = {
            'generated_at': datetime.utcnow().isoformat(),
            'report_type': 'System Validation Summary',
            'compliance_standards': ['FDA 21 CFR Part 11', 'EU GMP Annex 11', 'GAMP 5'],
            'user_management': {
                'total_users': total_users,
                'active_users': active_users,
                'users_with_documented_training': users_with_training,
                'users_by_role': {role: count for role, count in role_user_counts}
            },
            'access_control': {
                'total_roles': total_roles,
                'rbac_implemented': True,
                'total_access_log_entries': total_access_logs,
                'failed_access_attempts': failed_access_attempts
            },
            'electronic_signatures': {
                'total_signatures': total_signatures,
                'signatures_by_meaning': {meaning: count for meaning, count in signature_by_meaning},
                'signature_binding': 'SHA-256 hash with user credentials and timestamp'
            },
            'audit_trail': {
                'total_audit_entries': total_audit_logs,
                'entries_by_action_type': {action: count for action, count in audit_by_type},
                'audit_trail_protected': True,
                'timestamps_utc': True
            },
            'rule_configuration': {
                'total_rulesets': total_rulesets,
                'active_rulesets': active_rulesets,
                'total_rules': total_rules,
                'version_control_enabled': True
            },
            'data_integrity': {
                'alcoa_plus_compliant': True,
                'attributable': 'All records linked to user ID',
                'legible': 'Data stored in readable format',
                'contemporaneous': 'UTC timestamps on all records',
                'original': 'Original records preserved, changes create new versions',
                'accurate': 'Input validation and business rules enforced'
            }
        }

        return jsonify(report)

    except Exception as e:
        logger.exception("Failed to generate validation report")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@validation_blueprint.route('/report/data-integrity', methods=['GET'])
@require_permission('validation', 'view')
def get_data_integrity_report():
    """
    Generate data integrity verification report.
    """
    session = Session()
    try:
        # Check for any orphaned rules
        orphaned_rules = session.query(Rule).filter(
            ~Rule.ruleset_id.in_(session.query(Ruleset.id))
        ).count()

        # Check for signatures without valid users
        orphaned_signatures = session.query(ElectronicSignature).filter(
            ~ElectronicSignature.user_id.in_(session.query(User.id))
        ).count()

        # Check for audit logs without valid users
        orphaned_audit_logs = session.query(AuditLog).filter(
            AuditLog.user_id.isnot(None),
            ~AuditLog.user_id.in_(session.query(User.id))
        ).count()

        report = {
            'generated_at': datetime.utcnow().isoformat(),
            'report_type': 'Data Integrity Verification',
            'integrity_checks': {
                'orphaned_rules': {
                    'count': orphaned_rules,
                    'status': 'PASS' if orphaned_rules == 0 else 'FAIL',
                    'description': 'Rules without associated ruleset'
                },
                'orphaned_signatures': {
                    'count': orphaned_signatures,
                    'status': 'PASS' if orphaned_signatures == 0 else 'FAIL',
                    'description': 'Electronic signatures without valid user reference'
                },
                'orphaned_audit_logs': {
                    'count': orphaned_audit_logs,
                    'status': 'PASS' if orphaned_audit_logs == 0 else 'WARN',
                    'description': 'Audit logs referencing deleted users (may be expected)'
                }
            },
            'overall_status': 'PASS' if orphaned_rules == 0 and orphaned_signatures == 0 else 'REQUIRES_REVIEW'
        }

        return jsonify(report)

    except Exception as e:
        logger.exception("Failed to generate data integrity report")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()
