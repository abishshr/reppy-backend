"""SQLAlchemy database models."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.infrastructure.database.connection import Base


class User(Base):
    """User account."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    apple_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    profile: Mapped["UserProfile"] = relationship(back_populates="user", uselist=False)
    memories: Mapped[list["UserMemory"]] = relationship(back_populates="user")
    meal_logs: Mapped[list["MealLog"]] = relationship(back_populates="user")
    workout_logs: Mapped[list["WorkoutLog"]] = relationship(back_populates="user")
    daily_activities: Mapped[list["DailyActivity"]] = relationship(back_populates="user")
    conversation_sessions: Mapped[list["ConversationSession"]] = relationship(
        back_populates="user"
    )
    meal_plans: Mapped[list["MealPlan"]] = relationship(back_populates="user")
    grocery_lists: Mapped[list["GroceryList"]] = relationship(back_populates="user")
    workout_plans: Mapped[list["WorkoutPlan"]] = relationship(back_populates="user")
    weight_logs: Mapped[list["WeightLog"]] = relationship(back_populates="user")
    water_logs: Mapped[list["WaterLog"]] = relationship(back_populates="user")
    personal_records: Mapped[list["PersonalRecord"]] = relationship(back_populates="user")
    # New relationships
    progress_photos: Mapped[list["ProgressPhoto"]] = relationship(back_populates="user")
    body_measurements: Mapped[list["BodyMeasurement"]] = relationship(back_populates="user")
    workout_templates: Mapped[list["WorkoutTemplate"]] = relationship(back_populates="user")
    achievements: Mapped[list["UserAchievement"]] = relationship(back_populates="user")
    challenge_participations: Mapped[list["ChallengeParticipant"]] = relationship(back_populates="user")
    activity_feed: Mapped[list["ActivityFeedItem"]] = relationship(back_populates="user")
    menstrual_cycle_logs: Mapped[list["MenstrualCycleLog"]] = relationship(back_populates="user")
    menstrual_cycle_settings: Mapped["MenstrualCycleSettings"] = relationship(back_populates="user", uselist=False)
    # Fasting relationships
    fasting_sessions: Mapped[list["FastingSession"]] = relationship(back_populates="user")
    fasting_settings: Mapped["FastingSettings"] = relationship(back_populates="user", uselist=False)


class UserProfile(Base):
    """User profile with fitness preferences and goals."""

    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    name: Mapped[str | None] = mapped_column(String(100))
    age: Mapped[int | None] = mapped_column(Integer)
    sex: Mapped[str | None] = mapped_column(String(20))  # male, female, other
    height_cm: Mapped[float | None] = mapped_column(Float)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    activity_level: Mapped[str | None] = mapped_column(
        String(50)
    )  # sedentary, light, moderate, active, very_active
    goals: Mapped[list[str] | None] = mapped_column(
        JSON, default=list
    )  # fat_loss, muscle_gain, maintenance, health
    diet_style: Mapped[str | None] = mapped_column(
        String(50)
    )  # omnivore, vegetarian, vegan, keto, etc.
    allergies: Mapped[list[str] | None] = mapped_column(JSON, default=list)
    equipment: Mapped[list[str] | None] = mapped_column(
        JSON, default=list
    )  # home, gym, bodyweight
    timezone: Mapped[str | None] = mapped_column(String(50), default="UTC")
    daily_calorie_target: Mapped[int | None] = mapped_column(Integer)
    daily_protein_target: Mapped[float | None] = mapped_column(Float)
    daily_carbs_target: Mapped[float | None] = mapped_column(Float)
    daily_fat_target: Mapped[float | None] = mapped_column(Float)
    # Micronutrient targets (FDA recommendations as defaults)
    daily_sugar_target_g: Mapped[float | None] = mapped_column(Float, default=50)  # <50g recommended
    daily_fiber_target_g: Mapped[float | None] = mapped_column(Float, default=28)  # 28g recommended
    daily_sodium_target_mg: Mapped[float | None] = mapped_column(Float, default=2300)  # <2300mg recommended
    daily_saturated_fat_target_g: Mapped[float | None] = mapped_column(Float, default=20)  # <20g for 2000 cal diet
    daily_steps_goal: Mapped[int | None] = mapped_column(Integer, default=10000)
    daily_water_goal_ml: Mapped[int | None] = mapped_column(Integer, default=2500)  # 2.5L default
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Streak tracking
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_activity_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    streak_grace_hours: Mapped[int] = mapped_column(Integer, default=36)  # Hours before streak breaks

    # Goal timeline prediction
    weight_goal_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_rate_kg_per_week: Mapped[float | None] = mapped_column(Float, nullable=True)  # Negative = loss, positive = gain
    goal_target_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="profile")


