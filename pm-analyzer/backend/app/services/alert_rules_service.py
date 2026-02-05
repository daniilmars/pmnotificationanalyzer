"""
Alert Rules Engine for PM Notification Analyzer

Defines and evaluates alert rules to trigger notifications based on:
- Quality score thresholds
- Reliability metrics
- Equipment status changes
- Maintenance deadlines
- Audit compliance

Rules can be predefined or user-configured.
"""

import os
import json
import logging
import sqlite3
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum

from app.services.notification_service import (
    EmailNotificationService,
    get_notification_service,
    Alert,
    AlertType,
    AlertSeverity
)

logger = logging.getLogger(__name__)


class RuleOperator(Enum):
    """Comparison operators for rules"""
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUAL = "lte"
    CONTAINS = "contains"
    IN = "in"
    NOT_IN = "not_in"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"


class RuleAction(Enum):
    """Actions to take when rule triggers"""
    SEND_EMAIL = "send_email"
    CREATE_TASK = "create_task"
    LOG_EVENT = "log_event"
    WEBHOOK = "webhook"


@dataclass
class RuleCondition:
    """A single condition in a rule"""
    field: str
    operator: RuleOperator
    value: Any

    def evaluate(self, data: Dict[str, Any]) -> bool:
        """Evaluate this condition against data"""
        field_value = self._get_nested_value(data, self.field)

        if self.operator == RuleOperator.IS_NULL:
            return field_value is None
        if self.operator == RuleOperator.IS_NOT_NULL:
            return field_value is not None

        if field_value is None:
            return False

        if self.operator == RuleOperator.EQUALS:
            return field_value == self.value
        elif self.operator == RuleOperator.NOT_EQUALS:
            return field_value != self.value
        elif self.operator == RuleOperator.GREATER_THAN:
            return field_value > self.value
        elif self.operator == RuleOperator.GREATER_THAN_OR_EQUAL:
            return field_value >= self.value
        elif self.operator == RuleOperator.LESS_THAN:
            return field_value < self.value
        elif self.operator == RuleOperator.LESS_THAN_OR_EQUAL:
            return field_value <= self.value
        elif self.operator == RuleOperator.CONTAINS:
            return self.value in str(field_value)
        elif self.operator == RuleOperator.IN:
            return field_value in self.value
        elif self.operator == RuleOperator.NOT_IN:
            return field_value not in self.value

        return False

    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """Get nested value from dict using dot notation"""
        keys = path.split('.')
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value

    def to_dict(self) -> Dict:
        return {
            'field': self.field,
            'operator': self.operator.value,
            'value': self.value
        }


@dataclass
class AlertRule:
    """Definition of an alert rule"""
    id: str
    name: str
    description: str
    alert_type: AlertType
    severity: AlertSeverity
    conditions: List[RuleCondition]
    match_all: bool = True  # True = AND, False = OR
    actions: List[RuleAction] = field(default_factory=lambda: [RuleAction.SEND_EMAIL])
    recipients: List[str] = field(default_factory=list)
    enabled: bool = True
    cooldown_minutes: int = 60  # Min time between repeat alerts
    created_at: datetime = field(default_factory=datetime.now)
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0

    def evaluate(self, data: Dict[str, Any]) -> bool:
        """Evaluate if this rule triggers for the given data"""
        if not self.enabled:
            return False

        # Check cooldown
        if self.last_triggered:
            cooldown_end = self.last_triggered + timedelta(minutes=self.cooldown_minutes)
            if datetime.now() < cooldown_end:
                return False

        # Evaluate conditions
        if self.match_all:
            return all(c.evaluate(data) for c in self.conditions)
        else:
            return any(c.evaluate(data) for c in self.conditions)

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'alert_type': self.alert_type.value,
            'severity': self.severity.value,
            'conditions': [c.to_dict() for c in self.conditions],
            'match_all': self.match_all,
            'actions': [a.value for a in self.actions],
            'recipients': self.recipients,
            'enabled': self.enabled,
            'cooldown_minutes': self.cooldown_minutes,
            'created_at': self.created_at.isoformat(),
            'last_triggered': self.last_triggered.isoformat() if self.last_triggered else None,
            'trigger_count': self.trigger_count
        }


