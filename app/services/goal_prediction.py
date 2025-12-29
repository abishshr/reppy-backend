"""Goal timeline prediction service."""

from datetime import datetime, timedelta, timezone

from app.schemas.progress import GoalPredictionResponse, WeightDataPoint


def calculate_linear_regression(
    data_points: list[tuple[float, float]]
) -> tuple[float, float]:
    """
    Calculate linear regression slope and intercept.
    Returns (slope, intercept) where y = slope * x + intercept
    """
    if len(data_points) < 2:
        return 0.0, data_points[0][1] if data_points else 0.0

    n = len(data_points)
    sum_x = sum(p[0] for p in data_points)
    sum_y = sum(p[1] for p in data_points)
    sum_xy = sum(p[0] * p[1] for p in data_points)
    sum_xx = sum(p[0] * p[0] for p in data_points)

    denominator = n * sum_xx - sum_x * sum_x
    if denominator == 0:
        return 0.0, sum_y / n

    slope = (n * sum_xy - sum_x * sum_y) / denominator
    intercept = (sum_y - slope * sum_x) / n

    return slope, intercept


def predict_weight_goal(
    weight_logs: list[tuple[datetime, float]],
    current_weight: float | None,
    goal_weight: float | None,
    target_rate_kg_per_week: float | None,
    goal_target_date: datetime | None,
    starting_weight: float | None = None,
) -> GoalPredictionResponse:
    """
    Calculate weight goal predictions based on historical data.

    Args:
        weight_logs: List of (datetime, weight_kg) tuples, sorted by date
        current_weight: Current weight in kg
        goal_weight: Target weight in kg
        target_rate_kg_per_week: Desired rate of weight loss per week
        goal_target_date: User's target date to reach goal
        starting_weight: Weight when goal was set (optional)
    """
    now = datetime.now(timezone.utc)

    # No data case
    if not weight_logs or current_weight is None:
        return GoalPredictionResponse(
            current_weight=current_weight,
            goal_weight=goal_weight,
            weight_to_lose=None,
            target_rate_kg_per_week=target_rate_kg_per_week,
            actual_rate_kg_per_week=None,
            predicted_goal_date=None,
            target_goal_date=goal_target_date,
            weeks_to_goal=None,
            days_to_goal=None,
            is_on_track=False,
            on_track_percentage=None,
            status="no_data",
            status_message="Log your weight to see predictions",
            weight_history=[],
            trend_line=[],
            total_lost=None,
            progress_percentage=None,
        )

    # No goal case
    if goal_weight is None:
        weight_history = [
            WeightDataPoint(date=log[0], weight_kg=log[1]) for log in weight_logs
        ]
        return GoalPredictionResponse(
            current_weight=current_weight,
            goal_weight=None,
            weight_to_lose=None,
            target_rate_kg_per_week=target_rate_kg_per_week,
            actual_rate_kg_per_week=None,
            predicted_goal_date=None,
            target_goal_date=None,
            weeks_to_goal=None,
            days_to_goal=None,
            is_on_track=False,
            on_track_percentage=None,
            status="no_goal",
            status_message="Set a weight goal to see predictions",
            weight_history=weight_history,
            trend_line=[],
            total_lost=None,
            progress_percentage=None,
        )

    # Calculate weight to lose
    weight_to_lose = current_weight - goal_weight

    # Calculate starting weight for progress
    start_weight = starting_weight or weight_logs[0][1]
    total_to_lose = start_weight - goal_weight
    total_lost = start_weight - current_weight

    # Progress percentage (only if losing weight toward goal)
    progress_percentage = None
    if total_to_lose > 0 and total_lost >= 0:
        progress_percentage = min(100.0, (total_lost / total_to_lose) * 100)

    # Calculate actual rate using linear regression on last 30 days
    recent_logs = [
        log for log in weight_logs if log[0] >= now - timedelta(days=30)
    ]

    if len(recent_logs) >= 2:
        # Convert dates to days from first log
        first_date = recent_logs[0][0]
        data_points = [
            ((log[0] - first_date).total_seconds() / 86400, log[1])
            for log in recent_logs
        ]
        slope, intercept = calculate_linear_regression(data_points)

        # Slope is kg per day, convert to per week
        actual_rate = slope * 7  # Negative means losing weight
    else:
        actual_rate = 0.0

    # Actual rate is negative if losing weight, but we display as positive
    actual_rate_display = -actual_rate if weight_to_lose > 0 else actual_rate

    # Predict goal date based on actual trend
    predicted_goal_date = None
    weeks_to_goal = None
    days_to_goal = None

    if actual_rate != 0 and weight_to_lose != 0:
        # Days to reach goal at current rate
        # If losing weight: weight_to_lose > 0, actual_rate < 0
        # If gaining weight: weight_to_lose < 0, actual_rate > 0
        if (weight_to_lose > 0 and actual_rate < 0) or (
            weight_to_lose < 0 and actual_rate > 0
        ):
            days = abs(weight_to_lose / (actual_rate / 7))
            days_to_goal = int(days)
            weeks_to_goal = int(days / 7)
            predicted_goal_date = now + timedelta(days=days)
        else:
            # Moving in wrong direction
            days_to_goal = None
            weeks_to_goal = None
            predicted_goal_date = None

    # Determine if on track
    is_on_track = False
    on_track_percentage = None
    status = "behind"
    status_message = ""

    target_rate = target_rate_kg_per_week or 0.5  # Default to 0.5 kg/week

    if weight_to_lose <= 0:
        # Already at or past goal
        is_on_track = True
        status = "ahead"
        status_message = "Congratulations! You've reached your goal!"
        on_track_percentage = 100.0
    elif actual_rate_display <= 0:
        # Gaining weight or maintaining when should be losing
        status = "behind"
        status_message = "You're currently gaining weight. Adjust your diet to get back on track."
        on_track_percentage = 0.0
    else:
        # Calculate how close to target rate (within 20% is on track)
        rate_ratio = actual_rate_display / target_rate
        on_track_percentage = min(100.0, rate_ratio * 100)

        if rate_ratio >= 1.2:
            status = "ahead"
            is_on_track = True
            status_message = f"Great progress! You're losing faster than your target rate."
        elif rate_ratio >= 0.8:
            status = "on_track"
            is_on_track = True
            status_message = f"You're on track to reach your goal!"
        elif rate_ratio >= 0.5:
            status = "behind"
            status_message = f"You're making progress, but slower than planned."
        else:
            status = "behind"
            status_message = f"Progress is slow. Consider adjusting your approach."

    # Add target date context
    if goal_target_date:
        days_until_target = (goal_target_date - now).days
        if days_until_target > 0 and predicted_goal_date:
            days_until_predicted = (predicted_goal_date - now).days
            if days_until_predicted <= days_until_target:
                status_message += f" You'll reach your goal before your target date!"
            else:
                days_late = days_until_predicted - days_until_target
                status_message += f" At current rate, you'll be about {days_late} days late."

    # Build weight history
    weight_history = [
        WeightDataPoint(date=log[0], weight_kg=log[1]) for log in weight_logs
    ]

    # Build trend line (from first log to predicted goal or 90 days out)
    trend_line = []
    if len(recent_logs) >= 2:
        first_date = recent_logs[0][0]
        data_points = [
            ((log[0] - first_date).total_seconds() / 86400, log[1])
            for log in recent_logs
        ]
        slope, intercept = calculate_linear_regression(data_points)

        # Generate trend points
        trend_start = weight_logs[0][0]
        trend_end = predicted_goal_date or (now + timedelta(days=90))
        total_days = (trend_end - trend_start).days

        for day in range(0, total_days + 1, max(1, total_days // 10)):
            date = trend_start + timedelta(days=day)
            # Calculate weight at this point on trend line
            days_from_first = (date - first_date).total_seconds() / 86400
            weight = slope * days_from_first + intercept
            trend_line.append(WeightDataPoint(date=date, weight_kg=round(weight, 2)))

    return GoalPredictionResponse(
        current_weight=round(current_weight, 2) if current_weight else None,
        goal_weight=round(goal_weight, 2) if goal_weight else None,
        weight_to_lose=round(weight_to_lose, 2) if weight_to_lose else None,
        target_rate_kg_per_week=target_rate,
        actual_rate_kg_per_week=(
            round(actual_rate_display, 2) if actual_rate_display else None
        ),
        predicted_goal_date=predicted_goal_date,
        target_goal_date=goal_target_date,
        weeks_to_goal=weeks_to_goal,
        days_to_goal=days_to_goal,
        is_on_track=is_on_track,
        on_track_percentage=round(on_track_percentage, 1) if on_track_percentage else None,
        status=status,
        status_message=status_message,
        weight_history=weight_history,
        trend_line=trend_line,
        total_lost=round(total_lost, 2) if total_lost else None,
        progress_percentage=round(progress_percentage, 1) if progress_percentage else None,
    )
