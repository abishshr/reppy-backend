"""MCP Orchestrator - coordinates AI model with tools."""

import json
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.ai.gemini_client import GeminiClient
from app.infrastructure.database import ConversationSession, ToolCall
from app.mcp.context_assembler import ContextAssembler
from app.mcp.memory.session_memory import SessionMemory
from app.mcp.tools import (
    BaseTool,
    ConfirmMealLogTool,
    ConfirmWorkoutLogTool,
    GetActivitySummaryTool,
    GetProgressSummaryTool,
    GetUserContextTool,
    LearnFactTool,
    LogMealSuggestionTool,
    LogWeightTool,
    LogWorkoutSuggestionTool,
    MenuRecommendationsTool,
    SuggestMealsTool,
)
from app.mcp.tools.meal_plan_tools import (
    GenerateMealPlanTool,
    GenerateGroceryListTool,
    GetMealSuggestionTool,
)
from app.mcp.tools.workout_plan_tools import (
    GenerateWorkoutPlanTool,
    GetTodaysWorkoutTool,
    CompleteWorkoutDayTool,
    SuggestExerciseAlternativeTool,
)


class MCPOrchestrator:
    """
    Orchestrates the MCP loop:
    1. Assemble context (RAG)
    2. Send to model with tools
    3. Execute tool calls
    4. Return response or continue loop
    """

    def __init__(
        self,
        db: AsyncSession,
        user_id: str,
        gemini_client: GeminiClient,
    ):
        self.db = db
        self.user_id = user_id
        self.gemini = gemini_client
        self.context_assembler = ContextAssembler(db)

        # Initialize tools
        self.tools: dict[str, BaseTool] = {
            "log_meal_suggestion": LogMealSuggestionTool(db, user_id),
            "confirm_log_meal": ConfirmMealLogTool(db, user_id),
            "log_workout_suggestion": LogWorkoutSuggestionTool(db, user_id),
            "confirm_log_workout": ConfirmWorkoutLogTool(db, user_id),
            "get_activity_summary": GetActivitySummaryTool(db, user_id),
            "get_user_context": GetUserContextTool(db, user_id),
            "suggest_meals": SuggestMealsTool(db, user_id),
            "menu_recommendations": MenuRecommendationsTool(db, user_id),
            "learn_user_fact": LearnFactTool(db, user_id),
            # Meal planning tools
            "generate_meal_plan": GenerateMealPlanTool(db, user_id),
            "generate_grocery_list": GenerateGroceryListTool(db, user_id),
            "suggest_meal": GetMealSuggestionTool(db, user_id),
            # Workout planning tools
            "generate_workout_plan": GenerateWorkoutPlanTool(db, user_id),
            "get_todays_workout": GetTodaysWorkoutTool(db, user_id),
            "complete_workout_day": CompleteWorkoutDayTool(db, user_id),
            "suggest_exercise_alternative": SuggestExerciseAlternativeTool(db, user_id),
            # Progress tracking tools
            "log_weight": LogWeightTool(db, user_id),
            "get_progress_summary": GetProgressSummaryTool(db, user_id),
        }

    async def process_message(
        self,
        message: str,
        session_id: str | None = None,
        image_url: str | None = None,
        image_base64: str | None = None,
        image_mime_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Process a user message through the MCP loop.

        Args:
            message: User's text message
            session_id: Optional session ID for conversation continuity
            image_url: Optional public URL of an uploaded image
            image_base64: Optional base64-encoded image data
            image_mime_type: MIME type of the image (e.g., "image/jpeg")

        Returns:
            dict with 'message', 'session_id', 'tool_calls', and 'pending_confirmation'
        """
        # Get or create session
        session = await SessionMemory.get_or_create(session_id, self.user_id)

        # Add user message to session
        await session.add_message("user", message)

        # Assemble context
        context = await self.context_assembler.assemble_context(self.user_id)

        # Get conversation history
        history = await session.get_formatted_history()

        # Build system prompt with context
        system_prompt = self._build_system_prompt(context)

        # Get tool schemas
        tool_schemas = [tool.get_schema() for tool in self.tools.values()]

        # Call Gemini with optional image for vision analysis
        response = await self.gemini.chat_with_tools(
            system_prompt=system_prompt,
            messages=history,
            tools=tool_schemas,
            image_url=image_url,
            image_base64=image_base64,
            image_mime_type=image_mime_type or "image/jpeg",
        )

        # Process tool calls if any
        tool_results = []
        pending_confirmation = None
        confirmation_type = None

        if response.get("tool_calls"):
            for tool_call in response["tool_calls"]:
                result = await self._execute_tool(
                    tool_call["name"],
                    tool_call.get("arguments", {}),
                    session.session_id,
                )
                tool_results.append({
                    "tool_name": tool_call["name"],
                    "status": "success" if result.success else "error",
                    "result": result.data,
                    "error": result.error,
                    "requires_confirmation": result.requires_confirmation,
                    "suggestion_id": result.suggestion_id,
                })

                if result.requires_confirmation:
                    pending_confirmation = result.data
                    # Determine type from tool name
                    if "meal" in tool_call["name"]:
                        confirmation_type = "meal"
                    elif "workout" in tool_call["name"]:
                        confirmation_type = "workout"

        # Add type to pending confirmation for frontend
        if pending_confirmation and confirmation_type:
            pending_confirmation["type"] = confirmation_type

        # Get the final text response
        final_message = response.get("text", "")

        # Generate default message if AI didn't provide one
        if not final_message and pending_confirmation:
            if confirmation_type == "meal":
                items = pending_confirmation.get("items", [])
                item_names = ", ".join(item.get("name", "") for item in items)
                calories = pending_confirmation.get("calories", 0)
                final_message = f"I've logged {item_names} ({int(calories)} calories). Please confirm to save."
            elif confirmation_type == "workout":
                exercises = pending_confirmation.get("exercises", [])
                ex_names = ", ".join(ex.get("name", "") for ex in exercises)
                final_message = f"I've logged your workout: {ex_names}. Please confirm to save."

        # Add assistant response to session
        await session.add_message(
            "assistant",
            final_message,
            tool_calls=[tc["name"] for tc in response.get("tool_calls", [])],
        )

        return {
            "message": final_message,
            "session_id": session.session_id,
            "tool_calls": tool_results,
            "pending_confirmation": pending_confirmation,
        }

    async def confirm_suggestion(
        self,
        suggestion_type: str,
        suggestion_id: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Confirm a pending suggestion (meal or workout)."""
        if suggestion_type == "meal":
            tool = self.tools["confirm_log_meal"]
        elif suggestion_type == "workout":
            tool = self.tools["confirm_log_workout"]
        else:
            return {
                "success": False,
                "error": f"Unknown suggestion type: {suggestion_type}",
            }

        result = await tool.execute(suggestion_id=suggestion_id)

        # Log the confirmation
        if session_id:
            session = await SessionMemory.get_or_create(session_id, self.user_id)
            await session.add_message(
                "system",
                f"User confirmed {suggestion_type} log: {suggestion_id}",
            )

        return {
            "success": result.success,
            "data": result.data,
            "error": result.error,
        }

    async def _execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        session_id: str,
    ) -> Any:
        """Execute a tool and log the call."""
        tool = self.tools.get(tool_name)

        if not tool:
            from app.mcp.tools.base import ToolResult
            return ToolResult(
                success=False,
                error=f"Unknown tool: {tool_name}",
            )

        # Execute the tool
        result = await tool.execute(**arguments)

        # Log the tool call (for debugging and analytics)
        await self._log_tool_call(
            session_id,
            tool_name,
            arguments,
            result,
        )

        return result

    async def _log_tool_call(
        self,
        session_id: str,
        tool_name: str,
        args: dict,
        result: Any,
    ) -> None:
        """Log a tool call to the database."""
        # Get or create conversation session record
        from sqlalchemy import select

        db_session = await self.db.execute(
            select(ConversationSession).where(
                ConversationSession.id == session_id
            )
        )
        session_record = db_session.scalar_one_or_none()

        if not session_record:
            session_record = ConversationSession(
                id=session_id,
                user_id=self.user_id,
            )
            self.db.add(session_record)
            await self.db.flush()

        # Create tool call record
        tool_call = ToolCall(
            session_id=session_id,
            tool_name=tool_name,
            args=args,
            result=result.data if hasattr(result, 'data') else None,
            status="success" if result.success else "error",
        )
        self.db.add(tool_call)

    def _build_system_prompt(self, context: dict[str, Any]) -> str:
        """Build the system prompt with context."""
        profile = context.get("profile", {})
        targets = context.get("targets", {})
        remaining = context.get("remaining_macros", {}).get("remaining", {})
        activity = context.get("activity", {})
        memories = context.get("memories", {})

        prompt = """You are Reppy, a friendly and knowledgeable AI fitness coach.
Your role is to help users log their meals and workouts, track their progress,
and provide personalized coaching advice.

IMPORTANT GUIDELINES:
- Be conversational and encouraging, but concise
- When a user describes food, ALWAYS use log_meal_suggestion to create a structured log
- When a user describes exercise, ALWAYS use log_workout_suggestion to create a structured log
- YOU must estimate calories and macros based on typical nutritional data - never ask the user for these values
- Use confidence scores: 0.8-0.9 for common foods with clear portions, 0.6-0.7 for uncertain portions
- Use metric units (kg, cm) unless user specifies otherwise
- Provide sugar and portion warnings when relevant
- Never claim to provide medical advice - you offer educational coaching only
- CRITICAL: Always call the logging tool with your best estimates. Do not ask follow-up questions about nutrition values.

USER PROFILE:
"""
        if profile:
            prompt += f"""- Name: {profile.get('name', 'User')}
- Age: {profile.get('age', 'Unknown')}
- Sex: {profile.get('sex', 'Not specified')}
- Height: {profile.get('height_cm', 'Unknown')} cm
- Weight: {profile.get('weight_kg', 'Unknown')} kg
- Activity level: {profile.get('activity_level', 'moderate')}
- Goals: {', '.join(profile.get('goals', [])) or 'Not set'}
- Diet style: {profile.get('diet_style', 'Not specified')}
- Allergies: {', '.join(profile.get('allergies', [])) or 'None'}
- Available equipment: {', '.join(profile.get('equipment', [])) or 'Bodyweight only'}
"""

        prompt += f"""
DAILY TARGETS:
- Calories: {targets.get('daily_calories', 'Not set')}
- Protein: {targets.get('daily_protein_g', 'Not set')}g
- Carbs: {targets.get('daily_carbs_g', 'Not set')}g
- Fat: {targets.get('daily_fat_g', 'Not set')}g
- Steps: {targets.get('daily_steps', 10000)}

REMAINING TODAY:
- Calories: {remaining.get('calories', 'N/A')}
- Protein: {remaining.get('protein_g', 'N/A')}g
- Carbs: {remaining.get('carbs_g', 'N/A')}g
- Fat: {remaining.get('fat_g', 'N/A')}g

ACTIVITY:
- Today's steps: {activity.get('today_steps', 0)}
- 7-day average: {activity.get('seven_day_average', 0)}
- Streak: {activity.get('streak_days', 0)} days

"""
        # Add learned memories if any exist
        if memories:
            prompt += "LEARNED PREFERENCES (remember these about the user):\n"
            if memories.get("food_preferences"):
                prompt += f"- Food preferences: {', '.join(memories['food_preferences'])}\n"
            if memories.get("food_dislikes"):
                prompt += f"- Dislikes: {', '.join(memories['food_dislikes'])}\n"
            if memories.get("workout_habits"):
                prompt += f"- Workout habits: {', '.join(memories['workout_habits'])}\n"
            if memories.get("schedule"):
                prompt += f"- Schedule: {', '.join(memories['schedule'])}\n"
            if memories.get("health_notes"):
                prompt += f"- Health notes: {', '.join(memories['health_notes'])}\n"
            if memories.get("goals"):
                prompt += f"- Personal goals: {', '.join(memories['goals'])}\n"
            prompt += "\n"

        prompt += """LEARNING USER PREFERENCES:
When the user mentions any of the following, use the learn_user_fact tool to remember it:
- Food preferences or dislikes ("I don't like spinach", "I love spicy food")
- Workout habits ("I gym in the morning", "I prefer cardio over weights")
- Schedule patterns ("I usually eat lunch at 1pm", "I work out on weekdays")
- Health conditions ("I'm lactose intolerant", "I have a knee injury")
- Personal goals ("Training for a marathon", "Trying to bulk up")
- Any other personal info that would help personalize future interactions

When suggesting meals, always provide:
1. All items with name, quantity, and unit
2. Accurate calorie and macro estimates (protein, carbs, fat)
3. A confidence score (0-1) indicating how certain you are
4. Brief educational notes (tips, warnings, suggestions)

When suggesting workouts, ALWAYS provide:
1. All exercises with sets, reps, and weight (if applicable)
2. estimated_duration_min - REQUIRED: estimate total workout time based on exercises, sets, and rest periods
3. estimated_calories_burned - REQUIRED: estimate calories based on exercise intensity, duration, and type
4. workout_type (strength, cardio, flexibility, or mixed)
5. A confidence score (0-1)
6. Brief notes with form tips or suggestions

For calorie estimation guidelines:
- Light activity (stretching, yoga): 3-4 cal/min
- Moderate activity (weight training): 5-7 cal/min
- Intense activity (HIIT, running): 8-12 cal/min

MEAL PHOTO ANALYSIS:
When the user sends a photo of food:
1. Identify ALL visible food items in the image
2. Estimate portion sizes based on visual cues (plate size, utensils, containers)
3. Use context clues like restaurant packaging or brand labels
4. Consider regional/cultural variations of dishes
5. When uncertain about exact ingredients, make educated assumptions and note them
6. ALWAYS call log_meal_suggestion with your analysis - don't just describe the food
7. Be confident but honest - use lower confidence scores (0.5-0.7) for ambiguous portions
8. Include relevant tips about the meal (sugar content, sodium, healthier alternatives)

Common portion estimation guides:
- Standard dinner plate: 10-12 inches diameter
- Palm-sized protein: ~3-4 oz (85-115g)
- Fist-sized portion: ~1 cup (240ml)
- Thumb-sized fat: ~1 tablespoon (15ml)
- Golf ball-sized: ~2 tablespoons (30ml)

MENU ASSISTANT (Restaurant Menu Analysis):
When the user shares a menu (photo or text) and asks what to order:
1. This is NOT a meal to log - it's a menu for recommendations
2. Read and identify all menu items (from image or text)
3. Use the menu_recommendations tool to provide structured recommendations:
   - menu_items: List all items you identified with estimated calories/macros
   - best_choices: Top 2-3 items that fit their goals and remaining macros
   - ok_choices: Acceptable options with suggested modifications
   - avoid: Items they should skip and why
   - allergy_warnings: Flag any items that may contain their allergens
   - overall_advice: General tips for ordering at this restaurant
4. Consider:
   - User's REMAINING daily calories and macros
   - Their fitness goals (fat loss, muscle gain, maintenance)
   - Dietary preferences and allergies from their profile
   - Today's activity (workouts done, steps taken)
   - Meal timing (if it's dinner and they've had high carbs, suggest lower carb options)
5. For each recommendation:
   - Explain WHY it's a good/bad choice
   - Suggest modifications (e.g., "ask for dressing on the side", "substitute fries for salad")
   - Estimate macros as accurately as possible

Menu assistant triggers:
- Photo shows text with prices, item names, descriptions
- User pastes menu text or lists menu items
- User says "what should I order" or "help me pick" or "analyze this menu"
- Photo clearly shows a restaurant menu format
- "I'm at [restaurant], what should I get?"

MEAL RECOMMENDATIONS:
When the user asks for meal suggestions or ideas:
1. Use the suggest_meals tool to provide personalized recommendations
2. Consider their remaining daily macros and calorie budget
3. Respect dietary preferences (vegetarian, vegan, keto, etc.)
4. Account for any allergies in their profile
5. Suggest 3-5 varied meal options with estimated nutrition
6. Include quick/easy options and more elaborate ones
7. Explain WHY each meal fits their goals

Recommendation triggers (use suggest_meals):
- "What should I eat?"
- "Suggest a meal"
- "I'm hungry"
- "Need meal ideas"
- "What's for [breakfast/lunch/dinner]?"
- Any request for food recommendations or suggestions

MEAL PLANNING:
When the user asks for a meal plan (multi-day planning):
IMPORTANT: You already have the user's profile data above (goals, diet style, allergies, calorie/macro targets).
DO NOT ask the user for information you already have. Use the profile data to generate the plan immediately.
- Use their "Daily Targets" for calorie and macro goals
- Use their "Diet style" to determine meal types (vegetarian, keto, etc.)
- Use their "Allergies" to avoid problematic ingredients
- Default to 7 days unless user specifies otherwise

1. Use the generate_meal_plan tool with a complete "plan" array
2. Generate a plan array with one object per day, each containing:
   - day: day number (1, 2, 3, etc.)
   - date: ISO date string
   - meals: array of meals for that day, each with:
     - type: "breakfast", "lunch", "dinner", or "snack"
     - name: meal name
     - description: brief description
     - calories: estimated calories
     - protein_g, carbs_g, fat_g: macros
     - ingredients: list of ingredients
     - prep_time_min: estimated prep time
     - instructions: cooking instructions
   - total_calories, total_protein, total_carbs, total_fat: day totals
3. Consider the user's calorie and macro targets from their profile
4. Respect dietary preferences and allergies
5. Vary meals to avoid repetition
6. Focus parameter options: balanced, high_protein, low_carb, vegetarian, quick_meals, budget_friendly

Meal plan triggers:
- "Create a meal plan"
- "Plan my meals for the week"
- "Weekly meal plan"
- "What should I eat this week?"
- Any multi-day meal planning request

GROCERY LIST GENERATION:
When the user asks for a grocery/shopping list:
1. Use the generate_grocery_list tool with a complete "items" array
2. Each item should have: name, quantity, unit, category
3. Categories: produce, protein, dairy, grains, pantry, frozen, other
4. Consolidate similar items (e.g., combine all eggs needed)
5. Group by category for easier shopping

WORKOUT PROGRAM PLANNING:
When the user asks for a workout plan or training program:
IMPORTANT: You already have the user's profile data above (goals, equipment, activity level).
DO NOT ask the user for information you already have. Use the profile data to generate the plan immediately.
- Use their "Goals" to determine the program goal (strength, hypertrophy, fat loss, etc.)
- Use their "Available equipment" to select appropriate exercises
- Use their "Activity level" to set difficulty (sedentary/light = beginner, moderate = intermediate, active/very_active = advanced)
- Default to 4 weeks, 4 days/week, upper_lower split unless user specifies otherwise

1. YOU MUST generate the complete workout program yourself and pass it as a JSON string in the "plan" parameter
2. The "plan" parameter is REQUIRED - you must provide a JSON string containing an array of workout days
3. Generate a plan array with one object per workout day, each containing:
   - week: week number (1, 2, 3, etc.)
   - day: day number within the week (1-7)
   - day_name: descriptive name (e.g., "Push Day", "Upper Body", "Leg Day")
   - workout_type: "strength", "cardio", "flexibility", or "mixed"
   - is_rest_day: false for workout days, true for rest days
   - exercises: array of exercises, each with:
     - name: exercise name
     - sets: number of sets (e.g., 3, 4)
     - reps: rep range as string (e.g., "8-12", "10", "AMRAP")
     - weight_suggestion: guidance like "moderate", "heavy", or specific kg
     - rest_sec: rest between sets (e.g., 60, 90, 120)
     - notes: form cues or tips
   - target_muscles: array of muscles worked (e.g., ["chest", "shoulders", "triceps"])
   - estimated_duration_min: total workout time
   - notes: any additional workout notes
4. Example plan parameter format (as JSON string):
   [{"week":1,"day":1,"day_name":"Upper Body A","workout_type":"strength","is_rest_day":false,"exercises":[{"name":"Bench Press","sets":4,"reps":"6-8","weight_suggestion":"moderate to heavy","rest_sec":120,"notes":"Keep back flat on bench"}],"target_muscles":["chest","shoulders","triceps"],"estimated_duration_min":60,"notes":"Focus on compound movements"}]
5. Consider the user's:
   - Fitness goals (strength, hypertrophy, fat loss, endurance)
   - Experience level (beginner, intermediate, advanced)
   - Available equipment from their profile
   - Days per week they can train
6. Include progressive overload - slightly increase difficulty week over week
7. Balance muscle groups appropriately for the split type
8. Include rest days (is_rest_day: true) as appropriate

Workout plan triggers:
- "Create a workout plan"
- "Make me a training program"
- "I want a workout schedule"
- "Plan my workouts for the week"
- "Give me a 4-week program"
- Any multi-week training program request

Split type options:
- full_body: Train all muscles each session (good for 2-3 days/week)
- upper_lower: Alternate upper and lower body (good for 4 days/week)
- push_pull_legs: Push, Pull, Legs rotation (good for 3-6 days/week)
- bro_split: One muscle group per day (good for 5-6 days/week)

GETTING TODAY'S WORKOUT:
When the user asks what workout they should do today:
1. Use the get_todays_workout tool to fetch their next scheduled workout
2. If they have no active plan, offer to create one
3. Present the exercises clearly with sets, reps, and weight suggestions

Today's workout triggers:
- "What's my workout today?"
- "What should I train today?"
- "What's next in my program?"

COMPLETING A WORKOUT:
When the user says they finished their workout:
1. Use the complete_workout_day tool to mark it done
2. Congratulate them and note their progress

EXERCISE ALTERNATIVES:
When the user can't do a specific exercise:
1. Use the suggest_exercise_alternative tool
2. Provide an alternative that targets the same muscles
3. Explain why it's a good substitute
"""
        return prompt
