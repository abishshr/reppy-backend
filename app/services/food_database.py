"""Unified food database service combining multiple data sources."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import select, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import FoodItem, UserFoodLog
from app.infrastructure.external.open_food_facts import (
    OpenFoodFactsClient,
    OpenFoodFactsProduct,
    get_open_food_facts_client,
)
from app.infrastructure.external.usda import (
    USDAClient,
    USDAFood,
    get_usda_client,
)


class FoodDatabaseService:
    """
    Unified service for food database operations.

    Combines Open Food Facts, USDA, and local user-created foods
    with intelligent caching and fallback logic.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.off_client: OpenFoodFactsClient = get_open_food_facts_client()
        self.usda_client: USDAClient = get_usda_client()

    async def search_foods(
        self,
        query: str,
        limit: int = 20,
        include_user_foods: bool = True,
        user_id: Optional[str] = None,
    ) -> list[FoodItem]:
        """
        Search for foods across all sources.

        Search priority:
        1. Local database (cached + user-created)
        2. Open Food Facts API
        3. USDA FoodData Central API

        Args:
            query: Search query
            limit: Maximum results to return
            include_user_foods: Whether to include user-created foods
            user_id: User ID for personalized results

        Returns:
            List of FoodItem objects
        """
        results: list[FoodItem] = []
        seen_names: set[str] = set()

        # 1. Search local database first (fast, includes cached + user-created)
        local_foods = await self._search_local(query, limit, user_id if include_user_foods else None)
        for food in local_foods:
            if food.name.lower() not in seen_names:
                results.append(food)
                seen_names.add(food.name.lower())

        # If we have enough results from local cache, return early
        if len(results) >= limit:
            return results[:limit]

        remaining = limit - len(results)

        # 2. Search Open Food Facts (good for branded products with barcodes)
        off_products = await self.off_client.search_products(query, limit=remaining)
        for product in off_products:
            if product.name.lower() not in seen_names:
                food_item = await self._cache_off_product(product)
                if food_item:
                    results.append(food_item)
                    seen_names.add(food_item.name.lower())

        if len(results) >= limit:
            return results[:limit]

        remaining = limit - len(results)

        # 3. Search USDA (good for generic foods and accurate nutrition)
        usda_foods = await self.usda_client.search_foods(query, limit=remaining)
        for usda_food in usda_foods:
            if usda_food.name.lower() not in seen_names:
                food_item = await self._cache_usda_food(usda_food)
                if food_item:
                    results.append(food_item)
                    seen_names.add(food_item.name.lower())

        return results[:limit]

    async def get_by_barcode(self, barcode: str) -> Optional[FoodItem]:
        """
        Look up a food by barcode.

        Search order:
        1. Local database (cached)
        2. Open Food Facts API
        3. USDA FoodData Central API

        Args:
            barcode: Product barcode (EAN-13, UPC-A, etc.)

        Returns:
            FoodItem if found, None otherwise
        """
        # 1. Check local cache first
        stmt = select(FoodItem).where(FoodItem.barcode == barcode)
        result = await self.db.execute(stmt)
        cached = result.scalar_one_or_none()
        if cached:
            return cached

        # 2. Try Open Food Facts (best barcode coverage)
        off_product = await self.off_client.get_product_by_barcode(barcode)
        if off_product:
            return await self._cache_off_product(off_product)

        # 3. Try USDA as fallback
        usda_food = await self.usda_client.search_by_barcode(barcode)
        if usda_food:
            return await self._cache_usda_food(usda_food, barcode=barcode)

        return None

    async def get_by_id(self, food_id: str) -> Optional[FoodItem]:
        """Get a food item by ID."""
        stmt = select(FoodItem).where(FoodItem.id == food_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user_food(
        self,
        user_id: str,
        name: str,
        calories: Optional[float] = None,
        protein_g: Optional[float] = None,
        carbs_g: Optional[float] = None,
        fat_g: Optional[float] = None,
        serving_size: Optional[str] = None,
        serving_size_g: Optional[float] = None,
        brand: Optional[str] = None,
        barcode: Optional[str] = None,
        **kwargs,
    ) -> FoodItem:
        """
        Create a user-defined food item.

        Args:
            user_id: ID of the user creating the food
            name: Food name
            calories: Calories per serving
            protein_g: Protein per serving
            carbs_g: Carbs per serving
            fat_g: Fat per serving
            serving_size: Human-readable serving size
            serving_size_g: Serving size in grams
            brand: Brand name (optional)
            barcode: Barcode (optional)
            **kwargs: Additional nutrition fields

        Returns:
            Created FoodItem
        """
        food_item = FoodItem(
            id=str(uuid4()),
            name=name,
            brand=brand,
            barcode=barcode,
            serving_size=serving_size,
            serving_size_g=serving_size_g,
            calories=calories,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
            fiber_g=kwargs.get("fiber_g"),
            sugar_g=kwargs.get("sugar_g"),
            sodium_mg=kwargs.get("sodium_mg"),
            saturated_fat_g=kwargs.get("saturated_fat_g"),
            cholesterol_mg=kwargs.get("cholesterol_mg"),
            source="user_created",
            is_verified=False,
            created_by_user_id=user_id,
        )

        self.db.add(food_item)
        await self.db.commit()
        await self.db.refresh(food_item)
        return food_item

    async def get_recent_foods(
        self,
        user_id: str,
        limit: int = 20,
    ) -> list[FoodItem]:
        """
        Get a user's recently logged foods.

        Args:
            user_id: User ID
            limit: Maximum results

        Returns:
            List of recently logged FoodItems
        """
        stmt = (
            select(FoodItem)
            .join(UserFoodLog, UserFoodLog.food_item_id == FoodItem.id)
            .where(UserFoodLog.user_id == user_id)
            .order_by(desc(UserFoodLog.last_logged_at))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_frequent_foods(
        self,
        user_id: str,
        limit: int = 20,
    ) -> list[FoodItem]:
        """
        Get a user's most frequently logged foods.

        Args:
            user_id: User ID
            limit: Maximum results

        Returns:
            List of frequently logged FoodItems
        """
        stmt = (
            select(FoodItem)
            .join(UserFoodLog, UserFoodLog.food_item_id == FoodItem.id)
            .where(UserFoodLog.user_id == user_id)
            .order_by(desc(UserFoodLog.times_logged))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_user_foods(
        self,
        user_id: str,
        limit: int = 50,
    ) -> list[FoodItem]:
        """
        Get all custom foods created by a user.

        Args:
            user_id: User ID
            limit: Maximum results

        Returns:
            List of user-created FoodItems
        """
        stmt = (
            select(FoodItem)
            .where(
                FoodItem.created_by_user_id == user_id,
                FoodItem.source == "user_created",
            )
            .order_by(desc(FoodItem.created_at))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete_food(self, food_id: str) -> None:
        """
        Delete a food item.

        Args:
            food_id: Food item ID to delete
        """
        stmt = select(FoodItem).where(FoodItem.id == food_id)
        result = await self.db.execute(stmt)
        food = result.scalar_one_or_none()
        if food:
            await self.db.delete(food)
            await self.db.commit()

    async def record_food_usage(
        self,
        user_id: str,
        food_item_id: str,
    ) -> None:
        """
        Record that a user logged a food (for recent/frequent tracking).

        Args:
            user_id: User ID
            food_item_id: Food item ID
        """
        # Check if entry exists
        stmt = select(UserFoodLog).where(
            UserFoodLog.user_id == user_id,
            UserFoodLog.food_item_id == food_item_id,
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing entry
            existing.times_logged += 1
            existing.last_logged_at = datetime.utcnow()
        else:
            # Create new entry
            log = UserFoodLog(
                id=str(uuid4()),
                user_id=user_id,
                food_item_id=food_item_id,
                times_logged=1,
            )
            self.db.add(log)

        await self.db.commit()

    async def _search_local(
        self,
        query: str,
        limit: int,
        user_id: Optional[str] = None,
    ) -> list[FoodItem]:
        """Search local database for foods."""
        search_pattern = f"%{query}%"

        # Base query
        conditions = [
            FoodItem.name.ilike(search_pattern),
        ]

        # Also search brand
        conditions.append(FoodItem.brand.ilike(search_pattern))

        stmt = (
            select(FoodItem)
            .where(or_(*conditions))
            .order_by(
                # Prioritize verified foods
                desc(FoodItem.is_verified),
                # Then by name match quality (exact matches first)
                func.length(FoodItem.name),
            )
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _cache_off_product(
        self,
        product: OpenFoodFactsProduct,
    ) -> Optional[FoodItem]:
        """Cache an Open Food Facts product to local database."""
        if not product.name:
            return None

        # Check if already cached
        if product.code:
            stmt = select(FoodItem).where(
                FoodItem.barcode == product.code,
                FoodItem.source == "open_food_facts",
            )
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                return existing

        # Calculate nutrition per serving
        calories = product.calories_serving
        protein = product.protein_serving
        carbs = product.carbs_serving
        fat = product.fat_serving

        # If per-serving not available, use per 100g with serving size
        if calories is None and product.calories_100g is not None:
            serving_g = product.serving_size_g or 100.0
            multiplier = serving_g / 100.0
            calories = product.calories_100g * multiplier if product.calories_100g else None
            protein = product.protein_100g * multiplier if product.protein_100g else None
            carbs = product.carbs_100g * multiplier if product.carbs_100g else None
            fat = product.fat_100g * multiplier if product.fat_100g else None

        food_item = FoodItem(
            id=str(uuid4()),
            external_id=product.code,
            barcode=product.code,
            name=product.name,
            brand=product.brand,
            serving_size=product.serving_size or "100g",
            serving_size_g=product.serving_size_g or 100.0,
            calories=calories,
            protein_g=protein,
            carbs_g=carbs,
            fat_g=fat,
            fiber_g=product.fiber_100g * (product.serving_size_g or 100.0) / 100.0
            if product.fiber_100g and product.serving_size_g
            else product.fiber_100g,
            sugar_g=product.sugar_100g * (product.serving_size_g or 100.0) / 100.0
            if product.sugar_100g and product.serving_size_g
            else product.sugar_100g,
            sodium_mg=product.sodium_100g * 1000 * (product.serving_size_g or 100.0) / 100.0
            if product.sodium_100g and product.serving_size_g
            else (product.sodium_100g * 1000 if product.sodium_100g else None),
            saturated_fat_g=product.saturated_fat_100g * (product.serving_size_g or 100.0) / 100.0
            if product.saturated_fat_100g and product.serving_size_g
            else product.saturated_fat_100g,
            image_url=product.image_url,
            thumbnail_url=product.image_thumb_url,
            source="open_food_facts",
            is_verified=True,  # Data from official source
        )

        self.db.add(food_item)
        try:
            await self.db.commit()
            await self.db.refresh(food_item)
        except Exception:
            await self.db.rollback()
            # Return without caching if there's a conflict
            return food_item

        return food_item

    async def _cache_usda_food(
        self,
        usda_food: USDAFood,
        barcode: Optional[str] = None,
    ) -> Optional[FoodItem]:
        """Cache a USDA food to local database."""
        if not usda_food.name:
            return None

        # Check if already cached
        stmt = select(FoodItem).where(
            FoodItem.external_id == str(usda_food.fdc_id),
            FoodItem.source == "usda",
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        # USDA nutrition is per 100g, calculate per serving
        serving_g = usda_food.serving_size or 100.0
        multiplier = serving_g / 100.0

        food_item = FoodItem(
            id=str(uuid4()),
            external_id=str(usda_food.fdc_id),
            barcode=barcode or usda_food.gtin_upc,
            name=usda_food.name,
            brand=usda_food.brand,
            description=usda_food.description,
            serving_size=usda_food.household_serving
            or f"{serving_g}{usda_food.serving_size_unit or 'g'}",
            serving_size_g=serving_g,
            calories=usda_food.calories * multiplier if usda_food.calories else None,
            protein_g=usda_food.protein_g * multiplier if usda_food.protein_g else None,
            carbs_g=usda_food.carbs_g * multiplier if usda_food.carbs_g else None,
            fat_g=usda_food.fat_g * multiplier if usda_food.fat_g else None,
            fiber_g=usda_food.fiber_g * multiplier if usda_food.fiber_g else None,
            sugar_g=usda_food.sugar_g * multiplier if usda_food.sugar_g else None,
            sodium_mg=usda_food.sodium_mg * multiplier if usda_food.sodium_mg else None,
            saturated_fat_g=usda_food.saturated_fat_g * multiplier
            if usda_food.saturated_fat_g
            else None,
            cholesterol_mg=usda_food.cholesterol_mg * multiplier
            if usda_food.cholesterol_mg
            else None,
            source="usda",
            is_verified=True,  # Data from official source
        )

        self.db.add(food_item)
        try:
            await self.db.commit()
            await self.db.refresh(food_item)
        except Exception:
            await self.db.rollback()
            return food_item

        return food_item


# Factory function
def get_food_database_service(db: AsyncSession) -> FoodDatabaseService:
    """Get a FoodDatabaseService instance."""
    return FoodDatabaseService(db)
