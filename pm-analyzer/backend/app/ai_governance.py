# pm-analyzer/backend/app/ai_governance.py
"""
AI Governance Module for Regulatory Compliance.

Provides:
- Prompt template versioning with full audit trail
- AI usage logging for compliance audits
- Model governance (approved models list)
- Configuration versioning

Supports FDA 21 CFR Part 11 and EU GMP Annex 11 requirements for
computerized system validation in regulated environments.
"""
import os
import json
import hashlib
import sqlite3
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
from functools import wraps

logger = logging.getLogger(__name__)

# AI Governance Configuration
APPROVED_MODELS = os.environ.get('APPROVED_AI_MODELS', 'gemini-pro,gemini-1.5-pro,gemini-1.5-flash').split(',')
AI_GOVERNANCE_ENABLED = os.environ.get('AI_GOVERNANCE_ENABLED', 'true').lower() == 'true'
AI_USAGE_LOG_RETENTION_DAYS = int(os.environ.get('AI_USAGE_LOG_RETENTION_DAYS', '2555'))  # ~7 years default


def get_governance_db_path() -> str:
    """Get the path for the AI governance database."""
    default_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data', 'ai_governance.db'
    )
    return os.environ.get('AI_GOVERNANCE_DB_PATH', default_path)


def init_governance_db():
    """Initialize the AI governance database schema."""
    db_path = get_governance_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    schema = '''
    -- Prompt Templates with versioning
    CREATE TABLE IF NOT EXISTS prompt_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_name TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        template_content TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        description TEXT,
        purpose TEXT,
        created_by TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        approved_by TEXT,
        approved_at TIMESTAMP,
        status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'pending_approval', 'approved', 'deprecated')),
        effective_from TIMESTAMP,
        effective_to TIMESTAMP,
        UNIQUE(template_name, version)
    );

    -- Prompt Template Approvals (electronic signatures)
    CREATE TABLE IF NOT EXISTS prompt_approvals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_id INTEGER NOT NULL,
        approver_id TEXT NOT NULL,
        approval_type TEXT NOT NULL CHECK (approval_type IN ('review', 'approval', 'rejection')),
        comments TEXT,
        signature_hash TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ip_address TEXT,
        FOREIGN KEY (template_id) REFERENCES prompt_templates(id)
    );

    -- AI Model Registry (approved models)
    CREATE TABLE IF NOT EXISTS ai_model_registry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model_id TEXT NOT NULL UNIQUE,
        model_name TEXT NOT NULL,
        provider TEXT NOT NULL,
        version TEXT,
        validation_status TEXT DEFAULT 'pending' CHECK (validation_status IN ('pending', 'validated', 'deprecated')),
        validation_date TIMESTAMP,
        validated_by TEXT,
        risk_assessment TEXT,
        intended_use TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- AI Usage Log (comprehensive audit trail)
    CREATE TABLE IF NOT EXISTS ai_usage_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id TEXT NOT NULL UNIQUE,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        user_id TEXT,
        session_id TEXT,
        model_id TEXT NOT NULL,
        template_name TEXT,
        template_version INTEGER,
        input_hash TEXT NOT NULL,
        input_preview TEXT,
        output_hash TEXT,
        output_preview TEXT,
        tokens_input INTEGER,
        tokens_output INTEGER,
        latency_ms INTEGER,
        status TEXT NOT NULL CHECK (status IN ('success', 'error', 'timeout', 'filtered')),
        error_message TEXT,
        context_type TEXT,
        context_id TEXT,
        ip_address TEXT,
        user_agent TEXT
    );

    -- AI Configuration History
    CREATE TABLE IF NOT EXISTS ai_config_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        config_name TEXT NOT NULL,
        config_value TEXT NOT NULL,
        previous_value TEXT,
        changed_by TEXT NOT NULL,
        changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        change_reason TEXT,
        signature_hash TEXT
    );

    -- Create indexes for performance
    CREATE INDEX IF NOT EXISTS idx_prompt_templates_name_status ON prompt_templates(template_name, status);
    CREATE INDEX IF NOT EXISTS idx_ai_usage_log_timestamp ON ai_usage_log(timestamp);
    CREATE INDEX IF NOT EXISTS idx_ai_usage_log_user ON ai_usage_log(user_id);
    CREATE INDEX IF NOT EXISTS idx_ai_usage_log_context ON ai_usage_log(context_type, context_id);
    CREATE INDEX IF NOT EXISTS idx_ai_config_history_name ON ai_config_history(config_name);
    '''

    with sqlite3.connect(db_path) as db:
        db.executescript(schema)
        db.commit()

    logger.info(f"AI Governance database initialized at {db_path}")


def _get_db():
    """Get a database connection."""
    db_path = get_governance_db_path()
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    return db


def compute_hash(content: str) -> str:
    """Compute SHA-256 hash of content for integrity verification."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


# =============================================================================
# PROMPT TEMPLATE MANAGEMENT
# =============================================================================

def create_prompt_template(
    template_name: str,
    template_content: str,
    created_by: str,
    description: str = None,
    purpose: str = None
) -> Tuple[bool, Optional[Dict], Optional[str]]:
    """
    Create a new prompt template or new version of existing template.

    Returns: (success, template_data, error_message)
    """
    if not AI_GOVERNANCE_ENABLED:
        return True, {"id": 0, "version": 0}, None

    db = _get_db()
    try:
        cursor = db.cursor()

        # Get current max version for this template
        cursor.execute(
            "SELECT MAX(version) as max_version FROM prompt_templates WHERE template_name = ?",
            (template_name,)
        )
        result = cursor.fetchone()
        new_version = (result['max_version'] or 0) + 1

        content_hash = compute_hash(template_content)

        cursor.execute('''
            INSERT INTO prompt_templates
            (template_name, version, template_content, content_hash, description, purpose, created_by, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'draft')
        ''', (template_name, new_version, template_content, content_hash, description, purpose, created_by))

        template_id = cursor.lastrowid
        db.commit()

        logger.info(f"Created prompt template: {template_name} v{new_version} by {created_by}")

        return True, {
            "id": template_id,
            "template_name": template_name,
            "version": new_version,
            "status": "draft",
            "content_hash": content_hash
        }, None

    except Exception as e:
        logger.error(f"Failed to create prompt template: {e}")
        return False, None, str(e)
    finally:
        db.close()


def approve_prompt_template(
    template_id: int,
    approver_id: str,
    approval_type: str,
    password_hash: str,
    comments: str = None,
    ip_address: str = None
) -> Tuple[bool, Optional[str]]:
    """
    Approve or reject a prompt template with electronic signature.

    approval_type: 'review', 'approval', or 'rejection'
    """
    if not AI_GOVERNANCE_ENABLED:
        return True, None

    db = _get_db()
    try:
        cursor = db.cursor()

        # Create signature hash (combines user, time, content for integrity)
        timestamp = datetime.utcnow().isoformat()
        signature_data = f"{approver_id}:{timestamp}:{approval_type}:{template_id}"
        signature_hash = compute_hash(signature_data + password_hash)

        cursor.execute('''
            INSERT INTO prompt_approvals
            (template_id, approver_id, approval_type, comments, signature_hash, ip_address)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (template_id, approver_id, approval_type, comments, signature_hash, ip_address))

        # Update template status based on approval
        if approval_type == 'approval':
            cursor.execute('''
                UPDATE prompt_templates
                SET status = 'approved', approved_by = ?, approved_at = CURRENT_TIMESTAMP, effective_from = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (approver_id, template_id))
        elif approval_type == 'rejection':
            cursor.execute(
                "UPDATE prompt_templates SET status = 'draft' WHERE id = ?",
                (template_id,)
            )
        elif approval_type == 'review':
            cursor.execute(
                "UPDATE prompt_templates SET status = 'pending_approval' WHERE id = ?",
                (template_id,)
            )

        db.commit()
        logger.info(f"Prompt template {template_id} {approval_type} by {approver_id}")
        return True, None

    except Exception as e:
        logger.error(f"Failed to process template approval: {e}")
        return False, str(e)
    finally:
        db.close()


def get_active_prompt_template(template_name: str) -> Optional[Dict]:
    """Get the currently active (approved) version of a prompt template."""
    if not AI_GOVERNANCE_ENABLED:
        return None

    db = _get_db()
    try:
        cursor = db.cursor()
        cursor.execute('''
            SELECT * FROM prompt_templates
            WHERE template_name = ? AND status = 'approved'
            AND (effective_from IS NULL OR effective_from <= CURRENT_TIMESTAMP)
            AND (effective_to IS NULL OR effective_to > CURRENT_TIMESTAMP)
            ORDER BY version DESC LIMIT 1
        ''', (template_name,))

        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        db.close()


def get_prompt_template_history(template_name: str) -> List[Dict]:
    """Get full version history of a prompt template."""
    db = _get_db()
    try:
        cursor = db.cursor()
        cursor.execute('''
            SELECT t.*,
                   (SELECT COUNT(*) FROM prompt_approvals WHERE template_id = t.id) as approval_count
            FROM prompt_templates t
            WHERE template_name = ?
            ORDER BY version DESC
        ''', (template_name,))

        return [dict(row) for row in cursor.fetchall()]
    finally:
        db.close()


# =============================================================================
# AI USAGE LOGGING
# =============================================================================

def generate_request_id() -> str:
    """Generate a unique request ID for AI usage tracking."""
    import uuid
    return str(uuid.uuid4())


def log_ai_usage(
    request_id: str,
    model_id: str,
    input_data: str,
    output_data: str = None,
    template_name: str = None,
    template_version: int = None,
    user_id: str = None,
    session_id: str = None,
    tokens_input: int = None,
    tokens_output: int = None,
    latency_ms: int = None,
    status: str = 'success',
    error_message: str = None,
    context_type: str = None,
    context_id: str = None,
    ip_address: str = None,
    user_agent: str = None
) -> bool:
    """
    Log an AI model usage event for audit compliance.

    This creates an immutable audit record of all AI interactions,
    supporting FDA 21 CFR Part 11 requirements for electronic records.
    """
    if not AI_GOVERNANCE_ENABLED:
        return True

    db = _get_db()
    try:
        cursor = db.cursor()

        # Compute hashes for input/output integrity
        input_hash = compute_hash(input_data) if input_data else None
        output_hash = compute_hash(output_data) if output_data else None

        # Create preview (first 500 chars) for quick review without exposing full data
        input_preview = input_data[:500] if input_data else None
        output_preview = output_data[:500] if output_data else None

        cursor.execute('''
            INSERT INTO ai_usage_log
            (request_id, model_id, template_name, template_version, user_id, session_id,
             input_hash, input_preview, output_hash, output_preview,
             tokens_input, tokens_output, latency_ms, status, error_message,
             context_type, context_id, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            request_id, model_id, template_name, template_version, user_id, session_id,
            input_hash, input_preview, output_hash, output_preview,
            tokens_input, tokens_output, latency_ms, status, error_message,
            context_type, context_id, ip_address, user_agent
        ))

        db.commit()
        return True

    except Exception as e:
        logger.error(f"Failed to log AI usage: {e}")
        return False
    finally:
        db.close()


def get_ai_usage_logs(
    start_date: datetime = None,
    end_date: datetime = None,
    user_id: str = None,
    model_id: str = None,
    context_type: str = None,
    context_id: str = None,
    status: str = None,
    limit: int = 1000,
    offset: int = 0
) -> List[Dict]:
    """
    Retrieve AI usage logs with filtering for audit purposes.
    """
    db = _get_db()
    try:
        cursor = db.cursor()

        query = "SELECT * FROM ai_usage_log WHERE 1=1"
        params = []

        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date.isoformat())
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date.isoformat())
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if model_id:
            query += " AND model_id = ?"
            params.append(model_id)
        if context_type:
            query += " AND context_type = ?"
            params.append(context_type)
        if context_id:
            query += " AND context_id = ?"
            params.append(context_id)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        db.close()


# =============================================================================
# MODEL GOVERNANCE
# =============================================================================

def validate_model(model_id: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that a model is approved for use.

    Returns: (is_approved, error_message)
    """
    if not AI_GOVERNANCE_ENABLED:
        return True, None

    # Check environment-based approved list first
    if model_id in APPROVED_MODELS:
        return True, None

    # Check database registry
    db = _get_db()
    try:
        cursor = db.cursor()
        cursor.execute(
            "SELECT validation_status FROM ai_model_registry WHERE model_id = ?",
            (model_id,)
        )
        row = cursor.fetchone()

        if row and row['validation_status'] == 'validated':
            return True, None

        logger.warning(f"Attempted to use non-approved model: {model_id}")
        return False, f"Model '{model_id}' is not approved for use. Approved models: {', '.join(APPROVED_MODELS)}"
    finally:
        db.close()


