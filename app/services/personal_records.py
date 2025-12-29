"""Personal Records service for tracking exercise PRs."""

from datetime import datetime
from typing import Optional
from dataclasses import dataclass

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import PersonalRecord, WorkoutLog


@dataclass
class PRUpdate:
    """Result of checking/updating a PR."""
    exercise_name: str
    is_new_weight_pr: bool = False
    is_new_volume_pr: bool = False
    is_new_reps_pr: bool = False
    new_weight_kg: Optional[float] = None
    new_volume_kg: Optional[float] = None
    new_reps: Optional[int] = None
    previous_weight_kg: Optional[float] = None
    previous_volume_kg: Optional[float] = None
    previous_reps: Optional[int] = None


def normalize_exercise_name(name: str) -> str:
    """Normalize exercise name for consistent PR tracking."""
    # Convert to lowercase, strip whitespace, replace common variations
    normalized = name.lower().strip()

    # Common normalizations
    replacements = {
        "bench press": "barbell bench press",
        "flat bench": "barbell bench press",
        "squat": "barbell squat",
        "back squat": "barbell squat",
        "deadlift": "barbell deadlift",
        "conventional deadlift": "barbell deadlift",
        "overhead press": "barbell overhead press",
        "ohp": "barbell overhead press",
        "military press": "barbell overhead press",
        "pull up": "pull-up",
        "pullup": "pull-up",
        "chin up": "chin-up",
        "chinup": "chin-up",
    }

    return replacements.get(normalized, normalized)


