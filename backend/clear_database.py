"""
Clear Database Script - Delete All Workflow Data

This script allows you to delete all workflows and related data from the database.
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

from database.base import engine
from sqlalchemy import text
from sqlalchemy.orm import Session


def clear_all_data():
    """Delete all data from all tables."""
    print("=" * 70)
    print("StitchFlow V2 - Clear All Database Data")
    print("=" * 70)
    print("\n⚠️  WARNING: This will delete ALL data from the database!")
    print("This includes:")
    print("  - All workflows")
    print("  - All reasoning results")
    print("  - All policy screening results")
    print("  - All decisions")
    print("  - All audit log entries")
    print("  - Policy rules will be kept")
    print()
    
    response = input("Are you sure you want to continue? (type 'yes' to confirm): ")
    
    if response.lower() != 'yes':
        print("\n❌ Operation cancelled.")
        return
    
    print("\n🗑️  Deleting all data...")
    
    with Session(engine) as session:
        try:
            # Delete in order to respect foreign key constraints
            tables_to_clear = [
                ('decisions', 'Decisions'),
                ('policy_screening_results', 'Policy Screening Results'),
                ('reasoning_results', 'Reasoning Results'),
                ('audit_log', 'Audit Log Entries'),
                ('workflows', 'Workflows')
            ]
            
            for table_name, display_name in tables_to_clear:
                result = session.execute(text(f"DELETE FROM {table_name}"))
                count = result.rowcount
                print(f"  ✅ Deleted {count} {display_name}")
            
            session.commit()
            
            print("\n✅ All data deleted successfully!")
            print("\nDatabase is now empty (except policy rules).")
            
        except Exception as e:
            session.rollback()
            print(f"\n❌ Error deleting data: {str(e)}")
            return 1
    
    return 0


def clear_workflows_only():
    """Delete only workflows and their related data."""
    print("=" * 70)
    print("StitchFlow V2 - Clear Workflows Only")
    print("=" * 70)
    print("\n⚠️  This will delete all workflows and related data.")
    print("Audit log entries will be kept for compliance.")
    print()
    
    response = input("Are you sure? (type 'yes' to confirm): ")
    
    if response.lower() != 'yes':
        print("\n❌ Operation cancelled.")
        return
    
    print("\n🗑️  Deleting workflows...")
    
    with Session(engine) as session:
        try:
            # Delete related data first
            tables = [
                ('decisions', 'Decisions'),
                ('policy_screening_results', 'Policy Screening Results'),
                ('reasoning_results', 'Reasoning Results'),
                ('workflows', 'Workflows')
            ]
            
            for table_name, display_name in tables:
                result = session.execute(text(f"DELETE FROM {table_name}"))
                count = result.rowcount
                print(f"  ✅ Deleted {count} {display_name}")
            
            session.commit()
            
            print("\n✅ Workflows deleted successfully!")
            print("Audit log entries have been preserved.")
            
        except Exception as e:
            session.rollback()
            print(f"\n❌ Error deleting workflows: {str(e)}")
            return 1
    
    return 0


def show_statistics():
    """Show current database statistics."""
    print("=" * 70)
    print("StitchFlow V2 - Database Statistics")
    print("=" * 70)
    
    with Session(engine) as session:
        try:
            tables = [
                ('workflows', 'Workflows'),
                ('reasoning_results', 'Reasoning Results'),
                ('policy_screening_results', 'Policy Screening Results'),
                ('decisions', 'Decisions'),
                ('audit_log', 'Audit Log Entries'),
                ('policy_rules', 'Policy Rules')
            ]
            
            print("\nCurrent database contents:")
            for table_name, display_name in tables:
                result = session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                count = result.scalar()
                print(f"  📊 {display_name}: {count}")
            
        except Exception as e:
            print(f"\n❌ Error retrieving statistics: {str(e)}")


def main():
    """Main menu."""
    while True:
        print("\n" + "=" * 70)
        print("StitchFlow V2 - Database Management")
        print("=" * 70)
        print("\nWhat would you like to do?")
        print("  1. View database statistics")
        print("  2. Delete all workflows (keep audit log)")
        print("  3. Delete ALL data (including audit log)")
        print("  4. Exit")
        print()
        
        choice = input("Enter your choice (1-4): ").strip()
        
        if choice == '1':
            show_statistics()
        elif choice == '2':
            clear_workflows_only()
        elif choice == '3':
            clear_all_data()
        elif choice == '4':
            print("\n👋 Goodbye!")
            break
        else:
            print("\n❌ Invalid choice. Please enter 1, 2, 3, or 4.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled by user.")
        sys.exit(0)
