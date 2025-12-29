"""Health impact score service using Gemini AI."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from app.infrastructure.ai.gemini_client import GeminiClient


@dataclass
class HealthScoreBreakdown:
    """Breakdown of health score components."""
    nutritional_balance: int  # 0-100
    processing_level: int  # 0-100 (higher = less processed)
    ingredient_quality: int  # 0-100
    macro_balance: int  # 0-100


@dataclass
class MealHealthAnalysis:
    """Complete health analysis of a meal."""
    overall_score: int  # 0-100
    breakdown: HealthScoreBreakdown
    insights: list[str]
    suggestions: list[str]
    positive_aspects: list[str]
    concerns: list[str]


async def analyze_meal_health(
    meal_items: list[dict],
    user_goals: dict | None = None,
    dietary_style: str | None = None,
) -> MealHealthAnalysis:
    """
    Analyze the health impact of a meal using AI.

    Args:
        meal_items: List of food items with nutritional info
        user_goals: User's dietary goals (calories, macros, etc.)
        dietary_style: User's dietary preference (vegan, keto, etc.)
    """
    client = GeminiClient()

    prompt = f"""Analyze the health impact of this meal and provide a detailed assessment.

Meal items:
{json.dumps(meal_items, indent=2)}

User dietary style: {dietary_style or 'Not specified'}
User goals: {json.dumps(user_goals) if user_goals else 'Not specified'}

Provide your analysis in the following JSON format:
{{
    "overall_score": <0-100>,
    "breakdown": {{
        "nutritional_balance": <0-100>,
        "processing_level": <0-100>,
        "ingredient_quality": <0-100>,
        "macro_balance": <0-100>
    }},
    "insights": ["insight1", "insight2"],
    "suggestions": ["suggestion1", "suggestion2"],
    "positive_aspects": ["positive1", "positive2"],
    "concerns": ["concern1", "concern2"]
}}

Score guidelines:
- 80-100: Excellent health impact
- 60-79: Good, with room for improvement
- 40-59: Moderate, consider adjustments
- 0-39: Poor, significant improvements needed

Focus on:
1. Nutrient density and variety
2. Processing level of foods
3. Protein, fiber, and micronutrient content
4. Sugar, sodium, and unhealthy fat levels
5. Alignment with user's dietary style and goals"""

    response = await client.generate_text(prompt)

    try:
        # Parse JSON from response
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        if json_start != -1 and json_end > json_start:
            data = json.loads(response[json_start:json_end])

            return MealHealthAnalysis(
                overall_score=data.get("overall_score", 50),
                breakdown=HealthScoreBreakdown(
                    nutritional_balance=data.get("breakdown", {}).get("nutritional_balance", 50),
                    processing_level=data.get("breakdown", {}).get("processing_level", 50),
                    ingredient_quality=data.get("breakdown", {}).get("ingredient_quality", 50),
                    macro_balance=data.get("breakdown", {}).get("macro_balance", 50),
                ),
                insights=data.get("insights", []),
                suggestions=data.get("suggestions", []),
                positive_aspects=data.get("positive_aspects", []),
                concerns=data.get("concerns", []),
            )
    except json.JSONDecodeError:
        pass

    # Default response if parsing fails
    return MealHealthAnalysis(
        overall_score=50,
        breakdown=HealthScoreBreakdown(
            nutritional_balance=50,
            processing_level=50,
            ingredient_quality=50,
            macro_balance=50,
        ),
        insights=["Unable to analyze this meal"],
        suggestions=["Try logging more detailed food items"],
        positive_aspects=[],
        concerns=[],
    )


async def get_daily_health_summary(
    meals: list[dict],
    user_goals: dict | None = None,
) -> dict:
    """
    Get a health summary for all meals in a day.
    """
    if not meals:
        return {
            "average_score": 0,
            "meal_scores": [],
            "daily_insights": ["No meals logged today"],
            "overall_rating": "unknown",
        }

    # Calculate average score if meals have scores
    scores = [m.get("health_score", 50) for m in meals if m.get("health_score")]
    avg_score = sum(scores) / len(scores) if scores else 50

    # Determine rating
    if avg_score >= 80:
        rating = "excellent"
    elif avg_score >= 60:
        rating = "good"
    elif avg_score >= 40:
        rating = "fair"
    else:
        rating = "needs_improvement"

    return {
        "average_score": round(avg_score, 1),
        "meal_count": len(meals),
        "overall_rating": rating,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }
