from colorama import Fore, Style
from .tools.base.markdown_scraper_tool import scrape_website_to_markdown
from .tools.base.search_tools import get_recent_news
from .tools.base.gmail_tools import GmailTools
from .tools.google_docs_tools import GoogleDocsManager
from .tools.lead_research import research_lead_on_linkedin
from .tools.company_research import research_lead_company, generate_company_profile
from .tools.youtube_tools import get_youtube_stats
from .tools.rag_tool import fetch_similar_case_study
from .prompts import *
from .state import LeadData, CompanyData, Report, GraphInputState, GraphState
from .structured_outputs import WebsiteData, EmailResponse
from .utils import invoke_llm, get_report, get_current_date, save_reports_locally, GEMINI_FLASH_MODEL, GEMINI_PRO_MODEL

# Enable or disable sending emails directly using GMAIL
# Should be confident about the quality of the email
SEND_EMAIL_DIRECTLY = False
# Enable or disable saving emails to Google Docs
# By defauly all reports are save locally in `reports` folder
SAVE_TO_GOOGLE_DOCS = False

class OutReachAutomationNodes:
    def __init__(self, loader):
        self.lead_loader = loader

        # Only initialize Google Docs Manager if feature is enabled
        # This allows the app to run without Google OAuth credentials
        if SAVE_TO_GOOGLE_DOCS:
            print("[INFO] Initializing Google Docs Manager (SAVE_TO_GOOGLE_DOCS enabled)...")
            self.docs_manager = GoogleDocsManager()
        else:
            print("[INFO] Google Docs Manager disabled (SAVE_TO_GOOGLE_DOCS=False)")
            self.docs_manager = None

        self.drive_folder_name = ""

    def get_new_leads(self, state: GraphInputState):
        print(Fore.YELLOW + "----- Fetching new leads -----\n" + Style.RESET_ALL)
        
        # Fetch new leads using the provided loader
        raw_leads = self.lead_loader.fetch_records()
        
        # Structure the leads
        leads = [
            LeadData(
                id=lead["id"],
                name=f'{lead.get("First Name", "")} {lead.get("Last Name", "")}',
                email=lead.get("Email", ""),
                phone=lead.get("Phone", ""),
                address=lead.get("Address", ""),
                profile="" # will be constructed
            )
            for lead in raw_leads
        ]
        
        print(Fore.YELLOW + f"----- Fetched {len(leads)} leads -----\n" + Style.RESET_ALL)
        return {"leads_data": leads, "number_leads": len(leads)}
    
    @staticmethod
    def check_for_remaining_leads(state: GraphState):
        """Checks for remaining leads and updates lead_data in the state."""
        print(Fore.YELLOW + "----- Checking for remaining leads -----\n" + Style.RESET_ALL)
        
        current_lead = None
        if state["leads_data"]:
            current_lead = state["leads_data"].pop()
        return {"current_lead": current_lead}

    @staticmethod
    def check_if_there_more_leads(state: GraphState):
        # Number of leads remaining
        num_leads = state["number_leads"]
        if num_leads > 0:
            print(Fore.YELLOW + f"----- Found {num_leads} more leads -----\n" + Style.RESET_ALL)
            return "Found leads"
        else:
            print(Fore.GREEN + "----- Finished, No more leads -----\n" + Style.RESET_ALL)
            return "No more leads"

    def fetch_linkedin_profile_data(self, state: GraphState):
        print(Fore.YELLOW + "----- Searching Lead data on LinkedIn -----\n" + Style.RESET_ALL)
        lead_data = state["current_lead"]
        company_data = state.get("company_data", CompanyData())
        # Scrape lead linkedin profile
        (
            lead_profile, 
            company_name, 
            company_website,
            company_linkedin_url
        ) = research_lead_on_linkedin(lead_data.name, lead_data.email)
        lead_data.profile = lead_profile

        # Research company on linkedin
        company_profile = research_lead_company(company_linkedin_url)
        
        # Update company name from LinkedIn data
        company_data.name = company_name
        company_data.website = company_website
        company_data.profile = str(company_profile)
            
        # Update folder name for saving reports in Drive
        self.drive_folder_name = f"{lead_data.name}_{company_data.name}"
        
        return {
            "current_lead": lead_data,
            "company_data": company_data,
            "reports": []
        }
    
    def review_company_website(self, state: GraphState):
        print(Fore.YELLOW + "----- Scraping company website -----\n" + Style.RESET_ALL)
        lead_data = state.get("current_lead")
        company_data = state.get("company_data")
        
        company_website = company_data.website
        if company_website:
            # Scrape company website
            content = scrape_website_to_markdown(company_website)
            website_info = invoke_llm(
                system_prompt=WEBSITE_ANALYSIS_PROMPT.format(main_url=company_website),
                user_message=content,
                response_format=WebsiteData
            )

            # Extract all relevant links
            company_data.social_media_links.blog = website_info.blog_url
            company_data.social_media_links.facebook = website_info.facebook
            company_data.social_media_links.twitter = website_info.twitter
            company_data.social_media_links.youtube = website_info.youtube
            
            # Update company profile with website summary
            company_data.profile = generate_company_profile(company_data.profile, website_info.summary)
                 
        inputs = f"""
        # **Lead Profile:**

        {lead_data.profile}

        # **Company Information:**

        {company_data.profile}
        """
        
        # Generate general lead search report
        print(f"\n[REPORT GENERATION] Generating General Lead Research Report...")
        general_lead_search_report = invoke_llm(
            system_prompt=LEAD_SEARCH_REPORT_PROMPT,
            user_message=inputs
        )

        # Quality check for report
        print(f"[REPORT GENERATION] Report Length: {len(general_lead_search_report)} characters")
        print(f"[REPORT GENERATION] Report Preview (first 200 chars):")
        print(f"{general_lead_search_report[:200]}...")

        lead_search_report = Report(
            title="General Lead Research Report",
            content=general_lead_search_report,
            is_markdown=True
        )

        print(f"[REPORT GENERATION] General Lead Research Report created successfully\n")

        return {
            "company_data": company_data,
            "reports": [lead_search_report]
        }
    
    @staticmethod
    def collect_company_information(state: GraphState):
        return {"reports": []}
    
    def analyze_blog_content(self, state: GraphState):
        print(Fore.YELLOW + "----- Analyzing company main blog -----\n" + Style.RESET_ALL)
        blog_analysis_report = ""

        # Check if company has a blog
        company_data = state["company_data"]
        blog_url = company_data.social_media_links.blog
        if blog_url:
            try:
                print(f"[BLOG SCRAPING] Attempting to scrape: {blog_url}")
                blog_content = scrape_website_to_markdown(blog_url)
                print(f"[BLOG SCRAPING] Successfully scraped {len(blog_content)} characters")
                prompt = BLOG_ANALYSIS_PROMPT.format(company_name=company_data.name)
                blog_analysis_report = invoke_llm(
                    system_prompt=prompt,
                    user_message=blog_content
                )
                blog_analysis_report = Report(
                    title="Blog Analysis Report",
                    content=blog_analysis_report,
                    is_markdown=True
                )
                print(f"[BLOG SCRAPING] Blog analysis report generated successfully")
            except Exception as e:
                print(f"[BLOG SCRAPING] WARNING: Failed to scrape blog - {str(e)}")
                print(f"[BLOG SCRAPING] Continuing with empty blog report")
                blog_analysis_report = Report(
                    title="Blog Analysis Report",
                    content="No blog content available (scraping failed)",
                    is_markdown=True
                )
        else:
            print(f"[BLOG SCRAPING] No blog URL found, skipping")
        return {"reports": [blog_analysis_report]}
    
    def analyze_social_media_content(self, state: GraphState):
        print(Fore.YELLOW + "----- Analyzing company social media accounts -----\n" + Style.RESET_ALL)
        
        # Load states
        company_data = state["company_data"]
        
        # Get social media urls
        facebook_url = company_data.social_media_links.facebook
        twitter_url = company_data.social_media_links.twitter
        youtube_url = company_data.social_media_links.youtube

        # Initialize reports list (will contain reports for available social media channels)
        reports = []

        # Check If company has Youtube channel
        if youtube_url:
            youtube_data = get_youtube_stats(youtube_url)
            prompt = YOUTUBE_ANALYSIS_PROMPT.format(company_name=company_data.name)
            youtube_insight = invoke_llm(
                system_prompt=prompt,
                user_message=youtube_data
            )
            youtube_analysis_report = Report(
                title="Youtube Analysis Report",
                content=youtube_insight,
                is_markdown=True
            )
            reports.append(youtube_analysis_report)

        # Check If company has Facebook account
        if facebook_url:
            # TODO Add Facebook analysis part
            pass

        # Check If company has Twitter account
        if twitter_url:
            # TODO Add Twitter analysis part
            pass

        return {
            "company_data": company_data,
            "reports": reports
        }
    
    def analyze_recent_news(self, state: GraphState):
        print(Fore.YELLOW + "----- Analyzing recent news about company -----\n" + Style.RESET_ALL)
        
        # Load states
        company_data = state["company_data"]
        
        # Fetch recent news using serper API
        recent_news = get_recent_news(company=company_data.name)
        number_months = 6
        current_date = get_current_date()
        news_analysis_prompt = NEWS_ANALYSIS_PROMPT.format(
            company_name=company_data.name, 
            number_months=number_months, 
            date=current_date
        )
        
        # Craft news analysis prompt
        if not recent_news.strip():
            news_insight = "No recent news found for this company."
        else:
            news_insight = invoke_llm(
                system_prompt=news_analysis_prompt,
                user_message=recent_news
            )
        
        news_analysis_report = Report(
            title="News Analysis Report",
            content=news_insight,
            is_markdown=True
        )
        return {"reports": [news_analysis_report]}
    
    def generate_digital_presence_report(self, state: GraphState):
        print(Fore.YELLOW + "----- Generate Digital presence analysis report -----\n" + Style.RESET_ALL)
        
        # Load reports
        reports = state["reports"]
        blog_analysis_report = get_report(reports, "Blog Analysis Report")
        facebook_analysis_report = get_report(reports, "Facebook Analysis Report")
        twitter_analysis_report = get_report(reports, "Twitter Analysis Report")
        youtube_analysis_report = get_report(reports, "Youtube Analysis Report")
        news_analysis_report = get_report(reports, "News Analysis Report")
        
        inputs = f"""
        # **Digital Presence Data:**
        ## **Blog Information:**

        {blog_analysis_report}
        
        ## **Facebook Information:**

        {facebook_analysis_report}
        
        ## **Twitter Information:**

        {twitter_analysis_report}

        ## **Youtube Information:**

        {youtube_analysis_report}

        # **Recent News:**

        {news_analysis_report}
        """
        
        prompt = DIGITAL_PRESENCE_REPORT_PROMPT.format(
            company_name=state["company_data"].name, date=get_current_date()
        )

        print(f"\n[REPORT GENERATION] Generating Digital Presence Report...")
        digital_presence_report = invoke_llm(
            system_prompt=prompt,
            user_message=inputs
        )

        # Quality check
        print(f"[REPORT GENERATION] Report Length: {len(digital_presence_report)} characters")
        print(f"[REPORT GENERATION] Report Preview (first 200 chars):")
        print(f"{digital_presence_report[:200]}...")

        digital_presence_report = Report(
            title="Digital Presence Report",
            content=digital_presence_report,
            is_markdown=True
        )

        print(f"[REPORT GENERATION] Digital Presence Report created successfully\n")
        return {"reports": [digital_presence_report]}
    
    def generate_full_lead_research_report(self, state: GraphState):
        print(Fore.YELLOW + "----- Generate global lead analysis report -----\n" + Style.RESET_ALL)
        
        # Load reports
        reports = state["reports"]
        general_lead_search_report = get_report(reports, "General Lead Research Report")
        digital_presence_report = get_report(reports, "Digital Presence Report")
        
        inputs = f"""
        # **Lead & company Information:**

        {general_lead_search_report}
        
        ---

        # **Digital Presence Information:**

        {digital_presence_report}
        """
        
        prompt = GLOBAL_LEAD_RESEARCH_REPORT_PROMPT.format(
            company_name=state["company_data"].name, date=get_current_date()
        )

        print(f"\n[REPORT GENERATION] Generating Global Lead Analysis Report...")
        full_report = invoke_llm(
            system_prompt=prompt,
            user_message=inputs
        )

        # Quality check
        print(f"[REPORT GENERATION] Report Length: {len(full_report)} characters")
        print(f"[REPORT GENERATION] Report Preview (first 200 chars):")
        print(f"{full_report[:200]}...")

        global_research_report = Report(
            title="Global Lead Analysis Report",
            content=full_report,
            is_markdown=True
        )

        print(f"[REPORT GENERATION] Global Lead Analysis Report created successfully\n")
        return {"reports": [global_research_report]}
    
    @staticmethod
    def score_lead(state: GraphState):
        """
        Score the lead based on the company profile and open positions.

        @param state: The current state of the application.
        @return: Updated state with the lead score.
        """
        print(Fore.YELLOW + "----- Scoring lead -----\n" + Style.RESET_ALL)
        
        # Load reports
        reports = state["reports"]
        global_research_report = get_report(reports, "Global Lead Analysis Report")
        print("global_research_report",global_research_report,"reports",reports)
        # Scoring lead
        lead_score = invoke_llm(
            system_prompt=SCORE_LEAD_PROMPT,
            user_message=global_research_report
        )
        return {"lead_score": lead_score.strip()}

    @staticmethod
    def is_lead_qualified(state: GraphState):
        """
        Check if the lead is qualified based on the lead score.

        @param state: The current state of the application.
        @return: Updated state with the qualification status.
        """
        print(Fore.YELLOW + "----- Checking if lead is qualified -----\n" + Style.RESET_ALL)
        return {"reports": []}

    @staticmethod
    def check_if_qualified(state: GraphState):
        """
        Check if the lead is qualified based on the lead score.

        @param state: The current state of the application.
        @return: Updated state with the qualification status.
        """
        # Checking if the lead score is 7 or higher
        print(f"Score: {state['lead_score']}")

        # Extract numeric score from formatted string if needed
        import re
        score_str = str(state["lead_score"])
        # Try to extract a number from the string (handles formats like "**Final Score: 3.5**")
        match = re.search(r'(\d+\.?\d*)', score_str)
        if match:
            score = float(match.group(1))
        else:
            score = 0.0

        is_qualified = score >= 7
        if is_qualified:
            print(Fore.GREEN + "Lead is qualified\n" + Style.RESET_ALL)
            return "qualified"
        else:
            print(Fore.RED + "Lead is not qualified\n" + Style.RESET_ALL)
            return "not qualified"
    
    @staticmethod
    def create_outreach_materials(state: GraphState):
        return {"reports": []}
    
    def generate_custom_outreach_report(self, state: GraphState):
        print(Fore.YELLOW + "----- Crafting Custom outreach report based on gathered information -----\n" + Style.RESET_ALL)
        
        # Load reports
        reports = state["reports"]
        general_lead_search_report = get_report(reports, "General Lead Research Report")
        global_research_report = get_report(reports, "Global Lead Analysis Report")
        
        # TODO Create better description to fetch accurate similar case study using RAG
        # get relevant case study
        case_study_report = fetch_similar_case_study(general_lead_search_report)
        
        inputs = f"""
        **Research Report:**

        {global_research_report}

        ---

        **Case Study:**

        {case_study_report}
        """
        
        # Generate report
        custom_outreach_report = invoke_llm(
            system_prompt=GENERATE_OUTREACH_REPORT_PROMPT,
            user_message=inputs
        )
        
        # TODO Find better way to include correct links into the final report
        # Proof read generated report
        inputs = f"""
        {custom_outreach_report}

        ---

        **Correct Links:**

        ** Our website link**: https://elevateAI.com
        ** Case study link**: https://elevateAI.com/case-studies/A
        """
        
        # Call our editor/proof-reader agent
        revised_outreach_report = invoke_llm(
            system_prompt=PROOF_READER_PROMPT,
            user_message=inputs
        )

        # Store report into google docs and get shareable link (if enabled)
        custom_report_link = None
        folder_link = None

        if SAVE_TO_GOOGLE_DOCS and self.docs_manager:
            new_doc = self.docs_manager.add_document(
                content=revised_outreach_report,
                doc_title="Outreach Report",
                folder_name=self.drive_folder_name,
                make_shareable=True,
                folder_shareable=True, # Set to false if only personal or true if with a team
                markdown=True
            )
            if new_doc:
                custom_report_link = new_doc.get("shareable_url")
                folder_link = new_doc.get("folder_url")
        else:
            print("[INFO] Skipping Google Docs upload (feature disabled or not configured)")

        return {
            "custom_outreach_report_link": custom_report_link,
            "reports_folder_link": folder_link
        }

    def generate_personalized_email(self, state: GraphState):
        """
        Generate a personalized email for the lead.

        @param state: The current state of the application.
        @return: Updated state with the generated email.
        """
        print(Fore.YELLOW + "----- Generating personalized email -----\n" + Style.RESET_ALL)
        
        # Load reports
        reports = state["reports"]
        general_lead_search_report = get_report(reports, "General Lead Research Report")
        
        lead_data = f"""
        # **Lead & company Information:**

        {general_lead_search_report}

        # Outreach report Link:

        {state["custom_outreach_report_link"]}
        """
        output = invoke_llm(
            system_prompt=PERSONALIZE_EMAIL_PROMPT,
            user_message=lead_data,
            response_format=EmailResponse
        )
        
        # Get relevant fields
        subject = output.subject
        personalized_email = output.email
        
        # Get lead email
        email = state["current_lead"].email
        
        # Create draft email
        gmail = GmailTools()
        gmail.create_draft_email(
            recipient=email,
            subject=subject,
            email_content=personalized_email
        )
        
        # Send email directly
        if SEND_EMAIL_DIRECTLY:
            gmail.send_email(
                recipient=email,
                subject=subject,
                email_content=personalized_email
            )
        
        # Save email with reports for reference
        personalized_email_doc = Report(
            title="Personalized Email",
            content=personalized_email,
            is_markdown=False
        )
        return {"reports": [personalized_email_doc]}

    def generate_interview_script(self, state: GraphState):
        print(Fore.YELLOW + "----- Generating interview script -----\n" + Style.RESET_ALL)
        
        # Load reports
        reports = state["reports"]
        global_research_report = get_report(reports, "Global Lead Analysis Report")
        
        # Generating SPIN questions
        spin_questions = invoke_llm(
            system_prompt=GENERATE_SPIN_QUESTIONS_PROMPT,
            user_message=global_research_report
        )
        
        inputs = f"""
        # **Lead & company Information:**

        {global_research_report}

        # **SPIN questions:**

        {spin_questions}
        """
        
        # Generating interview script
        interview_script = invoke_llm(
            system_prompt=WRITE_INTERVIEW_SCRIPT_PROMPT,
            user_message=inputs
        )
        
        interview_script_doc = Report(
            title="Interview Script",
            content=interview_script,
            is_markdown=True
        )
        
        return {"reports": [interview_script_doc]}
    
    @staticmethod
    def await_reports_creation(state: GraphState):
        return {"reports": []}
    
    def save_reports_to_google_docs(self, state: GraphState):
        print(Fore.YELLOW + "----- Save Reports to Google Docs -----\n" + Style.RESET_ALL)
        
        # Load all reports
        reports = state["reports"]
        
        # Ensure reports are saved locally
        save_reports_locally(reports)

        # Save all reports to Google docs (if enabled and configured)
        if SAVE_TO_GOOGLE_DOCS and self.docs_manager:
            print("[INFO] Uploading reports to Google Docs...")
            for report in reports:
                self.docs_manager.add_document(
                    content=report.content,
                    doc_title=report.title,
                    folder_name=self.drive_folder_name,
                    markdown=report.is_markdown
                )
        else:
            print("[INFO] Reports saved locally only (Google Docs disabled)")

        return state

    def update_CRM(self, state: GraphState):
        print(Fore.YELLOW + "----- Updating CRM records -----\n" + Style.RESET_ALL)
        
        # save new record data, ensure correct fields are used
        new_data = {
            "Status": "ATTEMPTED_TO_CONTACT", # Set lead to attempted contact
            "Score": state["lead_score"],
            "Analysis Reports": state.get("reports_folder_link", "Local reports folder"),
            "Outreach Report": state.get("custom_outreach_report_link", ""),
            "Last Contacted": get_current_date()
        }
        self.lead_loader.update_record(state["current_lead"].id, new_data)
        
        # reset reports list
        state["reports"] = []
        
        return {"number_leads": state["number_leads"] - 1}