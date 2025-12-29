"""Achievement seed data."""

ACHIEVEMENTS = [
    # ==========================================================================
    # Workout Achievements
    # ==========================================================================
    {
        "code": "first_workout",
        "name": "First Steps",
        "description": "Complete your first workout",
        "category": "workout",
        "icon": "figure.run",
        "points": 10,
        "tier": "bronze",
        "requirement_type": "workout_count",
        "requirement_value": 1,
    },
    {
        "code": "workout_10",
        "name": "Getting Started",
        "description": "Complete 10 workouts",
        "category": "workout",
        "icon": "figure.strengthtraining.traditional",
        "points": 25,
        "tier": "bronze",
        "requirement_type": "workout_count",
        "requirement_value": 10,
    },
    {
        "code": "workout_50",
        "name": "Dedicated",
        "description": "Complete 50 workouts",
        "category": "workout",
        "icon": "flame",
        "points": 50,
        "tier": "silver",
        "requirement_type": "workout_count",
        "requirement_value": 50,
    },
    {
        "code": "workout_100",
        "name": "Century Club",
        "description": "Complete 100 workouts",
        "category": "workout",
        "icon": "star.fill",
        "points": 100,
        "tier": "gold",
        "requirement_type": "workout_count",
        "requirement_value": 100,
    },
    {
        "code": "workout_365",
        "name": "Iron Will",
        "description": "Complete 365 workouts",
        "category": "workout",
        "icon": "crown.fill",
        "points": 250,
        "tier": "platinum",
        "requirement_type": "workout_count",
        "requirement_value": 365,
    },
    # ==========================================================================
    # Streak Achievements
    # ==========================================================================
    {
        "code": "streak_3",
        "name": "Building Momentum",
        "description": "Maintain a 3-day streak",
        "category": "consistency",
        "icon": "flame",
        "points": 15,
        "tier": "bronze",
        "requirement_type": "streak_days",
        "requirement_value": 3,
    },
    {
        "code": "streak_7",
        "name": "Week Warrior",
        "description": "Maintain a 7-day streak",
        "category": "consistency",
        "icon": "flame.fill",
        "points": 30,
        "tier": "bronze",
        "requirement_type": "streak_days",
        "requirement_value": 7,
    },
    {
        "code": "streak_30",
        "name": "Monthly Monster",
        "description": "Maintain a 30-day streak",
        "category": "consistency",
        "icon": "calendar",
        "points": 75,
        "tier": "silver",
        "requirement_type": "streak_days",
        "requirement_value": 30,
    },
    {
        "code": "streak_90",
        "name": "Quarter Champion",
        "description": "Maintain a 90-day streak",
        "category": "consistency",
        "icon": "calendar.badge.clock",
        "points": 150,
        "tier": "gold",
        "requirement_type": "streak_days",
        "requirement_value": 90,
    },
    {
        "code": "streak_365",
        "name": "Year of Iron",
        "description": "Maintain a 365-day streak",
        "category": "consistency",
        "icon": "trophy.fill",
        "points": 500,
        "tier": "platinum",
        "requirement_type": "streak_days",
        "requirement_value": 365,
    },
    # ==========================================================================
    # Strength Achievements
    # ==========================================================================
    {
        "code": "first_pr",
        "name": "Personal Best",
        "description": "Set your first personal record",
        "category": "strength",
        "icon": "trophy",
        "points": 20,
        "tier": "bronze",
        "requirement_type": "pr_count",
        "requirement_value": 1,
    },
    {
        "code": "pr_10",
        "name": "Record Breaker",
        "description": "Set 10 personal records",
        "category": "strength",
        "icon": "trophy.fill",
        "points": 50,
        "tier": "silver",
        "requirement_type": "pr_count",
        "requirement_value": 10,
    },
    {
        "code": "pr_50",
        "name": "PR Machine",
        "description": "Set 50 personal records",
        "category": "strength",
        "icon": "bolt.fill",
        "points": 100,
        "tier": "gold",
        "requirement_type": "pr_count",
        "requirement_value": 50,
    },
    {
        "code": "bodyweight_bench",
        "name": "Bodyweight Bench",
        "description": "Bench press your bodyweight",
        "category": "strength",
        "icon": "dumbbell.fill",
        "points": 75,
        "tier": "silver",
        "requirement_type": "lift_ratio",
        "requirement_value": 100,  # 100% of bodyweight
    },
    {
        "code": "2x_bodyweight_squat",
        "name": "Double Bodyweight Squat",
        "description": "Squat twice your bodyweight",
        "category": "strength",
        "icon": "figure.strengthtraining.traditional",
        "points": 150,
        "tier": "gold",
        "requirement_type": "lift_ratio",
        "requirement_value": 200,  # 200% of bodyweight
    },
    # ==========================================================================
    # Nutrition Achievements
    # ==========================================================================
    {
        "code": "first_meal_log",
        "name": "Calorie Counter",
        "description": "Log your first meal",
        "category": "nutrition",
        "icon": "fork.knife",
        "points": 10,
        "tier": "bronze",
        "requirement_type": "meal_log_count",
        "requirement_value": 1,
    },
    {
        "code": "meal_log_100",
        "name": "Nutrition Nerd",
        "description": "Log 100 meals",
        "category": "nutrition",
        "icon": "chart.bar.fill",
        "points": 50,
        "tier": "silver",
        "requirement_type": "meal_log_count",
        "requirement_value": 100,
    },
    {
        "code": "protein_goal_7",
        "name": "Protein Pro",
        "description": "Hit your protein goal 7 days in a row",
        "category": "nutrition",
        "icon": "leaf.fill",
        "points": 40,
        "tier": "silver",
        "requirement_type": "protein_streak",
        "requirement_value": 7,
    },
    {
        "code": "hydration_hero",
        "name": "Hydration Hero",
        "description": "Hit your water goal 30 days in a row",
        "category": "nutrition",
        "icon": "drop.fill",
        "points": 75,
        "tier": "gold",
        "requirement_type": "water_streak",
        "requirement_value": 30,
    },
    # ==========================================================================
    # Social Achievements
    # ==========================================================================
    {
        "code": "first_friend",
        "name": "Workout Buddy",
        "description": "Add your first friend",
        "category": "social",
        "icon": "person.2",
        "points": 15,
        "tier": "bronze",
        "requirement_type": "friend_count",
        "requirement_value": 1,
    },
    {
        "code": "social_butterfly",
        "name": "Social Butterfly",
        "description": "Add 10 friends",
        "category": "social",
        "icon": "person.3.fill",
        "points": 40,
        "tier": "silver",
        "requirement_type": "friend_count",
        "requirement_value": 10,
    },
    {
        "code": "challenge_complete",
        "name": "Challenger",
        "description": "Complete your first challenge",
        "category": "social",
        "icon": "flag.fill",
        "points": 25,
        "tier": "bronze",
        "requirement_type": "challenge_count",
        "requirement_value": 1,
    },
    {
        "code": "challenge_10",
        "name": "Challenge Champion",
        "description": "Complete 10 challenges",
        "category": "social",
        "icon": "medal.fill",
        "points": 75,
        "tier": "gold",
        "requirement_type": "challenge_count",
        "requirement_value": 10,
    },
    # ==========================================================================
    # Weight Goals
    # ==========================================================================
    {
        "code": "weight_loss_5kg",
        "name": "First Milestone",
        "description": "Lose 5kg from your starting weight",
        "category": "weight",
        "icon": "arrow.down.circle.fill",
        "points": 50,
        "tier": "silver",
        "requirement_type": "weight_loss",
        "requirement_value": 5,
    },
    {
        "code": "weight_loss_10kg",
        "name": "Transformation",
        "description": "Lose 10kg from your starting weight",
        "category": "weight",
        "icon": "figure.stand",
        "points": 100,
        "tier": "gold",
        "requirement_type": "weight_loss",
        "requirement_value": 10,
    },
    {
        "code": "muscle_gain_5kg",
        "name": "Gains Train",
        "description": "Gain 5kg of lean mass",
        "category": "weight",
        "icon": "arrow.up.circle.fill",
        "points": 50,
        "tier": "silver",
        "requirement_type": "weight_gain",
        "requirement_value": 5,
    },
]


async def seed_achievements(db):
    """Seed achievements into database."""
    from sqlalchemy import select
    from app.infrastructure.database import Achievement

    for achievement_data in ACHIEVEMENTS:
        # Check if already exists
        result = await db.execute(
            select(Achievement).where(Achievement.code == achievement_data["code"])
        )
        existing = result.scalar_one_or_none()

        if not existing:
            achievement = Achievement(**achievement_data)
            db.add(achievement)

    await db.commit()