class UserMemory(Base):
    """
    Learned user preferences extracted from conversations.

    This stores key facts the AI learns about the user over time,
    like food preferences, workout habits, and personal notes.
    """

    __tablename__ = "user_memories"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    category: Mapped[str] = mapped_column(
        String(50)
    )  # food_preference, workout_habit, schedule, health_note, goal, other
    fact: Mapped[str] = mapped_column(Text)  # The learned fact
    confidence: Mapped[float] = mapped_column(Float, default=0.8)  # How confident we are
    source: Mapped[str | None] = mapped_column(String(50))  # chat, onboarding, manual
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # Can be invalidated
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="memories")


class MealLog(Base):
    """Logged meal with nutrition data."""

    __tablename__ = "meal_logs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    meal_type: Mapped[str | None] = mapped_column(
        String(50)
    )  # breakfast, lunch, dinner, snack
    items: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list
    )  # [{name, quantity, unit}]
    calories: Mapped[int | None] = mapped_column(Integer)
    protein_g: Mapped[float | None] = mapped_column(Float)
    carbs_g: Mapped[float | None] = mapped_column(Float)
    fat_g: Mapped[float | None] = mapped_column(Float)
    sugar_g_est: Mapped[float | None] = mapped_column(Float)
    fiber_g_est: Mapped[float | None] = mapped_column(Float)
    sodium_mg_est: Mapped[float | None] = mapped_column(Float)
    saturated_fat_g_est: Mapped[float | None] = mapped_column(Float)
    cholesterol_mg_est: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)  # 0.0 - 1.0
    notes: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(500))

    # AI Health Analysis
    health_score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-100
    health_score_breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # {nutritional_balance, processing_level, ingredient_quality, insights, suggestions}
    ai_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Nutrient synergy insights
    synergy_insights: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    # [{type: "beneficial"/"inhibiting", nutrients: [...], message, advice}]

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="meal_logs")


class WorkoutLog(Base):
    """Logged workout session."""

    __tablename__ = "workout_logs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    workout_type: Mapped[str | None] = mapped_column(
        String(50)
    )  # strength, cardio, flexibility, mixed
    exercises: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list
    )  # [{name, sets, reps, weight_kg, duration_min, rest_sec}]
    duration_min: Mapped[int | None] = mapped_column(Integer)
    calories_burned_est: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="workout_logs")


class PersonalRecord(Base):
    """Personal records for exercises - tracks PRs per exercise."""

    __tablename__ = "personal_records"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    exercise_name: Mapped[str] = mapped_column(String(200))  # Normalized exercise name

    # Weight PR (heaviest weight lifted)
    max_weight_kg: Mapped[float | None] = mapped_column(Float)
    max_weight_reps: Mapped[int | None] = mapped_column(Integer)  # Reps at max weight
    max_weight_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    max_weight_workout_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))

    # Volume PR (weight × reps × sets in single session)
    max_volume_kg: Mapped[float | None] = mapped_column(Float)
    max_volume_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    max_volume_workout_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))

    # Reps PR (most reps at any weight)
    max_reps: Mapped[int | None] = mapped_column(Integer)
    max_reps_weight_kg: Mapped[float | None] = mapped_column(Float)
    max_reps_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Tracking
    times_performed: Mapped[int] = mapped_column(Integer, default=0)
    last_performed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_weight_kg: Mapped[float | None] = mapped_column(Float)
    last_reps: Mapped[int | None] = mapped_column(Integer)
    last_sets: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Unique constraint - one PR record per user per exercise
    __table_args__ = (
        UniqueConstraint("user_id", "exercise_name", name="uq_user_exercise_pr"),
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="personal_records")


