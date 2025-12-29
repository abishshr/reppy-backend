"""Blood work integration service for applying recommendations to other features."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import Supplement, UserProfile
from app.schemas.blood_work import ApplyRecommendationsResponse


class BloodWorkIntegrationService:
    """Service for integrating blood work insights with other app features."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def apply_recommendations(
        self,
        user_id: str,
        analysis: dict,
        apply_supplements: bool = False,
        apply_targets: bool = False,
    ) -> ApplyRecommendationsResponse:
        """
        Apply blood work analysis recommendations to the user's account.

        Args:
            user_id: User ID
            analysis: Cached AI analysis dict from BloodWorkPanel
            apply_supplements: Create suggested supplements
            apply_targets: Update micronutrient targets

        Returns:
            ApplyRecommendationsResponse with applied actions
        """
        applied_actions = []
        supplements_created = []
        targets_updated = []

        # Apply supplement recommendations
        if apply_supplements:
            supplement_recs = analysis.get("supplement_recommendations", [])
            for rec in supplement_recs:
                result = await self._create_supplement_from_recommendation(
                    user_id=user_id,
                    recommendation=rec,
                )
                if result:
                    supplements_created.append(result)
                    applied_actions.append(f"Created supplement: {result}")

        # Apply target adjustments
        if apply_targets:
            target_adjustments = analysis.get("target_adjustments", [])
            for adj in target_adjustments:
                result = await self._update_nutrient_target(
                    user_id=user_id,
                    adjustment=adj,
                )
                if result:
                    targets_updated.append(result)
                    applied_actions.append(f"Updated target: {result}")

        return ApplyRecommendationsResponse(
            applied_actions=applied_actions,
            supplements_created=supplements_created,
            targets_updated=targets_updated,
        )

    async def _create_supplement_from_recommendation(
        self,
        user_id: str,
        recommendation: dict,
    ) -> str | None:
        """
        Create a supplement based on blood work recommendation.

        Returns:
            Supplement name if created, None if skipped/failed
        """
        supplement_name = recommendation.get("supplement_name", "")
        if not supplement_name:
            return None

        # Check if similar supplement already exists
        existing = await self.db.execute(
            select(Supplement).where(
                Supplement.user_id == user_id,
                Supplement.name.ilike(f"%{supplement_name}%"),
                Supplement.is_active == True,
            )
        )
        if existing.scalar_one_or_none():
            print(f"[BloodWorkIntegrations] Supplement '{supplement_name}' already exists, skipping")
            return None

        # Map common supplements to their nutrient values
        supplement_defaults = self._get_supplement_defaults(supplement_name)

        # Create the supplement
        notes = f"Recommended based on blood work: {recommendation.get('reason', '')}"
        if recommendation.get("dosage_suggestion"):
            notes += f"\nSuggested dosage: {recommendation['dosage_suggestion']}"

        supplement = Supplement(
            user_id=user_id,
            name=supplement_name,
            notes=notes,
            **supplement_defaults,
        )
        self.db.add(supplement)
        await self.db.commit()

        return supplement_name

    async def _update_nutrient_target(
        self,
        user_id: str,
        adjustment: dict,
    ) -> str | None:
        """
        Update a user's daily nutrient target based on blood work.

        Returns:
            Target name if updated, None if failed
        """
        nutrient = adjustment.get("nutrient", "")
        suggested_target = adjustment.get("suggested_target")

        if not nutrient or suggested_target is None:
            return None

        # Map nutrient names to profile fields
        nutrient_to_field = {
            "iron_mg": None,  # Not currently in UserProfile
            "vitamin_d_mcg": None,  # Not currently in UserProfile
            "calcium_mg": None,  # Not currently in UserProfile
            "protein_g": "daily_protein_target",
            "carbs_g": "daily_carbs_target",
            "fat_g": "daily_fat_target",
            "sugar_g": "daily_sugar_target_g",
            "fiber_g": "daily_fiber_target_g",
            "sodium_mg": "daily_sodium_target_mg",
            "saturated_fat_g": "daily_saturated_fat_target_g",
        }

        field = nutrient_to_field.get(nutrient)
        if not field:
            print(f"[BloodWorkIntegrations] No profile field for nutrient: {nutrient}")
            return None

        # Get user profile
        result = await self.db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()

        if not profile:
            return None

        # Update the target
        setattr(profile, field, suggested_target)
        profile.updated_at = datetime.utcnow()
        await self.db.commit()

        return f"{nutrient}: {suggested_target} {adjustment.get('unit', '')}"

    def _get_supplement_defaults(self, supplement_name: str) -> dict:
        """
        Get default nutrient values for common supplements.

        Returns:
            Dict of nutrient fields and values
        """
        name_lower = supplement_name.lower()

        # Common supplement presets
        presets = {
            "vitamin d": {
                "serving_size": "1 softgel",
                "vitamin_d_mcg": 125,  # 5000 IU
            },
            "vitamin d3": {
                "serving_size": "1 softgel",
                "vitamin_d_mcg": 125,
            },
            "vitamin b12": {
                "serving_size": "1 tablet",
                "vitamin_b12_mcg": 1000,
            },
            "iron": {
                "serving_size": "1 tablet",
                "iron_mg": 25,
            },
            "ferrous": {
                "serving_size": "1 tablet",
                "iron_mg": 25,
            },
            "magnesium": {
                "serving_size": "1 capsule",
                "magnesium_mg": 400,
            },
            "zinc": {
                "serving_size": "1 tablet",
                "zinc_mg": 15,
            },
            "omega": {
                "serving_size": "1 softgel",
                "omega3_mg": 1000,
            },
            "fish oil": {
                "serving_size": "1 softgel",
                "omega3_mg": 1000,
            },
            "calcium": {
                "serving_size": "1 tablet",
                "calcium_mg": 500,
            },
            "folate": {
                "serving_size": "1 tablet",
                "vitamin_b9_mcg": 400,
            },
            "folic acid": {
                "serving_size": "1 tablet",
                "vitamin_b9_mcg": 400,
            },
        }

        for key, values in presets.items():
            if key in name_lower:
                return values

        # Default empty
        return {"serving_size": "1 serving"}

    async def get_meal_plan_adjustments(self, analysis: dict) -> dict:
        """
        Get dietary adjustments based on blood work for meal plan generation.

        Returns:
            Dict with dietary preferences and tags for meal planning
        """
        adjustments = {
            "tags": [],
            "foods_to_emphasize": [],
            "foods_to_limit": [],
            "special_considerations": [],
        }

        # Extract nutrition recommendations
        nutrition_recs = analysis.get("nutrition_recommendations", [])
        for rec in nutrition_recs:
            adjustments["foods_to_emphasize"].extend(rec.get("foods_to_increase", []))
            adjustments["foods_to_limit"].extend(rec.get("foods_to_limit", []))

        # Check for specific conditions based on markers
        # High glucose/HbA1c -> low glycemic
        if self._has_high_marker(analysis, ["fasting_glucose_mg_dl", "hba1c_percent"]):
            adjustments["tags"].append("low_glycemic")
            adjustments["special_considerations"].append("Focus on low glycemic index foods")

        # High LDL/cholesterol -> heart healthy
        if self._has_high_marker(analysis, ["ldl_mg_dl", "total_cholesterol_mg_dl"]):
            adjustments["tags"].append("heart_healthy")
            adjustments["special_considerations"].append("Limit saturated fats, emphasize fiber")

        # Low iron/ferritin -> iron rich
        if self._has_low_marker(analysis, ["iron_mcg_dl", "ferritin_ng_ml"]):
            adjustments["tags"].append("iron_rich")
            adjustments["foods_to_emphasize"].extend(["red meat", "spinach", "lentils", "beans"])

        # Low vitamin D
        if self._has_low_marker(analysis, ["vitamin_d_ng_ml"]):
            adjustments["foods_to_emphasize"].extend(["fatty fish", "eggs", "fortified milk"])

        # High triglycerides -> reduce refined carbs
        if self._has_high_marker(analysis, ["triglycerides_mg_dl"]):
            adjustments["tags"].append("low_carb")
            adjustments["foods_to_limit"].extend(["sugar", "refined grains", "alcohol"])

        return adjustments

    async def get_workout_intensity_adjustment(self, analysis: dict) -> dict:
        """
        Get workout intensity modifier based on blood work.

        Returns:
            Dict with intensity_modifier (0.7-1.0) and reasoning
        """
        result = {
            "intensity_modifier": 1.0,
            "reasons": [],
        }

        # Check for markers that should reduce intensity
        workout_recs = analysis.get("workout_recommendations", [])
        if workout_recs:
            # Use the lowest intensity modifier from recommendations
            modifiers = [rec.get("intensity_modifier", 1.0) for rec in workout_recs]
            result["intensity_modifier"] = min(modifiers)
            result["reasons"] = [rec.get("reason", "") for rec in workout_recs if rec.get("reason")]
        else:
            # Check markers directly
            if self._has_low_marker(analysis, ["hemoglobin_g_dl"]):
                result["intensity_modifier"] = min(result["intensity_modifier"], 0.7)
                result["reasons"].append("Low hemoglobin may affect oxygen delivery")

            if self._has_low_marker(analysis, ["ferritin_ng_ml"]):
                result["intensity_modifier"] = min(result["intensity_modifier"], 0.8)
                result["reasons"].append("Low ferritin suggests depleted iron stores")

            if self._has_high_marker(analysis, ["tsh_miu_l"]):
                result["intensity_modifier"] = min(result["intensity_modifier"], 0.85)
                result["reasons"].append("Elevated TSH suggests thyroid issues")

            if self._has_high_marker(analysis, ["cortisol_mcg_dl"]):
                result["intensity_modifier"] = min(result["intensity_modifier"], 0.85)
                result["reasons"].append("High cortisol suggests chronic stress")

        return result

    def _has_high_marker(self, analysis: dict, marker_keys: list[str]) -> bool:
        """Check if any of the specified markers are high."""
        critical = analysis.get("critical_markers", [])
        for marker in critical:
            if isinstance(marker, dict):
                if marker.get("marker_key") in marker_keys and marker.get("status") == "high":
                    return True
        return False

    def _has_low_marker(self, analysis: dict, marker_keys: list[str]) -> bool:
        """Check if any of the specified markers are low."""
        critical = analysis.get("critical_markers", [])
        for marker in critical:
            if isinstance(marker, dict):
                if marker.get("marker_key") in marker_keys and marker.get("status") == "low":
                    return True
        return False


def get_blood_work_integration_service(db: AsyncSession) -> BloodWorkIntegrationService:
    """Get a blood work integration service instance."""
    return BloodWorkIntegrationService(db)