@dataclass
class Subscription:
    """User subscription to alerts"""
    id: str
    user_id: str
    email: str
    alert_types: List[AlertType] = field(default_factory=lambda: list(AlertType))
    min_severity: AlertSeverity = AlertSeverity.MEDIUM
    equipment_filter: List[str] = field(default_factory=list)
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)

    def should_receive(self, alert: Alert) -> bool:
        """Check if this subscription should receive the alert"""
        if not self.enabled:
            return False

        # Check alert type
        if alert.alert_type not in self.alert_types:
            return False

        # Check severity (higher severity = lower enum value in our case)
        severity_order = [AlertSeverity.CRITICAL, AlertSeverity.HIGH,
                        AlertSeverity.MEDIUM, AlertSeverity.LOW, AlertSeverity.INFO]
        if severity_order.index(alert.severity) > severity_order.index(self.min_severity):
            return False

        # Check equipment filter
        if self.equipment_filter and alert.equipment_id:
            if alert.equipment_id not in self.equipment_filter:
                return False

        return True

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'email': self.email,
            'alert_types': [t.value for t in self.alert_types],
            'min_severity': self.min_severity.value,
            'equipment_filter': self.equipment_filter,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat()
        }


class AlertRulesService:
    """Service for managing and evaluating alert rules"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'data', 'alerts.db'
        )
        self.notification_service = get_notification_service()
        self._rules: Dict[str, AlertRule] = {}
        self._subscriptions: Dict[str, Subscription] = {}
        self._init_db()
        self._load_predefined_rules()

    def _init_db(self):
        """Initialize the alerts database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_rules (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                config TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                created_at TEXT,
                last_triggered TEXT,
                trigger_count INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                email TEXT NOT NULL,
                config TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                created_at TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id TEXT,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT,
                recipients TEXT,
                triggered_at TEXT NOT NULL,
                data TEXT
            )
        """)

        conn.commit()
        conn.close()

    def _load_predefined_rules(self):
        """Load predefined alert rules"""
        predefined = [
            AlertRule(
                id="critical_quality",
                name="Critical Quality Score",
                description="Alert when quality score drops below 50%",
                alert_type=AlertType.QUALITY_ALERT,
                severity=AlertSeverity.CRITICAL,
                conditions=[
                    RuleCondition("quality_score", RuleOperator.LESS_THAN, 50)
                ]
            ),
            AlertRule(
                id="low_quality",
                name="Low Quality Score",
                description="Alert when quality score is below 70%",
                alert_type=AlertType.QUALITY_ALERT,
                severity=AlertSeverity.HIGH,
                conditions=[
                    RuleCondition("quality_score", RuleOperator.LESS_THAN, 70),
                    RuleCondition("quality_score", RuleOperator.GREATER_THAN_OR_EQUAL, 50)
                ]
            ),
            AlertRule(
                id="critical_reliability",
                name="Critical Reliability Risk",
                description="Alert when equipment has critical reliability score",
                alert_type=AlertType.RELIABILITY_WARNING,
                severity=AlertSeverity.CRITICAL,
                conditions=[
                    RuleCondition("reliability_score", RuleOperator.LESS_THAN, 40)
                ]
            ),
            AlertRule(
                id="high_failure_probability",
                name="High Failure Probability",
                description="Alert when failure probability exceeds 70%",
                alert_type=AlertType.RELIABILITY_WARNING,
                severity=AlertSeverity.HIGH,
                conditions=[
                    RuleCondition("failure_probability", RuleOperator.GREATER_THAN, 0.7)
                ]
            ),
            AlertRule(
                id="overdue_maintenance",
                name="Overdue Maintenance",
                description="Alert when maintenance is overdue",
                alert_type=AlertType.OVERDUE_MAINTENANCE,
                severity=AlertSeverity.HIGH,
                conditions=[
                    RuleCondition("days_overdue", RuleOperator.GREATER_THAN, 0)
                ]
            ),
            AlertRule(
                id="critical_equipment_down",
                name="Critical Equipment Down",
                description="Alert when critical equipment has failure notification",
                alert_type=AlertType.EQUIPMENT_FAILURE,
                severity=AlertSeverity.CRITICAL,
                conditions=[
                    RuleCondition("notification_type", RuleOperator.EQUALS, "M1"),
                    RuleCondition("priority", RuleOperator.EQUALS, "1")
                ]
            ),
            AlertRule(
                id="alcoa_violation",
                name="ALCOA+ Compliance Violation",
                description="Alert when ALCOA+ compliance score drops below 80%",
                alert_type=AlertType.AUDIT_COMPLIANCE,
                severity=AlertSeverity.HIGH,
                conditions=[
                    RuleCondition("alcoa_compliance_score", RuleOperator.LESS_THAN, 80)
                ]
            )
        ]

        for rule in predefined:
            self._rules[rule.id] = rule

    # ==========================================
    # Rule Management
    # ==========================================

    def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """Get a rule by ID"""
        return self._rules.get(rule_id)

    def list_rules(self, enabled_only: bool = False) -> List[AlertRule]:
        """List all rules"""
        rules = list(self._rules.values())
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        return rules

    def create_rule(self, rule: AlertRule) -> AlertRule:
        """Create a new rule"""
        self._rules[rule.id] = rule
        self._save_rule(rule)
        return rule

    def update_rule(self, rule_id: str, updates: Dict[str, Any]) -> Optional[AlertRule]:
        """Update an existing rule"""
        rule = self._rules.get(rule_id)
        if not rule:
            return None

        for key, value in updates.items():
            if hasattr(rule, key):
                setattr(rule, key, value)

        self._save_rule(rule)
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule"""
        if rule_id in self._rules:
            del self._rules[rule_id]
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))
            conn.commit()
            conn.close()
            return True
        return False

    def enable_rule(self, rule_id: str) -> bool:
        """Enable a rule"""
        return self.update_rule(rule_id, {'enabled': True}) is not None

    def disable_rule(self, rule_id: str) -> bool:
        """Disable a rule"""
        return self.update_rule(rule_id, {'enabled': False}) is not None

    def _save_rule(self, rule: AlertRule):
        """Save rule to database"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO alert_rules (id, name, description, config, enabled, created_at, last_triggered, trigger_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rule.id, rule.name, rule.description, json.dumps(rule.to_dict()),
            1 if rule.enabled else 0, rule.created_at.isoformat(),
            rule.last_triggered.isoformat() if rule.last_triggered else None,
            rule.trigger_count
        ))
        conn.commit()
        conn.close()

    # ==========================================
    # Subscription Management
    # ==========================================

    def get_subscription(self, subscription_id: str) -> Optional[Subscription]:
        """Get a subscription by ID"""
        return self._subscriptions.get(subscription_id)

    def get_user_subscriptions(self, user_id: str) -> List[Subscription]:
        """Get all subscriptions for a user"""
        return [s for s in self._subscriptions.values() if s.user_id == user_id]

    def create_subscription(self, subscription: Subscription) -> Subscription:
        """Create a new subscription"""
        self._subscriptions[subscription.id] = subscription
        self._save_subscription(subscription)
        return subscription

    def update_subscription(self, subscription_id: str, updates: Dict[str, Any]) -> Optional[Subscription]:
        """Update a subscription"""
        sub = self._subscriptions.get(subscription_id)
        if not sub:
            return None

        for key, value in updates.items():
            if hasattr(sub, key):
                setattr(sub, key, value)

        self._save_subscription(sub)
        return sub

    def delete_subscription(self, subscription_id: str) -> bool:
        """Delete a subscription"""
        if subscription_id in self._subscriptions:
            del self._subscriptions[subscription_id]
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM subscriptions WHERE id = ?", (subscription_id,))
            conn.commit()
            conn.close()
            return True
        return False

    def _save_subscription(self, subscription: Subscription):
        """Save subscription to database"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO subscriptions (id, user_id, email, config, enabled, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            subscription.id, subscription.user_id, subscription.email,
            json.dumps(subscription.to_dict()), 1 if subscription.enabled else 0,
            subscription.created_at.isoformat()
        ))
        conn.commit()
        conn.close()

    # ==========================================
    # Rule Evaluation & Alert Triggering
    # ==========================================

    def evaluate_and_alert(self, data: Dict[str, Any], context: str = "") -> List[Alert]:
        """
        Evaluate all rules against data and send alerts.

        Args:
            data: Data to evaluate rules against
            context: Optional context string for logging

        Returns:
            List of triggered alerts
        """
        triggered_alerts = []

        for rule in self.list_rules(enabled_only=True):
            if rule.evaluate(data):
                alert = self._trigger_rule(rule, data, context)
                if alert:
                    triggered_alerts.append(alert)

        return triggered_alerts

    def _trigger_rule(self, rule: AlertRule, data: Dict[str, Any], context: str) -> Optional[Alert]:
        """Trigger a rule and send alert"""
        logger.info(f"Rule triggered: {rule.name} ({rule.id})")

        # Update rule stats
        rule.last_triggered = datetime.now()
        rule.trigger_count += 1
        self._save_rule(rule)

        # Get recipients from subscriptions
        recipients = set(rule.recipients)

        for sub in self._subscriptions.values():
            if sub.enabled:
                # Create temporary alert to check subscription
                temp_alert = Alert(
                    alert_type=rule.alert_type,
                    severity=rule.severity,
                    title="",
                    message="",
                    equipment_id=data.get('equipment_id')
                )
                if sub.should_receive(temp_alert):
                    recipients.add(sub.email)

        if not recipients:
            logger.warning(f"No recipients for rule {rule.id}")
            return None

        # Create alert
        alert = Alert(
            alert_type=rule.alert_type,
            severity=rule.severity,
            title=self._format_title(rule, data),
            message=self._format_message(rule, data),
            details=self._extract_details(data),
            recipients=list(recipients),
            notification_id=data.get('notification_id'),
            equipment_id=data.get('equipment_id'),
            order_id=data.get('order_id')
        )

        # Execute actions
        for action in rule.actions:
            if action == RuleAction.SEND_EMAIL:
                self.notification_service.send_alert(alert)
            elif action == RuleAction.LOG_EVENT:
                self._log_alert(rule.id, alert, data)
            # Additional actions can be added here

        # Log the alert
        self._log_alert(rule.id, alert, data)

        return alert

    def _format_title(self, rule: AlertRule, data: Dict) -> str:
        """Format alert title"""
        title = rule.name

        if data.get('equipment_id'):
            title = f"{title}: {data['equipment_id']}"
        elif data.get('notification_id'):
            title = f"{title}: Notification {data['notification_id']}"

        return title

    def _format_message(self, rule: AlertRule, data: Dict) -> str:
        """Format alert message"""
        message = rule.description

        # Add context from data
        if data.get('quality_score') is not None:
            message += f"\n\nQuality Score: {data['quality_score']:.1f}%"
        if data.get('reliability_score') is not None:
            message += f"\n\nReliability Score: {data['reliability_score']:.1f}%"
        if data.get('failure_probability') is not None:
            message += f"\nFailure Probability: {data['failure_probability']*100:.1f}%"

        return message

    def _extract_details(self, data: Dict) -> Dict[str, Any]:
        """Extract relevant details from data"""
        details = {}
        relevant_fields = [
            'quality_score', 'reliability_score', 'failure_probability',
            'notification_type', 'priority', 'equipment_id', 'order_id',
            'days_overdue', 'mtbf_hours', 'mttr_hours', 'availability'
        ]

        for field in relevant_fields:
            if field in data and data[field] is not None:
                value = data[field]
                # Format percentages
                if field in ['quality_score', 'reliability_score', 'availability']:
                    value = f"{value:.1f}%"
                elif field == 'failure_probability':
                    value = f"{value*100:.1f}%"
                details[field.replace('_', ' ').title()] = value

        return details

    def _log_alert(self, rule_id: str, alert: Alert, data: Dict):
        """Log alert to database"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO alert_log (rule_id, alert_type, severity, title, message, recipients, triggered_at, data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rule_id, alert.alert_type.value, alert.severity.value,
            alert.title, alert.message, json.dumps(alert.recipients),
            alert.timestamp.isoformat(), json.dumps(data)
        ))
        conn.commit()
        conn.close()

    # ==========================================
    # Alert Log
    # ==========================================

    def get_alert_log(self, limit: int = 100, rule_id: Optional[str] = None,
                      alert_type: Optional[AlertType] = None) -> List[Dict]:
        """Get alert log entries"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        query = "SELECT * FROM alert_log WHERE 1=1"
        params = []

        if rule_id:
            query += " AND rule_id = ?"
            params.append(rule_id)
        if alert_type:
            query += " AND alert_type = ?"
            params.append(alert_type.value)

        query += " ORDER BY triggered_at DESC LIMIT ?"
        params.append(limit)

        cursor = conn.execute(query, params)
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return results


# Global service instance
_alert_rules_service: Optional[AlertRulesService] = None


def get_alert_rules_service() -> AlertRulesService:
    """Get or create alert rules service instance"""
    global _alert_rules_service
    if _alert_rules_service is None:
        _alert_rules_service = AlertRulesService()
    return _alert_rules_service