class DailyActivity(Base):
    """Daily activity tracking (steps, etc.)."""

    __tablename__ = "daily_activity"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    steps: Mapped[int | None] = mapped_column(Integer, default=0)
    source: Mapped[str | None] = mapped_column(String(50))  # apple_health, manual, etc.
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Unique constraint for user + date + source
    __table_args__ = (UniqueConstraint("user_id", "date", "source", name="uq_user_date_source"),)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="daily_activities")


class ConversationSession(Base):
    """AI conversation session for context tracking."""

    __tablename__ = "conversation_sessions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary_text: Mapped[str | None] = mapped_column(Text)
    key_facts: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="conversation_sessions")
    tool_calls: Mapped[list["ToolCall"]] = relationship(back_populates="session")


class ToolCall(Base):
    """Record of AI tool calls for debugging and analytics."""

    __tablename__ = "tool_calls"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    session_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("conversation_sessions.id", ondelete="CASCADE")
    )
    tool_name: Mapped[str] = mapped_column(String(100))
    args: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(50))  # success, error, pending
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    session: Mapped["ConversationSession"] = relationship(back_populates="tool_calls")


class MealPlan(Base):
    """AI-generated meal plan for a user."""

    __tablename__ = "meal_plans"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(200))  # e.g., "Week 1 - Fat Loss"
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    goal: Mapped[str | None] = mapped_column(String(100))  # fat_loss, muscle_gain, etc.
    daily_calorie_target: Mapped[int | None] = mapped_column(Integer)
    daily_protein_target: Mapped[float | None] = mapped_column(Float)
    daily_carbs_target: Mapped[float | None] = mapped_column(Float)
    daily_fat_target: Mapped[float | None] = mapped_column(Float)
    preferences: Mapped[dict[str, Any] | None] = mapped_column(JSON)  # diet style, allergies
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="meal_plans")
    days: Mapped[list["MealPlanDay"]] = relationship(
        back_populates="meal_plan", cascade="all, delete-orphan"
    )


class MealPlanDay(Base):
    """A single day within a meal plan."""

    __tablename__ = "meal_plan_days"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    meal_plan_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("meal_plans.id", ondelete="CASCADE")
    )
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    day_number: Mapped[int] = mapped_column(Integer)  # 1-7 for weekly plan
    meals: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    # Each meal: {type: "breakfast", name: "...", items: [...], calories, protein, carbs, fat, recipe}
    total_calories: Mapped[int | None] = mapped_column(Integer)
    total_protein: Mapped[float | None] = mapped_column(Float)
    total_carbs: Mapped[float | None] = mapped_column(Float)
    total_fat: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    meal_plan: Mapped["MealPlan"] = relationship(back_populates="days")


class GroceryList(Base):
    """Grocery list generated from a meal plan."""

    __tablename__ = "grocery_lists"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    meal_plan_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("meal_plans.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(200))
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    # Each item: {name, quantity, unit, category, checked}
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="grocery_lists")


class WorkoutPlan(Base):
    """AI-generated workout plan/program for a user."""

    __tablename__ = "workout_plans"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(200))  # e.g., "8-Week Strength Program"
    description: Mapped[str | None] = mapped_column(Text)
    duration_weeks: Mapped[int] = mapped_column(Integer)  # Total program duration
    days_per_week: Mapped[int] = mapped_column(Integer)  # Training days per week
    goal: Mapped[str | None] = mapped_column(
        String(100)
    )  # strength, hypertrophy, endurance, fat_loss, general_fitness
    difficulty: Mapped[str | None] = mapped_column(
        String(50)
    )  # beginner, intermediate, advanced
    equipment: Mapped[list[str] | None] = mapped_column(
        JSON, default=list
    )  # Required equipment
    split_type: Mapped[str | None] = mapped_column(
        String(50)
    )  # full_body, upper_lower, push_pull_legs, bro_split
    preferences: Mapped[dict[str, Any] | None] = mapped_column(JSON)  # Additional preferences
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    current_week: Mapped[int] = mapped_column(Integer, default=1)
    current_day: Mapped[int] = mapped_column(Integer, default=1)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="workout_plans")
    days: Mapped[list["WorkoutPlanDay"]] = relationship(
        back_populates="workout_plan", cascade="all, delete-orphan"
    )


