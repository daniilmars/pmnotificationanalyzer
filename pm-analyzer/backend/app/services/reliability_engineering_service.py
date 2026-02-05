"""
Reliability Engineering Service

Provides comprehensive reliability engineering metrics and analysis:
- MTBF (Mean Time Between Failures)
- MTTR (Mean Time To Repair)
- Equipment availability and reliability scoring
- Failure mode analysis (FMEA-style)
- Predictive maintenance indicators
- Weibull distribution analysis
- RCM (Reliability-Centered Maintenance) support
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import math
import statistics
from collections import defaultdict


class FailureSeverity(Enum):
    """Severity classification for failures"""
    CRITICAL = 10  # Safety/environmental impact, production stop
    HIGH = 8       # Significant production impact
    MEDIUM = 5     # Moderate impact, workaround available
    LOW = 3        # Minor impact
    NEGLIGIBLE = 1 # No significant impact


class OccurrenceProbability(Enum):
    """Probability of occurrence classification"""
    VERY_HIGH = 10  # Failure almost inevitable
    HIGH = 8        # Repeated failures
    MODERATE = 5    # Occasional failures
    LOW = 3         # Relatively few failures
    REMOTE = 1      # Failure unlikely


class DetectionRating(Enum):
    """Detection capability classification"""
    ABSOLUTE_UNCERTAINTY = 10  # Cannot detect
    VERY_REMOTE = 9            # Very remote chance of detection
    REMOTE = 8                 # Remote chance of detection
    VERY_LOW = 7               # Very low chance of detection
    LOW = 6                    # Low chance of detection
    MODERATE = 5               # Moderate chance of detection
    MODERATELY_HIGH = 4        # Moderately high chance
    HIGH = 3                   # High chance of detection
    VERY_HIGH = 2              # Very high chance of detection
    ALMOST_CERTAIN = 1         # Almost certain detection


@dataclass
class FailureEvent:
    """Represents a single failure event"""
    notification_id: str
    equipment_id: str
    functional_location: str
    failure_date: datetime
    repair_completed_date: Optional[datetime]
    failure_mode: str
    failure_cause: str
    damage_code: str
    downtime_hours: float
    repair_hours: float
    severity: FailureSeverity
    description: str


@dataclass
class MTBFResult:
    """MTBF calculation result"""
    equipment_id: str
    mtbf_hours: float
    mtbf_days: float
    total_operating_hours: float
    failure_count: int
    calculation_period_days: int
    confidence_level: float
    trend: str  # 'improving', 'stable', 'degrading'


@dataclass
class MTTRResult:
    """MTTR calculation result"""
    equipment_id: str
    mttr_hours: float
    min_repair_time: float
    max_repair_time: float
    repair_count: int
    std_deviation: float
    trend: str


@dataclass
class AvailabilityResult:
    """Equipment availability calculation"""
    equipment_id: str
    availability_percent: float
    uptime_hours: float
    downtime_hours: float
    planned_downtime_hours: float
    unplanned_downtime_hours: float
    total_period_hours: float


@dataclass
class FMEAItem:
    """Failure Mode and Effects Analysis item"""
    failure_mode: str
    potential_effect: str
    severity: int
    occurrence: int
    detection: int
    rpn: int  # Risk Priority Number
    recommended_action: str
    current_controls: str
    equipment_affected: List[str]
    occurrence_count: int


@dataclass
class ReliabilityScore:
    """Overall equipment reliability score"""
    equipment_id: str
    overall_score: float  # 0-100
    mtbf_score: float
    mttr_score: float
    availability_score: float
    failure_trend_score: float
    maintenance_compliance_score: float
    risk_level: str  # 'low', 'medium', 'high', 'critical'
    recommendations: List[str]


@dataclass
class WeibullParameters:
    """Weibull distribution parameters for failure analysis"""
    equipment_id: str
    shape_parameter: float  # Beta - indicates failure pattern
    scale_parameter: float  # Eta - characteristic life
    failure_pattern: str    # 'infant_mortality', 'random', 'wear_out'
    reliability_at_time: Dict[int, float]  # R(t) at various times


@dataclass
class PredictiveMaintenanceIndicator:
    """Predictive maintenance recommendation"""
    equipment_id: str
    predicted_failure_probability: float  # Next 30 days
    recommended_action: str
    urgency: str  # 'immediate', 'soon', 'scheduled', 'monitor'
    estimated_remaining_life_days: float
    confidence_level: float
    contributing_factors: List[Dict[str, Any]]


class ReliabilityEngineeringService:
    """
    Service for reliability engineering calculations and analysis.

    Implements industry-standard reliability metrics and provides
    actionable insights for maintenance optimization.
    """

    def __init__(self):
        self.failure_events: List[FailureEvent] = []
        self.equipment_operating_hours: Dict[str, float] = {}

    def load_notifications_as_failures(self, notifications: List[Dict]) -> List[FailureEvent]:
        """
        Convert PM notifications to failure events for analysis.
        """
        failure_events = []

        for notif in notifications:
            # Determine severity from priority or notification type
            severity = self._determine_severity(notif)

            # Calculate downtime and repair time
            downtime_hours, repair_hours = self._calculate_times(notif)

            failure_event = FailureEvent(
                notification_id=notif.get('NotificationId', ''),
                equipment_id=notif.get('EquipmentNumber', 'UNKNOWN'),
                functional_location=notif.get('FunctionalLocation', ''),
                failure_date=self._parse_date(notif.get('CreationDate')),
                repair_completed_date=self._parse_date(notif.get('CompletionDate')),
                failure_mode=notif.get('DamageCode', 'UNKNOWN'),
                failure_cause=notif.get('CauseCode', 'UNKNOWN'),
                damage_code=notif.get('DamageCode', ''),
                downtime_hours=downtime_hours,
                repair_hours=repair_hours,
                severity=severity,
                description=notif.get('Description', '')
            )
            failure_events.append(failure_event)

        self.failure_events = failure_events
        return failure_events

    def _determine_severity(self, notif: Dict) -> FailureSeverity:
        """Determine failure severity from notification data."""
        priority = notif.get('Priority', '3')
        notif_type = notif.get('NotificationType', '')

        # Map priority to severity
        if priority == '1' or 'SAFETY' in notif_type.upper():
            return FailureSeverity.CRITICAL
        elif priority == '2':
            return FailureSeverity.HIGH
        elif priority == '3':
            return FailureSeverity.MEDIUM
        elif priority == '4':
            return FailureSeverity.LOW
        else:
            return FailureSeverity.NEGLIGIBLE

    def _calculate_times(self, notif: Dict) -> Tuple[float, float]:
        """Calculate downtime and repair hours from notification."""
        creation_date = self._parse_date(notif.get('CreationDate'))
        completion_date = self._parse_date(notif.get('CompletionDate'))
        malfunction_start = self._parse_date(notif.get('MalfunctionStart'))
        malfunction_end = self._parse_date(notif.get('MalfunctionEnd'))

        # Calculate downtime
        downtime_hours = 0.0
        if malfunction_start and malfunction_end:
            downtime_hours = (malfunction_end - malfunction_start).total_seconds() / 3600
        elif creation_date and completion_date:
            downtime_hours = (completion_date - creation_date).total_seconds() / 3600

        # Estimate repair hours (subset of downtime)
        repair_hours = downtime_hours * 0.6  # Assume 60% is actual repair

        return max(0, downtime_hours), max(0, repair_hours)

    def _parse_date(self, date_value: Any) -> Optional[datetime]:
        """Parse date from various formats."""
        if date_value is None:
            return None
        if isinstance(date_value, datetime):
            return date_value
        if isinstance(date_value, str):
            try:
                # Try ISO format first
                return datetime.fromisoformat(date_value.replace('Z', '+00:00'))
            except ValueError:
                try:
                    # Try common date format
                    return datetime.strptime(date_value, '%Y-%m-%d')
                except ValueError:
                    return None
        return None

    def calculate_mtbf(
        self,
        equipment_id: str,
        period_days: int = 365,
        assumed_operating_hours_per_day: float = 16.0
    ) -> MTBFResult:
        """
        Calculate Mean Time Between Failures for equipment.

        MTBF = Total Operating Time / Number of Failures
        """
        # Filter failures for this equipment
        equipment_failures = [
            f for f in self.failure_events
            if f.equipment_id == equipment_id
        ]

        # Calculate period boundaries
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)

        # Filter failures within period
        period_failures = [
            f for f in equipment_failures
            if f.failure_date and start_date <= f.failure_date <= end_date
        ]

        failure_count = len(period_failures)

        # Calculate total operating hours
        total_operating_hours = period_days * assumed_operating_hours_per_day

        # Subtract downtime
        total_downtime = sum(f.downtime_hours for f in period_failures)
        actual_operating_hours = max(1, total_operating_hours - total_downtime)

        # Calculate MTBF
        if failure_count > 0:
            mtbf_hours = actual_operating_hours / failure_count
        else:
            mtbf_hours = actual_operating_hours  # No failures = high MTBF

        mtbf_days = mtbf_hours / assumed_operating_hours_per_day

        # Calculate trend by comparing recent vs older failures
        trend = self._calculate_failure_trend(period_failures)

        # Confidence level based on data points
        confidence = min(1.0, failure_count / 10) if failure_count > 0 else 0.5

        return MTBFResult(
            equipment_id=equipment_id,
            mtbf_hours=round(mtbf_hours, 2),
            mtbf_days=round(mtbf_days, 2),
            total_operating_hours=round(actual_operating_hours, 2),
            failure_count=failure_count,
            calculation_period_days=period_days,
            confidence_level=round(confidence, 2),
            trend=trend
        )

    def calculate_mttr(self, equipment_id: str, period_days: int = 365) -> MTTRResult:
        """
        Calculate Mean Time To Repair for equipment.

        MTTR = Total Repair Time / Number of Repairs
        """
        # Filter failures for this equipment with repair times
        equipment_failures = [
            f for f in self.failure_events
            if f.equipment_id == equipment_id and f.repair_hours > 0
        ]

        # Calculate period boundaries
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)

        # Filter within period
        period_failures = [
            f for f in equipment_failures
            if f.failure_date and start_date <= f.failure_date <= end_date
        ]

        if not period_failures:
            return MTTRResult(
                equipment_id=equipment_id,
                mttr_hours=0.0,
                min_repair_time=0.0,
                max_repair_time=0.0,
                repair_count=0,
                std_deviation=0.0,
                trend='stable'
            )

        repair_times = [f.repair_hours for f in period_failures]

        mttr_hours = statistics.mean(repair_times)
        std_dev = statistics.stdev(repair_times) if len(repair_times) > 1 else 0

        # Calculate trend
        trend = self._calculate_repair_trend(period_failures)

        return MTTRResult(
            equipment_id=equipment_id,
            mttr_hours=round(mttr_hours, 2),
            min_repair_time=round(min(repair_times), 2),
            max_repair_time=round(max(repair_times), 2),
            repair_count=len(period_failures),
            std_deviation=round(std_dev, 2),
            trend=trend
        )

    def calculate_availability(
        self,
        equipment_id: str,
        period_days: int = 365,
        assumed_operating_hours_per_day: float = 16.0
    ) -> AvailabilityResult:
        """
        Calculate equipment availability.

        Availability = (Total Time - Downtime) / Total Time * 100
        Or using MTBF/MTTR: Availability = MTBF / (MTBF + MTTR)
        """
        # Filter failures for this equipment
        equipment_failures = [
            f for f in self.failure_events
            if f.equipment_id == equipment_id
        ]

        # Calculate period boundaries
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)

        # Filter within period
        period_failures = [
            f for f in equipment_failures
            if f.failure_date and start_date <= f.failure_date <= end_date
        ]

        total_period_hours = period_days * 24  # Calendar time
        potential_operating_hours = period_days * assumed_operating_hours_per_day

        # Calculate unplanned downtime
        unplanned_downtime = sum(f.downtime_hours for f in period_failures)

        # Estimate planned downtime (assume 5% of operating time)
        planned_downtime = potential_operating_hours * 0.05

        total_downtime = unplanned_downtime + planned_downtime
        uptime_hours = potential_operating_hours - unplanned_downtime

        # Calculate availability
        availability = (uptime_hours / potential_operating_hours) * 100 if potential_operating_hours > 0 else 100

        return AvailabilityResult(
            equipment_id=equipment_id,
            availability_percent=round(max(0, min(100, availability)), 2),
            uptime_hours=round(uptime_hours, 2),
            downtime_hours=round(total_downtime, 2),
            planned_downtime_hours=round(planned_downtime, 2),
            unplanned_downtime_hours=round(unplanned_downtime, 2),
            total_period_hours=round(total_period_hours, 2)
        )

    def perform_fmea_analysis(self, period_days: int = 365) -> List[FMEAItem]:
        """
        Perform Failure Mode and Effects Analysis.

        Calculates Risk Priority Number (RPN) for each failure mode:
        RPN = Severity × Occurrence × Detection
        """
        # Group failures by failure mode
        failure_modes: Dict[str, List[FailureEvent]] = defaultdict(list)

        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)

        for failure in self.failure_events:
            if failure.failure_date and start_date <= failure.failure_date <= end_date:
                failure_modes[failure.failure_mode].append(failure)

        fmea_items = []
        total_failures = len([f for f in self.failure_events
                            if f.failure_date and start_date <= f.failure_date <= end_date])

        for mode, failures in failure_modes.items():
            if mode == 'UNKNOWN':
                continue

            # Calculate severity (max severity encountered)
            severity = max(f.severity.value for f in failures)

            # Calculate occurrence based on frequency
            occurrence_rate = len(failures) / max(1, total_failures)
            occurrence = self._map_occurrence_to_rating(occurrence_rate, len(failures))

            # Detection rating (based on whether issues were caught early)
            detection = self._estimate_detection_rating(failures)

            # Calculate RPN
            rpn = severity * occurrence * detection

            # Get affected equipment
            equipment_affected = list(set(f.equipment_id for f in failures))

            # Generate recommended action based on RPN
            recommended_action = self._generate_fmea_action(rpn, mode, severity)

            fmea_items.append(FMEAItem(
                failure_mode=mode,
                potential_effect=self._get_failure_effect(failures),
                severity=severity,
                occurrence=occurrence,
                detection=detection,
                rpn=rpn,
                recommended_action=recommended_action,
                current_controls="Standard PM procedures",
                equipment_affected=equipment_affected,
                occurrence_count=len(failures)
            ))

        # Sort by RPN descending
        fmea_items.sort(key=lambda x: x.rpn, reverse=True)

        return fmea_items

    def calculate_reliability_score(
        self,
        equipment_id: str,
        period_days: int = 365
    ) -> ReliabilityScore:
        """
        Calculate comprehensive reliability score for equipment.
        """
        # Get component metrics
        mtbf = self.calculate_mtbf(equipment_id, period_days)
        mttr = self.calculate_mttr(equipment_id, period_days)
        availability = self.calculate_availability(equipment_id, period_days)

        # Score MTBF (target: > 2000 hours = 100%)
        mtbf_score = min(100, (mtbf.mtbf_hours / 2000) * 100)

        # Score MTTR (target: < 4 hours = 100%)
        if mttr.mttr_hours <= 0:
            mttr_score = 100
        else:
            mttr_score = max(0, min(100, (1 - (mttr.mttr_hours - 4) / 20) * 100))

        # Availability score
        availability_score = availability.availability_percent

        # Failure trend score
        trend_score = 80  # Default
        if mtbf.trend == 'improving':
            trend_score = 100
        elif mtbf.trend == 'degrading':
            trend_score = 50

        # Maintenance compliance score (placeholder - would need PM order data)
        maintenance_compliance_score = 85

        # Calculate overall score (weighted average)
        overall_score = (
            mtbf_score * 0.25 +
            mttr_score * 0.20 +
            availability_score * 0.30 +
            trend_score * 0.15 +
            maintenance_compliance_score * 0.10
        )

        # Determine risk level
        risk_level = self._determine_risk_level(overall_score, mtbf, availability)

        # Generate recommendations
        recommendations = self._generate_reliability_recommendations(
            mtbf, mttr, availability, overall_score
        )

        return ReliabilityScore(
            equipment_id=equipment_id,
            overall_score=round(overall_score, 1),
            mtbf_score=round(mtbf_score, 1),
            mttr_score=round(mttr_score, 1),
            availability_score=round(availability_score, 1),
            failure_trend_score=round(trend_score, 1),
            maintenance_compliance_score=round(maintenance_compliance_score, 1),
            risk_level=risk_level,
            recommendations=recommendations
        )

    def estimate_weibull_parameters(
        self,
        equipment_id: str,
        period_days: int = 365
    ) -> WeibullParameters:
        """
        Estimate Weibull distribution parameters for failure analysis.

        Beta (shape parameter):
        - β < 1: Infant mortality (decreasing failure rate)
        - β = 1: Random failures (constant failure rate)
        - β > 1: Wear-out (increasing failure rate)
        """
        # Filter failures for this equipment
        equipment_failures = [
            f for f in self.failure_events
            if f.equipment_id == equipment_id and f.failure_date
        ]

        # Sort by date
        equipment_failures.sort(key=lambda x: x.failure_date)

        if len(equipment_failures) < 3:
            # Not enough data for meaningful Weibull analysis
            return WeibullParameters(
                equipment_id=equipment_id,
                shape_parameter=1.0,  # Assume random
                scale_parameter=1000.0,
                failure_pattern='random',
                reliability_at_time={30: 0.95, 90: 0.85, 180: 0.75, 365: 0.60}
            )

        # Calculate time between failures
        tbf_values = []
        for i in range(1, len(equipment_failures)):
            delta = (equipment_failures[i].failure_date -
                    equipment_failures[i-1].failure_date)
            tbf_hours = delta.total_seconds() / 3600
            if tbf_hours > 0:
                tbf_values.append(tbf_hours)

        if not tbf_values:
            return WeibullParameters(
                equipment_id=equipment_id,
                shape_parameter=1.0,
                scale_parameter=1000.0,
                failure_pattern='random',
                reliability_at_time={30: 0.95, 90: 0.85, 180: 0.75, 365: 0.60}
            )

        # Simplified Weibull parameter estimation
        mean_tbf = statistics.mean(tbf_values)
        std_tbf = statistics.stdev(tbf_values) if len(tbf_values) > 1 else mean_tbf * 0.3

        # Estimate shape parameter (beta) from coefficient of variation
        cv = std_tbf / mean_tbf if mean_tbf > 0 else 1.0

        # Approximate beta from CV (simplified method)
        if cv > 1.2:
            beta = 0.7  # High variability suggests infant mortality
        elif cv < 0.5:
            beta = 3.0  # Low variability suggests wear-out
        else:
            beta = 1.0 + (1.0 - cv)  # Linear approximation

        # Estimate scale parameter (eta)
        # Using the relationship: mean ≈ eta * Γ(1 + 1/beta)
        gamma_approx = math.gamma(1 + 1/beta) if beta > 0 else 1
        eta = mean_tbf / gamma_approx if gamma_approx > 0 else mean_tbf

        # Determine failure pattern
        if beta < 0.95:
            failure_pattern = 'infant_mortality'
        elif beta > 1.05:
            failure_pattern = 'wear_out'
        else:
            failure_pattern = 'random'

        # Calculate reliability at various times
        reliability_at_time = {}
        for days in [30, 90, 180, 365]:
            hours = days * 16  # Operating hours
            # R(t) = exp(-(t/eta)^beta)
            if eta > 0:
                r_t = math.exp(-((hours / eta) ** beta))
                reliability_at_time[days] = round(max(0, min(1, r_t)), 3)
            else:
                reliability_at_time[days] = 0.5

        return WeibullParameters(
            equipment_id=equipment_id,
            shape_parameter=round(beta, 2),
            scale_parameter=round(eta, 2),
            failure_pattern=failure_pattern,
            reliability_at_time=reliability_at_time
        )

    def generate_predictive_indicators(
        self,
        equipment_id: str,
        period_days: int = 365
    ) -> PredictiveMaintenanceIndicator:
        """
        Generate predictive maintenance indicators for equipment.
        """
        mtbf = self.calculate_mtbf(equipment_id, period_days)
        weibull = self.estimate_weibull_parameters(equipment_id, period_days)

        # Get most recent failure
        equipment_failures = [
            f for f in self.failure_events
            if f.equipment_id == equipment_id and f.failure_date
        ]
        equipment_failures.sort(key=lambda x: x.failure_date, reverse=True)

        # Calculate time since last failure
        if equipment_failures:
            last_failure = equipment_failures[0]
            time_since_failure = (datetime.now() - last_failure.failure_date).days
        else:
            time_since_failure = period_days

        # Estimate failure probability in next 30 days
        # Using Weibull reliability function
        current_hours = time_since_failure * 16
        future_hours = (time_since_failure + 30) * 16

        eta = weibull.scale_parameter
        beta = weibull.shape_parameter

        if eta > 0:
            r_current = math.exp(-((current_hours / eta) ** beta))
            r_future = math.exp(-((future_hours / eta) ** beta))
            # Conditional probability of failure
            failure_probability = 1 - (r_future / r_current) if r_current > 0 else 0.5
        else:
            failure_probability = 0.3

        failure_probability = max(0, min(1, failure_probability))

        # Estimate remaining life
        if mtbf.mtbf_days > 0:
            estimated_remaining_life = max(0, mtbf.mtbf_days - time_since_failure)
        else:
            estimated_remaining_life = 90  # Default

        # Determine urgency
        if failure_probability > 0.7:
            urgency = 'immediate'
            recommended_action = 'Schedule immediate preventive maintenance'
        elif failure_probability > 0.5:
            urgency = 'soon'
            recommended_action = 'Plan maintenance within 2 weeks'
        elif failure_probability > 0.3:
            urgency = 'scheduled'
            recommended_action = 'Include in next scheduled maintenance window'
        else:
            urgency = 'monitor'
            recommended_action = 'Continue monitoring, no immediate action required'

        # Identify contributing factors
        contributing_factors = []

        if weibull.failure_pattern == 'wear_out':
            contributing_factors.append({
                'factor': 'Wear-out pattern detected',
                'impact': 'high',
                'description': 'Equipment showing age-related degradation'
            })

        if mtbf.trend == 'degrading':
            contributing_factors.append({
                'factor': 'Decreasing MTBF trend',
                'impact': 'high',
                'description': 'Time between failures is decreasing'
            })

        if time_since_failure > mtbf.mtbf_days * 0.8:
            contributing_factors.append({
                'factor': 'Approaching expected failure interval',
                'impact': 'medium',
                'description': f'Operating at {round(time_since_failure/mtbf.mtbf_days*100)}% of MTBF'
            })

        return PredictiveMaintenanceIndicator(
            equipment_id=equipment_id,
            predicted_failure_probability=round(failure_probability, 3),
            recommended_action=recommended_action,
            urgency=urgency,
            estimated_remaining_life_days=round(estimated_remaining_life, 1),
            confidence_level=mtbf.confidence_level,
            contributing_factors=contributing_factors
        )

    def get_equipment_summary(self, period_days: int = 365) -> Dict[str, Any]:
        """
        Get summary statistics for all equipment.
        """
        # Get unique equipment
        equipment_ids = list(set(f.equipment_id for f in self.failure_events))

        summaries = []
        for eq_id in equipment_ids:
            if eq_id == 'UNKNOWN':
                continue

            reliability = self.calculate_reliability_score(eq_id, period_days)
            availability = self.calculate_availability(eq_id, period_days)
            predictive = self.generate_predictive_indicators(eq_id, period_days)

            summaries.append({
                'equipment_id': eq_id,
                'reliability_score': reliability.overall_score,
                'availability': availability.availability_percent,
                'risk_level': reliability.risk_level,
                'failure_probability': predictive.predicted_failure_probability,
                'urgency': predictive.urgency,
                'recommendations': reliability.recommendations[:2]  # Top 2
            })

        # Sort by risk
        risk_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        summaries.sort(key=lambda x: risk_order.get(x['risk_level'], 4))

        # Calculate overall statistics
        total_equipment = len(summaries)
        avg_reliability = statistics.mean([s['reliability_score'] for s in summaries]) if summaries else 0
        avg_availability = statistics.mean([s['availability'] for s in summaries]) if summaries else 100

        critical_count = len([s for s in summaries if s['risk_level'] == 'critical'])
        high_risk_count = len([s for s in summaries if s['risk_level'] == 'high'])

        return {
            'total_equipment': total_equipment,
            'average_reliability_score': round(avg_reliability, 1),
            'average_availability': round(avg_availability, 1),
            'critical_risk_count': critical_count,
            'high_risk_count': high_risk_count,
            'equipment_summaries': summaries
        }

    def _calculate_failure_trend(self, failures: List[FailureEvent]) -> str:
        """Calculate trend based on failure frequency."""
        if len(failures) < 4:
            return 'stable'

        # Sort by date
        sorted_failures = sorted(failures, key=lambda x: x.failure_date)

        # Compare first half vs second half
        mid = len(sorted_failures) // 2
        first_half = sorted_failures[:mid]
        second_half = sorted_failures[mid:]

        if not first_half or not second_half:
            return 'stable'

        # Calculate average time between failures for each half
        def avg_tbf(failure_list):
            if len(failure_list) < 2:
                return float('inf')
            tbfs = []
            for i in range(1, len(failure_list)):
                delta = (failure_list[i].failure_date - failure_list[i-1].failure_date).days
                tbfs.append(delta)
            return statistics.mean(tbfs) if tbfs else float('inf')

        first_avg = avg_tbf(first_half)
        second_avg = avg_tbf(second_half)

        if second_avg > first_avg * 1.2:
            return 'improving'
        elif second_avg < first_avg * 0.8:
            return 'degrading'
        else:
            return 'stable'

    def _calculate_repair_trend(self, failures: List[FailureEvent]) -> str:
        """Calculate trend based on repair times."""
        if len(failures) < 4:
            return 'stable'

        sorted_failures = sorted(failures, key=lambda x: x.failure_date)
        mid = len(sorted_failures) // 2

        first_half_avg = statistics.mean([f.repair_hours for f in sorted_failures[:mid]])
        second_half_avg = statistics.mean([f.repair_hours for f in sorted_failures[mid:]])

        if second_half_avg < first_half_avg * 0.8:
            return 'improving'
        elif second_half_avg > first_half_avg * 1.2:
            return 'degrading'
        else:
            return 'stable'

    def _map_occurrence_to_rating(self, rate: float, count: int) -> int:
        """Map occurrence rate to FMEA rating."""
        if count >= 10 or rate > 0.3:
            return 10
        elif count >= 7 or rate > 0.2:
            return 8
        elif count >= 4 or rate > 0.1:
            return 5
        elif count >= 2 or rate > 0.05:
            return 3
        else:
            return 1

    def _estimate_detection_rating(self, failures: List[FailureEvent]) -> int:
        """Estimate detection rating based on failure characteristics."""
        # If failures have varying severities, detection might be poor
        severities = [f.severity.value for f in failures]

        if max(severities) >= FailureSeverity.CRITICAL.value:
            return 8  # If critical failures occur, detection is poor
        elif max(severities) >= FailureSeverity.HIGH.value:
            return 6
        else:
            return 4  # Reasonable detection

    def _generate_fmea_action(self, rpn: int, mode: str, severity: int) -> str:
        """Generate recommended action based on RPN."""
        if rpn >= 200:
            return f"URGENT: Implement design changes or additional controls for {mode}"
        elif rpn >= 100:
            return f"HIGH PRIORITY: Review and improve detection/prevention for {mode}"
        elif rpn >= 50:
            return f"MODERATE: Monitor and consider preventive measures for {mode}"
        else:
            return f"LOW: Continue current controls for {mode}"

    def _get_failure_effect(self, failures: List[FailureEvent]) -> str:
        """Get potential effect description from failures."""
        total_downtime = sum(f.downtime_hours for f in failures)
        avg_downtime = total_downtime / len(failures) if failures else 0

        if avg_downtime > 24:
            return "Extended production stoppage, significant impact"
        elif avg_downtime > 8:
            return "Production delay, moderate impact"
        elif avg_downtime > 2:
            return "Short interruption, minor impact"
        else:
            return "Minimal operational impact"

    def _determine_risk_level(
        self,
        overall_score: float,
        mtbf: MTBFResult,
        availability: AvailabilityResult
    ) -> str:
        """Determine risk level based on metrics."""
        if overall_score < 40 or availability.availability_percent < 80:
            return 'critical'
        elif overall_score < 60 or availability.availability_percent < 90:
            return 'high'
        elif overall_score < 80 or availability.availability_percent < 95:
            return 'medium'
        else:
            return 'low'

    def _generate_reliability_recommendations(
        self,
        mtbf: MTBFResult,
        mttr: MTTRResult,
        availability: AvailabilityResult,
        overall_score: float
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        if mtbf.mtbf_hours < 500:
            recommendations.append(
                "Critical: MTBF is very low. Investigate root causes and consider equipment replacement or major overhaul."
            )
        elif mtbf.mtbf_hours < 1000:
            recommendations.append(
                "Improve preventive maintenance frequency to increase time between failures."
            )

        if mttr.mttr_hours > 8:
            recommendations.append(
                "Reduce repair time by improving spare parts availability and technician training."
            )

        if availability.availability_percent < 90:
            recommendations.append(
                "Availability below target. Review maintenance strategy and consider predictive maintenance."
            )

        if mtbf.trend == 'degrading':
            recommendations.append(
                "Failure rate is increasing. Schedule detailed equipment inspection."
            )

        if not recommendations:
            recommendations.append(
                "Equipment is performing well. Continue current maintenance practices."
            )

        return recommendations


# Singleton instance
_reliability_service = None


def get_reliability_service() -> ReliabilityEngineeringService:
    """Get or create the reliability engineering service instance."""
    global _reliability_service
    if _reliability_service is None:
        _reliability_service = ReliabilityEngineeringService()
    return _reliability_service
