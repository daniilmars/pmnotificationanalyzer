# rule-manager/backend/app/api.py
import os
import json
from flask import Blueprint, jsonify, request, current_app
from sqlalchemy import func
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
                    "id": r.id, "name": r.name, "description": r.description, "rule_type": r.rule_type,
                    "target_field": r.target_field, "condition": r.condition, "value": r.value,
                    "score_impact": r.score_impact, "feedback_message": r.feedback_message
                } for r in ruleset.rules
            ]
        }
        return jsonify(ruleset_data)
    finally:
        session.close()

@api_blueprint.route('/rulesets/<string:id>', methods=['DELETE'])
def delete_ruleset(id):
    session = Session()
    try:
        ruleset_to_delete = session.query(Ruleset).filter_by(id=id).first()
        if not ruleset_to_delete:
            return jsonify({'error': 'Ruleset not found'}), 404

        if ruleset_to_delete.status != 'Draft':
            return jsonify({'error': 'Only Draft rulesets can be deleted.'}), 400

        log_event(session, user_id="manual_user", action_type="DELETE_RULESET", entity_changed=id, old_value=ruleset_to_delete.name)
        session.delete(ruleset_to_delete)
        session.commit()
        return jsonify({"message": "Ruleset deleted successfully."})
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
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

        # Copy rules from old version to new version
        for old_rule in old_version.rules:
            new_rule = Rule(
                ruleset_id=new_version.id,
                name=old_rule.name,
                description=old_rule.description,
                rule_type=old_rule.rule_type,
                target_field=old_rule.target_field,
                condition=old_rule.condition,
                value=old_rule.value,
                score_impact=old_rule.score_impact,
                feedback_message=old_rule.feedback_message
            )
            session.add(new_rule)

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

@api_blueprint.route('/rulesets/<string:id>/new-version', methods=['POST'])
def create_new_version(id):
    data = request.get_json()
    if not data or 'created_by' not in data:
        return jsonify({'error': 'Missing created_by field'}), 400

    session = Session()
    try:
        active_ruleset = session.query(Ruleset).filter_by(id=id, status='Active').first()
        if not active_ruleset:
            return jsonify({'error': 'Can only create a new version from an Active ruleset.'}), 404

        # Find the highest version number for this group
        max_version = session.query(func.max(Ruleset.version)).filter_by(group_id=active_ruleset.group_id).scalar()

        new_version_number = max_version + 1
        new_draft_ruleset = Ruleset(
            group_id=active_ruleset.group_id,
            version=new_version_number,
            name=active_ruleset.name,
            notification_type=active_ruleset.notification_type,
            status='Draft',
            created_by=data['created_by']
        )
        session.add(new_draft_ruleset)

        # Copy rules from the active version to the new draft
        for old_rule in active_ruleset.rules:
            new_rule = Rule(
                ruleset=new_draft_ruleset, # Set relationship object
                name=old_rule.name,
                description=old_rule.description,
                rule_type=old_rule.rule_type,
                target_field=old_rule.target_field,
                condition=old_rule.condition,
                value=old_rule.value,
                score_impact=old_rule.score_impact,
                feedback_message=old_rule.feedback_message
            )
            session.add(new_rule)

        log_event(session, user_id=data['created_by'], action_type="CREATE_NEW_VERSION", entity_changed=new_draft_ruleset.id, old_value={"from_version": active_ruleset.version})
        session.commit()
        return jsonify({"id": new_draft_ruleset.id, "version": new_draft_ruleset.version}), 201

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
                rule_type=rule_data.get('rule_type', 'VALIDATION'),
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

@api_blueprint.route('/rules/<string:rule_id>', methods=['PUT'])
def update_rule(rule_id):
    session = Session()
    try:
        rule_to_update = session.query(Rule).filter_by(id=rule_id).first()
        if not rule_to_update:
            return jsonify({'error': 'Rule not found'}), 404

        ruleset = session.query(Ruleset).filter_by(id=rule_to_update.ruleset_id).first()
        if ruleset.status != 'Draft':
            return jsonify({'error': 'Only rules in a Draft ruleset can be updated.'}), 400

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No update data provided'}), 400

        # Simple update for all fields provided in the payload
        for key, value in data.items():
            if hasattr(rule_to_update, key):
                setattr(rule_to_update, key, value)

        log_event(session, user_id=data.get('created_by', 'manual_user'), action_type="UPDATE_RULE", entity_changed=rule_id, new_value=data)
        session.commit()
        return jsonify({"message": "Rule updated successfully."})
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@api_blueprint.route('/rules/<string:rule_id>', methods=['DELETE'])
def delete_rule(rule_id):
    session = Session()
    try:
        rule_to_delete = session.query(Rule).filter_by(id=rule_id).first()
        if not rule_to_delete:
            return jsonify({'error': 'Rule not found'}), 404

        ruleset = session.query(Ruleset).filter_by(id=rule_to_delete.ruleset_id).first()
        if ruleset.status != 'Draft':
            return jsonify({'error': 'Only rules in a Draft ruleset can be deleted.'}), 400

        log_event(session, user_id="manual_user", action_type="DELETE_RULE", entity_changed=rule_id, old_value=rule_to_delete.name)
        session.delete(rule_to_delete)
        session.commit()
        return jsonify({"message": "Rule deleted successfully."})
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
