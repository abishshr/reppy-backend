"""Nutrient synergy analysis service."""

from dataclasses import dataclass


@dataclass
class SynergyInsight:
    """A single nutrient synergy or interaction."""
    type: str  # "beneficial" or "inhibiting"
    title: str
    description: str
    foods_involved: list[str]
    impact: str  # "high", "medium", "low"


# Known beneficial nutrient combinations
BENEFICIAL_SYNERGIES = [
    {
        "nutrients": ["iron", "vitamin_c"],
        "title": "Iron + Vitamin C",
        "description": "Vitamin C significantly enhances iron absorption. Consider pairing iron-rich foods with citrus or peppers.",
        "impact": "high",
    },
    {
        "nutrients": ["calcium", "vitamin_d"],
        "title": "Calcium + Vitamin D",
        "description": "Vitamin D is essential for calcium absorption. Sunlight exposure or fortified foods help.",
        "impact": "high",
    },
    {
        "nutrients": ["fat", "vitamin_a"],
        "title": "Fat + Vitamin A",
        "description": "Vitamin A is fat-soluble and needs dietary fat for absorption. Add healthy fats to vegetables.",
        "impact": "medium",
    },
    {
        "nutrients": ["fat", "vitamin_d"],
        "title": "Fat + Vitamin D",
        "description": "Vitamin D absorption is enhanced when consumed with dietary fat.",
        "impact": "medium",
    },
    {
        "nutrients": ["fat", "vitamin_e"],
        "title": "Fat + Vitamin E",
        "description": "Vitamin E is fat-soluble. Pair vitamin E-rich foods with healthy fats.",
        "impact": "medium",
    },
    {
        "nutrients": ["fat", "vitamin_k"],
        "title": "Fat + Vitamin K",
        "description": "Vitamin K needs fat for absorption. Use olive oil with leafy greens.",
        "impact": "medium",
    },
    {
        "nutrients": ["protein", "vitamin_b6"],
        "title": "Protein + Vitamin B6",
        "description": "B6 aids protein metabolism. Higher protein intake may require more B6.",
        "impact": "medium",
    },
    {
        "nutrients": ["turmeric", "black_pepper"],
        "title": "Turmeric + Black Pepper",
        "description": "Piperine in black pepper increases curcumin absorption by up to 2000%.",
        "impact": "high",
    },
]

# Known inhibiting interactions
INHIBITING_INTERACTIONS = [
    {
        "nutrients": ["calcium", "iron"],
        "title": "Calcium blocks Iron",
        "description": "Calcium can reduce iron absorption. Separate calcium-rich dairy from iron-rich meals.",
        "impact": "high",
    },
    {
        "nutrients": ["caffeine", "iron"],
        "title": "Caffeine blocks Iron",
        "description": "Caffeine inhibits iron absorption. Wait 1-2 hours after meals before coffee/tea.",
        "impact": "medium",
    },
    {
        "nutrients": ["caffeine", "calcium"],
        "title": "Caffeine reduces Calcium",
        "description": "Excessive caffeine can increase calcium excretion. Moderate coffee intake.",
        "impact": "low",
    },
    {
        "nutrients": ["phytates", "zinc"],
        "title": "Phytates block Zinc",
        "description": "Phytates in grains/legumes can reduce zinc absorption. Soaking helps reduce phytates.",
        "impact": "medium",
    },
    {
        "nutrients": ["oxalates", "calcium"],
        "title": "Oxalates block Calcium",
        "description": "Oxalates in spinach/rhubarb bind calcium. Don't rely on these as calcium sources.",
        "impact": "medium",
    },
]

# Food to nutrient mapping (simplified)
FOOD_NUTRIENTS = {
    "spinach": ["iron", "calcium", "vitamin_k", "oxalates"],
    "orange": ["vitamin_c"],
    "lemon": ["vitamin_c"],
    "beef": ["iron", "protein", "zinc"],
    "chicken": ["protein", "vitamin_b6"],
    "salmon": ["vitamin_d", "omega_3", "protein"],
    "egg": ["vitamin_d", "protein", "fat"],
    "milk": ["calcium", "vitamin_d"],
    "cheese": ["calcium", "fat"],
    "yogurt": ["calcium", "protein"],
    "broccoli": ["vitamin_c", "vitamin_k", "fiber"],
    "carrot": ["vitamin_a", "fiber"],
    "sweet_potato": ["vitamin_a", "fiber"],
    "olive_oil": ["fat", "vitamin_e"],
    "nuts": ["fat", "vitamin_e", "zinc"],
    "coffee": ["caffeine"],
    "tea": ["caffeine"],
    "beans": ["iron", "protein", "phytates", "fiber"],
    "lentils": ["iron", "protein", "phytates"],
    "turmeric": ["turmeric"],
    "pepper": ["black_pepper"],
}


def analyze_meal_synergies(meal_items: list[dict]) -> list[SynergyInsight]:
    """
    Analyze a meal for nutrient synergies and interactions.

    Args:
        meal_items: List of food items with 'name' field

    Returns:
        List of synergy insights
    """
    insights = []

    # Extract food names
    food_names = []
    for item in meal_items:
        name = item.get("name", "").lower()
        food_names.append(name)

    # Find all nutrients present
    present_nutrients = set()
    food_nutrient_map = {}

    for food in food_names:
        for known_food, nutrients in FOOD_NUTRIENTS.items():
            if known_food in food:
                present_nutrients.update(nutrients)
                food_nutrient_map[known_food] = nutrients

    # Check for beneficial synergies
    for synergy in BENEFICIAL_SYNERGIES:
        required = set(synergy["nutrients"])
        if required.issubset(present_nutrients):
            # Find which foods contribute
            contributing_foods = []
            for food, nutrients in food_nutrient_map.items():
                if any(n in nutrients for n in required):
                    contributing_foods.append(food)

            if len(contributing_foods) >= 2:
                insights.append(SynergyInsight(
                    type="beneficial",
                    title=synergy["title"],
                    description=synergy["description"],
                    foods_involved=contributing_foods[:3],
                    impact=synergy["impact"],
                ))

    # Check for inhibiting interactions
    for interaction in INHIBITING_INTERACTIONS:
        required = set(interaction["nutrients"])
        if required.issubset(present_nutrients):
            contributing_foods = []
            for food, nutrients in food_nutrient_map.items():
                if any(n in nutrients for n in required):
                    contributing_foods.append(food)

            if len(contributing_foods) >= 2:
                insights.append(SynergyInsight(
                    type="inhibiting",
                    title=interaction["title"],
                    description=interaction["description"],
                    foods_involved=contributing_foods[:3],
                    impact=interaction["impact"],
                ))

    return insights