def register_model(
    model_id: str,
    model_name: str,
    provider: str,
    version: str = None,
    intended_use: str = None,
    risk_assessment: str = None
) -> Tuple[bool, Optional[str]]:
    """Register a new AI model in the governance registry."""
    db = _get_db()
    try:
        cursor = db.cursor()
        cursor.execute('''
            INSERT INTO ai_model_registry
            (model_id, model_name, provider, version, intended_use, risk_assessment)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (model_id, model_name, provider, version, intended_use, risk_assessment))
        db.commit()

        logger.info(f"Registered AI model: {model_id}")
        return True, None
    except sqlite3.IntegrityError:
        return False, f"Model {model_id} already registered"
    except Exception as e:
        return False, str(e)
    finally:
        db.close()


def validate_model_for_use(
    model_id: str,
    validated_by: str
) -> Tuple[bool, Optional[str]]:
    """Mark a model as validated for production use."""
    db = _get_db()
    try:
        cursor = db.cursor()
        cursor.execute('''
            UPDATE ai_model_registry
            SET validation_status = 'validated', validated_by = ?, validation_date = CURRENT_TIMESTAMP
            WHERE model_id = ?
        ''', (validated_by, model_id))

        if cursor.rowcount == 0:
            return False, f"Model {model_id} not found in registry"

        db.commit()
        logger.info(f"Model {model_id} validated by {validated_by}")
        return True, None
    except Exception as e:
        return False, str(e)
    finally:
        db.close()


# =============================================================================
# CONFIGURATION VERSIONING
# =============================================================================

def log_config_change(
    config_name: str,
    config_value: Any,
    changed_by: str,
    change_reason: str = None,
    password_hash: str = None
) -> bool:
    """Log a configuration change with optional electronic signature."""
    if not AI_GOVERNANCE_ENABLED:
        return True

    db = _get_db()
    try:
        cursor = db.cursor()

        # Get previous value
        cursor.execute(
            "SELECT config_value FROM ai_config_history WHERE config_name = ? ORDER BY changed_at DESC LIMIT 1",
            (config_name,)
        )
        row = cursor.fetchone()
        previous_value = row['config_value'] if row else None

        # Create signature if password provided
        signature_hash = None
        if password_hash:
            timestamp = datetime.utcnow().isoformat()
            signature_data = f"{changed_by}:{timestamp}:{config_name}:{json.dumps(config_value)}"
            signature_hash = compute_hash(signature_data + password_hash)

        config_value_str = json.dumps(config_value) if not isinstance(config_value, str) else config_value

        cursor.execute('''
            INSERT INTO ai_config_history
            (config_name, config_value, previous_value, changed_by, change_reason, signature_hash)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (config_name, config_value_str, previous_value, changed_by, change_reason, signature_hash))

        db.commit()
        logger.info(f"Config change logged: {config_name} by {changed_by}")
        return True

    except Exception as e:
        logger.error(f"Failed to log config change: {e}")
        return False
    finally:
        db.close()


