"""
Email Notification Service for PM Notification Analyzer

Provides email notifications for:
- Critical equipment failures
- Quality score alerts
- Overdue maintenance
- Audit compliance issues
- System alerts

Supports multiple providers:
- SMTP (default)
- SendGrid
- AWS SES
- Mailgun
"""

import os
import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json

logger = logging.getLogger(__name__)


class EmailProvider(Enum):
    """Supported email providers"""
    SMTP = "smtp"
    SENDGRID = "sendgrid"
    AWS_SES = "aws_ses"
    MAILGUN = "mailgun"


class AlertSeverity(Enum):
    """Alert severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertType(Enum):
    """Types of alerts"""
    EQUIPMENT_FAILURE = "equipment_failure"
    QUALITY_ALERT = "quality_alert"
    OVERDUE_MAINTENANCE = "overdue_maintenance"
    RELIABILITY_WARNING = "reliability_warning"
    AUDIT_COMPLIANCE = "audit_compliance"
    SYSTEM_ERROR = "system_error"
    NOTIFICATION_CREATED = "notification_created"
    ORDER_STATUS_CHANGE = "order_status_change"


@dataclass
class EmailConfig:
    """Email service configuration"""
    provider: EmailProvider = EmailProvider.SMTP
    enabled: bool = False

    # SMTP Configuration
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True

    # SendGrid Configuration
    sendgrid_api_key: str = ""

    # AWS SES Configuration
    aws_region: str = "us-east-1"
    aws_access_key: str = ""
    aws_secret_key: str = ""

    # Mailgun Configuration
    mailgun_api_key: str = ""
    mailgun_domain: str = ""

    # General settings
    from_email: str = "noreply@pmanalyzer.example.com"
    from_name: str = "PM Notification Analyzer"
    reply_to: str = ""

    @classmethod
    def from_env(cls) -> 'EmailConfig':
        """Load configuration from environment variables"""
        provider_str = os.environ.get('EMAIL_PROVIDER', 'smtp').lower()
        provider = EmailProvider(provider_str) if provider_str in [e.value for e in EmailProvider] else EmailProvider.SMTP

        return cls(
            provider=provider,
            enabled=os.environ.get('EMAIL_ENABLED', 'false').lower() == 'true',
            smtp_host=os.environ.get('SMTP_HOST', ''),
            smtp_port=int(os.environ.get('SMTP_PORT', '587')),
            smtp_user=os.environ.get('SMTP_USER', ''),
            smtp_password=os.environ.get('SMTP_PASSWORD', ''),
            smtp_use_tls=os.environ.get('SMTP_USE_TLS', 'true').lower() == 'true',
            sendgrid_api_key=os.environ.get('SENDGRID_API_KEY', ''),
            aws_region=os.environ.get('AWS_REGION', 'us-east-1'),
            aws_access_key=os.environ.get('AWS_ACCESS_KEY_ID', ''),
            aws_secret_key=os.environ.get('AWS_SECRET_ACCESS_KEY', ''),
            mailgun_api_key=os.environ.get('MAILGUN_API_KEY', ''),
            mailgun_domain=os.environ.get('MAILGUN_DOMAIN', ''),
            from_email=os.environ.get('EMAIL_FROM', 'noreply@pmanalyzer.example.com'),
            from_name=os.environ.get('EMAIL_FROM_NAME', 'PM Notification Analyzer'),
            reply_to=os.environ.get('EMAIL_REPLY_TO', '')
        )


@dataclass
class Alert:
    """Represents an alert to be sent"""
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    recipients: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    notification_id: Optional[str] = None
    equipment_id: Optional[str] = None
    order_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'alert_type': self.alert_type.value,
            'severity': self.severity.value,
            'title': self.title,
            'message': self.message,
            'details': self.details,
            'recipients': self.recipients,
            'timestamp': self.timestamp.isoformat(),
            'notification_id': self.notification_id,
            'equipment_id': self.equipment_id,
            'order_id': self.order_id
        }


@dataclass
class NotificationPreference:
    """User notification preferences"""
    user_id: str
    email: str
    enabled: bool = True
    alert_types: List[AlertType] = field(default_factory=lambda: list(AlertType))
    min_severity: AlertSeverity = AlertSeverity.MEDIUM
    equipment_filter: List[str] = field(default_factory=list)  # Empty = all
    digest_mode: bool = False  # True = daily digest, False = immediate
    quiet_hours_start: Optional[int] = None  # Hour (0-23)
    quiet_hours_end: Optional[int] = None


class EmailNotificationService:
    """Service for sending email notifications"""

    def __init__(self, config: Optional[EmailConfig] = None):
        self.config = config or EmailConfig.from_env()
        self._alert_history: List[Alert] = []

    # ==========================================
    # Email Sending
    # ==========================================

    def send_email(self, to: List[str], subject: str, html_body: str,
                   text_body: Optional[str] = None,
                   attachments: Optional[List[Dict]] = None) -> bool:
        """
        Send an email using the configured provider.

        Args:
            to: List of recipient email addresses
            subject: Email subject
            html_body: HTML content
            text_body: Plain text content (optional)
            attachments: List of {'filename': str, 'content': bytes, 'mimetype': str}

        Returns:
            True if sent successfully
        """
        if not self.config.enabled:
            logger.warning("Email notifications are disabled")
            return False

        if not to:
            logger.warning("No recipients specified")
            return False

        try:
            if self.config.provider == EmailProvider.SMTP:
                return self._send_smtp(to, subject, html_body, text_body, attachments)
            elif self.config.provider == EmailProvider.SENDGRID:
                return self._send_sendgrid(to, subject, html_body, text_body, attachments)
            elif self.config.provider == EmailProvider.AWS_SES:
                return self._send_ses(to, subject, html_body, text_body, attachments)
            elif self.config.provider == EmailProvider.MAILGUN:
                return self._send_mailgun(to, subject, html_body, text_body, attachments)
            else:
                logger.error(f"Unknown email provider: {self.config.provider}")
                return False

        except Exception as e:
            logger.exception(f"Failed to send email: {e}")
            return False

    def _send_smtp(self, to: List[str], subject: str, html_body: str,
                   text_body: Optional[str], attachments: Optional[List[Dict]]) -> bool:
        """Send email via SMTP"""
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{self.config.from_name} <{self.config.from_email}>"
        msg['To'] = ', '.join(to)

        if self.config.reply_to:
            msg['Reply-To'] = self.config.reply_to

        # Add text and HTML parts
        if text_body:
            msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        # Add attachments
        if attachments:
            for attachment in attachments:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment['content'])
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename={attachment["filename"]}'
                )
                msg.attach(part)

        # Send
        context = ssl.create_default_context()

        if self.config.smtp_use_tls:
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                server.starttls(context=context)
                if self.config.smtp_user:
                    server.login(self.config.smtp_user, self.config.smtp_password)
                server.sendmail(self.config.from_email, to, msg.as_string())
        else:
            with smtplib.SMTP_SSL(self.config.smtp_host, self.config.smtp_port, context=context) as server:
                if self.config.smtp_user:
                    server.login(self.config.smtp_user, self.config.smtp_password)
                server.sendmail(self.config.from_email, to, msg.as_string())

        logger.info(f"Email sent via SMTP to {len(to)} recipients")
        return True

    def _send_sendgrid(self, to: List[str], subject: str, html_body: str,
                       text_body: Optional[str], attachments: Optional[List[Dict]]) -> bool:
        """Send email via SendGrid"""
        import requests

        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {
            "Authorization": f"Bearer {self.config.sendgrid_api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "personalizations": [{"to": [{"email": email} for email in to]}],
            "from": {"email": self.config.from_email, "name": self.config.from_name},
            "subject": subject,
            "content": [
                {"type": "text/html", "value": html_body}
            ]
        }

        if text_body:
            data["content"].insert(0, {"type": "text/plain", "value": text_body})

        if self.config.reply_to:
            data["reply_to"] = {"email": self.config.reply_to}

        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()

        logger.info(f"Email sent via SendGrid to {len(to)} recipients")
        return True

    def _send_ses(self, to: List[str], subject: str, html_body: str,
                  text_body: Optional[str], attachments: Optional[List[Dict]]) -> bool:
        """Send email via AWS SES"""
        import boto3

        client = boto3.client(
            'ses',
            region_name=self.config.aws_region,
            aws_access_key_id=self.config.aws_access_key,
            aws_secret_access_key=self.config.aws_secret_key
        )

        body = {'Html': {'Data': html_body, 'Charset': 'UTF-8'}}
        if text_body:
            body['Text'] = {'Data': text_body, 'Charset': 'UTF-8'}

        response = client.send_email(
            Source=f"{self.config.from_name} <{self.config.from_email}>",
            Destination={'ToAddresses': to},
            Message={
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': body
            },
            ReplyToAddresses=[self.config.reply_to] if self.config.reply_to else []
        )

        logger.info(f"Email sent via AWS SES: {response['MessageId']}")
        return True

    def _send_mailgun(self, to: List[str], subject: str, html_body: str,
                      text_body: Optional[str], attachments: Optional[List[Dict]]) -> bool:
        """Send email via Mailgun"""
        import requests

        url = f"https://api.mailgun.net/v3/{self.config.mailgun_domain}/messages"

        data = {
            "from": f"{self.config.from_name} <{self.config.from_email}>",
            "to": to,
            "subject": subject,
            "html": html_body
        }

        if text_body:
            data["text"] = text_body

        if self.config.reply_to:
            data["h:Reply-To"] = self.config.reply_to

        response = requests.post(
            url,
            auth=("api", self.config.mailgun_api_key),
            data=data,
            timeout=30
        )
        response.raise_for_status()

        logger.info(f"Email sent via Mailgun to {len(to)} recipients")
        return True

    # ==========================================
    # Alert Sending
    # ==========================================

    def send_alert(self, alert: Alert) -> bool:
        """Send an alert notification"""
        if not alert.recipients:
            logger.warning("No recipients for alert")
            return False

        # Generate email content
        subject = self._generate_alert_subject(alert)
        html_body = self._generate_alert_html(alert)
        text_body = self._generate_alert_text(alert)

        # Send email
        success = self.send_email(
            to=alert.recipients,
            subject=subject,
            html_body=html_body,
            text_body=text_body
        )

        # Track alert
        if success:
            self._alert_history.append(alert)

        return success

    def _generate_alert_subject(self, alert: Alert) -> str:
        """Generate email subject for alert"""
        severity_prefix = {
            AlertSeverity.CRITICAL: "🚨 CRITICAL",
            AlertSeverity.HIGH: "⚠️ HIGH",
            AlertSeverity.MEDIUM: "⚡ MEDIUM",
            AlertSeverity.LOW: "ℹ️ LOW",
            AlertSeverity.INFO: "📋 INFO"
        }

        prefix = severity_prefix.get(alert.severity, "")
        return f"{prefix}: {alert.title}"

    def _generate_alert_html(self, alert: Alert) -> str:
        """Generate HTML email body for alert"""
        severity_colors = {
            AlertSeverity.CRITICAL: "#dc3545",
            AlertSeverity.HIGH: "#fd7e14",
            AlertSeverity.MEDIUM: "#ffc107",
            AlertSeverity.LOW: "#17a2b8",
            AlertSeverity.INFO: "#6c757d"
        }

        color = severity_colors.get(alert.severity, "#6c757d")

        details_html = ""
        if alert.details:
            details_rows = "".join(
                f"<tr><td style='padding: 8px; border-bottom: 1px solid #ddd;'><strong>{k}</strong></td>"
                f"<td style='padding: 8px; border-bottom: 1px solid #ddd;'>{v}</td></tr>"
                for k, v in alert.details.items()
            )
            details_html = f"""
            <h3 style="color: #333; margin-top: 20px;">Details</h3>
            <table style="width: 100%; border-collapse: collapse;">
                {details_rows}
            </table>
            """

        links_html = ""
        links = []
        if alert.notification_id:
            links.append(f"Notification: {alert.notification_id}")
        if alert.equipment_id:
            links.append(f"Equipment: {alert.equipment_id}")
        if alert.order_id:
            links.append(f"Order: {alert.order_id}")
        if links:
            links_html = f"<p style='color: #666; font-size: 12px;'>Related: {' | '.join(links)}</p>"

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: {color}; color: white; padding: 15px 20px; border-radius: 8px 8px 0 0;">
                <h1 style="margin: 0; font-size: 20px;">{alert.title}</h1>
                <p style="margin: 5px 0 0 0; font-size: 14px; opacity: 0.9;">
                    {alert.severity.value.upper()} | {alert.alert_type.value.replace('_', ' ').title()}
                </p>
            </div>

            <div style="background: #f8f9fa; padding: 20px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 8px 8px;">
                <p style="margin-top: 0;">{alert.message}</p>

                {details_html}

                {links_html}

                <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">

                <p style="color: #666; font-size: 12px; margin-bottom: 0;">
                    Sent by PM Notification Analyzer at {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
                </p>
            </div>
        </body>
        </html>
        """

    def _generate_alert_text(self, alert: Alert) -> str:
        """Generate plain text email body for alert"""
        lines = [
            f"[{alert.severity.value.upper()}] {alert.title}",
            "",
            alert.message,
            ""
        ]

        if alert.details:
            lines.append("Details:")
            for k, v in alert.details.items():
                lines.append(f"  - {k}: {v}")
            lines.append("")

        if alert.notification_id:
            lines.append(f"Notification: {alert.notification_id}")
        if alert.equipment_id:
            lines.append(f"Equipment: {alert.equipment_id}")
        if alert.order_id:
            lines.append(f"Order: {alert.order_id}")

        lines.extend([
            "",
            f"Sent by PM Notification Analyzer at {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        ])

        return "\n".join(lines)

    # ==========================================
    # Predefined Alert Types
    # ==========================================

    def send_critical_failure_alert(self, equipment_id: str, description: str,
                                    recipients: List[str], details: Dict = None) -> bool:
        """Send critical equipment failure alert"""
        alert = Alert(
            alert_type=AlertType.EQUIPMENT_FAILURE,
            severity=AlertSeverity.CRITICAL,
            title=f"Critical Equipment Failure: {equipment_id}",
            message=description,
            details=details or {},
            recipients=recipients,
            equipment_id=equipment_id
        )
        return self.send_alert(alert)

    def send_quality_alert(self, notification_id: str, quality_score: float,
                          issues: List[str], recipients: List[str]) -> bool:
        """Send quality score alert"""
        severity = AlertSeverity.HIGH if quality_score < 50 else AlertSeverity.MEDIUM

        alert = Alert(
            alert_type=AlertType.QUALITY_ALERT,
            severity=severity,
            title=f"Quality Alert: Notification {notification_id}",
            message=f"Quality score is {quality_score:.1f}%, which is below acceptable threshold.",
            details={
                'Quality Score': f"{quality_score:.1f}%",
                'Issues Found': len(issues),
                'Top Issues': ', '.join(issues[:3]) if issues else 'None'
            },
            recipients=recipients,
            notification_id=notification_id
        )
        return self.send_alert(alert)

    def send_overdue_maintenance_alert(self, equipment_id: str, days_overdue: int,
                                       order_id: str, recipients: List[str]) -> bool:
        """Send overdue maintenance alert"""
        severity = AlertSeverity.CRITICAL if days_overdue > 30 else AlertSeverity.HIGH

        alert = Alert(
            alert_type=AlertType.OVERDUE_MAINTENANCE,
            severity=severity,
            title=f"Overdue Maintenance: {equipment_id}",
            message=f"Maintenance is {days_overdue} days overdue for equipment {equipment_id}.",
            details={
                'Days Overdue': days_overdue,
                'Order Number': order_id,
                'Equipment': equipment_id
            },
            recipients=recipients,
            equipment_id=equipment_id,
            order_id=order_id
        )
        return self.send_alert(alert)

    def send_reliability_warning(self, equipment_id: str, reliability_score: float,
                                failure_probability: float, recipients: List[str]) -> bool:
        """Send reliability warning"""
        severity = AlertSeverity.HIGH if failure_probability > 0.7 else AlertSeverity.MEDIUM

        alert = Alert(
            alert_type=AlertType.RELIABILITY_WARNING,
            severity=severity,
            title=f"Reliability Warning: {equipment_id}",
            message=f"Equipment {equipment_id} has high failure probability and requires attention.",
            details={
                'Reliability Score': f"{reliability_score:.1f}%",
                'Failure Probability': f"{failure_probability*100:.1f}%",
                'Recommended Action': 'Schedule preventive maintenance'
            },
            recipients=recipients,
            equipment_id=equipment_id
        )
        return self.send_alert(alert)

    def send_audit_compliance_alert(self, issue: str, affected_records: int,
                                   recipients: List[str]) -> bool:
        """Send audit compliance alert"""
        alert = Alert(
            alert_type=AlertType.AUDIT_COMPLIANCE,
            severity=AlertSeverity.HIGH,
            title="Audit Compliance Issue Detected",
            message=issue,
            details={
                'Affected Records': affected_records,
                'Compliance Standard': 'FDA 21 CFR Part 11',
                'Action Required': 'Review and remediate'
            },
            recipients=recipients
        )
        return self.send_alert(alert)

    # ==========================================
    # Alert History
    # ==========================================

    def get_alert_history(self, limit: int = 100) -> List[Dict]:
        """Get recent alert history"""
        return [alert.to_dict() for alert in self._alert_history[-limit:]]


# Global service instance
_notification_service: Optional[EmailNotificationService] = None


def get_notification_service() -> EmailNotificationService:
    """Get or create notification service instance"""
    global _notification_service
    if _notification_service is None:
        _notification_service = EmailNotificationService()
    return _notification_service


def check_email_available() -> Dict[str, Any]:
    """Check email service availability"""
    config = EmailConfig.from_env()
    return {
        'enabled': config.enabled,
        'provider': config.provider.value,
        'from_email': config.from_email
    }