class WeightLog(Base):
    """Weight log entry for tracking weight over time."""

    __tablename__ = "weight_logs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    weight_kg: Mapped[float] = mapped_column(Float)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(50))  # manual, apple_health

    # Relationships
    user: Mapped["User"] = relationship(back_populates="weight_logs")


class WorkoutPlanDay(Base):
    """A single workout day within a workout plan."""

    __tablename__ = "workout_plan_days"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    workout_plan_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("workout_plans.id", ondelete="CASCADE")
    )
    week_number: Mapped[int] = mapped_column(Integer)  # 1-12 for program weeks
    day_number: Mapped[int] = mapped_column(Integer)  # 1-7 for day of week
    day_name: Mapped[str | None] = mapped_column(String(100))  # e.g., "Push Day", "Leg Day"
    workout_type: Mapped[str | None] = mapped_column(
        String(50)
    )  # strength, cardio, flexibility, rest
    exercises: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    # Each exercise: {name, sets, reps, weight_kg, rest_sec, tempo, notes, is_superset, superset_with}
    target_muscles: Mapped[list[str] | None] = mapped_column(JSON, default=list)
    estimated_duration_min: Mapped[int | None] = mapped_column(Integer)
    estimated_calories: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    is_rest_day: Mapped[bool] = mapped_column(Boolean, default=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    workout_plan: Mapped["WorkoutPlan"] = relationship(back_populates="days")


class WaterLog(Base):
    """Water intake log entry."""

    __tablename__ = "water_logs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    amount_ml: Mapped[int] = mapped_column(Integer)  # Amount in milliliters
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    source: Mapped[str | None] = mapped_column(String(50), default="manual")  # manual, quick_add

    # Relationships
    user: Mapped["User"] = relationship(back_populates="water_logs")


class FoodItem(Base):
    """Food item from external databases or user-created."""

    __tablename__ = "food_items"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    # External identifiers
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    # Basic info
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Serving info
    serving_size: Mapped[str | None] = mapped_column(String(100))  # "1 cup", "100g", etc.
    serving_size_g: Mapped[float | None] = mapped_column(Float)  # Serving in grams
    serving_size_ml: Mapped[float | None] = mapped_column(Float)  # For liquids

    # Nutrition per serving
    calories: Mapped[float | None] = mapped_column(Float)
    protein_g: Mapped[float | None] = mapped_column(Float)
    carbs_g: Mapped[float | None] = mapped_column(Float)
    fat_g: Mapped[float | None] = mapped_column(Float)
    fiber_g: Mapped[float | None] = mapped_column(Float)
    sugar_g: Mapped[float | None] = mapped_column(Float)
    sodium_mg: Mapped[float | None] = mapped_column(Float)
    saturated_fat_g: Mapped[float | None] = mapped_column(Float)
    cholesterol_mg: Mapped[float | None] = mapped_column(Float)

    # Media
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Source and verification
    source: Mapped[str] = mapped_column(
        String(50), default="user_created"
    )  # open_food_facts, usda, user_created
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # User who created (for user_created foods)
    created_by_user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Unique constraint on barcode + source to avoid duplicates
    __table_args__ = (
        UniqueConstraint("barcode", "source", name="uq_barcode_source"),
    )


class UserFoodLog(Base):
    """Track which foods a user has logged (for recent/frequent)."""

    __tablename__ = "user_food_logs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    food_item_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("food_items.id", ondelete="CASCADE")
    )
    times_logged: Mapped[int] = mapped_column(Integer, default=1)
    last_logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "food_item_id", name="uq_user_food"),
    )


# =============================================================================
# Progress Photos
# =============================================================================


class ProgressPhoto(Base):
    """Progress photos for tracking physical transformation."""

    __tablename__ = "progress_photos"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    photo_url: Mapped[str] = mapped_column(String(500))  # Cloud storage URL
    thumbnail_url: Mapped[str | None] = mapped_column(String(500))
    photo_type: Mapped[str] = mapped_column(
        String(20), default="front"
    )  # front, side, back
    weight_kg: Mapped[float | None] = mapped_column(Float)  # Weight at time of photo
    notes: Mapped[str | None] = mapped_column(Text)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationship
    user: Mapped["User"] = relationship(back_populates="progress_photos")


