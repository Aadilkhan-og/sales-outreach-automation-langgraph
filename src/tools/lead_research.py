from src.utils import invoke_llm, GEMINI_FLASH_MODEL
from .base.search_tools import google_search


EXTRACT_LEAD_FROM_SEARCH = """
# Role
You are an Expert Lead profile creator specializing in extracting professional information from Google search results.

# Objective
Extract and generate a 300-word professional profile from Google search result snippets, focusing on job title, company, expertise, and current focus.

# Context
The lead profile helps sales teams understand prospects for meetings or calls. Search results may include LinkedIn profiles, company websites, press releases, and professional directories.

# Instructions
- Extract the following information if available:
  * Current job title and role
  * Current company name
  * Location (city/country if mentioned)
  * Professional expertise and skills
  * Career background and experience
  * Education (if mentioned)
  * Notable achievements or projects
- Use only information explicitly stated in the search results
- Do not make assumptions or embellish
- If information is unclear or missing, state "Not available"
- Keep the profile neutral and factual; avoid words like "impressive" or "seasoned"
- Limit the profile to 300 words
- Format as a coherent professional summary
"""

def extract_company_name(email):
    """
    Extracts the company name from a professional email address.
    """
    try:
        # Split the email to get the domain part
        company_name = email.split('@')[1]
        return company_name
    except IndexError:
        return "Company not found"

def research_lead_on_linkedin(lead_name, lead_email):
    """
    Researches the lead using Google search results and AI extraction.
    No LinkedIn scraping required - extracts information from search snippets.

    @param lead_name: The name of the lead to search for.
    @param lead_email: The lead's email address.
    @return: Tuple of (profile_summary, company_name, company_website, company_linkedin_url)
    """
    # Extract company name from email domain
    company_name = extract_company_name(lead_email)

    # Search Google for the person with multiple queries for better coverage
    queries = [
        f"{lead_name} {company_name}",
        f"{lead_name} LinkedIn",
        f'"{lead_name}" professional profile'
    ]

    all_search_results = []
    for query in queries:
        try:
            results = google_search(query)
            if results:
                all_search_results.extend(results[:5])  # Get top 5 from each query
        except Exception as e:
            print(f"[WARNING] Search query failed for '{query}': {e}")
            continue

    if not all_search_results:
        print(f"[INFO] No search results found for {lead_name}")
        return (
            f"Lead: {lead_name} ({lead_email})\nCompany: {company_name}\nNo additional information available from search results.",
            company_name,
            "",
            ""
        )

    # Format search results for AI extraction
    formatted_results = []
    for idx, result in enumerate(all_search_results, 1):
        title = result.get('title', 'No title')
        snippet = result.get('snippet', 'No snippet')
        link = result.get('link', 'No link')
        formatted_results.append(f"Result {idx}:\nTitle: {title}\nSnippet: {snippet}\nURL: {link}\n")

    search_data = "\n".join(formatted_results)

    # Use AI to extract structured information from search results
    extraction_input = (
        f"# Lead Name: {lead_name}\n"
        f"# Lead Email: {lead_email}\n"
        f"# Company (from email domain): {company_name}\n\n"
        f"# Google Search Results:\n{search_data}"
    )

    print(f"[INFO] Extracting lead profile from {len(all_search_results)} search results")

    profile_summary = invoke_llm(
        system_prompt=EXTRACT_LEAD_FROM_SEARCH,
        user_message=extraction_input,
        model=GEMINI_FLASH_MODEL
    )
    print("profile_summary",profile_summary)
    # Try to extract company website and LinkedIn URL from search results
    company_website = ""
    company_linkedin_url = ""

    for result in all_search_results:
        link = result.get('link', '')
        # Look for company LinkedIn page
        if 'linkedin.com/company/' in link and not company_linkedin_url:
            company_linkedin_url = link
        # Look for company website (not LinkedIn, not social media)
        elif company_name.lower().replace('.com', '').replace('.', '') in link.lower():
            if 'linkedin.com' not in link and 'facebook.com' not in link and 'twitter.com' not in link:
                company_website = link

    return (
        profile_summary,
        company_name,
        company_website,
        company_linkedin_url
    )