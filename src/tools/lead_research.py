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
    print(f"\n{'='*80}")
    print(f"[LEAD RESEARCH] Starting research for: {lead_name} ({lead_email})")
    print(f"{'='*80}")

    # Extract company name from email domain
    company_name = extract_company_name(lead_email)
    print(f"[LEAD RESEARCH] Extracted company from email: {company_name}")

    # Search Google for the person with multiple targeted queries for better coverage
    queries = [
        f"{lead_name} {company_name} LinkedIn",  # Primary LinkedIn search
        f'"{lead_name}" {company_name} title role',  # Job title focused
        f"{lead_name} {company_name} location",  # Location focused
        f'"{lead_name}" professional profile',  # General profile
        f"{lead_name} {company_name} experience background"  # Experience focused
    ]

    print(f"[LEAD RESEARCH] Executing {len(queries)} search queries...")
    all_search_results = []
    for idx, query in enumerate(queries, 1):
        try:
            print(f"[LEAD RESEARCH] Query {idx}/{len(queries)}: '{query}'")
            results = google_search(query)
            if results:
                print(f"[LEAD RESEARCH] Found {len(results)} results for query {idx}")
                all_search_results.extend(results[:5])  # Get top 5 from each query
            else:
                print(f"[LEAD RESEARCH] No results for query {idx}")
        except Exception as e:
            print(f"[WARNING] Search query failed for '{query}': {e}")
            continue

    print(f"[LEAD RESEARCH] Total search results collected: {len(all_search_results)}")

    if not all_search_results:
        print(f"[LEAD RESEARCH] QUALITY WARNING: No search results found for {lead_name}")
        print(f"[LEAD RESEARCH] Returning minimal profile data")
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

    print(f"[LEAD RESEARCH] Invoking LLM for profile extraction from {len(all_search_results)} results...")

    profile_summary = invoke_llm(
        system_prompt=EXTRACT_LEAD_FROM_SEARCH,
        user_message=extraction_input
    )

    # Quality analysis
    print(f"\n[LEAD RESEARCH] ===== QUALITY ANALYSIS =====")
    print(f"[LEAD RESEARCH] Profile Summary Length: {len(profile_summary)} characters")
    print(f"[LEAD RESEARCH] Profile Summary Preview (first 300 chars):")
    print(f"{profile_summary[:300]}...")

    # Check for quality indicators
    quality_indicators = {
        'has_job_title': any(word in profile_summary.lower() for word in ['title:', 'role:', 'position:', 'ceo', 'director', 'manager', 'engineer']),
        'has_company': company_name.lower() in profile_summary.lower() if company_name != "Company not found" else False,
        'has_location': any(word in profile_summary.lower() for word in ['location:', 'city:', 'country:', 'based in']),
        'has_experience': any(word in profile_summary.lower() for word in ['experience:', 'background:', 'career:', 'worked at']),
        'has_education': any(word in profile_summary.lower() for word in ['education:', 'degree:', 'university', 'college']),
        'is_not_empty': len(profile_summary) > 100,
        'no_error_message': 'not available' not in profile_summary.lower() and 'no information' not in profile_summary.lower()
    }

    quality_score = sum(quality_indicators.values())
    total_checks = len(quality_indicators)

    print(f"[LEAD RESEARCH] Quality Indicators ({quality_score}/{total_checks} passed):")
    for indicator, passed in quality_indicators.items():
        status = "PASS" if passed else "FAIL"
        print(f"[LEAD RESEARCH]   - {indicator}: {status}")

    if quality_score < 3:
        print(f"[LEAD RESEARCH] WARNING: Low quality profile (score: {quality_score}/{total_checks})")
    elif quality_score < 5:
        print(f"[LEAD RESEARCH] NOTICE: Moderate quality profile (score: {quality_score}/{total_checks})")
    else:
        print(f"[LEAD RESEARCH] SUCCESS: High quality profile (score: {quality_score}/{total_checks})")

    # Try to extract company website and LinkedIn URL from search results
    company_website = ""
    company_linkedin_url = ""

    print(f"[LEAD RESEARCH] Extracting company URLs from search results...")
    for result in all_search_results:
        link = result.get('link', '')
        # Look for company LinkedIn page
        if 'linkedin.com/company/' in link and not company_linkedin_url:
            company_linkedin_url = link
            print(f"[LEAD RESEARCH] Found company LinkedIn: {company_linkedin_url}")
        # Look for company website (not LinkedIn, not social media)
        elif company_name.lower().replace('.com', '').replace('.', '') in link.lower():
            if 'linkedin.com' not in link and 'facebook.com' not in link and 'twitter.com' not in link:
                company_website = link
                print(f"[LEAD RESEARCH] Found company website: {company_website}")

    print(f"[LEAD RESEARCH] ===== EXTRACTION COMPLETE =====")
    print(f"[LEAD RESEARCH] Company Name: {company_name}")
    print(f"[LEAD RESEARCH] Company Website: {company_website if company_website else 'NOT FOUND'}")
    print(f"[LEAD RESEARCH] Company LinkedIn: {company_linkedin_url if company_linkedin_url else 'NOT FOUND'}")
    print(f"{'='*80}\n")

    return (
        profile_summary,
        company_name,
        company_website,
        company_linkedin_url
    )