# =============================================================================
# Body Measurements
# =============================================================================


class BodyMeasurement(Base):
    """Body measurements for tracking physical progress."""

    __tablename__ = "body_measurements"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Measurements in centimeters
    neck_cm: Mapped[float | None] = mapped_column(Float)
    shoulders_cm: Mapped[float | None] = mapped_column(Float)
    chest_cm: Mapped[float | None] = mapped_column(Float)
    left_bicep_cm: Mapped[float | None] = mapped_column(Float)
    right_bicep_cm: Mapped[float | None] = mapped_column(Float)
    left_forearm_cm: Mapped[float | None] = mapped_column(Float)
    right_forearm_cm: Mapped[float | None] = mapped_column(Float)
    waist_cm: Mapped[float | None] = mapped_column(Float)
    hips_cm: Mapped[float | None] = mapped_column(Float)
    left_thigh_cm: Mapped[float | None] = mapped_column(Float)
    right_thigh_cm: Mapped[float | None] = mapped_column(Float)
    left_calf_cm: Mapped[float | None] = mapped_column(Float)
    right_calf_cm: Mapped[float | None] = mapped_column(Float)

    # Body composition (if available)
    body_fat_percentage: Mapped[float | None] = mapped_column(Float)

    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationship
    user: Mapped["User"] = relationship(back_populates="body_measurements")


# =============================================================================
# Workout Templates
# =============================================================================


class WorkoutTemplate(Base):
    """Saved workout templates for reuse."""

    __tablename__ = "workout_templates"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    workout_type: Mapped[str | None] = mapped_column(
        String(50)
    )  # strength, cardio, flexibility, mixed
    exercises: Mapped[list[dict] | None] = mapped_column(JSON, default=list)
    estimated_duration_min: Mapped[int | None] = mapped_column(Integer)
    target_muscles: Mapped[list[str] | None] = mapped_column(JSON, default=list)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)  # For sharing
    times_used: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationship
    user: Mapped["User"] = relationship(back_populates="workout_templates")


# =============================================================================
# Achievements & Badges
# =============================================================================


class Achievement(Base):
    """Achievement/badge definitions."""

    __tablename__ = "achievements"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    code: Mapped[str] = mapped_column(String(50), unique=True)  # e.g., "first_workout"
    name: Mapped[str] = mapped_column(String(100))  # Display name
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(
        String(50)
    )  # workout, nutrition, consistency, strength, social
    icon: Mapped[str] = mapped_column(String(50))  # SF Symbol name or emoji
    points: Mapped[int] = mapped_column(Integer, default=10)
    tier: Mapped[str] = mapped_column(
        String(20), default="bronze"
    )  # bronze, silver, gold, platinum
    requirement_type: Mapped[str] = mapped_column(
        String(50)
    )  # count, streak, pr, weight, etc.
    requirement_value: Mapped[int] = mapped_column(Integer)  # e.g., 10 workouts
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class UserAchievement(Base):
    """User's unlocked achievements."""

    __tablename__ = "user_achievements"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    achievement_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("achievements.id", ondelete="CASCADE")
    )
    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    progress: Mapped[int] = mapped_column(Integer, default=0)  # For partial progress
    notified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="achievements")
    achievement: Mapped["Achievement"] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
    )


# =============================================================================
# Challenges
# =============================================================================


class Challenge(Base):
    """Community or personal challenges."""

    __tablename__ = "challenges"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    challenge_type: Mapped[str] = mapped_column(
        String(50)
    )  # workout_count, total_volume, streak, steps, etc.
    target_value: Mapped[float] = mapped_column(Float)  # Goal to reach
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    max_participants: Mapped[int | None] = mapped_column(Integer)
    reward_points: Mapped[int] = mapped_column(Integer, default=100)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ChallengeParticipant(Base):
    """Users participating in challenges."""

    __tablename__ = "challenge_participants"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    challenge_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("challenges.id", ondelete="CASCADE")
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    current_value: Mapped[float] = mapped_column(Float, default=0)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    challenge: Mapped["Challenge"] = relationship()
    user: Mapped["User"] = relationship(back_populates="challenge_participations")

    __table_args__ = (
        UniqueConstraint("challenge_id", "user_id", name="uq_challenge_user"),
    )


