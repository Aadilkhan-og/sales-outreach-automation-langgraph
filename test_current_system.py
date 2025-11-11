"""
Test script to verify current system is working
Tests with 1 lead to avoid long processing time
"""

import os
import sys
from dotenv import load_dotenv
from src.graph import OutReachAutomation
from src.tools.leads_loader.apollo import ApolloLeadLoader

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Load environment variables
load_dotenv()

def test_system():
    print("Testing Current AI SDR System\n")
    print("=" * 60)

    # Check environment variables
    print("\n1. Checking Environment Variables...")
    required_vars = [
        "LLM_PROVIDER",
        "OPENAI_API_KEY",
        "APOLLO_CSV_PATH",
        "SERPER_API_KEY",
        "RAPIDAPI_KEY"
    ]

    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mask API keys
            if "KEY" in var or "API" in var:
                display_value = value[:10] + "..." if len(value) > 10 else "***"
            else:
                display_value = value
            print(f"   ✅ {var}: {display_value}")
        else:
            print(f"   ❌ {var}: NOT SET")
            missing_vars.append(var)

    if missing_vars:
        print(f"\n[WARNING] Missing required variables: {', '.join(missing_vars)}")
        print("Please check your .env file")
        return False

    # Test CSV file access
    print("\n2. Checking CSV File...")
    csv_path = os.getenv("APOLLO_CSV_PATH")
    if os.path.exists(csv_path):
        import pandas as pd
        try:
            df = pd.read_csv(csv_path)
            print(f"   ✅ CSV file found: {len(df)} leads")
            print(f"   Columns: {list(df.columns[:5])}...")
        except Exception as e:
            print(f"   ❌ Error reading CSV: {e}")
            return False
    else:
        print(f"   ❌ CSV file not found: {csv_path}")
        return False

    # Initialize lead loader
    print("\n3. Initializing Lead Loader...")
    try:
        lead_loader = ApolloLeadLoader(csv_file_path=csv_path)
        print("   ✅ Lead loader initialized")
    except Exception as e:
        print(f"   ❌ Error initializing loader: {e}")
        return False

    # Test with 1 lead
    print("\n4. Testing with 1 Lead...")
    print("   (This will take 2-5 minutes...)\n")

    try:
        # Initialize automation
        automation = OutReachAutomation(lead_loader)
        app = automation.app

        # Process first lead only
        inputs = {"leads_ids": []}  # Empty = fetch from CSV
        config = {'recursion_limit': 1000}

        print("   [STARTING] workflow...\n")
        output = app.invoke(inputs, config)

        print("\n" + "=" * 60)
        print("[SUCCESS] TEST COMPLETED SUCCESSFULLY!")
        print("=" * 60)

        # Display output summary
        print(f"\n[RESULTS]")
        print(f"   Leads processed: {output.get('number_leads', 0)}")

        if output.get('current_lead'):
            lead = output['current_lead']
            print(f"   Lead name: {lead.get('name', 'N/A')}")
            print(f"   Lead email: {lead.get('email', 'N/A')}")

        if output.get('lead_score'):
            print(f"   Lead score: {output['lead_score']}")

        if output.get('reports'):
            print(f"   Reports generated: {len(output['reports'])}")

        if output.get('personalized_email'):
            print(f"   Email generated: YES ({len(output['personalized_email'])} chars)")

        print(f"\nCheck 'reports' folder for generated content")

        return True

    except Exception as e:
        print(f"\n[ERROR] during execution:")
        print(f"   {str(e)}")
        import traceback
        print(f"\nFull traceback:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_system()

    if success:
        print("\n" + "=" * 60)
        print("[SUCCESS] SYSTEM IS WORKING CORRECTLY!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Check 'reports' folder for generated content")
        print("2. Review the personalized email")
        print("3. Ready to add email sending capability!")
    else:
        print("\n" + "=" * 60)
        print("[FAILED] SYSTEM TEST FAILED")
        print("=" * 60)
        print("\nPlease fix the errors above before proceeding")
