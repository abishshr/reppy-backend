"""Blood work analysis service using Gemini AI for OCR and health insights."""

import json
from datetime import datetime

from app.infrastructure.ai.gemini_client import GeminiClient
from app.schemas.blood_work import (
    BloodWorkOCRResponse,
    BloodWorkAnalysisResponse,
    BloodMarkerResult,
    MarkerCategorySummary,
    MarkerStatus,
    SupplementRecommendation,
    NutritionRecommendation,
    WorkoutRecommendation,
    LifestyleRecommendation,
    TargetAdjustment,
    REFERENCE_RANGES,
)


class BloodWorkAnalyzer:
    """Service for analyzing blood work using AI."""

    def __init__(self):
        self.client = GeminiClient()

    async def extract_from_image(
        self,
        image_base64: str | None = None,
        image_url: str | None = None,
        mime_type: str = "image/jpeg",
    ) -> BloodWorkOCRResponse:
        """
        Extract blood work values from a lab report image using Gemini Vision.

        Args:
            image_base64: Base64-encoded image data
            image_url: URL of the image
            mime_type: MIME type of the image

        Returns:
            BloodWorkOCRResponse with extracted values and confidence
        """
        # Build the marker list for extraction
        marker_list = []
        for key, ref in REFERENCE_RANGES.items():
            marker_list.append(f"- {ref.name}: field name '{key}', unit: {ref.unit}")

        prompt = f"""You are a medical lab report OCR specialist. Extract blood test values from this lab report image.

Look for these markers (extract the numeric value only, in the specified units):
{chr(10).join(marker_list)}

Important instructions:
1. Only extract values that are clearly visible and readable
2. Convert units if necessary (e.g., if the report shows mcg/L instead of ng/mL, convert)
3. Mark any values you're uncertain about
4. Try to identify the lab name and test date
5. Be very precise with decimal values

Return your findings in this exact JSON format:
{{
    "success": true,
    "confidence": 0.85,
    "lab_name": "Quest Diagnostics" or null,
    "test_date": "2024-03-15" or null,
    "extracted_values": {{
        "vitamin_d_ng_ml": 42.5,
        "vitamin_b12_pg_ml": 450,
        ...
    }},
    "uncertain_values": {{
        "ferritin_ng_ml": {{
            "value": 85,
            "confidence": 0.6,
            "raw_text": "85 ng/mL (possibly obscured)"
        }}
    }},
    "warnings": [
        "Some values in the metabolic panel section were partially obscured",
        "Test date was estimated from header"
    ]
}}

Only include markers that are present in the image. Do not guess or hallucinate values.
If the image is not a lab report or is unreadable, return success: false."""

        try:
            # Use chat_with_tools for vision capability
            response = await self.client.chat_with_tools(
                system_prompt="You are an expert at reading medical lab reports and extracting structured data.",
                messages=[{"role": "user", "content": prompt}],
                tools=[],
                image_base64=image_base64,
                image_url=image_url,
                image_mime_type=mime_type,
            )

            text = response.get("text", "")

            # Parse the JSON response
            json_start = text.find("{")
            json_end = text.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                data = json.loads(text[json_start:json_end])

                # Parse test date if provided
                test_date = None
                if data.get("test_date"):
                    try:
                        test_date = datetime.strptime(data["test_date"], "%Y-%m-%d")
                    except ValueError:
                        pass

                return BloodWorkOCRResponse(
                    success=data.get("success", False),
                    confidence=data.get("confidence", 0.5),
                    lab_name=data.get("lab_name"),
                    test_date=test_date,
                    warnings=data.get("warnings", []),
                    extracted_values=data.get("extracted_values", {}),
                    uncertain_values=data.get("uncertain_values", {}),
                )

        except Exception as e:
            print(f"[BloodWorkAnalyzer] OCR extraction error: {e}")

        return BloodWorkOCRResponse(
            success=False,
            confidence=0,
            warnings=["Failed to extract values from the image. Please try manual entry."],
        )

    async def analyze_panel(
        self,
        panel,  # BloodWorkPanel model
        user_profile=None,  # UserProfile model
        previous_panels: list = None,  # Previous BloodWorkPanel models
    ) -> BloodWorkAnalysisResponse:
        """
        Analyze a blood work panel and generate health recommendations.

        Args:
            panel: BloodWorkPanel model instance
            user_profile: Optional UserProfile for context
            previous_panels: Optional list of previous panels for trend analysis

        Returns:
            BloodWorkAnalysisResponse with health score and recommendations
        """
        # Collect all marker results
        all_markers: list[BloodMarkerResult] = []
        for marker_key, ref in REFERENCE_RANGES.items():
            value = getattr(panel, marker_key, None)
            if value is not None:
                status = self._classify_status(value, marker_key)
                all_markers.append(
                    BloodMarkerResult(
                        marker_key=marker_key,
                        name=ref.name,
                        value=value,
                        unit=ref.unit,
                        status=status,
                        reference_low=ref.low,
                        reference_high=ref.high,
                        optimal_low=ref.optimal_low,
                        optimal_high=ref.optimal_high,
                    )
                )

        if not all_markers:
            return BloodWorkAnalysisResponse(
                health_score=0,
                summary="No blood markers were found in this panel.",
                categories=[],
                analyzed_at=datetime.utcnow(),
            )

        # Categorize markers
        categories = self._categorize_markers(all_markers)

        # Calculate health score
        health_score, score_breakdown = self._calculate_health_score(categories)

        # Find critical markers (out of range)
        critical_markers = [m for m in all_markers if m.status in (MarkerStatus.LOW, MarkerStatus.HIGH)]

        # Build context for AI analysis
        markers_summary = []
        for m in all_markers:
            markers_summary.append(
                f"- {m.name}: {m.value} {m.unit} ({m.status.value}) [ref: {m.reference_low}-{m.reference_high}]"
            )

        profile_context = ""
        if user_profile:
            profile_context = f"""
User Profile:
- Age: {user_profile.age or 'Unknown'}
- Sex: {user_profile.sex or 'Unknown'}
- Goals: {', '.join(user_profile.goals) if user_profile.goals else 'Unknown'}
- Diet style: {user_profile.diet_style or 'Unknown'}
- Activity level: {user_profile.activity_level or 'Unknown'}
"""

        trend_context = ""
        if previous_panels:
            trend_notes = []
            for prev in previous_panels[:3]:
                for m in all_markers:
                    prev_value = getattr(prev, m.marker_key, None)
                    if prev_value is not None:
                        change = ((m.value - prev_value) / prev_value * 100) if prev_value != 0 else 0
                        if abs(change) > 10:
                            direction = "increased" if change > 0 else "decreased"
                            trend_notes.append(f"{m.name}: {direction} by {abs(change):.1f}% from {prev.test_date.date()}")
                break  # Only compare with most recent previous panel
            if trend_notes:
                trend_context = f"\nRecent trends:\n" + "\n".join(trend_notes[:10])

        prompt = f"""Analyze these blood work results and provide personalized health recommendations.

Blood Work Results:
{chr(10).join(markers_summary)}
{profile_context}
{trend_context}

Provide your analysis in this JSON format:
{{
    "summary": "2-3 sentence overall health summary based on results",
    "supplement_recommendations": [
        {{
            "supplement_name": "Vitamin D3",
            "reason": "Your vitamin D is at 25 ng/mL, below optimal range",
            "dosage_suggestion": "2000-4000 IU daily with food",
            "priority": "high",
            "related_markers": ["vitamin_d_ng_ml"]
        }}
    ],
    "nutrition_recommendations": [
        {{
            "recommendation": "Increase iron-rich foods",
            "foods_to_increase": ["red meat", "spinach", "lentils"],
            "foods_to_limit": ["coffee with meals", "calcium supplements with iron"],
            "reason": "Low ferritin indicates iron stores are depleted",
            "related_markers": ["ferritin_ng_ml", "iron_mcg_dl"]
        }}
    ],
    "workout_recommendations": [
        {{
            "recommendation": "Consider reducing high-intensity training temporarily",
            "intensity_modifier": 0.8,
            "reason": "Low hemoglobin may affect oxygen delivery during intense exercise",
            "related_markers": ["hemoglobin_g_dl"]
        }}
    ],
    "lifestyle_recommendations": [
        {{
            "category": "stress",
            "recommendation": "Practice stress management techniques",
            "reason": "Elevated cortisol suggests chronic stress"
        }}
    ],
    "target_adjustments": [
        {{
            "nutrient": "iron_mg",
            "current_target": 18,
            "suggested_target": 27,
            "unit": "mg",
            "reason": "Based on low ferritin levels, increase daily iron target"
        }}
    ]
}}

Guidelines:
- Focus on markers that are out of range or suboptimal
- Provide specific, actionable recommendations
- Consider interactions between markers (e.g., iron absorption, thyroid function)
- Adjust intensity_modifier between 0.7-1.0 (1.0 = no change needed)
- Prioritize supplement recommendations: high, medium, low
- Be specific about dosages when recommending supplements"""

        try:
            response = await self.client.generate_text(prompt)

            # Parse JSON from response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                data = json.loads(response[json_start:json_end])

                return BloodWorkAnalysisResponse(
                    health_score=health_score,
                    health_score_breakdown=score_breakdown,
                    summary=data.get("summary", "Analysis complete."),
                    categories=categories,
                    critical_markers=critical_markers,
                    supplement_recommendations=[
                        SupplementRecommendation(**rec)
                        for rec in data.get("supplement_recommendations", [])
                    ],
                    nutrition_recommendations=[
                        NutritionRecommendation(**rec)
                        for rec in data.get("nutrition_recommendations", [])
                    ],
                    workout_recommendations=[
                        WorkoutRecommendation(**rec)
                        for rec in data.get("workout_recommendations", [])
                    ],
                    lifestyle_recommendations=[
                        LifestyleRecommendation(**rec)
                        for rec in data.get("lifestyle_recommendations", [])
                    ],
                    target_adjustments=[
                        TargetAdjustment(**adj)
                        for adj in data.get("target_adjustments", [])
                    ],
                    analyzed_at=datetime.utcnow(),
                )

        except Exception as e:
            print(f"[BloodWorkAnalyzer] Analysis error: {e}")

        # Return basic analysis without AI recommendations
        return BloodWorkAnalysisResponse(
            health_score=health_score,
            health_score_breakdown=score_breakdown,
            summary="Blood work analysis complete. Review your results with a healthcare provider.",
            categories=categories,
            critical_markers=critical_markers,
            analyzed_at=datetime.utcnow(),
        )

    def _classify_status(self, value: float, marker_key: str) -> MarkerStatus:
        """Classify a marker value as low/suboptimal/optimal/high."""
        ref = REFERENCE_RANGES.get(marker_key)
        if not ref:
            return MarkerStatus.OPTIMAL

        if value < ref.low:
            return MarkerStatus.LOW
        elif value > ref.high:
            return MarkerStatus.HIGH
        elif ref.optimal_low and ref.optimal_high:
            if value < ref.optimal_low:
                return MarkerStatus.SUBOPTIMAL_LOW
            elif value > ref.optimal_high:
                return MarkerStatus.SUBOPTIMAL_HIGH
            else:
                return MarkerStatus.OPTIMAL
        else:
            return MarkerStatus.OPTIMAL

    def _categorize_markers(self, markers: list[BloodMarkerResult]) -> list[MarkerCategorySummary]:
        """Group markers by category."""
        # Define categories
        category_map = {
            "Vitamins & Minerals": [
                "vitamin_d_ng_ml", "vitamin_b12_pg_ml", "folate_ng_ml", "iron_mcg_dl",
                "ferritin_ng_ml", "tibc_mcg_dl", "vitamin_a_mcg_dl", "vitamin_e_mg_dl",
                "zinc_mcg_dl", "magnesium_mg_dl", "calcium_mg_dl"
            ],
            "Metabolic": [
                "fasting_glucose_mg_dl", "hba1c_percent", "insulin_miu_ml", "homa_ir"
            ],
            "Lipids": [
                "total_cholesterol_mg_dl", "ldl_mg_dl", "hdl_mg_dl",
                "triglycerides_mg_dl", "vldl_mg_dl"
            ],
            "Hormones": [
                "testosterone_total_ng_dl", "testosterone_free_pg_ml", "estradiol_pg_ml",
                "tsh_miu_l", "t3_ng_dl", "t4_mcg_dl", "cortisol_mcg_dl"
            ],
            "Complete Blood Count": [
                "hemoglobin_g_dl", "hematocrit_percent", "rbc_million_per_ul",
                "wbc_thousand_per_ul", "platelets_thousand_per_ul",
                "mcv_fl", "mch_pg", "mchc_g_dl"
            ],
            "Liver & Kidney": [
                "alt_u_l", "ast_u_l", "alp_u_l", "bilirubin_mg_dl",
                "creatinine_mg_dl", "bun_mg_dl", "egfr_ml_min"
            ],
        }

        # Build marker lookup
        marker_lookup = {m.marker_key: m for m in markers}

        # Build category summaries
        summaries = []
        for category_name, marker_keys in category_map.items():
            category_markers = [
                marker_lookup[key] for key in marker_keys
                if key in marker_lookup
            ]
            if not category_markers:
                continue

            optimal = sum(1 for m in category_markers if m.status == MarkerStatus.OPTIMAL)
            suboptimal = sum(
                1 for m in category_markers
                if m.status in (MarkerStatus.SUBOPTIMAL_LOW, MarkerStatus.SUBOPTIMAL_HIGH)
            )
            out_of_range = sum(
                1 for m in category_markers
                if m.status in (MarkerStatus.LOW, MarkerStatus.HIGH)
            )

            summaries.append(
                MarkerCategorySummary(
                    category=category_name,
                    total_markers=len(category_markers),
                    optimal_count=optimal,
                    suboptimal_count=suboptimal,
                    out_of_range_count=out_of_range,
                    markers=category_markers,
                )
            )

        return summaries

    def _calculate_health_score(
        self, categories: list[MarkerCategorySummary]
    ) -> tuple[int, dict[str, int]]:
        """
        Calculate overall health score (0-100) based on marker statuses.

        Returns:
            Tuple of (overall_score, category_scores_dict)
        """
        if not categories:
            return 0, {}

        category_scores = {}
        category_weights = {
            "Vitamins & Minerals": 1.0,
            "Metabolic": 1.2,
            "Lipids": 1.1,
            "Hormones": 1.0,
            "Complete Blood Count": 1.1,
            "Liver & Kidney": 1.1,
        }

        total_weighted_score = 0
        total_weight = 0

        for cat in categories:
            if cat.total_markers == 0:
                continue

            # Calculate category score
            # Optimal = 100, Suboptimal = 60, Out of range = 20
            score_sum = (
                cat.optimal_count * 100 +
                cat.suboptimal_count * 60 +
                cat.out_of_range_count * 20
            )
            category_score = score_sum // cat.total_markers

            weight = category_weights.get(cat.category, 1.0)
            total_weighted_score += category_score * weight
            total_weight += weight

            category_scores[cat.category] = category_score

        overall_score = int(total_weighted_score / total_weight) if total_weight > 0 else 0

        return overall_score, category_scores


# Singleton instance
_analyzer_instance: BloodWorkAnalyzer | None = None


def get_blood_work_analyzer() -> BloodWorkAnalyzer:
    """Get or create the blood work analyzer instance."""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = BloodWorkAnalyzer()
    return _analyzer_instance
