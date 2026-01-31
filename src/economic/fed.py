"""Fed Watch Module.

Track Federal Reserve meetings, rate decisions, and expectations.
"""

from datetime import datetime, date, timedelta, timezone
from typing import Optional
import logging

from src.economic.config import (
    RateDecision,
    FedWatchConfig,
    DEFAULT_FED_CONFIG,
)
from src.economic.models import FedMeeting, RateExpectation

logger = logging.getLogger(__name__)


class FedWatcher:
    """Tracks Federal Reserve meetings and rate expectations.
    
    Example:
        fed = FedWatcher()
        
        # Get next meeting
        next_meeting = fed.get_next_meeting()
        print(f"Next FOMC: {next_meeting.meeting_date}")
        
        # Get rate expectations
        expectations = fed.get_rate_expectations()
        print(f"Probability of hold: {expectations.prob_hold}%")
    """
    
    def __init__(self, config: Optional[FedWatchConfig] = None):
        self.config = config or DEFAULT_FED_CONFIG
        self._meetings: dict[str, FedMeeting] = {}
        self._expectations: dict[date, RateExpectation] = {}
    
    # =========================================================================
    # Meeting Management
    # =========================================================================
    
    def add_meeting(self, meeting: FedMeeting) -> None:
        """Add a Fed meeting."""
        self._meetings[meeting.meeting_id] = meeting
    
    def get_meeting(self, meeting_id: str) -> Optional[FedMeeting]:
        """Get meeting by ID."""
        return self._meetings.get(meeting_id)
    
    def get_meetings_by_date(self, target_date: date) -> list[FedMeeting]:
        """Get meetings on a specific date."""
        return [
            m for m in self._meetings.values()
            if m.meeting_date == target_date
        ]
    
    def get_next_meeting(self) -> Optional[FedMeeting]:
        """Get next upcoming FOMC meeting."""
        today = date.today()
        
        upcoming = [
            m for m in self._meetings.values()
            if m.meeting_date and m.meeting_date >= today
            and m.meeting_type == "FOMC"
        ]
        
        if not upcoming:
            return None
        
        upcoming.sort(key=lambda m: m.meeting_date)
        return upcoming[0]
    
    def get_upcoming_meetings(self, limit: int = 8) -> list[FedMeeting]:
        """Get upcoming Fed meetings."""
        today = date.today()
        
        upcoming = [
            m for m in self._meetings.values()
            if m.meeting_date and m.meeting_date >= today
        ]
        
        upcoming.sort(key=lambda m: m.meeting_date)
        return upcoming[:limit]
    
    def get_past_meetings(self, limit: int = 10) -> list[FedMeeting]:
        """Get past Fed meetings."""
        today = date.today()
        
        past = [
            m for m in self._meetings.values()
            if m.meeting_date and m.meeting_date < today
        ]
        
        past.sort(key=lambda m: m.meeting_date, reverse=True)
        return past[:limit]
    
    # =========================================================================
    # Rate Decisions
    # =========================================================================
    
    def record_decision(
        self,
        meeting_id: str,
        decision: RateDecision,
        new_rate: float,
        statement_tone: Optional[str] = None,
    ) -> Optional[FedMeeting]:
        """Record a rate decision."""
        meeting = self._meetings.get(meeting_id)
        if meeting:
            meeting.rate_before = self.config.current_rate
            meeting.rate_after = new_rate
            meeting.rate_decision = decision
            meeting.rate_change = new_rate - self.config.current_rate
            meeting.statement_tone = statement_tone
            
            # Update current rate
            self.config.current_rate = new_rate
            
            return meeting
        return None
    
    def get_rate_history(self) -> list[tuple[date, float, RateDecision]]:
        """Get rate decision history."""
        history = []
        
        for m in self._meetings.values():
            if m.rate_decision and m.meeting_date:
                history.append((
                    m.meeting_date,
                    m.rate_after or m.rate_before or 0,
                    m.rate_decision,
                ))
        
        history.sort(key=lambda x: x[0], reverse=True)
        return history
    
    def get_current_rate(self) -> float:
        """Get current Fed funds rate."""
        return self.config.current_rate
    
    def get_rate_at_date(self, target_date: date) -> Optional[float]:
        """Get rate as of a specific date."""
        meetings = [
            m for m in self._meetings.values()
            if m.meeting_date and m.meeting_date <= target_date
            and m.rate_after is not None
        ]
        
        if not meetings:
            return self.config.current_rate
        
        meetings.sort(key=lambda m: m.meeting_date, reverse=True)
        return meetings[0].rate_after
    
    # =========================================================================
    # Rate Expectations
    # =========================================================================
    
    def set_expectations(
        self,
        meeting_date: date,
        expectations: RateExpectation,
    ) -> None:
        """Set rate expectations for a meeting."""
        expectations.target_date = meeting_date
        expectations.current_rate = self.config.current_rate
        self._expectations[meeting_date] = expectations
    
    def get_expectations(
        self,
        meeting_date: Optional[date] = None,
    ) -> Optional[RateExpectation]:
        """Get rate expectations for a meeting."""
        if meeting_date is None:
            # Get next meeting
            next_meeting = self.get_next_meeting()
            if next_meeting and next_meeting.meeting_date:
                meeting_date = next_meeting.meeting_date
            else:
                return None
        
        return self._expectations.get(meeting_date)
    
    def calculate_implied_rate(
        self,
        prob_hike: float,
        prob_cut: float,
        rate_step: float = 0.25,
    ) -> float:
        """Calculate implied rate from probabilities."""
        current = self.config.current_rate
        prob_hold = 100 - prob_hike - prob_cut
        
        implied = (
            current * (prob_hold / 100) +
            (current + rate_step) * (prob_hike / 100) +
            (current - rate_step) * (prob_cut / 100)
        )
        
        return round(implied, 4)
    
    # =========================================================================
    # Analysis
    # =========================================================================
    
    def get_rate_path(self) -> list[dict]:
        """Get expected rate path based on market expectations."""
        path = []
        current_rate = self.config.current_rate
        
        for meeting in self.get_upcoming_meetings():
            exp = self._expectations.get(meeting.meeting_date)
            
            if exp:
                implied = self.calculate_implied_rate(
                    exp.prob_hike_25 + exp.prob_hike_50,
                    exp.prob_cut_25 + exp.prob_cut_50,
                )
            else:
                implied = current_rate
            
            path.append({
                "date": meeting.meeting_date,
                "meeting_type": meeting.meeting_type,
                "implied_rate": implied,
                "change_from_current": implied - self.config.current_rate,
            })
            
            current_rate = implied
        
        return path
    
    def get_meeting_summary(self, meeting_id: str) -> dict:
        """Get summary of a meeting."""
        meeting = self._meetings.get(meeting_id)
        if not meeting:
            return {}
        
        exp = self._expectations.get(meeting.meeting_date) if meeting.meeting_date else None
        
        return {
            "date": meeting.meeting_date,
            "type": meeting.meeting_type,
            "has_projections": meeting.has_projections,
            "rate_decision": meeting.rate_decision.value if meeting.rate_decision else None,
            "rate_change": meeting.rate_change,
            "was_surprise": meeting.was_surprise,
            "statement_tone": meeting.statement_tone,
            "expectations": {
                "prob_hike": exp.prob_hike_25 + exp.prob_hike_50 if exp else None,
                "prob_cut": exp.prob_cut_25 + exp.prob_cut_50 if exp else None,
                "prob_hold": exp.prob_hold if exp else None,
            } if exp else None,
        }
    
    def count_decisions(self) -> dict[str, int]:
        """Count rate decisions by type."""
        counts = {"hike": 0, "cut": 0, "hold": 0}
        
        for m in self._meetings.values():
            if m.rate_decision:
                counts[m.rate_decision.value] += 1
        
        return counts


