"""Menstrual cycle analyzer service.

Provides phase detection, predictions, and personalized recommendations
based on the user's cycle phase. Integrates with AI for enhanced
context-aware suggestions.
"""

from datetime import datetime, timedelta
from typing import Optional

from app.schemas.menstrual_cycle import (
    CyclePhase,
    CycleRecommendationsResponse,
    CycleStatusResponse,
)


# =============================================================================
# Phase Definitions (typical cycle lengths)
# =============================================================================

# Standard phase lengths for a 28-day cycle
PHASE_LENGTHS = {
    CyclePhase.menstruation: (1, 5),     # Days 1-5
    CyclePhase.follicular: (6, 13),       # Days 6-13
    CyclePhase.ovulation: (14, 16),       # Days 14-16
    CyclePhase.luteal: (17, 28),          # Days 17-28
}

# Fertile window typically spans days 10-17 (5 days before ovulation + ovulation)
FERTILE_WINDOW = (10, 17)


# =============================================================================
# Phase-Specific Recommendations
# =============================================================================

PHASE_RECOMMENDATIONS = {
    CyclePhase.menstruation: {
        "phase_description": "Your body is shedding the uterine lining. Energy levels may be lower, and you may experience cramps or fatigue.",
        "nutrition_tips": [
            "Focus on iron-rich foods to replenish blood loss",
            "Pair iron with vitamin C for better absorption",
            "Stay well-hydrated with warm beverages",
            "Opt for anti-inflammatory foods to reduce cramps",
            "Include magnesium-rich foods to ease muscle tension",
        ],
        "recommended_foods": [
            "Spinach", "Red meat", "Lentils", "Dark chocolate",
            "Ginger tea", "Turmeric", "Salmon", "Leafy greens",
            "Citrus fruits", "Nuts and seeds"
        ],
        "foods_to_limit": [
            "Caffeine (can worsen cramps)",
            "Alcohol (dehydrating)",
            "Salty foods (increase bloating)",
            "Processed sugars",
        ],
        "workout_tips": [
            "Listen to your body - rest if needed",
            "Gentle yoga or stretching can help cramps",
            "Light walking is beneficial",
            "Avoid high-intensity workouts if fatigued",
            "Focus on mobility and flexibility",
        ],
        "workout_intensity": "light",
        "self_care_tips": [
            "Use a heating pad for cramps",
            "Prioritize sleep and rest",
            "Take warm baths to relax muscles",
            "Practice deep breathing exercises",
        ],
    },
    CyclePhase.follicular: {
        "phase_description": "Estrogen is rising, boosting your mood and energy. This is a great time for new challenges and high-energy activities.",
        "nutrition_tips": [
            "Focus on lean proteins to support muscle building",
            "Include fermented foods for gut health",
            "Eat fresh, vibrant vegetables",
            "Support estrogen metabolism with cruciferous veggies",
            "Stay energized with complex carbohydrates",
        ],
        "recommended_foods": [
            "Eggs", "Chicken breast", "Yogurt", "Kimchi",
            "Broccoli", "Brussels sprouts", "Quinoa",
            "Sweet potatoes", "Berries", "Avocado"
        ],
        "foods_to_limit": [
            "Heavy, greasy foods",
            "Excessive caffeine",
        ],
        "workout_tips": [
            "Great time for high-intensity workouts",
            "Try new exercises or classes",
            "Strength training is highly effective now",
            "Push your limits - energy is high",
            "Cardio sessions can be more intense",
        ],
        "workout_intensity": "high",
        "self_care_tips": [
            "Channel your energy into creative projects",
            "Social activities can be fulfilling",
            "Set new fitness goals",
            "Start new healthy habits",
        ],
    },
    CyclePhase.ovulation: {
        "phase_description": "Peak fertility and energy! Estrogen peaks and testosterone rises. You may feel more confident and social.",
        "nutrition_tips": [
            "Support liver detoxification to process hormones",
            "Focus on fiber to help eliminate excess estrogen",
            "Include anti-inflammatory foods",
            "Light, fresh meals work well",
            "Support hormone balance with zinc-rich foods",
        ],
        "recommended_foods": [
            "Asparagus", "Brussels sprouts", "Leafy greens",
            "Berries", "Almonds", "Flaxseeds", "Wild salmon",
            "Oysters", "Pumpkin seeds", "Citrus fruits"
        ],
        "foods_to_limit": [
            "Processed foods",
            "Excess dairy",
            "Alcohol",
        ],
        "workout_tips": [
            "Peak performance time - go all out!",
            "High-intensity interval training (HIIT)",
            "Heavy lifting for strength gains",
            "Competitive sports and activities",
            "Push for personal records",
        ],
        "workout_intensity": "high",
        "self_care_tips": [
            "Great time for social events",
            "Schedule important meetings or presentations",
            "Take on challenging projects",
            "Communication skills are heightened",
        ],
    },
    CyclePhase.luteal: {
        "phase_description": "Progesterone rises, which may cause PMS symptoms. Energy gradually decreases. Focus on nourishing and calming activities.",
        "nutrition_tips": [
            "Include complex carbs to boost serotonin",
            "Magnesium helps with mood and cravings",
            "B vitamins support energy and mood",
            "Healthy fats help balance hormones",
            "Fiber helps with potential constipation",
        ],
        "recommended_foods": [
            "Dark chocolate", "Bananas", "Chickpeas",
            "Brown rice", "Sunflower seeds", "Turkey",
            "Spinach", "Avocado", "Walnuts", "Oatmeal"
        ],
        "foods_to_limit": [
            "High-sodium foods (bloating)",
            "Refined sugars (mood swings)",
            "Caffeine (anxiety)",
            "Alcohol (sleep disruption)",
        ],
        "workout_tips": [
            "Moderate intensity is best",
            "Yoga and Pilates are beneficial",
            "Steady-state cardio (walking, swimming)",
            "Reduce intensity as period approaches",
            "Focus on maintenance, not PRs",
        ],
        "workout_intensity": "moderate",
        "self_care_tips": [
            "Prioritize rest and sleep",
            "Journal to process emotions",
            "Gentle self-massage",
            "Reduce commitments if possible",
            "Practice stress-reduction techniques",
        ],
    },
}


