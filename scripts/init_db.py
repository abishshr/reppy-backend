"""
Database initialization script for production deployment.

This script handles the case where the database schema is out of sync with
alembic migrations. It:
1. Adds any missing columns via raw SQL (safe - ignores if exists)
2. Creates any missing tables

Run before starting the server to ensure database is in correct state.
"""

import asyncio
import os
import sys

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.infrastructure.database.connection import engine


# Columns that may be missing from user_profiles table
USER_PROFILE_COLUMNS = [
    ("injuries", "JSONB", "DEFAULT '[]'::jsonb"),
    ("medical_conditions", "JSONB", "DEFAULT '[]'::jsonb"),
    ("preferred_ingredients", "JSONB", "DEFAULT '[]'::jsonb"),
    ("daily_water_goal_ml", "INTEGER", "DEFAULT 2500"),
    ("daily_sugar_target_g", "DOUBLE PRECISION", "DEFAULT 50"),
    ("daily_fiber_target_g", "DOUBLE PRECISION", "DEFAULT 28"),
    ("daily_sodium_target_mg", "DOUBLE PRECISION", "DEFAULT 2300"),
    ("daily_saturated_fat_target_g", "DOUBLE PRECISION", "DEFAULT 20"),
    ("current_streak", "INTEGER", "DEFAULT 0"),
    ("longest_streak", "INTEGER", "DEFAULT 0"),
    ("last_activity_date", "TIMESTAMP WITH TIME ZONE", ""),
    ("streak_grace_hours", "INTEGER", "DEFAULT 36"),
    ("weight_goal_kg", "DOUBLE PRECISION", ""),
    ("target_rate_kg_per_week", "DOUBLE PRECISION", ""),
    ("goal_target_date", "TIMESTAMP WITH TIME ZONE", ""),
]

# Columns for meal_logs table (micronutrients)
MEAL_LOG_COLUMNS = [
    ("sugar_g_est", "DOUBLE PRECISION", ""),
    ("fiber_g_est", "DOUBLE PRECISION", ""),
    ("sodium_mg_est", "DOUBLE PRECISION", ""),
    ("saturated_fat_g_est", "DOUBLE PRECISION", ""),
    ("cholesterol_mg_est", "DOUBLE PRECISION", ""),
    ("vitamin_a_mcg_est", "DOUBLE PRECISION", ""),
    ("vitamin_c_mg_est", "DOUBLE PRECISION", ""),
    ("vitamin_d_mcg_est", "DOUBLE PRECISION", ""),
    ("vitamin_e_mg_est", "DOUBLE PRECISION", ""),
    ("vitamin_k_mcg_est", "DOUBLE PRECISION", ""),
    ("vitamin_b1_mg_est", "DOUBLE PRECISION", ""),
    ("vitamin_b2_mg_est", "DOUBLE PRECISION", ""),
    ("vitamin_b3_mg_est", "DOUBLE PRECISION", ""),
    ("vitamin_b6_mg_est", "DOUBLE PRECISION", ""),
    ("vitamin_b9_mcg_est", "DOUBLE PRECISION", ""),
    ("vitamin_b12_mcg_est", "DOUBLE PRECISION", ""),
    ("calcium_mg_est", "DOUBLE PRECISION", ""),
    ("iron_mg_est", "DOUBLE PRECISION", ""),
    ("magnesium_mg_est", "DOUBLE PRECISION", ""),
    ("phosphorus_mg_est", "DOUBLE PRECISION", ""),
    ("potassium_mg_est", "DOUBLE PRECISION", ""),
    ("zinc_mg_est", "DOUBLE PRECISION", ""),
    ("selenium_mcg_est", "DOUBLE PRECISION", ""),
    ("copper_mcg_est", "DOUBLE PRECISION", ""),
    ("manganese_mg_est", "DOUBLE PRECISION", ""),
    ("health_score", "INTEGER", ""),
    ("health_score_breakdown", "JSONB", ""),
    ("ai_analyzed_at", "TIMESTAMP WITH TIME ZONE", ""),
    ("synergy_insights", "JSONB", ""),
]


