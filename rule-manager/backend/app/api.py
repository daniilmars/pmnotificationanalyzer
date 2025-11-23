# rule-manager/backend/app/api.py
import os
import json
from flask import Blueprint, jsonify, request, current_app
from werkzeug.utils import secure_filename
from .database import Session, Ruleset, Rule, AuditLog, generate_uuid
from .audit_service import log_event
from . import sop_service

api_blueprint = Blueprint('api', __name__)

@api_blueprint.route('/audit-log', methods=['GET'])
def get_audit_log():
    """(Temporary) Retrieve all audit log entries."""
    session = Session()
    try:
        logs = session.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()
        log_list = [
            {
                "id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "user_id": log.user_id,
                "action_type": log.action_type,
                "entity_changed": log.entity_changed,
                "new_value": log.new_value_json
            } for log in logs
        ]
        return jsonify(log_list)
    finally:
        session.close()

@api_blueprint.route('/rulesets', methods=['GET'])
def get_rulesets():
    """Retrieve a list of all rulesets, with optional filtering."""
    session = Session()
    try:
        query = session.query(Ruleset)
        notification_type = request.args.get('notification_type')
        if notification_type:
            query = query.filter(Ruleset.notification_type == notification_type)
        status = request.args.get('status')
        if status:
            query = query.filter(Ruleset.status == status)
        rulesets_query = query.all()
        rulesets_list = [
            {
                "id": rs.id,
                "group_id": rs.group_id,
                "name": rs.name,
                "version": rs.version,
                "status": rs.status,
                "notification_type": rs.notification_type,
                "created_at": rs.created_at.isoformat(),
                "created_by": rs.created_by
            } for rs in rulesets_query
        ]
        return jsonify(rulesets_list)
    finally:
        session.close()

@api_blueprint.route('/rulesets', methods=['POST'])
def create_ruleset():
    data = request.get_json()
    if not data or not all(k in data for k in ('name', 'notification_type', 'created_by')):
        return jsonify({'error': 'Missing required fields'}), 400
    session = Session()
    try:
        new_id = generate_uuid()
        new_ruleset = Ruleset(
            id=new_id, group_id=new_id, version=1,
            name=data['name'],
            notification_type=data['notification_type'],
            created_by=data['created_by']
        )
        session.add(new_ruleset)
        log_event(session, user_id=data['created_by'], action_type="CREATE_RULESET", entity_changed=new_ruleset.id, new_value=data)
        session.commit()
        response_data = { "id": new_ruleset.id, "group_id": new_ruleset.group_id, "name": new_ruleset.name, "version": new_ruleset.version, "status": new_ruleset.status }
        return jsonify(response_data), 201
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@api_blueprint.route('/rulesets/<string:id>', methods=['GET'])
def get_ruleset(id):
    session = Session()
    try:
        ruleset = session.query(Ruleset).filter_by(id=id).first()
        if not ruleset:
            return jsonify({'error': 'Ruleset not found'}), 404
        ruleset_data = {
            "id": ruleset.id, "name": ruleset.name, "version": ruleset.version, "status": ruleset.status,
            "rules": [
                {
                    "id": r.id, "name": r.name, "description": r.description,
                    "target_field": r.target_field, "condition": r.condition, "value": r.value,
                    "score_impact": r.score_impact, "feedback_message": r.feedback_message
                } for r in ruleset.rules
            ]
        }
        return jsonify(ruleset_data)
    finally:
        session.close()

@api_blueprint.route('/rulesets/<string:id>', methods=['PUT'])
def update_ruleset(id):
    session = Session()
    try:
        old_version = session.query(Ruleset).filter_by(id=id, status='Draft').first()
        if not old_version:
            return jsonify({'error': 'Only Draft rulesets can be updated.'}), 400
        data = request.get_json()
        if not data or 'created_by' not in data:
             return jsonify({'error': 'Missing created_by field'}), 400
        old_value = { "name": old_version.name, "notification_type": old_version.notification_type }
        old_version.status = 'Retired'
        new_version = Ruleset(
            group_id=old_version.group_id, version=old_version.version + 1,
            name=data.get('name', old_version.name),
            notification_type=data.get('notification_type', old_version.notification_type),
            status='Draft', created_by=data['created_by']
        )
        session.add(new_version)
        log_event(session, user_id=data['created_by'], action_type="UPDATE_RULESET", entity_changed=new_version.id, old_value=old_value, new_value=data)
        session.commit()
        return jsonify({"id": new_version.id, "version": new_version.version})
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@api_blueprint.route('/rulesets/<string:id>/activate', methods=['POST'])
def activate_ruleset(id):
    data = request.get_json()
    if not data or 'created_by' not in data:
        return jsonify({'error': 'Missing created_by field'}), 400
    session = Session()
    try:
        ruleset_to_activate = session.query(Ruleset).filter_by(id=id, status='Draft').first()
        if not ruleset_to_activate:
            return jsonify({'error': 'Draft ruleset not found.'}), 404
        currently_active = session.query(Ruleset).filter_by(group_id=ruleset_to_activate.group_id, status='Active').first()
        if currently_active:
            currently_active.status = 'Retired'
            log_event(session, user_id=data['created_by'], action_type="RETIRE_RULESET", entity_changed=currently_active.id)
        ruleset_to_activate.status = 'Active'
        log_event(session, user_id=data['created_by'], action_type="ACTIVATE_RULESET", entity_changed=ruleset_to_activate.id)
        session.commit()
        return jsonify({'message': f'Ruleset version {ruleset_to_activate.version} activated.'})
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@api_blueprint.route('/rulesets/<string:ruleset_id>/rules', methods=['POST'])
def add_rule_to_ruleset(ruleset_id):
    session = Session()
    try:
        ruleset = session.query(Ruleset).filter_by(id=ruleset_id, status='Draft').first()
        if not ruleset:
            return jsonify({'error': 'Can only add rules to Draft rulesets.'}), 404
        rules_data = request.get_json()
        if not isinstance(rules_data, list):
            return jsonify({'error': 'Request must be a list of rule objects'}), 400
        added_rules = []
        for rule_data in rules_data:
            new_rule = Rule(
                ruleset_id=ruleset_id, name=rule_data['name'],
                description=rule_data.get('description'), target_field=rule_data['target_field'],
                condition=rule_data['condition'], value=rule_data.get('value'),
                score_impact=rule_data['score_impact'], feedback_message=rule_data['feedback_message']
            )
            session.add(new_rule)
            added_rules.append(new_rule)
        log_event(session, user_id="manual_user", action_type="ADD_RULES_TO_RULESET", entity_changed=ruleset_id, new_value=[r.name for r in added_rules])
        session.commit()
        return jsonify({"message": f"{len(added_rules)} rules added."}), 201
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@api_blueprint.route('/sop-assistant/extract', methods=['POST'])
def extract_from_sop():
    if 'sop_file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['sop_file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and file.filename.endswith('.pdf'):
        filename = secure_filename(file.filename)
        temp_dir = os.path.join(current_app.instance_path, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        temp_filepath = os.path.join(temp_dir, filename)
        file.save(temp_filepath)
        try:
            extracted_rules_json = sop_service.extract_rules_from_sop(temp_filepath)
            extracted_rules = json.loads(extracted_rules_json)
            return jsonify(extracted_rules)
        except Exception as e:
            return jsonify({'error': f"Failed to process SOP: {str(e)}"}), 500
        finally:
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
    else:
        return jsonify({'error': 'Invalid file type. Only PDF is supported.'}), 400
