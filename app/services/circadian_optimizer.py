"""Circadian rhythm optimization service for meal timing."""

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone


@dataclass
class MealTimingAnalysis:
    """Analysis of user's meal timing patterns."""
    average_first_meal: time | None
    average_last_meal: time | None
    eating_window_hours: float | None
    late_night_eating_frequency: float  # Percentage of days
    consistency_score: int  # 0-100
    meal_time_variance_minutes: float


@dataclass
class CircadianRecommendation:
    """A circadian-based meal timing recommendation."""
    priority: str  # "high", "medium", "low"
    title: str
    description: str
    action: str
    benefit: str


def analyze_meal_timing(meal_logs: list[dict]) -> MealTimingAnalysis:
    """
    Analyze user's meal timing patterns.

    Args:
        meal_logs: List of meal logs with 'logged_at' datetime
    """
    if not meal_logs:
        return MealTimingAnalysis(
            average_first_meal=None,
            average_last_meal=None,
            eating_window_hours=None,
            late_night_eating_frequency=0,
            consistency_score=0,
            meal_time_variance_minutes=0,
        )

    # Group meals by date
    daily_meals: dict[str, list[datetime]] = {}
    for meal in meal_logs:
        logged_at = meal.get("logged_at")
        if isinstance(logged_at, str):
            logged_at = datetime.fromisoformat(logged_at.replace("Z", "+00:00"))
        if logged_at:
            date_key = logged_at.date().isoformat()
            if date_key not in daily_meals:
                daily_meals[date_key] = []
            daily_meals[date_key].append(logged_at)

    if not daily_meals:
        return MealTimingAnalysis(
            average_first_meal=None,
            average_last_meal=None,
            eating_window_hours=None,
            late_night_eating_frequency=0,
            consistency_score=0,
            meal_time_variance_minutes=0,
        )

    # Calculate first and last meal times for each day
    first_meal_minutes = []
    last_meal_minutes = []
    eating_windows = []
    late_night_days = 0

    for date_key, meals in daily_meals.items():
        sorted_meals = sorted(meals)
        first = sorted_meals[0]
        last = sorted_meals[-1]

        # Convert to minutes from midnight
        first_mins = first.hour * 60 + first.minute
        last_mins = last.hour * 60 + last.minute

        first_meal_minutes.append(first_mins)
        last_meal_minutes.append(last_mins)

        # Calculate eating window
        if last_mins > first_mins:
            eating_windows.append((last_mins - first_mins) / 60)

        # Check for late night eating (after 9 PM)
        if last.hour >= 21:
            late_night_days += 1

    # Calculate averages
    avg_first_mins = sum(first_meal_minutes) / len(first_meal_minutes)
    avg_last_mins = sum(last_meal_minutes) / len(last_meal_minutes)
    avg_eating_window = sum(eating_windows) / len(eating_windows) if eating_windows else 0

    avg_first_meal = time(int(avg_first_mins // 60), int(avg_first_mins % 60))
    avg_last_meal = time(int(avg_last_mins // 60), int(avg_last_mins % 60))

    # Calculate variance
    variance_first = sum((m - avg_first_mins) ** 2 for m in first_meal_minutes) / len(first_meal_minutes)
    variance_last = sum((m - avg_last_mins) ** 2 for m in last_meal_minutes) / len(last_meal_minutes)
    avg_variance = (variance_first + variance_last) / 2

    # Calculate consistency score (lower variance = higher consistency)
    # Perfect consistency would be 0 variance, terrible would be 180+ minute variance
    max_variance = 180 ** 2  # 3 hours squared
    consistency_score = max(0, min(100, int(100 * (1 - avg_variance / max_variance))))

    late_night_frequency = (late_night_days / len(daily_meals)) * 100

    return MealTimingAnalysis(
        average_first_meal=avg_first_meal,
        average_last_meal=avg_last_meal,
        eating_window_hours=round(avg_eating_window, 1),
        late_night_eating_frequency=round(late_night_frequency, 1),
        consistency_score=consistency_score,
        meal_time_variance_minutes=round(avg_variance ** 0.5, 1),
    )


def get_circadian_recommendations(analysis: MealTimingAnalysis) -> list[CircadianRecommendation]:
    """
    Generate personalized circadian recommendations based on analysis.
    """
    recommendations = []

    # Check eating window
    if analysis.eating_window_hours and analysis.eating_window_hours > 12:
        recommendations.append(CircadianRecommendation(
            priority="high",
            title="Consider a Shorter Eating Window",
            description=f"Your eating window is {analysis.eating_window_hours:.1f} hours. Research suggests 10-12 hours may be optimal.",
            action="Try to finish eating 2-3 hours earlier each day",
            benefit="Improved metabolic health and sleep quality",
        ))

    # Check late night eating
    if analysis.late_night_eating_frequency > 30:
        recommendations.append(CircadianRecommendation(
            priority="high",
            title="Reduce Late Night Eating",
            description=f"You eat after 9 PM on {analysis.late_night_eating_frequency:.0f}% of days.",
            action="Aim to finish your last meal by 8 PM",
            benefit="Better sleep and improved morning energy levels",
        ))

    # Check consistency
    if analysis.consistency_score < 50:
        recommendations.append(CircadianRecommendation(
            priority="medium",
            title="Improve Meal Timing Consistency",
            description="Your meal times vary significantly day to day.",
            action="Try to eat at similar times each day",
            benefit="Regulated hunger hormones and improved metabolism",
        ))

    # Check first meal timing
    if analysis.average_first_meal and analysis.average_first_meal.hour < 6:
        recommendations.append(CircadianRecommendation(
            priority="low",
            title="Consider Delaying Breakfast",
            description="Very early eating may not align with your circadian rhythm.",
            action="Wait until at least 7-8 AM for your first meal if possible",
            benefit="Better alignment with natural cortisol rhythms",
        ))
    elif analysis.average_first_meal and analysis.average_first_meal.hour > 11:
        recommendations.append(CircadianRecommendation(
            priority="medium",
            title="Consider Earlier First Meal",
            description="Late first meals may disrupt metabolic timing.",
            action="Try having a light breakfast by 10 AM",
            benefit="Improved energy levels and metabolism throughout the day",
        ))

    # If everything looks good
    if not recommendations:
        recommendations.append(CircadianRecommendation(
            priority="low",
            title="Great Meal Timing!",
            description="Your eating patterns align well with circadian principles.",
            action="Keep up the good work!",
            benefit="Optimal metabolic health",
        ))

    return recommendations


def get_optimal_meal_times(wake_time: time, sleep_time: time) -> dict:
    """
    Suggest optimal meal times based on wake/sleep schedule.
    """
    wake_minutes = wake_time.hour * 60 + wake_time.minute
    sleep_minutes = sleep_time.hour * 60 + sleep_time.minute

    # Handle overnight sleep
    if sleep_minutes < wake_minutes:
        sleep_minutes += 24 * 60

    # Calculate optimal windows
    # Breakfast: 1-2 hours after waking
    breakfast_mins = wake_minutes + 90
    breakfast = time(int((breakfast_mins % 1440) // 60), int(breakfast_mins % 60))

    # Lunch: 4-5 hours after breakfast (mid-day)
    lunch_mins = wake_minutes + 360  # 6 hours after wake
    lunch = time(int((lunch_mins % 1440) // 60), int(lunch_mins % 60))

    # Dinner: 3 hours before sleep
    dinner_mins = sleep_minutes - 180
    dinner = time(int((dinner_mins % 1440) // 60), int(dinner_mins % 60))

    # Last meal cutoff: 2-3 hours before sleep
    cutoff_mins = sleep_minutes - 150
    cutoff = time(int((cutoff_mins % 1440) // 60), int(cutoff_mins % 60))

    return {
        "breakfast": breakfast.strftime("%H:%M"),
        "lunch": lunch.strftime("%H:%M"),
        "dinner": dinner.strftime("%H:%M"),
        "eating_cutoff": cutoff.strftime("%H:%M"),
        "eating_window_hours": 10,
    }
