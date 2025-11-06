import os
import requests
from src.utils import invoke_llm, GEMINI_FLASH_MODEL
from linkedin_api import Linkedin

def extract_linkedin_url_base(search_results):
    """
    Extracts the LinkedIn URL from the search results.
    """
    for result in search_results:
        if 'linkedin.com/in' in result['link']:
            return result['link']
    return ""


def extract_linkedin_url(search_results):
    EXTRACT_LINKEDIN_URL_PROMPT = """
    **Role:**  
    You are an expert in extracting LinkedIn URLs from Google search results, specializing in finding the correct personal LinkedIn URL.

    **Objective:**  
    From the provided search results, find the LinkedIn URL of a specific person working at a specific company.

    **Instructions:**  
    1. Output **only** the correct LinkedIn URL if found, nothing else.  
    2. If no valid URL exists, output **only** an empty string.  
    3. Only consider URLs with `"/in"`. Ignore those with `"/posts"` or `"/company"`.  
    """
    
    result = invoke_llm(
        system_prompt=EXTRACT_LINKEDIN_URL_PROMPT, 
        user_message=str(search_results),
        model=GEMINI_FLASH_MODEL
    )
    return result
    
    
def scrape_linkedin_with_api(linkedin_url, is_company=False):
    """
    Scrapes LinkedIn profile data using the linkedin-api package.

    @param linkedin_url: The LinkedIn URL to scrape.
    @param is_company: Boolean indicating whether to scrape a company profile or a person profile.
    @return: The scraped LinkedIn profile data in a standardized format.
    """
    try:
        # Initialize LinkedIn API client
        email = os.getenv("LINKEDIN_EMAIL")
        password = os.getenv("LINKEDIN_PASSWORD")

        if not email or not password:
            print("LinkedIn credentials not found in environment variables")
            return None

        api = Linkedin(email, password)

        # Extract profile ID from URL
        # URL format: https://www.linkedin.com/in/profile-id/ or https://www.linkedin.com/company/company-id/
        profile_id = linkedin_url.rstrip('/').split('/')[-1]

        if is_company:
            # Get company profile
            company_data = api.get_company(profile_id)
            # Transform to match the expected format
            return {
                "data": {
                    "full_name": company_data.get("name", ""),
                    "about": company_data.get("description", ""),
                    "company": company_data.get("name", ""),
                    "company_industry": company_data.get("industryName", ""),
                    "location": company_data.get("headquarter", {}).get("city", ""),
                    "city": company_data.get("headquarter", {}).get("city", ""),
                    "country": company_data.get("headquarter", {}).get("country", ""),
                    "company_website": company_data.get("companyPageUrl", ""),
                    "company_linkedin_url": linkedin_url
                }
            }
        else:
            # Get person profile
            profile_data = api.get_profile(profile_id)

            # Debug: Print available keys to understand structure
            print(f"[DEBUG] LinkedIn profile keys: {list(profile_data.keys())[:20]}")

            # Transform to match the expected format
            return {
                "data": {
                    "full_name": f"{profile_data.get('firstName', '')} {profile_data.get('lastName', '')}".strip(),
                    "about": profile_data.get("summary", ""),
                    "location": profile_data.get("locationName", ""),
                    "city": profile_data.get("geoLocationName", ""),
                    "country": profile_data.get("geoCountryName", ""),
                    "skills": [skill.get("name", "") for skill in profile_data.get("skills", [])],
                    "company": profile_data.get("experience", [{}])[0].get("companyName", "") if profile_data.get("experience") else "",
                    "company_industry": "",
                    "current_company_join_month": "",
                    "current_company_join_year": "",
                    "company_website": "",
                    "company_linkedin_url": "",
                    "educations": [
                        {
                            "school": edu.get("schoolName", ""),
                            "field_of_study": edu.get("fieldOfStudy", ""),
                            "degree": edu.get("degreeName", ""),
                            "date_range": f"{edu.get('timePeriod', {}).get('startDate', {}).get('year', '')} - {edu.get('timePeriod', {}).get('endDate', {}).get('year', '')}",
                            "activities_and_societies": edu.get("activities", "")
                        } for edu in profile_data.get("education", [])
                    ],
                    "experiences": [
                        {
                            "company": exp.get("companyName", ""),
                            "title": exp.get("title", ""),
                            "date_range": f"{exp.get('timePeriod', {}).get('startDate', {}).get('year', '')} - {exp.get('timePeriod', {}).get('endDate', {}).get('year', 'Present')}",
                            "is_current": not exp.get("timePeriod", {}).get("endDate"),
                            "location": exp.get("locationName", ""),
                            "description": exp.get("description", "")
                        } for exp in profile_data.get("experience", [])
                    ],
                    "certifications": [
                        {
                            "name": cert.get("name", ""),
                            "issuer": cert.get("authority", ""),
                            "date": cert.get("timePeriod", {}).get("startDate", {}).get("year", "")
                        } for cert in profile_data.get("certifications", [])
                    ],
                    "organizations": [],
                    "volunteers": [
                        {
                            "organization": vol.get("companyName", ""),
                            "role": vol.get("role", ""),
                            "date_range": f"{vol.get('timePeriod', {}).get('startDate', {}).get('year', '')} - {vol.get('timePeriod', {}).get('endDate', {}).get('year', '')}",
                            "description": vol.get("description", "")
                        } for vol in profile_data.get("volunteer", [])
                    ],
                    "honors_and_awards": [
                        {
                            "name": award.get("title", ""),
                            "issuer": award.get("issuer", ""),
                            "date": award.get("issueDate", {}).get("year", ""),
                            "description": award.get("description", "")
                        } for award in profile_data.get("honors", [])
                    ]
                }
            }
    except KeyError as e:
        print(f"[ERROR] LinkedIn API returned unexpected data structure. Missing key: {str(e)}")
        print(f"[ERROR] This usually means the profile data format changed or authentication failed")
        return None
    except Exception as e:
        print(f"[ERROR] Error scraping LinkedIn with linkedin-api: {type(e).__name__}: {str(e)}")
        import traceback
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        return None


def scrape_linkedin(linkedin_url, is_company=False, use_rapidapi=False):
    """
    Scrapes LinkedIn profile data based on the provided LinkedIn URL.

    @param linkedin_url: The LinkedIn URL to scrape.
    @param is_company: Boolean indicating whether to scrape a company profile or a person profile.
    @param use_rapidapi: Boolean to choose between RapidAPI or linkedin-api package. Default is False (uses linkedin-api).
    @return: The scraped LinkedIn profile data.
    """
    # Check if we should use RapidAPI or linkedin-api
    if use_rapidapi and os.getenv("RAPIDAPI_KEY") and os.getenv("RAPIDAPI_KEY") != "rapid-api-key":
        # Use RapidAPI method
        if is_company:
            url = "https://fresh-linkedin-profile-data.p.rapidapi.com/get-company-by-linkedinurl"
        else:
            url = "https://fresh-linkedin-profile-data.p.rapidapi.com/get-linkedin-profile"

        querystring = {"linkedin_url": linkedin_url}
        headers = {
          "x-rapidapi-key": os.getenv("RAPIDAPI_KEY"),
          "x-rapidapi-host": "fresh-linkedin-profile-data.p.rapidapi.com"
        }

        response = requests.get(url, headers=headers, params=querystring)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f"RapidAPI request failed with status code: {response.status_code}")
            print("Falling back to linkedin-api package...")
            return scrape_linkedin_with_api(linkedin_url, is_company)
    else:
        # Use linkedin-api package (default)
        return scrape_linkedin_with_api(linkedin_url, is_company)