# =============================================================================
# Social Features
# =============================================================================


class Friendship(Base):
    """Friend connections between users."""

    __tablename__ = "friendships"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    friend_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending, accepted, blocked
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("user_id", "friend_id", name="uq_friendship"),
    )


class ActivityFeedItem(Base):
    """Activity feed for social features."""

    __tablename__ = "activity_feed"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    activity_type: Mapped[str] = mapped_column(
        String(50)
    )  # workout, pr, achievement, challenge_complete, streak_milestone
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    extra_data: Mapped[dict | None] = mapped_column(JSON)  # Activity-specific data
    visibility: Mapped[str] = mapped_column(
        String(20), default="friends"
    )  # public, friends, private
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationship
    user: Mapped["User"] = relationship(back_populates="activity_feed")


class ActivityReaction(Base):
    """Reactions/kudos on activity feed items."""

    __tablename__ = "activity_reactions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    activity_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("activity_feed.id", ondelete="CASCADE")
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    reaction_type: Mapped[str] = mapped_column(
        String(20), default="kudos"
    )  # kudos, fire, muscle, etc.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("activity_id", "user_id", name="uq_activity_reaction"),
    )


# =============================================================================
# Menstrual Cycle Tracking (Female Users)
# =============================================================================


class MenstrualCycleLog(Base):
    """Daily menstrual cycle log entry."""

    __tablename__ = "menstrual_cycle_logs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_period_day: Mapped[bool] = mapped_column(Boolean, default=False)
    flow_intensity: Mapped[str | None] = mapped_column(
        String(20)
    )  # spotting, light, medium, heavy
    symptoms: Mapped[list[str] | None] = mapped_column(
        JSON, default=list
    )  # cramps, bloating, headache, fatigue, breast_tenderness, mood_swings
    mood: Mapped[int | None] = mapped_column(Integer)  # 1-5 scale
    energy_level: Mapped[int | None] = mapped_column(Integer)  # 1-5 scale
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Unique constraint - one log per user per date
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_user_cycle_date"),
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="menstrual_cycle_logs")


class MenstrualCycleSettings(Base):
    """User's menstrual cycle settings for predictions."""

    __tablename__ = "menstrual_cycle_settings"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    average_cycle_length: Mapped[int] = mapped_column(Integer, default=28)
    average_period_length: Mapped[int] = mapped_column(Integer, default=5)
    last_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notify_period_reminder: Mapped[bool] = mapped_column(Boolean, default=True)
    reminder_days_before: Mapped[int] = mapped_column(Integer, default=2)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="menstrual_cycle_settings")


# =============================================================================
# Intermittent Fasting
# =============================================================================


class FastingSession(Base):
    """Active or completed fasting session."""

    __tablename__ = "fasting_sessions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    protocol: Mapped[str] = mapped_column(String(20))  # 16:8, 18:6, 20:4, omad, 24h, 36h, 48h, 5:2, custom
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    target_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actual_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, completed, cancelled
    duration_hours: Mapped[float] = mapped_column(Float)  # Target duration in hours
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="fasting_sessions")


class FastingSettings(Base):
    """User's fasting preferences and settings."""

    __tablename__ = "fasting_settings"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    preferred_protocol: Mapped[str | None] = mapped_column(String(20), nullable=True)  # Default protocol
    eating_window_start: Mapped[str | None] = mapped_column(String(5), nullable=True)  # HH:MM format
    eating_window_end: Mapped[str | None] = mapped_column(String(5), nullable=True)  # HH:MM format
    notify_fast_complete: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_reminder_before_min: Mapped[int] = mapped_column(Integer, default=30)
    # 5:2 diet settings
    fasting_days_of_week: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)  # [1, 4] for Mon, Thu
    fasting_calorie_limit: Mapped[int | None] = mapped_column(Integer, default=500)  # Calories on fasting days
    # Fasting streak tracking
    current_fasting_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_fasting_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_fast_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="fasting_settings")
