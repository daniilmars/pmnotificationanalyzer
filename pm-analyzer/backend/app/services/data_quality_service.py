# pm-analyzer/backend/app/services/data_quality_service.py
"""
Data Quality Analytics Service for PM Notifications.

Provides comprehensive data quality metrics, scoring, and trend analysis
for plant maintenance notifications to support reliability engineering
and regulatory compliance requirements.

Implements ALCOA+ principles:
- Attributable: Who performed the action
- Legible: Data is readable and permanent
- Contemporaneous: Recorded at time of activity
- Original: First capture of data
- Accurate: Free from errors
- Complete: All required data present
- Consistent: Data matches across systems
- Enduring: Available for review period
- Available: Accessible when needed
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class QualityDimension(Enum):
    """Quality dimensions for data assessment."""
    COMPLETENESS = "completeness"
    ACCURACY = "accuracy"
    TIMELINESS = "timeliness"
    CONSISTENCY = "consistency"
    VALIDITY = "validity"


@dataclass
class FieldQualityScore:
    """Quality score for a single field."""
    field_name: str
    completeness: float  # 0-100
    validity: float  # 0-100
    issues: List[str]


@dataclass
class NotificationQualityScore:
    """Comprehensive quality score for a notification."""
    notification_id: str
    overall_score: float  # 0-100
    completeness_score: float
    accuracy_score: float
    timeliness_score: float
    consistency_score: float
    validity_score: float
    field_scores: List[FieldQualityScore]
    issues: List[Dict[str, Any]]
    alcoa_compliance: Dict[str, bool]
    recommendations: List[str]


@dataclass
class QualityTrend:
    """Quality trend data point."""
    period: str
    average_score: float
    notification_count: int
    completeness_avg: float
    accuracy_avg: float
    top_issues: List[str]


# =============================================================================
# FIELD DEFINITIONS AND WEIGHTS
# =============================================================================

# Required fields for completeness scoring
REQUIRED_FIELDS = {
    'NotificationId': {'weight': 1.0, 'critical': True},
    'Description': {'weight': 1.0, 'critical': True},
    'NotificationType': {'weight': 0.8, 'critical': True},
    'Priority': {'weight': 0.7, 'critical': False},
    'FunctionalLocation': {'weight': 0.8, 'critical': False},
    'Equipment': {'weight': 0.6, 'critical': False},
    'LongText': {'weight': 0.9, 'critical': False},
    'CreatedBy': {'weight': 0.5, 'critical': True},
    'CreationDate': {'weight': 0.5, 'critical': True},
}

# Field validation rules
FIELD_VALIDATORS = {
    'NotificationId': {
        'min_length': 1,
        'max_length': 20,
        'pattern': r'^[A-Z0-9]+$',
        'description': 'Notification ID must be alphanumeric'
    },
    'Description': {
        'min_length': 10,
        'max_length': 500,
        'description': 'Description should be 10-500 characters'
    },
    'LongText': {
        'min_length': 50,
        'recommended_length': 200,
        'description': 'Long text should be detailed (50+ characters recommended)'
    },
    'NotificationType': {
        'allowed_values': ['M1', 'M2', 'M3', 'M4', 'M5', 'Z1', 'Z2'],
        'description': 'Must be valid notification type'
    },
    'Priority': {
        'allowed_values': ['1', '2', '3', '4', 'Very High', 'High', 'Medium', 'Low'],
        'description': 'Must be valid priority level'
    }
}

# ALCOA+ compliance checks
ALCOA_CHECKS = {
    'attributable': ['CreatedBy', 'ChangedBy'],
    'legible': ['Description', 'LongText'],
    'contemporaneous': ['CreationDate', 'CreationTime'],
    'original': ['NotificationId'],
    'accurate': ['NotificationType', 'Priority', 'FunctionalLocation'],
    'complete': list(REQUIRED_FIELDS.keys()),
    'consistent': ['NotificationType', 'Priority'],
    'enduring': ['NotificationId', 'CreationDate'],
    'available': ['NotificationId']
}


# =============================================================================
# SCORING FUNCTIONS
# =============================================================================

def calculate_completeness_score(notification: Dict[str, Any]) -> Tuple[float, List[Dict]]:
    """
    Calculate completeness score for a notification.

    Returns: (score 0-100, list of issues)
    """
    issues = []
    total_weight = 0
    achieved_weight = 0

    for field, config in REQUIRED_FIELDS.items():
        weight = config['weight']
        total_weight += weight

        value = notification.get(field)

        if value is None or (isinstance(value, str) and not value.strip()):
            issues.append({
                'field': field,
                'issue': 'missing',
                'severity': 'critical' if config['critical'] else 'warning',
                'message': f"Required field '{field}' is missing or empty"
            })
        else:
            achieved_weight += weight

    score = (achieved_weight / total_weight * 100) if total_weight > 0 else 0
    return round(score, 2), issues


def calculate_validity_score(notification: Dict[str, Any]) -> Tuple[float, List[Dict]]:
    """
    Calculate validity score based on field validation rules.

    Returns: (score 0-100, list of issues)
    """
    import re

    issues = []
    valid_fields = 0
    total_validated = 0

    for field, rules in FIELD_VALIDATORS.items():
        value = notification.get(field)
        if value is None:
            continue

        total_validated += 1
        field_valid = True
        value_str = str(value)

        # Check minimum length
        if 'min_length' in rules and len(value_str) < rules['min_length']:
            field_valid = False
            issues.append({
                'field': field,
                'issue': 'too_short',
                'severity': 'warning',
                'message': f"'{field}' is too short (min: {rules['min_length']} chars)"
            })

        # Check maximum length
        if 'max_length' in rules and len(value_str) > rules['max_length']:
            field_valid = False
            issues.append({
                'field': field,
                'issue': 'too_long',
                'severity': 'warning',
                'message': f"'{field}' exceeds maximum length ({rules['max_length']} chars)"
            })

        # Check pattern
        if 'pattern' in rules and not re.match(rules['pattern'], value_str):
            field_valid = False
            issues.append({
                'field': field,
                'issue': 'invalid_format',
                'severity': 'error',
                'message': rules['description']
            })

        # Check allowed values
        if 'allowed_values' in rules and value_str not in rules['allowed_values']:
            field_valid = False
            issues.append({
                'field': field,
                'issue': 'invalid_value',
                'severity': 'error',
                'message': f"'{field}' has invalid value. {rules['description']}"
            })

        if field_valid:
            valid_fields += 1

    score = (valid_fields / total_validated * 100) if total_validated > 0 else 100
    return round(score, 2), issues


def calculate_timeliness_score(notification: Dict[str, Any]) -> Tuple[float, List[Dict]]:
    """
    Calculate timeliness score based on creation and processing dates.

    Returns: (score 0-100, list of issues)
    """
    issues = []
    score = 100.0

    creation_date = notification.get('CreationDate')
    malfunction_start = notification.get('MalfunctionStart')

    if creation_date and malfunction_start:
        try:
            # Parse dates (handle various formats)
            if isinstance(creation_date, str):
                creation_dt = datetime.fromisoformat(creation_date.replace('Z', '+00:00'))
            else:
                creation_dt = creation_date

            if isinstance(malfunction_start, str):
                malfunction_dt = datetime.fromisoformat(malfunction_start.replace('Z', '+00:00'))
            else:
                malfunction_dt = malfunction_start

            # Calculate delay in hours
            delay = (creation_dt - malfunction_dt).total_seconds() / 3600

            if delay > 72:  # More than 3 days
                score = 50
                issues.append({
                    'field': 'CreationDate',
                    'issue': 'significant_delay',
                    'severity': 'warning',
                    'message': f"Notification created {delay:.0f} hours after malfunction start"
                })
            elif delay > 24:  # More than 1 day
                score = 75
                issues.append({
                    'field': 'CreationDate',
                    'issue': 'moderate_delay',
                    'severity': 'info',
                    'message': f"Notification created {delay:.0f} hours after malfunction start"
                })

        except (ValueError, TypeError) as e:
            logger.debug(f"Could not parse dates for timeliness: {e}")

    return round(score, 2), issues


def calculate_consistency_score(notification: Dict[str, Any]) -> Tuple[float, List[Dict]]:
    """
    Calculate consistency score checking for logical consistency.

    Returns: (score 0-100, list of issues)
    """
    issues = []
    checks_passed = 0
    total_checks = 0

    # Check: If equipment is specified, functional location should be too
    total_checks += 1
    equipment = notification.get('Equipment')
    func_loc = notification.get('FunctionalLocation')

    if equipment and not func_loc:
        issues.append({
            'field': 'FunctionalLocation',
            'issue': 'missing_related',
            'severity': 'warning',
            'message': "Equipment specified but Functional Location is missing"
        })
    else:
        checks_passed += 1

    # Check: Priority should match notification type severity expectations
    total_checks += 1
    notif_type = notification.get('NotificationType', '')
    priority = notification.get('Priority', '')

    # M1 (breakdown) should typically have high priority
    if notif_type == 'M1' and priority in ['3', '4', 'Low']:
        issues.append({
            'field': 'Priority',
            'issue': 'inconsistent_priority',
            'severity': 'warning',
            'message': "Breakdown notification (M1) has low priority - verify if correct"
        })
    else:
        checks_passed += 1

    # Check: Long text should reference elements mentioned in short description
    total_checks += 1
    description = notification.get('Description', '').lower()
    long_text = notification.get('LongText', '').lower()

    if description and long_text:
        # Simple keyword overlap check
        desc_words = set(description.split())
        long_words = set(long_text.split())
        overlap = len(desc_words.intersection(long_words))

        if overlap < 2 and len(desc_words) > 3:
            issues.append({
                'field': 'LongText',
                'issue': 'content_mismatch',
                'severity': 'info',
                'message': "Long text may not be related to short description"
            })
        else:
            checks_passed += 1
    else:
        checks_passed += 1

    score = (checks_passed / total_checks * 100) if total_checks > 0 else 100
    return round(score, 2), issues


def check_alcoa_compliance(notification: Dict[str, Any]) -> Dict[str, bool]:
    """
    Check ALCOA+ compliance for a notification.

    Returns: Dict with each ALCOA+ principle and compliance status
    """
    compliance = {}

    for principle, fields in ALCOA_CHECKS.items():
        # Check if required fields for this principle are present and valid
        principle_met = True

        for field in fields:
            value = notification.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                principle_met = False
                break

        compliance[principle] = principle_met

    return compliance


def generate_recommendations(
    notification: Dict[str, Any],
    issues: List[Dict],
    alcoa_compliance: Dict[str, bool]
) -> List[str]:
    """
    Generate improvement recommendations based on issues found.
    """
    recommendations = []

    # Group issues by severity
    critical_issues = [i for i in issues if i.get('severity') == 'critical']
    warning_issues = [i for i in issues if i.get('severity') == 'warning']

    if critical_issues:
        missing_fields = [i['field'] for i in critical_issues if i['issue'] == 'missing']
        if missing_fields:
            recommendations.append(
                f"Add missing critical fields: {', '.join(missing_fields)}"
            )

    # Check long text quality
    long_text = notification.get('LongText', '')
    if len(long_text) < 50:
        recommendations.append(
            "Expand the long text with more details about the problem, "
            "observations, and any troubleshooting performed"
        )
    elif len(long_text) < 200:
        recommendations.append(
            "Consider adding more context to the long text for better traceability"
        )

    # ALCOA+ recommendations
    failed_principles = [p for p, met in alcoa_compliance.items() if not met]
    if 'attributable' in failed_principles:
        recommendations.append(
            "Ensure the notification creator is properly identified"
        )
    if 'contemporaneous' in failed_principles:
        recommendations.append(
            "Record notifications promptly when issues are discovered"
        )
    if 'complete' in failed_principles:
        recommendations.append(
            "Fill in all required fields to ensure complete documentation"
        )

    # Priority-specific recommendations
    priority = notification.get('Priority', '')
    notif_type = notification.get('NotificationType', '')

    if notif_type in ['M1', 'M2'] and not notification.get('Equipment'):
        recommendations.append(
            "Specify the affected equipment for maintenance notifications"
        )

    return recommendations[:5]  # Limit to top 5 recommendations


# =============================================================================
# MAIN SCORING FUNCTION
# =============================================================================

def calculate_notification_quality(notification: Dict[str, Any]) -> NotificationQualityScore:
    """
    Calculate comprehensive quality score for a notification.

    Args:
        notification: Dict containing notification data

    Returns:
        NotificationQualityScore with all metrics
    """
    # Calculate individual dimension scores
    completeness_score, completeness_issues = calculate_completeness_score(notification)
    validity_score, validity_issues = calculate_validity_score(notification)
    timeliness_score, timeliness_issues = calculate_timeliness_score(notification)
    consistency_score, consistency_issues = calculate_consistency_score(notification)

    # Combine all issues
    all_issues = completeness_issues + validity_issues + timeliness_issues + consistency_issues

    # Calculate accuracy score (combination of validity and consistency)
    accuracy_score = (validity_score * 0.6 + consistency_score * 0.4)

    # Calculate overall score with weighted dimensions
    overall_score = (
        completeness_score * 0.35 +
        accuracy_score * 0.25 +
        timeliness_score * 0.15 +
        consistency_score * 0.15 +
        validity_score * 0.10
    )

    # Check ALCOA+ compliance
    alcoa_compliance = check_alcoa_compliance(notification)

    # Generate recommendations
    recommendations = generate_recommendations(notification, all_issues, alcoa_compliance)

    # Calculate field-level scores
    field_scores = []
    for field in REQUIRED_FIELDS.keys():
        value = notification.get(field)
        field_completeness = 100 if value else 0
        field_validity = 100  # Default

        field_issues = [i['message'] for i in all_issues if i.get('field') == field]

        if field in FIELD_VALIDATORS and value:
            # Check validity for this specific field
            validator = FIELD_VALIDATORS[field]
            if 'min_length' in validator and len(str(value)) < validator['min_length']:
                field_validity -= 30
            if 'allowed_values' in validator and str(value) not in validator['allowed_values']:
                field_validity -= 50

        field_scores.append(FieldQualityScore(
            field_name=field,
            completeness=field_completeness,
            validity=max(0, field_validity),
            issues=field_issues
        ))

    return NotificationQualityScore(
        notification_id=notification.get('NotificationId', 'Unknown'),
        overall_score=round(overall_score, 2),
        completeness_score=completeness_score,
        accuracy_score=round(accuracy_score, 2),
        timeliness_score=timeliness_score,
        consistency_score=consistency_score,
        validity_score=validity_score,
        field_scores=field_scores,
        issues=all_issues,
        alcoa_compliance=alcoa_compliance,
        recommendations=recommendations
    )


# =============================================================================
# BATCH AND TREND ANALYSIS
# =============================================================================

def calculate_batch_quality(notifications: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate quality metrics for a batch of notifications.

    Returns aggregate statistics and distribution data.
    """
    if not notifications:
        return {
            'count': 0,
            'average_score': 0,
            'score_distribution': {},
            'common_issues': [],
            'alcoa_summary': {}
        }

    scores = []
    all_issues = []
    alcoa_results = defaultdict(int)

    for notif in notifications:
        quality = calculate_notification_quality(notif)
        scores.append(quality.overall_score)
        all_issues.extend(quality.issues)

        for principle, met in quality.alcoa_compliance.items():
            if met:
                alcoa_results[principle] += 1

    # Calculate distribution
    distribution = {
        'excellent': len([s for s in scores if s >= 90]),
        'good': len([s for s in scores if 75 <= s < 90]),
        'acceptable': len([s for s in scores if 60 <= s < 75]),
        'poor': len([s for s in scores if s < 60])
    }

    # Find most common issues
    issue_counts = defaultdict(int)
    for issue in all_issues:
        key = f"{issue.get('field', 'Unknown')}:{issue.get('issue', 'unknown')}"
        issue_counts[key] += 1

    common_issues = sorted(
        [{'issue': k, 'count': v} for k, v in issue_counts.items()],
        key=lambda x: x['count'],
        reverse=True
    )[:10]

    # ALCOA+ compliance percentages
    total = len(notifications)
    alcoa_summary = {
        principle: round(count / total * 100, 1)
        for principle, count in alcoa_results.items()
    }

    return {
        'count': len(notifications),
        'average_score': round(sum(scores) / len(scores), 2),
        'min_score': round(min(scores), 2),
        'max_score': round(max(scores), 2),
        'median_score': round(sorted(scores)[len(scores) // 2], 2),
        'score_distribution': distribution,
        'common_issues': common_issues,
        'alcoa_summary': alcoa_summary
    }


def calculate_quality_trend(
    notifications: List[Dict[str, Any]],
    period: str = 'weekly'
) -> List[QualityTrend]:
    """
    Calculate quality trends over time.

    Args:
        notifications: List of notifications with CreationDate
        period: 'daily', 'weekly', or 'monthly'

    Returns:
        List of QualityTrend data points
    """
    if not notifications:
        return []

    # Group notifications by period
    grouped = defaultdict(list)

    for notif in notifications:
        creation_date = notif.get('CreationDate')
        if not creation_date:
            continue

        try:
            if isinstance(creation_date, str):
                dt = datetime.fromisoformat(creation_date.replace('Z', '+00:00'))
            else:
                dt = creation_date

            if period == 'daily':
                period_key = dt.strftime('%Y-%m-%d')
            elif period == 'weekly':
                # ISO week
                period_key = f"{dt.year}-W{dt.isocalendar()[1]:02d}"
            else:  # monthly
                period_key = dt.strftime('%Y-%m')

            grouped[period_key].append(notif)

        except (ValueError, TypeError):
            continue

    # Calculate trends for each period
    trends = []
    for period_key in sorted(grouped.keys()):
        period_notifs = grouped[period_key]
        batch_stats = calculate_batch_quality(period_notifs)

        # Get completeness and accuracy averages
        completeness_scores = []
        accuracy_scores = []
        all_issues = []

        for notif in period_notifs:
            quality = calculate_notification_quality(notif)
            completeness_scores.append(quality.completeness_score)
            accuracy_scores.append(quality.accuracy_score)
            all_issues.extend([i.get('issue', 'unknown') for i in quality.issues])

        # Count top issues
        issue_counts = defaultdict(int)
        for issue in all_issues:
            issue_counts[issue] += 1
        top_issues = sorted(issue_counts.keys(), key=lambda x: issue_counts[x], reverse=True)[:3]

        trends.append(QualityTrend(
            period=period_key,
            average_score=batch_stats['average_score'],
            notification_count=len(period_notifs),
            completeness_avg=round(sum(completeness_scores) / len(completeness_scores), 2) if completeness_scores else 0,
            accuracy_avg=round(sum(accuracy_scores) / len(accuracy_scores), 2) if accuracy_scores else 0,
            top_issues=top_issues
        ))

    return trends


def to_dict(obj):
    """Convert dataclass objects to dictionaries recursively."""
    if hasattr(obj, '__dataclass_fields__'):
        return {k: to_dict(v) for k, v in asdict(obj).items()}
    elif isinstance(obj, list):
        return [to_dict(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    else:
        return obj
