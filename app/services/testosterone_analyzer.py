"""Testosterone impact analyzer for foods.

Analyzes foods to determine their potential impact on testosterone levels.
Uses a hybrid approach: keyword matching first, AI fallback for uncertain cases.
"""

from typing import Any


class TestosteroneAnalyzer:
    """Analyzes foods for testosterone impact using hybrid approach."""

    # Foods known to support testosterone production
    BOOSTING_KEYWORDS = [
        # High zinc foods
        "oyster", "oysters", "beef", "steak", "lamb", "venison", "bison",
        "crab", "lobster", "shrimp", "prawns", "clam", "mussel",
        # Eggs (cholesterol for hormone synthesis)
        "egg", "eggs", "omelette", "omelet", "frittata",
        # Fatty fish (vitamin D, omega-3)
        "salmon", "tuna", "sardine", "sardines", "mackerel", "herring",
        "trout", "anchovy", "anchovies",
        # Cruciferous vegetables (reduce estrogen via DIM)
        "broccoli", "cauliflower", "cabbage", "brussels sprout", "kale",
        "bok choy", "arugula", "watercress",
        # Alliums (boost testosterone)
        "garlic", "onion", "onions", "leek", "shallot",
        # Other testosterone-supporting foods
        "ginger", "pomegranate", "honey", "coconut",
        # Leafy greens (magnesium)
        "spinach", "swiss chard", "collard",
        # Healthy fats
        "avocado", "olive oil", "extra virgin olive oil",
        # Nuts and seeds (zinc, selenium, healthy fats)
        "almond", "almonds", "walnut", "walnuts", "brazil nut", "brazil nuts",
        "pumpkin seed", "pumpkin seeds", "sunflower seed",
        # High protein meats
        "chicken breast", "turkey breast", "lean beef", "sirloin",
        "tenderloin", "ribeye", "filet mignon",
        # Organ meats (nutrient dense)
        "liver", "kidney",
        # Dairy (vitamin D, saturated fat in moderation)
        "whole milk", "butter", "ghee", "cheese",
        # Testosterone-supporting herbs
        "ashwagandha", "fenugreek", "tongkat ali", "maca",
    ]

    # Foods that may lower testosterone
    REDUCING_KEYWORDS = [
        # Soy products (phytoestrogens)
        "soy", "soya", "tofu", "tempeh", "edamame", "soy milk", "soy sauce",
        "soy protein", "soybean", "miso",
        # Alcohol
        "beer", "wine", "vodka", "whiskey", "whisky", "rum", "gin", "tequila",
        "bourbon", "brandy", "cognac", "champagne", "sake", "alcohol",
        "cocktail", "margarita", "martini", "mojito",
        # Mint (may lower testosterone)
        "mint", "spearmint", "peppermint", "menthol",
        # Licorice (reduces testosterone)
        "licorice", "liquorice",
        # Flaxseed (high in lignans)
        "flax", "flaxseed", "flax seed", "linseed",
        # High sugar/processed foods
        "candy", "candies", "soda", "cola", "pepsi", "sprite", "fanta",
        "donut", "doughnut", "pastry", "pastries", "cake", "cupcake",
        "cookie", "cookies", "brownie", "ice cream",
        "chips", "crisps", "nachos", "cheetos", "doritos",
        # Trans fats/fried foods
        "fried", "deep fried", "french fries", "onion rings",
        # Processed meats (preservatives, additives)
        "hot dog", "hotdog", "bologna", "spam", "processed meat",
        # Vegetable oils (omega-6 inflammatory)
        "vegetable oil", "canola oil", "soybean oil", "corn oil",
        "margarine",
        # Sugary drinks
        "energy drink", "red bull", "monster energy",
        "fruit juice", "orange juice", "apple juice",  # High sugar
        # Fast food
        "mcdonald", "burger king", "wendy", "taco bell", "kfc",
    ]

    # Neutral foods - no significant impact
    NEUTRAL_KEYWORDS = [
        "rice", "pasta", "bread", "oatmeal", "cereal",
        "apple", "banana", "orange", "grape", "strawberry", "blueberry",
        "carrot", "tomato", "cucumber", "lettuce", "celery",
        "potato", "sweet potato",
        "water", "tea", "coffee",  # Plain versions
    ]

    def analyze_food(self, food_name: str, nutrients: dict[str, Any] | None = None) -> str | None:
        """
        Analyze a food's potential testosterone impact.

        Args:
            food_name: Name of the food
            nutrients: Optional dict with nutritional info (protein_g, zinc_mg, etc.)

        Returns:
            "boosts", "reduces", "neutral", or None if unknown
        """
        if not food_name:
            return None

        name_lower = food_name.lower().strip()

        # Step 1: Check for boosting keywords
        for keyword in self.BOOSTING_KEYWORDS:
            if keyword in name_lower:
                return "boosts"

        # Step 2: Check for reducing keywords
        for keyword in self.REDUCING_KEYWORDS:
            if keyword in name_lower:
                return "reduces"

        # Step 3: Check for neutral keywords
        for keyword in self.NEUTRAL_KEYWORDS:
            if keyword in name_lower:
                return "neutral"

        # Step 4: Analyze based on nutrients if available
        if nutrients:
            impact = self._analyze_nutrients(nutrients)
            if impact:
                return impact

        # Unknown - could use AI fallback here in the future
        return None

    def _analyze_nutrients(self, nutrients: dict[str, Any]) -> str | None:
        """
        Analyze testosterone impact based on nutrient profile.

        High protein + high zinc + moderate fat = likely boosting
        High sugar + low protein = likely reducing
        """
        protein = nutrients.get("protein_g", 0) or 0
        sugar = nutrients.get("sugar_g", 0) or 0
        fat = nutrients.get("fat_g", 0) or 0
        zinc = nutrients.get("zinc_mg", 0) or 0

        # High protein, good fat, low sugar = likely testosterone supporting
        if protein > 20 and fat > 5 and sugar < 5:
            return "boosts"

        # High zinc content = testosterone supporting
        if zinc > 3:
            return "boosts"

        # Very high sugar = likely testosterone reducing
        if sugar > 30:
            return "reduces"

        # High sugar, low protein = processed/junk food
        if sugar > 15 and protein < 5:
            return "reduces"

        return None

    def analyze_meal(self, items: list[dict[str, Any]]) -> str:
        """
        Analyze overall testosterone impact of a meal.

        Args:
            items: List of food items with optional testosterone_impact field

        Returns:
            "boosting", "reducing", "mixed", or "neutral"
        """
        if not items:
            return "neutral"

        boost_count = 0
        reduce_count = 0
        neutral_count = 0

        for item in items:
            impact = item.get("testosterone_impact")
            if impact == "boosts":
                boost_count += 1
            elif impact == "reduces":
                reduce_count += 1
            elif impact == "neutral":
                neutral_count += 1

        # Determine overall impact
        if boost_count > 0 and reduce_count > 0:
            # Both boosting and reducing foods
            if boost_count > reduce_count:
                return "mixed"  # Net positive but has some reducing foods
            elif reduce_count > boost_count:
                return "mixed"  # Net negative but has some boosting foods
            else:
                return "mixed"  # Equal amounts

        if boost_count > 0:
            return "boosting"

        if reduce_count > 0:
            return "reducing"

        return "neutral"

    def get_daily_summary(
        self, meals: list[dict[str, Any]]
    ) -> dict[str, int | str]:
        """
        Calculate daily testosterone impact summary.

        Args:
            meals: List of meals with their items

        Returns:
            Dict with boosting_count, reducing_count, neutral_count, overall_rating
        """
        boosting_count = 0
        reducing_count = 0
        neutral_count = 0

        for meal in meals:
            items = meal.get("items", [])
            for item in items:
                impact = item.get("testosterone_impact")
                if impact == "boosts":
                    boosting_count += 1
                elif impact == "reduces":
                    reducing_count += 1
                elif impact == "neutral":
                    neutral_count += 1

        # Calculate overall rating
        if boosting_count > reducing_count * 2:
            overall_rating = "great"
        elif boosting_count > reducing_count:
            overall_rating = "good"
        elif reducing_count > boosting_count:
            overall_rating = "poor"
        else:
            overall_rating = "neutral"

        return {
            "boosting_count": boosting_count,
            "reducing_count": reducing_count,
            "neutral_count": neutral_count,
            "overall_rating": overall_rating,
        }


# Singleton instance
testosterone_analyzer = TestosteroneAnalyzer()
