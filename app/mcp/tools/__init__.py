"""MCP tools for AI agent interactions."""

from app.mcp.tools.base import BaseTool, ToolResult
from app.mcp.tools.meal_tools import (
    ConfirmMealLogTool,
    LogMealSuggestionTool,
)
from app.mcp.tools.workout_tools import (
    ConfirmWorkoutLogTool,
    LogWorkoutSuggestionTool,
)
from app.mcp.tools.activity_tools import GetActivitySummaryTool
from app.mcp.tools.profile_tools import GetUserContextTool
from app.mcp.tools.recommendation_tools import MenuRecommendationsTool, SuggestMealsTool
from app.mcp.tools.memory_tools import LearnFactTool, GetUserMemoriesTools
from app.mcp.tools.workout_plan_tools import (
    GenerateWorkoutPlanTool,
    GetTodaysWorkoutTool,
    CompleteWorkoutDayTool,
    SuggestExerciseAlternativeTool,
)
from app.mcp.tools.progress_tools import LogWeightTool, GetProgressSummaryTool

__all__ = [
    "BaseTool",
    "CompleteWorkoutDayTool",
    "ConfirmMealLogTool",
    "ConfirmWorkoutLogTool",
    "GenerateWorkoutPlanTool",
    "GetActivitySummaryTool",
    "GetProgressSummaryTool",
    "GetTodaysWorkoutTool",
    "GetUserContextTool",
    "GetUserMemoriesTools",
    "LearnFactTool",
    "LogMealSuggestionTool",
    "LogWeightTool",
    "LogWorkoutSuggestionTool",
    "MenuRecommendationsTool",
    "SuggestExerciseAlternativeTool",
    "SuggestMealsTool",
    "ToolResult",
]
