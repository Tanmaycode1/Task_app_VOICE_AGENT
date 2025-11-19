"""Migration script to add scheduled_date field to tasks table."""

import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from app.db.base import engine
from app.models.task import Task


def migrate():
    """Add scheduled_date column and migrate existing data."""
    
    print("Starting migration: Add scheduled_date to tasks table")
    
    with engine.begin() as conn:
        # Step 1: Check if column already exists
        result = conn.execute(text("""
            SELECT COUNT(*) 
            FROM pragma_table_info('tasks') 
            WHERE name='scheduled_date'
        """))
        
        if result.scalar() > 0:
            print("✓ Column 'scheduled_date' already exists. Skipping migration.")
            return
        
        # Step 2: Add scheduled_date column (nullable first for migration)
        print("Adding scheduled_date column...")
        conn.execute(text("""
            ALTER TABLE tasks 
            ADD COLUMN scheduled_date DATETIME
        """))
        
        # Step 3: Migrate existing data
        # For existing tasks: use deadline if present, otherwise use created_at
        print("Migrating existing task data...")
        conn.execute(text("""
            UPDATE tasks
            SET scheduled_date = COALESCE(deadline, created_at)
            WHERE scheduled_date IS NULL
        """))
        
        # Step 4: Verify all tasks have scheduled_date
        result = conn.execute(text("""
            SELECT COUNT(*) FROM tasks WHERE scheduled_date IS NULL
        """))
        null_count = result.scalar()
        
        if null_count > 0:
            print(f"⚠ WARNING: {null_count} tasks still have NULL scheduled_date")
            print("Setting to created_at for these tasks...")
            conn.execute(text("""
                UPDATE tasks
                SET scheduled_date = created_at
                WHERE scheduled_date IS NULL
            """))
        
        # Step 5: Get count of migrated tasks
        result = conn.execute(text("SELECT COUNT(*) FROM tasks"))
        total_tasks = result.scalar()
        
        print(f"✓ Migration completed successfully!")
        print(f"  - Total tasks migrated: {total_tasks}")
        print(f"  - scheduled_date column added")
        print(f"  - Existing tasks: scheduled_date = deadline (if present) OR created_at")
    
    print("\nℹ️  Note: SQLite doesn't support NOT NULL constraints via ALTER TABLE.")
    print("   The ORM model enforces scheduled_date as required for new tasks.")
    print("   All existing tasks have been migrated successfully.")


if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