class PersonalRecordService:
    """Service for managing personal records."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_and_update_pr(
        self,
        user_id: str,
        exercise_name: str,
        weight_kg: Optional[float],
        reps: Optional[int],
        sets: Optional[int],
        workout_id: str,
        logged_at: datetime,
    ) -> PRUpdate:
        """
        Check if this exercise attempt sets any new PRs and update if so.

        Returns PRUpdate with flags for which PRs (if any) were broken.
        """
        normalized_name = normalize_exercise_name(exercise_name)

        # Calculate volume (weight × reps × sets)
        volume = None
        if weight_kg and reps and sets:
            volume = weight_kg * reps * sets

        # Get or create PR record for this exercise
        stmt = select(PersonalRecord).where(
            PersonalRecord.user_id == user_id,
            PersonalRecord.exercise_name == normalized_name,
        )
        result = await self.db.execute(stmt)
        pr_record = result.scalar_one_or_none()

        pr_update = PRUpdate(exercise_name=normalized_name)

        if not pr_record:
            # First time doing this exercise - create new PR record
            pr_record = PersonalRecord(
                user_id=user_id,
                exercise_name=normalized_name,
                times_performed=1,
                last_performed=logged_at,
                last_weight_kg=weight_kg,
                last_reps=reps,
                last_sets=sets,
            )

            # Set initial PRs
            if weight_kg:
                pr_record.max_weight_kg = weight_kg
                pr_record.max_weight_reps = reps
                pr_record.max_weight_date = logged_at
                pr_record.max_weight_workout_id = workout_id
                pr_update.is_new_weight_pr = True
                pr_update.new_weight_kg = weight_kg

            if volume:
                pr_record.max_volume_kg = volume
                pr_record.max_volume_date = logged_at
                pr_record.max_volume_workout_id = workout_id
                pr_update.is_new_volume_pr = True
                pr_update.new_volume_kg = volume

            if reps:
                pr_record.max_reps = reps
                pr_record.max_reps_weight_kg = weight_kg
                pr_record.max_reps_date = logged_at
                pr_update.is_new_reps_pr = True
                pr_update.new_reps = reps

            self.db.add(pr_record)
        else:
            # Update existing PR record
            pr_record.times_performed += 1
            pr_record.last_performed = logged_at
            pr_record.last_weight_kg = weight_kg
            pr_record.last_reps = reps
            pr_record.last_sets = sets

            # Check for new weight PR
            if weight_kg and (pr_record.max_weight_kg is None or weight_kg > pr_record.max_weight_kg):
                pr_update.previous_weight_kg = pr_record.max_weight_kg
                pr_record.max_weight_kg = weight_kg
                pr_record.max_weight_reps = reps
                pr_record.max_weight_date = logged_at
                pr_record.max_weight_workout_id = workout_id
                pr_update.is_new_weight_pr = True
                pr_update.new_weight_kg = weight_kg

            # Check for new volume PR
            if volume and (pr_record.max_volume_kg is None or volume > pr_record.max_volume_kg):
                pr_update.previous_volume_kg = pr_record.max_volume_kg
                pr_record.max_volume_kg = volume
                pr_record.max_volume_date = logged_at
                pr_record.max_volume_workout_id = workout_id
                pr_update.is_new_volume_pr = True
                pr_update.new_volume_kg = volume

            # Check for new reps PR (at same or higher weight)
            if reps and weight_kg:
                if pr_record.max_reps is None or reps > pr_record.max_reps:
                    # More reps at any weight
                    if pr_record.max_reps_weight_kg is None or weight_kg >= pr_record.max_reps_weight_kg:
                        pr_update.previous_reps = pr_record.max_reps
                        pr_record.max_reps = reps
                        pr_record.max_reps_weight_kg = weight_kg
                        pr_record.max_reps_date = logged_at
                        pr_update.is_new_reps_pr = True
                        pr_update.new_reps = reps

        await self.db.commit()
        return pr_update

    async def get_user_prs(self, user_id: str, limit: int = 50) -> list[PersonalRecord]:
        """Get all personal records for a user, ordered by last performed."""
        stmt = (
            select(PersonalRecord)
            .where(PersonalRecord.user_id == user_id)
            .order_by(PersonalRecord.last_performed.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_exercise_pr(self, user_id: str, exercise_name: str) -> Optional[PersonalRecord]:
        """Get PR for a specific exercise."""
        normalized_name = normalize_exercise_name(exercise_name)
        stmt = select(PersonalRecord).where(
            PersonalRecord.user_id == user_id,
            PersonalRecord.exercise_name == normalized_name,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_exercise_history(
        self,
        user_id: str,
        exercise_name: str,
        limit: int = 20,
    ) -> list[dict]:
        """
        Get history of an exercise from workout logs.
        Returns list of attempts with date, weight, reps, sets.
        """
        normalized_name = normalize_exercise_name(exercise_name)

        # Query workout logs and filter by exercise name in JSON
        stmt = (
            select(WorkoutLog)
            .where(WorkoutLog.user_id == user_id)
            .order_by(WorkoutLog.logged_at.desc())
            .limit(100)  # Get more to filter
        )
        result = await self.db.execute(stmt)
        workouts = result.scalars().all()

        history = []
        for workout in workouts:
            if not workout.exercises:
                continue

            for exercise in workout.exercises:
                ex_name = normalize_exercise_name(exercise.get("name", ""))
                if ex_name == normalized_name:
                    history.append({
                        "workout_id": workout.id,
                        "logged_at": workout.logged_at.isoformat(),
                        "weight_kg": exercise.get("weight_kg"),
                        "reps": exercise.get("reps"),
                        "sets": exercise.get("sets"),
                        "duration_min": exercise.get("duration_min"),
                        "notes": exercise.get("notes"),
                    })

            if len(history) >= limit:
                break

        return history[:limit]

    async def get_last_attempt(
        self,
        user_id: str,
        exercise_name: str,
    ) -> Optional[dict]:
        """Get the most recent attempt of an exercise."""
        history = await self.get_exercise_history(user_id, exercise_name, limit=1)
        return history[0] if history else None

    async def get_recent_prs(self, user_id: str, days: int = 7) -> list[PersonalRecord]:
        """Get PRs set within the last N days."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)

        stmt = (
            select(PersonalRecord)
            .where(
                PersonalRecord.user_id == user_id,
                (
                    (PersonalRecord.max_weight_date >= cutoff) |
                    (PersonalRecord.max_volume_date >= cutoff) |
                    (PersonalRecord.max_reps_date >= cutoff)
                )
            )
            .order_by(PersonalRecord.updated_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


def get_pr_service(db: AsyncSession) -> PersonalRecordService:
    """Get a PersonalRecordService instance."""
    return PersonalRecordService(db)