async def add_column_if_not_exists(conn, table: str, column: str, dtype: str, default: str = ""):
    """Add a column to a table if it doesn't exist."""
    check_query = text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = :table AND column_name = :column
    """)
    result = await conn.execute(check_query, {"table": table, "column": column})
    exists = result.fetchone() is not None

    if not exists:
        default_clause = default if default else ""
        add_query = text(f'ALTER TABLE {table} ADD COLUMN {column} {dtype} {default_clause}')
        try:
            await conn.execute(add_query)
            print(f"  Added column {table}.{column}")
        except Exception as e:
            print(f"  Warning: Could not add {table}.{column}: {e}")
    else:
        print(f"  Column {table}.{column} already exists")


async def ensure_table_exists(conn, table_name: str, create_sql: str):
    """Create table if it doesn't exist."""
    check_query = text("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = :table
    """)
    result = await conn.execute(check_query, {"table": table_name})
    exists = result.fetchone() is not None

    if not exists:
        try:
            await conn.execute(text(create_sql))
            print(f"  Created table {table_name}")
        except Exception as e:
            print(f"  Warning: Could not create {table_name}: {e}")
    else:
        print(f"  Table {table_name} already exists")


async def init_database():
    """Initialize database schema - add missing columns and tables."""
    print("Initializing database schema...")

    async with engine.begin() as conn:
        # Add missing columns to user_profiles
        print("\nChecking user_profiles columns...")
        for column, dtype, default in USER_PROFILE_COLUMNS:
            await add_column_if_not_exists(conn, "user_profiles", column, dtype, default)

        # Add missing columns to meal_logs
        print("\nChecking meal_logs columns...")
        for column, dtype, default in MEAL_LOG_COLUMNS:
            await add_column_if_not_exists(conn, "meal_logs", column, dtype, default)

        # Ensure blood_work_panels table exists
        print("\nChecking blood_work_panels table...")
        await ensure_table_exists(conn, "blood_work_panels", """
            CREATE TABLE blood_work_panels (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                lab_name VARCHAR(200),
                test_date TIMESTAMP WITH TIME ZONE NOT NULL,
                report_image_url VARCHAR(500),
                source VARCHAR(50) DEFAULT 'manual',
                ocr_confidence DOUBLE PRECISION,
                vitamin_d_ng_ml DOUBLE PRECISION,
                vitamin_b12_pg_ml DOUBLE PRECISION,
                folate_ng_ml DOUBLE PRECISION,
                iron_mcg_dl DOUBLE PRECISION,
                ferritin_ng_ml DOUBLE PRECISION,
                tibc_mcg_dl DOUBLE PRECISION,
                vitamin_a_mcg_dl DOUBLE PRECISION,
                vitamin_e_mg_dl DOUBLE PRECISION,
                zinc_mcg_dl DOUBLE PRECISION,
                magnesium_mg_dl DOUBLE PRECISION,
                calcium_mg_dl DOUBLE PRECISION,
                fasting_glucose_mg_dl DOUBLE PRECISION,
                hba1c_percent DOUBLE PRECISION,
                insulin_miu_ml DOUBLE PRECISION,
                homa_ir DOUBLE PRECISION,
                total_cholesterol_mg_dl DOUBLE PRECISION,
                ldl_mg_dl DOUBLE PRECISION,
                hdl_mg_dl DOUBLE PRECISION,
                triglycerides_mg_dl DOUBLE PRECISION,
                vldl_mg_dl DOUBLE PRECISION,
                testosterone_total_ng_dl DOUBLE PRECISION,
                testosterone_free_pg_ml DOUBLE PRECISION,
                estradiol_pg_ml DOUBLE PRECISION,
                tsh_miu_l DOUBLE PRECISION,
                t3_ng_dl DOUBLE PRECISION,
                t4_mcg_dl DOUBLE PRECISION,
                cortisol_mcg_dl DOUBLE PRECISION,
                hemoglobin_g_dl DOUBLE PRECISION,
                hematocrit_percent DOUBLE PRECISION,
                rbc_million_per_ul DOUBLE PRECISION,
                wbc_thousand_per_ul DOUBLE PRECISION,
                platelets_thousand_per_ul DOUBLE PRECISION,
                mcv_fl DOUBLE PRECISION,
                mch_pg DOUBLE PRECISION,
                mchc_g_dl DOUBLE PRECISION,
                alt_u_l DOUBLE PRECISION,
                ast_u_l DOUBLE PRECISION,
                alp_u_l DOUBLE PRECISION,
                bilirubin_mg_dl DOUBLE PRECISION,
                creatinine_mg_dl DOUBLE PRECISION,
                bun_mg_dl DOUBLE PRECISION,
                egfr_ml_min DOUBLE PRECISION,
                ai_analysis JSONB,
                ai_analyzed_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)

        # Ensure supplements table exists
        print("\nChecking supplements table...")
        await ensure_table_exists(conn, "supplements", """
            CREATE TABLE supplements (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(200) NOT NULL,
                brand VARCHAR(200),
                serving_size VARCHAR(100),
                vitamin_a_mcg DOUBLE PRECISION,
                vitamin_c_mg DOUBLE PRECISION,
                vitamin_d_mcg DOUBLE PRECISION,
                vitamin_e_mg DOUBLE PRECISION,
                vitamin_k_mcg DOUBLE PRECISION,
                vitamin_b1_mg DOUBLE PRECISION,
                vitamin_b2_mg DOUBLE PRECISION,
                vitamin_b3_mg DOUBLE PRECISION,
                vitamin_b6_mg DOUBLE PRECISION,
                vitamin_b9_mcg DOUBLE PRECISION,
                vitamin_b12_mcg DOUBLE PRECISION,
                calcium_mg DOUBLE PRECISION,
                iron_mg DOUBLE PRECISION,
                magnesium_mg DOUBLE PRECISION,
                phosphorus_mg DOUBLE PRECISION,
                potassium_mg DOUBLE PRECISION,
                zinc_mg DOUBLE PRECISION,
                selenium_mcg DOUBLE PRECISION,
                copper_mcg DOUBLE PRECISION,
                manganese_mg DOUBLE PRECISION,
                iodine_mcg DOUBLE PRECISION,
                omega3_mg DOUBLE PRECISION,
                biotin_mcg DOUBLE PRECISION,
                choline_mg DOUBLE PRECISION,
                notes TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)

        # Ensure supplement_logs table exists
        print("\nChecking supplement_logs table...")
        await ensure_table_exists(conn, "supplement_logs", """
            CREATE TABLE supplement_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                supplement_id UUID NOT NULL REFERENCES supplements(id) ON DELETE CASCADE,
                servings DOUBLE PRECISION DEFAULT 1.0,
                logged_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                notes TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)

        # Ensure fasting tables exist
        print("\nChecking fasting_sessions table...")
        await ensure_table_exists(conn, "fasting_sessions", """
            CREATE TABLE fasting_sessions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                protocol VARCHAR(20) NOT NULL,
                started_at TIMESTAMP WITH TIME ZONE NOT NULL,
                target_end_at TIMESTAMP WITH TIME ZONE NOT NULL,
                actual_end_at TIMESTAMP WITH TIME ZONE,
                status VARCHAR(20) DEFAULT 'active',
                duration_hours DOUBLE PRECISION NOT NULL,
                notes TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)

        print("\nChecking fasting_settings table...")
        await ensure_table_exists(conn, "fasting_settings", """
            CREATE TABLE fasting_settings (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                preferred_protocol VARCHAR(20),
                eating_window_start VARCHAR(5),
                eating_window_end VARCHAR(5),
                notify_fast_complete BOOLEAN DEFAULT TRUE,
                notify_reminder_before_min INTEGER DEFAULT 30,
                fasting_days_of_week JSONB,
                fasting_calorie_limit INTEGER DEFAULT 500,
                current_fasting_streak INTEGER DEFAULT 0,
                longest_fasting_streak INTEGER DEFAULT 0,
                last_fast_completed_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)

        await conn.commit()

    print("\nDatabase schema initialization complete!")


if __name__ == "__main__":
    asyncio.run(init_database())
