"""
Database Setup Script for StitchFlow V2

This script initializes the database, runs migrations, and optionally seeds data.
"""
import sys
import os
from pathlib import Path

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from database.base import engine, Base
from database.models import (
    WorkflowDB,
    ReasoningResultDB,
    PolicyScreeningResultDB,
    DecisionDB,
    AuditLogDB,
    PolicyRuleDB
)
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session


def check_database_exists():
    """Check if database tables exist."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    return len(tables) > 0


def create_tables():
    """Create all database tables."""
    print("[Database Setup] Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("[Database Setup] ✅ Tables created successfully")


def verify_tables():
    """Verify all required tables exist."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    required_tables = [
        'workflows',
        'reasoning_results',
        'policy_screening_results',
        'decisions',
        'audit_log',
        'policy_rules'
    ]
    
    print("\n[Database Setup] Verifying tables...")
    all_exist = True
    for table in required_tables:
        exists = table in tables
        status = "✅" if exists else "❌"
        print(f"  {status} {table}")
        if not exists:
            all_exist = False
    
    return all_exist


def seed_policy_rules():
    """Seed default policy rules."""
    print("\n[Database Setup] Seeding policy rules...")
    
    try:
        # Import and run seed script
        from seed_policy_rules import seed_policy_rules as seed_func
        seed_func()
        print("[Database Setup] ✅ Policy rules seeded successfully")
    except Exception as e:
        print(f"[Database Setup] ⚠️  Warning: Could not seed policy rules: {str(e)}")


def get_database_stats():
    """Get database statistics."""
    with Session(engine) as session:
        try:
            workflow_count = session.execute(text("SELECT COUNT(*) FROM workflows")).scalar()
            policy_count = session.execute(text("SELECT COUNT(*) FROM policy_rules")).scalar()
            audit_count = session.execute(text("SELECT COUNT(*) FROM audit_log")).scalar()
            
            print("\n[Database Setup] Database Statistics:")
            print(f"  📊 Workflows: {workflow_count}")
            print(f"  📋 Policy Rules: {policy_count}")
            print(f"  📝 Audit Entries: {audit_count}")
        except Exception as e:
            print(f"[Database Setup] ⚠️  Could not retrieve stats: {str(e)}")


def main():
    """Main setup function."""
    print("=" * 70)
    print("StitchFlow V2 - Database Setup")
    print("=" * 70)
    
    # Check if database exists
    db_exists = check_database_exists()
    
    if db_exists:
        print("\n[Database Setup] ℹ️  Database already exists")
        verify_tables()
    else:
        print("\n[Database Setup] ℹ️  Database does not exist, creating...")
        create_tables()
        
        # Verify creation
        if verify_tables():
            print("\n[Database Setup] ✅ All tables created successfully")
        else:
            print("\n[Database Setup] ❌ Some tables are missing")
            return 1
    
    # Ask about seeding
    print("\n[Database Setup] Seed default policy rules? (y/n): ", end="")
    response = input().strip().lower()
    
    if response in ['y', 'yes']:
        seed_policy_rules()
    else:
        print("[Database Setup] Skipping policy rule seeding")
    
    # Show stats
    get_database_stats()
    
    print("\n" + "=" * 70)
    print("✅ Database setup complete!")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Start the server: uvicorn main:app --reload")
    print("  2. Access API docs: http://localhost:8000/docs")
    print("  3. Upload a document to test the system")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
