"""Progress tracking schemas - photos, measurements, achievements."""

from datetime import datetime
from pydantic import BaseModel, Field


# =============================================================================
# Progress Photos
# =============================================================================


class ProgressPhotoCreate(BaseModel):
    """Request to create a progress photo."""

    photo_url: str
    thumbnail_url: str | None = None
    photo_type: str = Field(default="front", pattern="^(front|side|back)$")
    weight_kg: float | None = None
    notes: str | None = None
    taken_at: datetime | None = None


class ProgressPhotoResponse(BaseModel):
    """Progress photo response."""

    id: str
    photo_url: str
    thumbnail_url: str | None
    photo_type: str
    weight_kg: float | None
    notes: str | None
    taken_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Body Measurements
# =============================================================================


class BodyMeasurementCreate(BaseModel):
    """Request to log body measurements."""

    neck_cm: float | None = None
    shoulders_cm: float | None = None
    chest_cm: float | None = None
    left_bicep_cm: float | None = None
    right_bicep_cm: float | None = None
    left_forearm_cm: float | None = None
    right_forearm_cm: float | None = None
    waist_cm: float | None = None
    hips_cm: float | None = None
    left_thigh_cm: float | None = None
    right_thigh_cm: float | None = None
    left_calf_cm: float | None = None
    right_calf_cm: float | None = None
    body_fat_percentage: float | None = Field(None, ge=0, le=100)
    notes: str | None = None
    measured_at: datetime | None = None


class BodyMeasurementResponse(BaseModel):
    """Body measurement response."""

    id: str
    measured_at: datetime
    neck_cm: float | None
    shoulders_cm: float | None
    chest_cm: float | None
    left_bicep_cm: float | None
    right_bicep_cm: float | None
    left_forearm_cm: float | None
    right_forearm_cm: float | None
    waist_cm: float | None
    hips_cm: float | None
    left_thigh_cm: float | None
    right_thigh_cm: float | None
    left_calf_cm: float | None
    right_calf_cm: float | None
    body_fat_percentage: float | None
    notes: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Workout Templates
# =============================================================================


class WorkoutTemplateCreate(BaseModel):
    """Request to create a workout template."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    workout_type: str | None = Field(
        None, pattern="^(strength|cardio|flexibility|mixed)$"
    )
    exercises: list[dict] = Field(default_factory=list)
    estimated_duration_min: int | None = Field(None, ge=0)
    target_muscles: list[str] = Field(default_factory=list)
    is_public: bool = False


class WorkoutTemplateUpdate(BaseModel):
    """Request to update a workout template."""

    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    workout_type: str | None = None
    exercises: list[dict] | None = None
    estimated_duration_min: int | None = None
    target_muscles: list[str] | None = None
    is_public: bool | None = None


class WorkoutTemplateResponse(BaseModel):
    """Workout template response."""

    id: str
    name: str
    description: str | None
    workout_type: str | None
    exercises: list[dict]
    estimated_duration_min: int | None
    target_muscles: list[str]
    is_public: bool
    times_used: int
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Achievements
# =============================================================================


class AchievementResponse(BaseModel):
    """Achievement definition response."""

    id: str
    code: str
    name: str
    description: str
    category: str
    icon: str
    points: int
    tier: str
    requirement_type: str
    requirement_value: int

    class Config:
        from_attributes = True


class UserAchievementResponse(BaseModel):
    """User's achievement response."""

    id: str
    achievement: AchievementResponse
    unlocked_at: datetime
    progress: int

    class Config:
        from_attributes = True


class AchievementProgress(BaseModel):
    """Progress toward an achievement."""

    achievement: AchievementResponse
    current_value: int
    target_value: int
    progress_percent: float
    is_unlocked: bool
    unlocked_at: datetime | None = None


# =============================================================================
# Challenges
# =============================================================================


