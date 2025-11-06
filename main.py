import os
from dotenv import load_dotenv
from src.graph import OutReachAutomation
from src.state import *
from src.tools.leads_loader.apollo import ApolloLeadLoader
from src.tools.leads_loader.supabase_loader import SupabaseLeadLoader

# Load environment variables from a .env file
load_dotenv()

if __name__ == "__main__":
    # Option 1: Use Apollo.io with CSV export
    lead_loader = ApolloLeadLoader(
        csv_file_path=os.getenv("APOLLO_CSV_PATH")
    )

    # Option 2: Use Apollo.io API (requires API key)
    # lead_loader = ApolloLeadLoader(
    #     api_key=os.getenv("APOLLO_API_KEY")
    # )

    # Option 3: Use Supabase for persistent storage (when needed)
    # lead_loader = SupabaseLeadLoader(
    #     supabase_url=os.getenv("SUPABASE_URL"),
    #     supabase_key=os.getenv("SUPABASE_KEY"),
    #     table_name=os.getenv("SUPABASE_TABLE_NAME", "leads")
    # )
    
    # Instantiate the OutReachAutomation class
    automation = OutReachAutomation(lead_loader)
    app = automation.app
    
    # initial graph inputs:
    # Lead ids to be processed, leave empty to fetch all news leads
    inputs = {"leads_ids": []}


    # Run the outreach automation with the provided lead name and email
    config = {'recursion_limit': 1000}
    output = app.invoke(inputs, config)
    print(output)