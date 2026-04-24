"""
Seed default policy rules into the database.

Run this script to populate the database with sample policy rules.
"""
import uuid
from sqlalchemy.orm import Session

from database.base import SessionLocal
from models import PolicyRule
from database.utils import create_policy_rule


def seed_default_rules():
    """Create default policy rules for testing."""
    
    default_rules = [
        PolicyRule(
            rule_id=str(uuid.uuid4()),
            category="financial",
            name="High Budget Alert",
            description="Events or requests exceeding $10,000 require additional approval",
            keywords=["budget", "cost", "expense", "amount", "$", "price", "funding"],
            conditions={"max_amount": 10000},
            severity="high",
            requires_review=True
        ),
        PolicyRule(
            rule_id=str(uuid.uuid4()),
            category="financial",
            name="Medium Budget Alert",
            description="Events or requests between $5,000-$10,000 require manager approval",
            keywords=["budget", "cost", "expense", "amount", "$", "price"],
            conditions={"max_amount": 5000},
            severity="medium",
            requires_review=True
        ),
        PolicyRule(
            rule_id=str(uuid.uuid4()),
            category="legal",
            name="Contract Review Required",
            description="Any contract or agreement requires legal review",
            keywords=["contract", "agreement", "terms", "conditions", "legal", "binding"],
            conditions={},
            severity="high",
            requires_review=True
        ),
        PolicyRule(
            rule_id=str(uuid.uuid4()),
            category="operational",
            name="Large Event Coordination",
            description="Events with more than 100 attendees require coordination",
            keywords=["attendees", "participants", "people", "guests", "capacity"],
            conditions={},
            severity="medium",
            requires_review=True
        ),
        PolicyRule(
            rule_id=str(uuid.uuid4()),
            category="security",
            name="Data Privacy Check",
            description="Any data sharing or external access requires security review",
            keywords=["data", "share", "access", "external", "third-party", "privacy"],
            conditions={},
            severity="high",
            requires_review=True
        ),
        PolicyRule(
            rule_id=str(uuid.uuid4()),
            category="compliance",
            name="Regulatory Compliance",
            description="Activities involving regulated industries require compliance check",
            keywords=["regulatory", "compliance", "audit", "certification", "licensed"],
            conditions={},
            severity="critical",
            requires_review=True
        ),
        PolicyRule(
            rule_id=str(uuid.uuid4()),
            category="operational",
            name="Vendor Selection",
            description="New vendor selection requires procurement approval",
            keywords=["vendor", "supplier", "contractor", "third-party", "external"],
            conditions={},
            severity="medium",
            requires_review=True
        ),
        PolicyRule(
            rule_id=str(uuid.uuid4()),
            category="financial",
            name="Emergency Spending",
            description="Emergency or urgent spending requires executive approval",
            keywords=["emergency", "urgent", "immediate", "critical", "asap"],
            conditions={},
            severity="high",
            requires_review=True
        )
    ]
    
    db: Session = SessionLocal()
    
    try:
        print("Seeding policy rules...")
        
        for rule in default_rules:
            try:
                create_policy_rule(db, rule)
                print(f"✅ Created rule: {rule.name} ({rule.category}, {rule.severity})")
            except Exception as e:
                print(f"⚠️  Rule '{rule.name}' may already exist or error: {str(e)}")
        
        print(f"\n✅ Seeding complete! Created {len(default_rules)} policy rules.")
        
    except Exception as e:
        print(f"❌ Error seeding rules: {str(e)}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_default_rules()