class ChallengeCreate(BaseModel):
    """Request to create a challenge."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str
    challenge_type: str  # workout_count, total_volume, streak, steps
    target_value: float = Field(..., gt=0)
    start_date: datetime
    end_date: datetime
    is_public: bool = True
    max_participants: int | None = None
    reward_points: int = Field(default=100, ge=0)


class ChallengeResponse(BaseModel):
    """Challenge response."""

    id: str
    name: str
    description: str
    challenge_type: str
    target_value: float
    start_date: datetime
    end_date: datetime
    is_public: bool
    max_participants: int | None
    reward_points: int
    participant_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class ChallengeParticipantResponse(BaseModel):
    """Challenge participant info."""

    user_id: str
    user_name: str | None = None
    current_value: float
    progress_percent: float
    completed: bool
    completed_at: datetime | None
    rank: int | None = None


class ChallengeLeaderboard(BaseModel):
    """Challenge leaderboard."""

    challenge: ChallengeResponse
    participants: list[ChallengeParticipantResponse]
    my_rank: int | None = None
    my_progress: float | None = None


# =============================================================================
# Social
# =============================================================================


class FriendRequest(BaseModel):
    """Friend request."""

    friend_id: str


class FriendshipResponse(BaseModel):
    """Friendship response."""

    id: str
    user_id: str
    friend_id: str
    friend_name: str | None = None
    status: str
    created_at: datetime
    accepted_at: datetime | None

    class Config:
        from_attributes = True


class ActivityFeedItemResponse(BaseModel):
    """Activity feed item response."""

    id: str
    user_id: str
    user_name: str | None = None
    activity_type: str
    title: str
    description: str | None
    extra_data: dict | None
    visibility: str
    reaction_count: int = 0
    has_reacted: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class ReactionCreate(BaseModel):
    """Create a reaction."""

    reaction_type: str = Field(default="kudos", pattern="^(kudos|fire|muscle|clap)$")


# =============================================================================
# Weight Progress
# =============================================================================


class WeightLogCreate(BaseModel):
    """Request to log weight."""

    weight_kg: float = Field(..., gt=0, lt=500)
    notes: str | None = None
    source: str | None = "manual"
    logged_at: datetime | None = None


class WeightLogResponse(BaseModel):
    """Weight log response."""

    id: str
    weight_kg: float
    logged_at: datetime
    notes: str | None
    source: str | None

    class Config:
        from_attributes = True


class WeightTrend(BaseModel):
    """Single weight data point for trends."""

    date: datetime
    weight_kg: float


class WeightProgressResponse(BaseModel):
    """Weight progress analytics."""

    current_weight: float | None
    starting_weight: float | None
    lowest_weight: float | None
    highest_weight: float | None
    total_change: float | None
    avg_weekly_change: float | None
    trend: str | None  # losing, gaining, maintaining
    logs: list[WeightTrend]
    days_tracked: int


# =============================================================================
# Workout Progress
# =============================================================================


class WorkoutProgressResponse(BaseModel):
    """Workout progress analytics."""

    total_workouts: int
    workouts_this_week: int
    workouts_this_month: int
    current_streak: int
    longest_streak: int
    total_duration_min: int
    avg_workout_duration_min: float
    favorite_workout_type: str | None


# =============================================================================
# Nutrition Progress
# =============================================================================


class NutritionProgressResponse(BaseModel):
    """Nutrition progress analytics."""

    avg_daily_calories: float
    avg_daily_protein: float
    avg_daily_carbs: float
    avg_daily_fat: float
    days_on_target: int
    days_over_target: int
    days_under_target: int
    total_meals_logged: int


# =============================================================================
# Steps Progress
# =============================================================================


class StepsProgressResponse(BaseModel):
    """Steps progress analytics."""

    avg_daily_steps: int
    total_steps: int
    days_goal_met: int
    current_streak: int
    best_day_steps: int


# =============================================================================
# Summary
# =============================================================================


class ProgressSummaryResponse(BaseModel):
    """Complete progress summary."""

    weight: WeightProgressResponse | None
    workouts: WorkoutProgressResponse
    nutrition: NutritionProgressResponse
    steps: StepsProgressResponse
    period_days: int


# =============================================================================
# Goal Timeline Prediction
# =============================================================================


class GoalSettingsUpdate(BaseModel):
    """Update weight goal settings."""

    weight_goal_kg: float | None = Field(None, gt=0, lt=500)
    target_rate_kg_per_week: float | None = Field(None, ge=0.1, le=1.5)
    goal_target_date: datetime | None = None


class GoalSettingsResponse(BaseModel):
    """Current goal settings."""

    weight_goal_kg: float | None
    target_rate_kg_per_week: float | None
    goal_target_date: datetime | None

    class Config:
        from_attributes = True


class WeightDataPoint(BaseModel):
    """Single weight data point for prediction."""

    date: datetime
    weight_kg: float


class GoalPredictionResponse(BaseModel):
    """Weight goal prediction analytics."""

    # Current state
    current_weight: float | None
    goal_weight: float | None
    weight_to_lose: float | None

    # Target rate
    target_rate_kg_per_week: float | None
    actual_rate_kg_per_week: float | None

    # Predictions
    predicted_goal_date: datetime | None
    target_goal_date: datetime | None
    weeks_to_goal: int | None
    days_to_goal: int | None

    # Status
    is_on_track: bool
    on_track_percentage: float | None  # How close to target rate (100% = perfect)
    status: str  # "ahead", "on_track", "behind", "no_goal", "no_data"
    status_message: str

    # Historical data
    weight_history: list[WeightDataPoint]
    trend_line: list[WeightDataPoint]  # Linear regression trend

    # Progress
    total_lost: float | None
    progress_percentage: float | None  # % of goal achieved