def generate_sample_fed_data() -> FedWatcher:
    """Generate sample Fed meeting data."""
    fed = FedWatcher()
    today = date.today()
    
    # 2024 FOMC meeting dates (sample)
    fomc_dates = [
        (today + timedelta(days=15), True),   # Next meeting with SEP
        (today + timedelta(days=60), False),  # 2 months out
        (today + timedelta(days=105), True),  # With SEP
        (today + timedelta(days=150), False),
    ]
    
    for meeting_date, has_sep in fomc_dates:
        meeting = FedMeeting(
            meeting_date=meeting_date,
            meeting_type="FOMC",
            rate_before=5.50,
            has_projections=has_sep,
            prob_hike=5.0,
            prob_cut=15.0,
            prob_hold=80.0,
        )
        fed.add_meeting(meeting)
        
        # Set expectations
        fed.set_expectations(meeting_date, RateExpectation(
            target_date=meeting_date,
            prob_hike_25=5.0,
            prob_hike_50=0.0,
            prob_hold=80.0,
            prob_cut_25=12.0,
            prob_cut_50=3.0,
            implied_rate=5.47,
            current_rate=5.50,
        ))
    
    # Add some past meetings
    past_dates = [
        (today - timedelta(days=45), RateDecision.HOLD, 5.50, "hawkish"),
        (today - timedelta(days=90), RateDecision.HOLD, 5.50, "neutral"),
        (today - timedelta(days=135), RateDecision.HIKE, 5.50, "hawkish"),
    ]
    
    for meeting_date, decision, rate, tone in past_dates:
        meeting = FedMeeting(
            meeting_date=meeting_date,
            meeting_type="FOMC",
            rate_before=rate - 0.25 if decision == RateDecision.HIKE else rate,
            rate_after=rate,
            rate_decision=decision,
            rate_change=0.25 if decision == RateDecision.HIKE else 0,
            statement_tone=tone,
        )
        fed.add_meeting(meeting)
    
    return fed