def get_config_history(config_name: str, limit: int = 100) -> List[Dict]:
    """Get configuration change history."""
    db = _get_db()
    try:
        cursor = db.cursor()
        cursor.execute('''
            SELECT * FROM ai_config_history
            WHERE config_name = ?
            ORDER BY changed_at DESC
            LIMIT ?
        ''', (config_name, limit))

        return [dict(row) for row in cursor.fetchall()]
    finally:
        db.close()


# =============================================================================
# DECORATOR FOR GOVERNED AI CALLS
# =============================================================================

def governed_ai_call(
    template_name: str = None,
    context_type: str = None,
    require_approved_model: bool = True
):
    """
    Decorator for AI function calls that enforces governance policies.

    Usage:
        @governed_ai_call(template_name='analysis_prompt', context_type='notification')
        def analyze_notification(notification_id, ...):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            import time

            # Extract model from kwargs or use default
            model_id = kwargs.get('model', 'gemini-pro')

            # Validate model if required
            if require_approved_model:
                is_approved, error = validate_model(model_id)
                if not is_approved:
                    raise ValueError(error)

            # Generate request ID
            request_id = generate_request_id()

            # Get template if specified
            template_version = None
            if template_name:
                template = get_active_prompt_template(template_name)
                if template:
                    template_version = template['version']

            # Extract context ID if available
            context_id = kwargs.get('notification_id') or kwargs.get('ruleset_id') or kwargs.get('context_id')

            # Track timing
            start_time = time.time()
            status = 'success'
            error_message = None
            output_data = None

            try:
                result = func(*args, **kwargs)
                if hasattr(result, 'model_dump_json'):
                    output_data = result.model_dump_json()
                elif isinstance(result, dict):
                    output_data = json.dumps(result)
                else:
                    output_data = str(result)
                return result

            except Exception as e:
                status = 'error'
                error_message = str(e)
                raise

            finally:
                latency_ms = int((time.time() - start_time) * 1000)

                # Build input preview from kwargs
                input_data = json.dumps({
                    k: str(v)[:200] if v else None
                    for k, v in kwargs.items()
                    if k not in ('model', 'password')
                })

                # Log usage
                log_ai_usage(
                    request_id=request_id,
                    model_id=model_id,
                    input_data=input_data,
                    output_data=output_data,
                    template_name=template_name,
                    template_version=template_version,
                    latency_ms=latency_ms,
                    status=status,
                    error_message=error_message,
                    context_type=context_type,
                    context_id=context_id
                )

        return wrapper
    return decorator


# =============================================================================
# API ENDPOINTS FOR AI GOVERNANCE
# =============================================================================

def create_governance_blueprint():
    """Create Flask blueprint for AI governance endpoints."""
    from flask import Blueprint, jsonify, request

    governance_blueprint = Blueprint('ai_governance', __name__)

    @governance_blueprint.route('/prompts', methods=['GET'])
    def list_prompts():
        """List all prompt templates."""
        db = _get_db()
        try:
            cursor = db.cursor()
            cursor.execute('''
                SELECT DISTINCT template_name,
                       MAX(version) as latest_version,
                       MAX(CASE WHEN status = 'approved' THEN version END) as active_version
                FROM prompt_templates
                GROUP BY template_name
            ''')
            return jsonify([dict(row) for row in cursor.fetchall()])
        finally:
            db.close()

    @governance_blueprint.route('/prompts/<template_name>', methods=['GET'])
    def get_prompt_history(template_name):
        """Get version history for a prompt template."""
        history = get_prompt_template_history(template_name)
        return jsonify(history)

    @governance_blueprint.route('/prompts', methods=['POST'])
    def create_prompt():
        """Create a new prompt template."""
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400

        required = ['template_name', 'template_content', 'created_by']
        for field in required:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400

        success, template_data, error = create_prompt_template(
            template_name=data['template_name'],
            template_content=data['template_content'],
            created_by=data['created_by'],
            description=data.get('description'),
            purpose=data.get('purpose')
        )

        if success:
            return jsonify(template_data), 201
        return jsonify({'error': error}), 500

    @governance_blueprint.route('/usage-logs', methods=['GET'])
    def get_usage_logs():
        """Get AI usage logs for audit."""
        from datetime import datetime

        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        user_id = request.args.get('user_id')
        model_id = request.args.get('model_id')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))

        if start_date:
            start_date = datetime.fromisoformat(start_date)
        if end_date:
            end_date = datetime.fromisoformat(end_date)

        logs = get_ai_usage_logs(
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
            model_id=model_id,
            limit=limit,
            offset=offset
        )
        return jsonify(logs)

    @governance_blueprint.route('/models', methods=['GET'])
    def list_models():
        """List registered AI models."""
        db = _get_db()
        try:
            cursor = db.cursor()
            cursor.execute("SELECT * FROM ai_model_registry ORDER BY created_at DESC")
            return jsonify([dict(row) for row in cursor.fetchall()])
        finally:
            db.close()

    @governance_blueprint.route('/models', methods=['POST'])
    def register_new_model():
        """Register a new AI model."""
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400

        required = ['model_id', 'model_name', 'provider']
        for field in required:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400

        success, error = register_model(
            model_id=data['model_id'],
            model_name=data['model_name'],
            provider=data['provider'],
            version=data.get('version'),
            intended_use=data.get('intended_use'),
            risk_assessment=data.get('risk_assessment')
        )

        if success:
            return jsonify({'message': 'Model registered successfully'}), 201
        return jsonify({'error': error}), 400

    @governance_blueprint.route('/config-history/<config_name>', methods=['GET'])
    def get_config_change_history(config_name):
        """Get configuration change history."""
        limit = int(request.args.get('limit', 100))
        history = get_config_history(config_name, limit)
        return jsonify(history)

    @governance_blueprint.route('/export/csv', methods=['GET'])
    def export_usage_csv():
        """Export AI usage logs as CSV for validation documentation."""
        import csv
        from io import StringIO
        from flask import Response

        logs = get_ai_usage_logs(limit=10000)

        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            'request_id', 'timestamp', 'user_id', 'model_id',
            'template_name', 'template_version', 'status',
            'latency_ms', 'context_type', 'context_id'
        ])
        writer.writeheader()
        for log in logs:
            writer.writerow({k: log.get(k) for k in writer.fieldnames})

        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=ai_usage_audit_log.csv'}
        )

    return governance_blueprint
