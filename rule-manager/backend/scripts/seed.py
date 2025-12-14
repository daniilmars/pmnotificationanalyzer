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

            # Create an active AI Guidance ruleset
            ai_guidance_ruleset = Ruleset(
                group_id="ai-guidance-group",
                name="Default AI Guidance",
                notification_type="GENERAL", # Applies to all notification types
                status="Active",
                version=1,
                created_by="system_seed"
            )
            session.add(ai_guidance_ruleset)

            # Create AI Guidance rules (the 5 pillars of quality)
            pillars = [
                ("Compliance", "Analyze for adherence to GMP and other regulatory requirements."),
                ("Traceability", "Ensure the notification provides a clear audit trail of events and actions."),
                ("Root Cause", "Verify that a root cause analysis for the issue has been identified and documented."),
                ("Product Impact", "Assess the potential impact of the issue on product quality, safety, and efficacy."),
                ("CAPA", "Check for the presence and adequacy of Corrective and Preventive Actions.")
            ]

            for pillar_name, pillar_desc in pillars:
                rule = Rule(
                    ruleset=ai_guidance_ruleset,
                    rule_type='AI_GUIDANCE',
                    name=pillar_name,
                    description=pillar_desc,
                    target_field='N/A', # Not applicable for AI guidance
                    condition='N/A',   # Not applicable for AI guidance
                    value='',
                    score_impact=0,
                    feedback_message='' # Not applicable
                )
                session.add(rule)

            # Create a draft ruleset for M1 notifications for demonstration
            m1_ruleset = Ruleset(
                group_id="m1-draft-group",
                name="Draft Rules for Corrective Maintenance",
                notification_type="M1",
                status="Draft",
                version=1,
                created_by="system_seed"
            )
            session.add(m1_ruleset)

            # Create validation rules for the M1 ruleset
            rule1 = Rule(
                ruleset=m1_ruleset,
                rule_type='VALIDATION',
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
                rule_type='VALIDATION',
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