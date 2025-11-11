from src.utils import invoke_llm, GEMINI_FLASH_MODEL
from .base.search_tools import google_search

EXTRACT_COMPANY_FROM_SEARCH = """
### Role
You are an Expert Company profile generator specializing in extracting company information from Google search results.

### Objective
Extract and create a 300-word company profile from Google search result snippets, summarizing operations, value proposition, target audience, products/services, location, company size, year founded, and other relevant information.

### Context
This profile provides context for engaging with a prospect who works at the company. Search results may include company websites, news articles, directories, and social media profiles.

### Instructions
- Extract the following information if available:
  * Company name and description
  * Value proposition and mission
  * Target audience and market
  * Products/services offered
  * Location and headquarters
  * Company size (number of employees)
  * Year founded
  * Industry and sector
  * Recent news or achievements
- Use only information explicitly stated in the search results
- Do not make assumptions or invent information
- If specific information is not available, state "Not available"
- Keep the tone neutral and factual; avoid hype or subjective language
- Limit the profile to 300 words
- Format as a coherent company overview
"""

CREATE_COMPANY_PROFILE = """
### Role
You are an Expert Company profile generator with a particular expertise for generating a company profile from their scraped LinkedIn & website pages.

### Objective
Your goal is to look through the scraped LinkedIn company profile & website and create a 300-word company profile summarizing its operations, value proposition, target audience, products/services, location, company size, year founded and any other relevant information that might be useful to use when meeting the inbound lead that works for this company .

### Context
This profile provides context for engaging with a prospect who works at the company.

### Instructions
- If no data is available from LinkedIn *and* the website, output only: *"No company info available."*
- Use the available data from one or both sources; do not assume or invent information.
- Always include:
  - Company description
  - Value proposition
  - Target audience
  - Products/services
  - Location, size, and year founded
- Keep the tone neutral and factual; avoid hype or subjective language.
- Limit the profile to 300 words.
"""

