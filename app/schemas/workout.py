"""Workout logging schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class Exercise(BaseModel):
    """Individual exercise in a workout."""

    name: str = Field(..., min_length=1)
    sets: int | None = Field(None, ge=0)  # 0 for cardio/flexibility
    reps: int | None = Field(None, ge=0)  # 0 for cardio/flexibility
    weight_kg: float | None = Field(None, ge=0)
    duration_min: float | None = Field(None, ge=0)
    rest_sec: int | None = Field(None, ge=0)
    notes: str | None = None
    # New fields for enhanced tracking
    set_type: str | None = Field(
        None,
        pattern="^(warmup|working|failure|dropset)$",
        description="Type of set: warmup, working, failure, or dropset"
    )
    rpe: int | None = Field(
        None, ge=1, le=10,
        description="Rate of Perceived Exertion (1-10)"
    )
    is_superset: bool = Field(default=False, description="Part of a superset")
    superset_with: str | None = Field(None, description="Exercise name this is supersetted with")


WORKOUT_TYPES = [
    # Core types
    "strength",
    "cardio",
    "flexibility",
    "mixed",
    # Fitness programs
    "crossfit",
    "hyrox",
    "hiit",
    "functional",
    "endurance",
    "olympic_lifting",
    "powerlifting",
    "bodyweight",
    "circuit",
    # Combat sports
    "boxing",
    "muay_thai",
    "mma",
    "kickboxing",
    "wrestling",
    "bjj",
    # Mind-body
    "pilates",
    "yoga",
    "barre",
    # Other
    "swimming",
    "cycling",
    "running",
    "rowing",
    "sports",
]

WORKOUT_TYPE_PATTERN = f"^({'|'.join(WORKOUT_TYPES)})$"


class WorkoutSuggestion(BaseModel):
    """AI-suggested workout log before confirmation."""

    exercises: list[Exercise]
    workout_type: str | None = None  # See WORKOUT_TYPES
    estimated_duration_min: int | None = Field(None, ge=0)
    estimated_calories_burned: int | None = Field(None, ge=0)
    confidence: float = Field(..., ge=0, le=1)
    notes: str | None = None
    clarifying_questions: list[str] = Field(default_factory=list)
    suggestion_id: str | None = None


class WorkoutLogCreate(BaseModel):
    """Request body for logging a confirmed workout."""

    exercises: list[Exercise]
    workout_type: str | None = Field(
        None,
        pattern=WORKOUT_TYPE_PATTERN,
    )
    duration_min: int | None = Field(None, ge=0)
    calories_burned_est: int | None = Field(None, ge=0)
    confidence: float = Field(..., ge=0, le=1)
    notes: str | None = None
    logged_at: datetime | None = None


class PRInfo(BaseModel):
    """Information about a new PR that was set."""

    exercise_name: str
    pr_type: str  # "weight", "volume", "reps"
    new_value: float
    previous_value: float | None = None
    unit: str  # "kg", "reps", or "kg (volume)"


class WorkoutLogResponse(BaseModel):
    """Response body for a logged workout."""

    id: str
    user_id: str
    logged_at: datetime
    workout_type: str | None
    exercises: list[Exercise]
    duration_min: int | None
    calories_burned_est: int | None
    confidence: float | None
    notes: str | None
    created_at: datetime
    new_prs: list[PRInfo] = []  # Any PRs set in this workout

    class Config:
        from_attributes = True


class PersonalRecordResponse(BaseModel):
    """Response for a personal record."""

    id: str
    exercise_name: str

    # Weight PR
    max_weight_kg: float | None = None
    max_weight_reps: int | None = None
    max_weight_date: datetime | None = None

    # Volume PR
    max_volume_kg: float | None = None
    max_volume_date: datetime | None = None

    # Reps PR
    max_reps: int | None = None
    max_reps_weight_kg: float | None = None
    max_reps_date: datetime | None = None

    # Estimated 1RM (calculated from max weight and reps using Epley formula)
    estimated_1rm_kg: float | None = None

    # Tracking
    times_performed: int = 0
    last_performed: datetime | None = None
    last_weight_kg: float | None = None
    last_reps: int | None = None
    last_sets: int | None = None

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_with_1rm(cls, pr) -> "PersonalRecordResponse":
        """Create response with calculated 1RM."""
        data = {
            "id": pr.id,
            "exercise_name": pr.exercise_name,
            "max_weight_kg": pr.max_weight_kg,
            "max_weight_reps": pr.max_weight_reps,
            "max_weight_date": pr.max_weight_date,
            "max_volume_kg": pr.max_volume_kg,
            "max_volume_date": pr.max_volume_date,
            "max_reps": pr.max_reps,
            "max_reps_weight_kg": pr.max_reps_weight_kg,
            "max_reps_date": pr.max_reps_date,
            "times_performed": pr.times_performed,
            "last_performed": pr.last_performed,
            "last_weight_kg": pr.last_weight_kg,
            "last_reps": pr.last_reps,
            "last_sets": pr.last_sets,
            "estimated_1rm_kg": None,
        }
        # Calculate 1RM using Epley formula: 1RM = weight × (1 + reps/30)
        if pr.max_weight_kg and pr.max_weight_reps:
            if pr.max_weight_reps == 1:
                data["estimated_1rm_kg"] = pr.max_weight_kg
            else:
                data["estimated_1rm_kg"] = round(
                    pr.max_weight_kg * (1 + pr.max_weight_reps / 30), 1
                )
        return cls(**data)


class ExerciseAttempt(BaseModel):
    """A single attempt/set of an exercise from history."""

    workout_id: str
    logged_at: str
    weight_kg: float | None = None
    reps: int | None = None
    sets: int | None = None
    duration_min: float | None = None
    notes: str | None = None