class CycleAnalyzer:
    """Analyzes menstrual cycle data and provides recommendations."""

    @staticmethod
    def get_cycle_day(last_period_start: datetime, current_date: datetime = None) -> int:
        """Calculate the current day in the cycle."""
        if current_date is None:
            current_date = datetime.now()

        # Normalize to date only (remove time component)
        last_start = last_period_start.date() if hasattr(last_period_start, 'date') else last_period_start
        current = current_date.date() if hasattr(current_date, 'date') else current_date

        days_since = (current - last_start).days + 1  # Day 1 is the start
        return max(1, days_since)

    @staticmethod
    def get_current_phase(
        cycle_day: int,
        cycle_length: int = 28,
        period_length: int = 5
    ) -> tuple[CyclePhase, int, int]:
        """
        Determine the current cycle phase based on cycle day.

        Returns: (phase, day_in_phase, days_remaining_in_phase)
        """
        # Adjust phase boundaries based on actual cycle length
        ratio = cycle_length / 28.0

        # Menstruation: Days 1 to period_length
        if cycle_day <= period_length:
            return (
                CyclePhase.menstruation,
                cycle_day,
                period_length - cycle_day + 1
            )

        # Calculate adjusted phase boundaries
        follicular_end = int(13 * ratio)
        ovulation_end = int(16 * ratio)

        # Follicular: After period to ~day 13
        if cycle_day <= follicular_end:
            phase_day = cycle_day - period_length
            return (
                CyclePhase.follicular,
                phase_day,
                follicular_end - cycle_day + 1
            )

        # Ovulation: ~days 14-16
        if cycle_day <= ovulation_end:
            phase_day = cycle_day - follicular_end
            return (
                CyclePhase.ovulation,
                phase_day,
                ovulation_end - cycle_day + 1
            )

        # Luteal: Rest of cycle
        phase_day = cycle_day - ovulation_end
        return (
            CyclePhase.luteal,
            phase_day,
            cycle_length - cycle_day + 1
        )

    @staticmethod
    def predict_next_period(
        last_period_start: datetime,
        avg_cycle_length: int = 28
    ) -> datetime:
        """Predict the next period start date."""
        return last_period_start + timedelta(days=avg_cycle_length)

    @staticmethod
    def is_fertile_window(cycle_day: int, cycle_length: int = 28) -> bool:
        """Check if current day is within the fertile window."""
        # Fertile window is typically 5 days before ovulation + ovulation day
        # Ovulation usually occurs around day 14 of a 28-day cycle
        ratio = cycle_length / 28.0
        fertile_start = int(10 * ratio)
        fertile_end = int(17 * ratio)
        return fertile_start <= cycle_day <= fertile_end

    @staticmethod
    def get_ovulation_day(cycle_length: int = 28) -> int:
        """Estimate ovulation day based on cycle length."""
        # Ovulation typically occurs 14 days before the next period
        return cycle_length - 14

    @classmethod
    def get_cycle_status(
        cls,
        last_period_start: Optional[datetime],
        avg_cycle_length: int = 28,
        avg_period_length: int = 5
    ) -> CycleStatusResponse:
        """Get comprehensive cycle status."""
        if not last_period_start:
            return CycleStatusResponse(
                current_phase="unknown",
                cycle_day=0,
                days_until_period=None,
                next_period_date=None,
                is_fertile_window=False,
                phase_day=0,
                phase_days_remaining=0,
            )

        now = datetime.now(last_period_start.tzinfo) if last_period_start.tzinfo else datetime.now()
        cycle_day = cls.get_cycle_day(last_period_start, now)

        # Handle if we're past the expected cycle length (period might be late)
        if cycle_day > avg_cycle_length:
            # Assume we're in late luteal phase waiting for period
            phase = CyclePhase.luteal
            phase_day = cycle_day - (avg_cycle_length - 11)  # Approximate
            phase_days_remaining = 0  # Period expected any time
        else:
            phase, phase_day, phase_days_remaining = cls.get_current_phase(
                cycle_day, avg_cycle_length, avg_period_length
            )

        next_period = cls.predict_next_period(last_period_start, avg_cycle_length)
        days_until = (next_period.date() - now.date()).days

        return CycleStatusResponse(
            current_phase=phase.value,
            cycle_day=cycle_day,
            days_until_period=max(0, days_until),
            next_period_date=next_period,
            is_fertile_window=cls.is_fertile_window(cycle_day, avg_cycle_length),
            phase_day=phase_day,
            phase_days_remaining=max(0, phase_days_remaining),
        )

    @classmethod
    def get_recommendations(cls, phase: CyclePhase | str) -> CycleRecommendationsResponse:
        """Get recommendations for a specific cycle phase."""
        if isinstance(phase, str):
            try:
                phase = CyclePhase(phase)
            except ValueError:
                phase = CyclePhase.follicular  # Default

        recs = PHASE_RECOMMENDATIONS.get(phase, PHASE_RECOMMENDATIONS[CyclePhase.follicular])

        return CycleRecommendationsResponse(
            phase=phase.value,
            phase_description=recs["phase_description"],
            nutrition_tips=recs["nutrition_tips"],
            recommended_foods=recs["recommended_foods"],
            foods_to_limit=recs["foods_to_limit"],
            workout_tips=recs["workout_tips"],
            workout_intensity=recs["workout_intensity"],
            self_care_tips=recs["self_care_tips"],
        )

    @staticmethod
    def calculate_average_cycle_length(period_starts: list[datetime]) -> int:
        """Calculate average cycle length from historical period start dates."""
        if len(period_starts) < 2:
            return 28  # Default

        # Sort dates chronologically
        sorted_starts = sorted(period_starts)

        # Calculate differences between consecutive periods
        cycle_lengths = []
        for i in range(1, len(sorted_starts)):
            diff = (sorted_starts[i] - sorted_starts[i-1]).days
            # Filter out unrealistic values
            if 21 <= diff <= 45:
                cycle_lengths.append(diff)

        if not cycle_lengths:
            return 28

        return round(sum(cycle_lengths) / len(cycle_lengths))

    @staticmethod
    def get_phase_aware_meal_tip(phase: CyclePhase | str, meal_type: str = None) -> str:
        """Get a meal tip based on current cycle phase."""
        if isinstance(phase, str):
            try:
                phase = CyclePhase(phase)
            except ValueError:
                return ""

        tips = {
            CyclePhase.menstruation: "Consider adding iron-rich foods like spinach or lean red meat to support your body during menstruation.",
            CyclePhase.follicular: "Your energy is rising! Great time for lighter, protein-rich meals to fuel your workouts.",
            CyclePhase.ovulation: "Focus on fiber and fresh vegetables to support hormone balance during peak fertility.",
            CyclePhase.luteal: "Include complex carbs and magnesium-rich foods to help with mood and cravings.",
        }

        return tips.get(phase, "")

    @staticmethod
    def get_phase_aware_workout_tip(phase: CyclePhase | str) -> str:
        """Get a workout tip based on current cycle phase."""
        if isinstance(phase, str):
            try:
                phase = CyclePhase(phase)
            except ValueError:
                return ""

        tips = {
            CyclePhase.menstruation: "Listen to your body today. Gentle yoga or a light walk might feel better than intense exercise.",
            CyclePhase.follicular: "Energy is building! Great time to try new exercises or push your intensity.",
            CyclePhase.ovulation: "Peak performance time! Go for your personal records or high-intensity workouts.",
            CyclePhase.luteal: "Consider moderating intensity. Steady-state cardio or yoga works well as energy decreases.",
        }

        return tips.get(phase, "")


# Singleton instance for easy access
cycle_analyzer = CycleAnalyzer()
