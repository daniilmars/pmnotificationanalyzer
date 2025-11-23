import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, database
from app.database import Ruleset, Rule

app = create_app()

def seed_data():
    with app.app_context():
        session = database.Session()
        try:
            if session.query(Ruleset).count() > 0:
                print("Database already seeded.")
                return

            print("Seeding Rule Manager database...")

            # Create an active ruleset for M1 notifications
            m1_ruleset = Ruleset(
                group_id="m1-active-group",
                name="Active Rules for Corrective Maintenance",
                notification_type="M1",
                status="Active",
                version=1,
                created_by="system_seed"
            )
            session.add(m1_ruleset)

            # Create rules for the M1 ruleset
            rule1 = Rule(
                ruleset=m1_ruleset,
                name="REQUIRE_ROOT_CAUSE",
                description="The long text must contain a root cause analysis starting with 'Root Cause:'",
                target_field="Long Text",
                condition="starts with",
                value="Root Cause:",
                score_impact=-25,
                feedback_message="The long text must begin with a root cause analysis, starting with 'Root Cause: A'"
            )

            rule2 = Rule(
                ruleset=m1_ruleset,
                name="MINIMUM_LONG_TEXT_LENGTH",
                description="The long text must be of a minimum length to be considered detailed.",
                target_field="Long Text",
                condition="has length greater than",
                value="50",
                score_impact=-15,
                feedback_message="The long text is too short and lacks sufficient detail for a GMP record."
            )

            session.add(rule1)
            session.add(rule2)
            
            session.commit()
            print("Rule Manager database seeded successfully.")

        finally:
            session.close()

if __name__ == "__main__":
    seed_data()