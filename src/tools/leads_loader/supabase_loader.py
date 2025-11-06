import os
from typing import List, Dict, Optional
from .lead_loader_base import LeadLoaderBase

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("[WARNING] Supabase not installed. Run: pip install supabase")


class SupabaseLeadLoader(LeadLoaderBase):
    """
    Lead loader for Supabase database
    Useful when you need persistent storage with real-time updates
    """

    def __init__(self, supabase_url: str, supabase_key: str, table_name: str = "leads"):
        """
        Initialize Supabase Lead Loader

        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase anon/service key
            table_name: Name of the leads table in Supabase
        """
        if not SUPABASE_AVAILABLE:
            raise ImportError("Supabase package not installed. Run: pip install supabase")

        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.table_name = table_name

        # Initialize Supabase client
        self.client: Client = create_client(supabase_url, supabase_key)

    def fetch_records(self, lead_ids: Optional[List[str]] = None, status_filter: str = "NEW") -> List[Dict]:
        """
        Fetch leads from Supabase

        Args:
            lead_ids: Specific lead IDs to fetch
            status_filter: Filter by status

        Returns:
            List of lead records
        """
        try:
            if lead_ids:
                # Fetch specific leads by IDs
                response = self.client.table(self.table_name).select("*").in_("id", lead_ids).execute()
            else:
                # Fetch by status filter
                response = self.client.table(self.table_name).select("*").eq("Status", status_filter).execute()

            return response.data if response.data else []

        except Exception as e:
            print(f"❌ Error fetching from Supabase: {str(e)}")
            return []

    def update_record(self, lead_id: str, updates: Dict) -> Dict:
        """
        Update a lead record in Supabase

        Args:
            lead_id: Lead ID to update
            updates: Dictionary of fields to update

        Returns:
            Updated lead record
        """
        try:
            response = self.client.table(self.table_name).update(updates).eq("id", lead_id).execute()

            if response.data:
                print(f"[OK] Updated lead {lead_id} in Supabase")
                return response.data[0] if response.data else {}
            else:
                print(f"[WARNING] Lead {lead_id} not found in Supabase")
                return {}

        except Exception as e:
            print(f"❌ Error updating Supabase record: {str(e)}")
            return {}

    def insert_lead(self, lead_data: Dict) -> Dict:
        """
        Insert a new lead into Supabase

        Args:
            lead_data: Lead data dictionary

        Returns:
            Inserted lead record
        """
        try:
            response = self.client.table(self.table_name).insert(lead_data).execute()

            if response.data:
                print(f"[OK] Inserted new lead into Supabase")
                return response.data[0] if response.data else {}
            else:
                print(f"[WARNING] Failed to insert lead")
                return {}

        except Exception as e:
            print(f"❌ Error inserting lead: {str(e)}")
            return {}

    def bulk_insert_leads(self, leads_data: List[Dict]) -> List[Dict]:
        """
        Bulk insert multiple leads into Supabase

        Args:
            leads_data: List of lead data dictionaries

        Returns:
            List of inserted lead records
        """
        try:
            response = self.client.table(self.table_name).insert(leads_data).execute()

            if response.data:
                print(f"[OK] Inserted {len(response.data)} leads into Supabase")
                return response.data
            else:
                print(f"[WARNING] Failed to insert leads")
                return []

        except Exception as e:
            print(f"❌ Error bulk inserting leads: {str(e)}")
            return []

    def sync_from_apollo(self, apollo_loader):
        """
        Sync leads from Apollo to Supabase

        Args:
            apollo_loader: ApolloLeadLoader instance with loaded data

        Returns:
            Number of synced leads
        """
        try:
            # Get all leads from Apollo
            apollo_leads = apollo_loader.fetch_records(status_filter="NEW")

            if not apollo_leads:
                print("[WARNING] No leads to sync from Apollo")
                return 0

            # Insert into Supabase (handling duplicates)
            synced_count = 0
            for lead in apollo_leads:
                # Check if lead already exists
                existing = self.client.table(self.table_name).select("id").eq("Email", lead.get("Email")).execute()

                if not existing.data:
                    # Insert new lead
                    self.insert_lead(lead)
                    synced_count += 1
                else:
                    # Update existing lead
                    existing_id = existing.data[0]["id"]
                    self.update_record(existing_id, lead)
                    synced_count += 1

            print(f"[OK] Synced {synced_count} leads from Apollo to Supabase")
            return synced_count

        except Exception as e:
            print(f"❌ Error syncing from Apollo: {str(e)}")
            return 0