def research_lead_company(linkedin_url):
    """
    Researches a company using Google search results and AI extraction.
    No LinkedIn scraping required - extracts information from search snippets.

    @param linkedin_url: The company LinkedIn URL or company name to search.
    @return: Structured company information dictionary.
    """
    print(f"\n{'='*80}")
    print(f"[COMPANY RESEARCH] Starting company research")
    print(f"{'='*80}")

    # Extract company identifier from LinkedIn URL
    company_identifier = linkedin_url
    if 'linkedin.com/company/' in linkedin_url:
        # Extract company name from LinkedIn URL
        company_identifier = linkedin_url.split('/company/')[-1].split('/')[0].replace('-', ' ')
        print(f"[COMPANY RESEARCH] Extracted company name from LinkedIn URL: {company_identifier}")
    else:
        print(f"[COMPANY RESEARCH] Using provided identifier: {company_identifier}")

    print(f"[COMPANY RESEARCH] LinkedIn URL: {linkedin_url}")

    # Search Google for the company with multiple queries
    queries = [
        f"{company_identifier} company",
        f"{company_identifier} about",
        f'"{company_identifier}" company profile'
    ]

    print(f"[COMPANY RESEARCH] Executing {len(queries)} search queries...")
    all_search_results = []
    for idx, query in enumerate(queries, 1):
        try:
            print(f"[COMPANY RESEARCH] Query {idx}/{len(queries)}: '{query}'")
            results = google_search(query)
            if results:
                print(f"[COMPANY RESEARCH] Found {len(results)} results for query {idx}")
                all_search_results.extend(results[:5])  # Get top 5 from each query
            else:
                print(f"[COMPANY RESEARCH] No results for query {idx}")
        except Exception as e:
            print(f"[WARNING] Search query failed for '{query}': {e}")
            continue

    print(f"[COMPANY RESEARCH] Total search results collected: {len(all_search_results)}")

    if not all_search_results:
        print(f"[COMPANY RESEARCH] QUALITY WARNING: No search results found for company: {company_identifier}")
        print(f"[COMPANY RESEARCH] Returning minimal company data")
        return {
            "company_name": company_identifier,
            "description": "No information available from search results",
            "year_founded": "Not available",
            "industries": [],
            "specialties": "Not available",
            "employee_count": "Not available",
            "social_metrics": {"follower_count": 0},
            "locations": []
        }

    # Format search results for AI extraction
    formatted_results = []
    for idx, result in enumerate(all_search_results, 1):
        title = result.get('title', 'No title')
        snippet = result.get('snippet', 'No snippet')
        link = result.get('link', 'No link')
        formatted_results.append(f"Result {idx}:\nTitle: {title}\nSnippet: {snippet}\nURL: {link}\n")

    search_data = "\n".join(formatted_results)

    # Use AI to extract structured information
    extraction_input = (
        f"# Company Identifier: {company_identifier}\n"
        f"# Company LinkedIn URL: {linkedin_url}\n\n"
        f"# Google Search Results:\n{search_data}"
    )

    print(f"[COMPANY RESEARCH] Invoking LLM for company profile extraction from {len(all_search_results)} results...")

    company_description = invoke_llm(
        system_prompt=EXTRACT_COMPANY_FROM_SEARCH,
        user_message=extraction_input
    )

    # Quality analysis
    print(f"\n[COMPANY RESEARCH] ===== QUALITY ANALYSIS =====")
    print(f"[COMPANY RESEARCH] Company Description Length: {len(company_description)} characters")
    print(f"[COMPANY RESEARCH] Company Description Preview (first 300 chars):")
    print(f"{company_description[:300]}...")

    # Check for quality indicators
    quality_indicators = {
        'has_company_name': company_identifier.lower() in company_description.lower(),
        'has_value_proposition': any(word in company_description.lower() for word in ['provides', 'offers', 'delivers', 'specializes', 'focuses on']),
        'has_industry': any(word in company_description.lower() for word in ['industry:', 'sector:', 'market:', 'technology', 'software', 'services']),
        'has_products_services': any(word in company_description.lower() for word in ['products:', 'services:', 'solutions:', 'platform']),
        'has_location': any(word in company_description.lower() for word in ['location:', 'headquarters:', 'based in', 'located in']),
        'has_size_info': any(word in company_description.lower() for word in ['employees', 'company size:', 'team', 'staff']),
        'has_founding_info': any(word in company_description.lower() for word in ['founded', 'established', 'year:', 'since']),
        'is_substantial': len(company_description) > 200,
        'no_error_message': 'not available' not in company_description.lower() and 'no information' not in company_description.lower()
    }

    quality_score = sum(quality_indicators.values())
    total_checks = len(quality_indicators)

    print(f"[COMPANY RESEARCH] Quality Indicators ({quality_score}/{total_checks} passed):")
    for indicator, passed in quality_indicators.items():
        status = "PASS" if passed else "FAIL"
        print(f"[COMPANY RESEARCH]   - {indicator}: {status}")

    if quality_score < 4:
        print(f"[COMPANY RESEARCH] WARNING: Low quality company profile (score: {quality_score}/{total_checks})")
    elif quality_score < 6:
        print(f"[COMPANY RESEARCH] NOTICE: Moderate quality company profile (score: {quality_score}/{total_checks})")
    else:
        print(f"[COMPANY RESEARCH] SUCCESS: High quality company profile (score: {quality_score}/{total_checks})")

    print(f"[COMPANY RESEARCH] ===== EXTRACTION COMPLETE =====")
    print(f"{'='*80}\n")

    # Return structured company information
    # Note: Since we're extracting from text, we'll return a simplified structure
    return {
        "company_name": company_identifier,
        "description": company_description,
        "year_founded": "See description",
        "industries": [],
        "specialties": "See description",
        "employee_count": "See description",
        "social_metrics": {"follower_count": 0},
        "locations": []
    }

def generate_company_profile(company_linkedin_info, scraped_website):
    # Get company profile summary
    inputs = (
        f"# Scraped Website:\n {scraped_website}\n\n"
        f"# Company LinkedIn Information:\n{company_linkedin_info}"
    )
    profile_summary = invoke_llm(
        system_prompt=CREATE_COMPANY_PROFILE, 
        user_message=inputs
    )
    return profile_summary