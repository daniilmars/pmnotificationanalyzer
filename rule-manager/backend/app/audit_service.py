# rule-manager/backend/app/audit_service.py
from .database import Session, AuditLog
import json

def log_event(session, user_id, action_type, entity_changed=None, old_value=None, new_value=None, reason=None):
    """Creates an audit log entry."""
    
    # Ensure dictionary-like objects are serialized to JSON strings
    old_value_json = json.dumps(old_value) if isinstance(old_value, dict) else old_value
    new_value_json = json.dumps(new_value) if isinstance(new_value, dict) else new_value

    audit_entry = AuditLog(
        user_id=user_id,
        action_type=action_type,
        entity_changed=str(entity_changed) if entity_changed else None,
        old_value_json=old_value_json,
        new_value_json=new_value_json,
        reason_for_change=reason
    )
    session.add(audit_entry)
