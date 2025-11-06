import os
import csv
import requests
from typing import List, Dict, Optional
from .lead_loader_base import LeadLoaderBase


class ApolloLeadLoader(LeadLoaderBase):
    """
    Lead loader for Apollo.io that supports:
    1. CSV file export from Apollo
    2. Apollo API for direct integration
    """

    def __init__(self, api_key: Optional[str] = None, csv_file_path: Optional[str] = None):
        """
        Initialize Apollo Lead Loader

        Args:
            api_key: Apollo.io API key for API-based loading
            csv_file_path: Path to CSV file exported from Apollo
        """
        self.api_key = api_key
        self.csv_file_path = csv_file_path
        self.base_url = "https://api.apollo.io/v1"

        # In-memory storage for leads when using CSV
        self.leads_data = []

        if csv_file_path:
            self._load_csv()

    def _load_csv(self):
        """Load leads from CSV file exported from Apollo"""
        try:
            with open(self.csv_file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                self.leads_data = []

                for idx, row in enumerate(reader):
                    # Standardize the CSV data to match our lead format
                    lead = {
                        "id": row.get("# Id", str(idx)),  # Apollo CSV uses "# Id"
                        "Name": row.get("Name", row.get("First Name", "") + " " + row.get("Last Name", "")),
                        "Email": row.get("Email", ""),
                        "Title": row.get("Title", ""),
                        "Company": row.get("Company", row.get("Organization", "")),
                        "LinkedIn": row.get("LinkedIn", row.get("Person Linkedin Url", "")),
                        "Company LinkedIn": row.get("Company LinkedIn Url", ""),
                        "Website": row.get("Website", ""),
                        "Industry": row.get("Industry", ""),
                        "Phone": row.get("Phone", ""),
                        "Location": row.get("Location", row.get("City", "") + ", " + row.get("State", "")),
                        "Status": row.get("Status", "NEW"),
                        "raw_data": row  # Store original data
                    }
                    self.leads_data.append(lead)

                print(f"[OK] Loaded {len(self.leads_data)} leads from CSV: {self.csv_file_path}")
        except FileNotFoundError:
            print(f"[ERROR] CSV file not found: {self.csv_file_path}")
            self.leads_data = []
        except Exception as e:
            print(f"[ERROR] Error loading CSV: {str(e)}")
            self.leads_data = []

    def fetch_records(self, lead_ids: Optional[List[str]] = None, status_filter: str = "NEW") -> List[Dict]:
        """
        Fetch leads from Apollo (CSV or API)

        Args:
            lead_ids: Specific lead IDs to fetch
            status_filter: Filter by status (NEW, UNQUALIFIED, ATTEMPTED_TO_CONTACT)

        Returns:
            List of lead records
        """
        if self.csv_file_path:
            return self._fetch_from_csv(lead_ids, status_filter)
        elif self.api_key:
            return self._fetch_from_api(lead_ids, status_filter)
        else:
            print("[ERROR] No data source configured. Provide either csv_file_path or api_key.")
            return []

    def _fetch_from_csv(self, lead_ids: Optional[List[str]] = None, status_filter: str = "NEW") -> List[Dict]:
        """Fetch leads from loaded CSV data"""
        if lead_ids:
            # Fetch specific leads by ID
            return [lead for lead in self.leads_data if lead["id"] in lead_ids]
        else:
            # Fetch by status filter
            return [lead for lead in self.leads_data if lead.get("Status") == status_filter]

    def _fetch_from_api(self, lead_ids: Optional[List[str]] = None, status_filter: str = "NEW") -> List[Dict]:
        """
        Fetch leads from Apollo API
        Reference: https://apolloio.github.io/apollo-api-docs/
        """
        if not self.api_key:
            print("[ERROR] Apollo API key not configured")
            return []

        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self.api_key
        }

        try:
            if lead_ids:
                # Fetch specific people by IDs
                leads = []
                for lead_id in lead_ids:
                    url = f"{self.base_url}/people/{lead_id}"
                    response = requests.get(url, headers=headers)

                    if response.status_code == 200:
                        data = response.json()
                        person = data.get("person", {})
                        leads.append(self._format_apollo_person(person))
                    else:
                        print(f"[WARNING] Failed to fetch lead {lead_id}: {response.status_code}")

                return leads
            else:
                # Search for people with status filter
                url = f"{self.base_url}/people/search"
                payload = {
                    "page": 1,
                    "per_page": 100,
                    # Add custom field filter if you track status in Apollo
                }

                response = requests.post(url, headers=headers, json=payload)

                if response.status_code == 200:
                    data = response.json()
                    people = data.get("people", [])
                    return [self._format_apollo_person(person) for person in people]
                else:
                    print(f"[ERROR] Apollo API error: {response.status_code} - {response.text}")
                    return []

        except Exception as e:
            print(f"[ERROR] Error fetching from Apollo API: {str(e)}")
            return []

    def _format_apollo_person(self, person: Dict) -> Dict:
        """Format Apollo API person data to standard lead format"""
        return {
            "id": person.get("id", ""),
            "Name": f"{person.get('first_name', '')} {person.get('last_name', '')}".strip(),
            "Email": person.get("email", ""),
            "Title": person.get("title", ""),
            "Company": person.get("organization", {}).get("name", "") if person.get("organization") else "",
            "LinkedIn": person.get("linkedin_url", ""),
            "Company LinkedIn": person.get("organization", {}).get("linkedin_url", "") if person.get("organization") else "",
            "Website": person.get("organization", {}).get("website_url", "") if person.get("organization") else "",
            "Industry": person.get("organization", {}).get("industry", "") if person.get("organization") else "",
            "Phone": person.get("phone_numbers", [{}])[0].get("raw_number", "") if person.get("phone_numbers") else "",
            "Location": f"{person.get('city', '')}, {person.get('state', '')}".strip(", "),
            "Status": "NEW",  # Default status
            "raw_data": person
        }

    def update_record(self, lead_id: str, updates: Dict) -> Dict:
        """
        Update a lead record

        Args:
            lead_id: Lead ID to update
            updates: Dictionary of fields to update (typically {"Status": "ATTEMPTED_TO_CONTACT"})

        Returns:
            Updated lead record
        """
        if self.csv_file_path:
            return self._update_csv_record(lead_id, updates)
        elif self.api_key:
            return self._update_api_record(lead_id, updates)
        else:
            print("[ERROR] No data source configured")
            return {}

    def _update_csv_record(self, lead_id: str, updates: Dict) -> Dict:
        """Update lead in CSV data (in-memory)"""
        for lead in self.leads_data:
            if lead["id"] == lead_id:
                lead.update(updates)
                print(f"[OK] Updated lead {lead_id} in memory")
                return lead

        print(f"[WARNING] Lead {lead_id} not found in CSV data")
        return {}

    def _update_api_record(self, lead_id: str, updates: Dict) -> Dict:
        """
        Update lead via Apollo API
        Note: Apollo API has limited update capabilities for free tier
        """
        if not self.api_key:
            print("[ERROR] Apollo API key not configured")
            return {}

        # Apollo API doesn't support direct status updates in free tier
        # You might need to use custom fields or track status externally
        print(f"[INFO] Apollo API update for lead {lead_id}: {updates}")
        print("[WARNING] Note: Status tracking may require Apollo paid plan or external database")

        return {"id": lead_id, **updates}

    def export_updated_csv(self, output_path: Optional[str] = None):
        """
        Export updated leads back to CSV file

        Args:
            output_path: Path to save updated CSV. If None, overwrites original file.
        """
        if not self.csv_file_path:
            print("[ERROR] No CSV file loaded to export")
            return

        output_path = output_path or self.csv_file_path

        try:
            # Get all field names from the first lead
            if not self.leads_data:
                print("[WARNING] No leads data to export")
                return

            fieldnames = list(self.leads_data[0].keys())
            if "raw_data" in fieldnames:
                fieldnames.remove("raw_data")

            with open(output_path, 'w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()

                for lead in self.leads_data:
                    row = {k: v for k, v in lead.items() if k != "raw_data"}
                    writer.writerow(row)

            print(f"[OK] Exported {len(self.leads_data)} leads to: {output_path}")

        except Exception as e:
            print(f"[ERROR] Error exporting CSV: {str(e)}")
