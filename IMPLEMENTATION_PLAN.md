# AI SDR Implementation Plan: Week-by-Week Roadmap

## Overview

Transform your LangGraph outreach system into a **Floworks-style AI SDR agent** with autonomous 24/7 operation, automated follow-ups, and multi-channel orchestration.

**Timeline**: 12 weeks to production-ready AI SDR
**Current Progress**: Week 0 (Foundation complete, LLM migration done ✅)

---

## Phase 1: Email Automation Core (Weeks 1-4)

### Week 1: Email Infrastructure Setup

#### Day 1-2: SendGrid Integration
**Files to Create**:
- `src/tools/email/email_sender.py`
- `src/tools/email/email_tracker.py`
- `src/config/email_config.yaml`

**Tasks**:
```python
# src/tools/email/email_sender.py
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, TrackingSettings, ClickTracking, OpenTracking

class EmailSender:
    def __init__(self):
        self.client = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))

    def send_email(self, to_email, subject, html_content, lead_id):
        # Add tracking pixel
        tracking_pixel = self.generate_tracking_pixel(lead_id)
        html_with_tracking = html_content + tracking_pixel

        message = Mail(
            from_email=os.getenv('SENDER_EMAIL'),
            to_emails=to_email,
            subject=subject,
            html_content=html_with_tracking
        )

        # Enable click tracking
        message.tracking_settings = TrackingSettings(
            click_tracking=ClickTracking(enable=True),
            open_tracking=OpenTracking(enable=True)
        )

        response = self.client.send(message)
        return response.status_code, response.body

    def generate_tracking_pixel(self, lead_id):
        pixel_url = f"{os.getenv('TRACKING_DOMAIN')}/track/{lead_id}/open.gif"
        return f'<img src="{pixel_url}" width="1" height="1" alt="" />'
```

**Setup Tasks**:
- [ ] Create SendGrid account
- [ ] Verify sender domain (yourdomain.com)
- [ ] Set up domain authentication (SPF, DKIM, DMARC)
- [ ] Configure SendGrid webhook for events
- [ ] Add to `.env`: `SENDGRID_API_KEY`, `SENDER_EMAIL`

---

#### Day 3-4: Database Schema for Email Tracking
**Files to Create**:
- `database/schema.sql`
- `src/db/database.py`
- `src/models/email_tracking.py`

**Database Schema**:
```sql
-- database/schema.sql
CREATE TABLE IF NOT EXISTS email_campaigns (
    campaign_id SERIAL PRIMARY KEY,
    campaign_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS email_sends (
    send_id SERIAL PRIMARY KEY,
    campaign_id INT REFERENCES email_campaigns(campaign_id),
    lead_id VARCHAR(255) NOT NULL,
    lead_email VARCHAR(255) NOT NULL,
    subject VARCHAR(500),
    sent_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'sent',  -- sent, bounced, failed
    sendgrid_message_id VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS email_events (
    event_id SERIAL PRIMARY KEY,
    send_id INT REFERENCES email_sends(send_id),
    event_type VARCHAR(50),  -- open, click, bounce, spam, delivered
    event_timestamp TIMESTAMP DEFAULT NOW(),
    user_agent TEXT,
    ip_address VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS email_replies (
    reply_id SERIAL PRIMARY KEY,
    send_id INT REFERENCES email_sends(send_id),
    reply_content TEXT,
    replied_at TIMESTAMP DEFAULT NOW(),
    sentiment VARCHAR(50),  -- positive, negative, neutral, question
    requires_response BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS lead_sequences (
    sequence_id SERIAL PRIMARY KEY,
    lead_id VARCHAR(255) NOT NULL,
    sequence_type VARCHAR(100),  -- "cold_outreach", "follow_up"
    current_step INT DEFAULT 1,
    total_steps INT,
    next_action_date TIMESTAMP,
    status VARCHAR(50) DEFAULT 'active',  -- active, paused, completed
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_lead_id ON email_sends(lead_id);
CREATE INDEX idx_sent_at ON email_sends(sent_at);
CREATE INDEX idx_event_type ON email_events(event_type);
```

**Setup Tasks**:
- [ ] Install PostgreSQL (or use Supabase/Railway)
- [ ] Run schema migration
- [ ] Create database connection in `src/db/database.py`
- [ ] Add to `.env`: `DATABASE_URL`

---

#### Day 5-7: LangGraph Integration
**Files to Modify**:
- `src/graph.py` - Add email sending node
- `src/nodes.py` - Add `send_email_node` method
- `src/state.py` - Add email status fields

**Code Changes**:
```python
# src/state.py - Add to GraphState
class GraphState(TypedDict):
    # ... existing fields ...
    email_sent: bool
    email_send_id: int  # Reference to database
    email_tracking_enabled: bool

# src/nodes.py - New node
def send_email_node(self, state: GraphState):
    print(Fore.YELLOW + "----- Sending Personalized Email -----\n" + Style.RESET_ALL)

    lead = state["current_lead"]
    email_body = state["personalized_email"]
    subject = self.generate_email_subject(lead)

    # Send via SendGrid
    sender = EmailSender()
    status_code, _ = sender.send_email(
        to_email=lead.email,
        subject=subject,
        html_content=email_body,
        lead_id=lead.id
    )

    # Log to database
    send_id = self.log_email_send(lead.id, lead.email, subject, status_code)

    return {
        "email_sent": status_code == 202,
        "email_send_id": send_id
    }

# src/graph.py - Add to workflow
graph.add_node("send_email", nodes.send_email_node)
graph.add_edge("generate_personalized_email", "send_email")
```

**Testing**:
- [ ] Test email sending to personal email
- [ ] Verify tracking pixel appears in inbox
- [ ] Confirm database records created
- [ ] Test SendGrid webhook integration

**Week 1 Deliverable**: ✅ Emails sent automatically with tracking

---

### Week 2: Reply Monitoring System

#### Day 8-10: Gmail API Integration
**Files to Create**:
- `src/tools/email/gmail_monitor.py`
- `src/tools/email/reply_detector.py`

**Implementation**:
```python
# src/tools/email/gmail_monitor.py
import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta

class GmailMonitor:
    def __init__(self):
        self.creds = self.load_credentials()
        self.service = build('gmail', 'v1', credentials=self.creds)

    def check_for_replies(self, since_timestamp):
        """Poll inbox for new replies since timestamp"""
        query = f'in:inbox after:{since_timestamp} -from:me'

        results = self.service.users().messages().list(
            userId='me',
            q=query,
            maxResults=100
        ).execute()

        messages = results.get('messages', [])
        return [self.parse_message(msg['id']) for msg in messages]

    def parse_message(self, msg_id):
        """Extract email details"""
        msg = self.service.users().messages().get(
            userId='me',
            id=msg_id,
            format='full'
        ).execute()

        headers = {h['name']: h['value'] for h in msg['payload']['headers']}

        return {
            'message_id': msg_id,
            'from': headers.get('From'),
            'subject': headers.get('Subject'),
            'date': headers.get('Date'),
            'body': self.extract_body(msg),
            'in_reply_to': headers.get('In-Reply-To'),  # Original message ID
            'thread_id': msg['threadId']
        }

    def extract_body(self, msg):
        """Extract email body text"""
        # ... implement body extraction logic
        pass
```

**Setup Tasks**:
- [ ] Enable Gmail API in Google Console
- [ ] Create OAuth credentials
- [ ] Implement token refresh logic
- [ ] Add to `.env`: `GMAIL_CREDENTIALS_PATH`

---

#### Day 11-12: Reply Sentiment Analysis
**Files to Create**:
- `src/tools/email/sentiment_analyzer.py`
- `src/prompts/reply_analysis_prompts.py`

**Implementation**:
```python
# src/tools/email/sentiment_analyzer.py
from src.utils import invoke_llm

class ReplySentimentAnalyzer:
    def analyze_reply(self, reply_content, original_email, lead_profile):
        """Classify reply sentiment and intent"""

        prompt = f"""
        Analyze this email reply and classify it:

        Original Email: {original_email[:200]}...
        Reply: {reply_content}
        Lead Profile: {lead_profile}

        Classify the reply:
        1. Sentiment: positive, negative, neutral, question
        2. Intent: interested, not_interested, need_more_info, ready_to_meet
        3. Requires Human: yes/no
        4. Urgency: high, medium, low

        Return JSON format.
        """

        from src.structured_outputs import ReplyAnalysis
        result = invoke_llm(
            system_prompt="You are an email sentiment analyzer.",
            user_message=prompt,
            response_format=ReplyAnalysis
        )

        return result
```

**Testing**:
- [ ] Test with sample positive replies
- [ ] Test with negative/rejection replies
- [ ] Test with question-based replies
- [ ] Verify classification accuracy >80%

---

#### Day 13-14: Automated Reply Generation
**Files to Create**:
- `src/nodes_follow_up.py`
- `src/prompts/reply_prompts.py`

**Implementation**:
```python
# src/nodes_follow_up.py
class FollowUpNodes:
    def generate_reply_to_prospect(self, state: GraphState):
        """Generate contextual reply based on sentiment"""

        lead = state["current_lead"]
        reply_analysis = state["reply_analysis"]
        conversation_history = state["conversation_history"]

        # Different prompts based on sentiment
        if reply_analysis.sentiment == "positive":
            prompt = POSITIVE_REPLY_PROMPT
        elif reply_analysis.intent == "need_more_info":
            prompt = CLARIFICATION_REPLY_PROMPT
        elif reply_analysis.intent == "ready_to_meet":
            prompt = MEETING_BOOKING_PROMPT

        reply = invoke_llm(
            system_prompt=prompt,
            user_message=f"""
            Lead: {lead.name}
            Their Reply: {reply_analysis.content}
            Context: {conversation_history}

            Generate a helpful, concise reply.
            """
        )

        return {"generated_reply": reply}
```

**Week 2 Deliverable**: ✅ System detects replies and generates responses

---

### Week 3: Follow-Up Sequences

#### Day 15-17: Sequence Engine
**Files to Create**:
- `src/sequences/sequence_engine.py`
- `src/sequences/templates/cold_outreach.yaml`
- `src/sequences/sequence_scheduler.py`

**Sequence Definition**:
```yaml
# src/sequences/templates/cold_outreach.yaml
sequence_name: "Cold Outreach - 5 Touch"
sequence_type: "cold_outreach"
total_steps: 5

steps:
  - step: 1
    day: 0
    channel: email
    template: "initial_outreach_with_report"
    subject: "Quick question about {{company_name}}"
    wait_for_reply: true

  - step: 2
    day: 3
    condition: "no_reply"
    channel: email
    template: "follow_up_value_add"
    subject: "Re: Quick question about {{company_name}}"

  - step: 3
    day: 5
    condition: "no_reply"
    channel: linkedin
    template: "linkedin_connection"

  - step: 4
    day: 7
    condition: "no_reply"
    channel: email
    template: "breakup_email"
    subject: "Final note - {{first_name}}"

  - step: 5
    day: 14
    condition: "no_reply"
    channel: email
    template: "re_engagement"
    subject: "Checking in - {{company_name}}"
```

**Implementation**:
```python
# src/sequences/sequence_engine.py
class SequenceEngine:
    def __init__(self, db_connection):
        self.db = db_connection

    def start_sequence(self, lead_id, sequence_type):
        """Initialize sequence for a lead"""
        sequence = self.load_sequence_template(sequence_type)

        self.db.execute("""
            INSERT INTO lead_sequences
            (lead_id, sequence_type, current_step, total_steps, next_action_date, status)
            VALUES (%s, %s, 1, %s, NOW(), 'active')
        """, (lead_id, sequence_type, sequence['total_steps']))

    def process_sequences(self):
        """Check for sequences that need action"""
        due_sequences = self.db.query("""
            SELECT * FROM lead_sequences
            WHERE status = 'active'
            AND next_action_date <= NOW()
        """)

        for seq in due_sequences:
            self.execute_sequence_step(seq)

    def execute_sequence_step(self, sequence):
        """Execute current step in sequence"""
        lead = self.get_lead(sequence['lead_id'])
        step = self.get_step_config(sequence['sequence_type'], sequence['current_step'])

        # Check condition
        if step['condition'] == 'no_reply':
            if self.check_reply_exists(sequence['lead_id']):
                # Reply received, stop sequence
                self.mark_sequence_complete(sequence['sequence_id'])
                return

        # Execute action (send email, LinkedIn message, etc.)
        if step['channel'] == 'email':
            self.send_sequence_email(lead, step)
        elif step['channel'] == 'linkedin':
            self.send_linkedin_message(lead, step)

        # Update sequence
        self.advance_sequence(sequence)
```

---

#### Day 18-19: Background Job Queue
**Files to Create**:
- `src/workers/celery_app.py`
- `src/workers/tasks.py`

**Setup Celery**:
```python
# src/workers/celery_app.py
from celery import Celery
from celery.schedules import crontab

app = Celery('ai_sdr', broker='redis://localhost:6379/0')

app.conf.beat_schedule = {
    'monitor-inbox-every-5-minutes': {
        'task': 'src.workers.tasks.monitor_inbox',
        'schedule': 300.0,  # 5 minutes
    },
    'process-sequences-every-hour': {
        'task': 'src.workers.tasks.process_sequences',
        'schedule': 3600.0,  # 1 hour
    },
}

# src/workers/tasks.py
from src.workers.celery_app import app
from src.tools.email.gmail_monitor import GmailMonitor
from src.sequences.sequence_engine import SequenceEngine

@app.task
def monitor_inbox():
    """Background task to check for replies"""
    monitor = GmailMonitor()
    replies = monitor.check_for_replies(since_timestamp='1h')

    for reply in replies:
        # Process each reply
        analyze_and_respond.delay(reply)

@app.task
def analyze_and_respond(reply):
    """Analyze reply and generate response"""
    # ... implement reply handling logic
    pass

@app.task
def process_sequences():
    """Execute pending sequence steps"""
    engine = SequenceEngine(db)
    engine.process_sequences()
```

**Setup Tasks**:
- [ ] Install Redis
- [ ] Configure Celery
- [ ] Start Celery worker: `celery -A src.workers worker --loglevel=info`
- [ ] Start Celery beat: `celery -A src.workers beat --loglevel=info`

**Week 3 Deliverable**: ✅ Multi-touch sequences run automatically

---

### Week 4: Email Warmup System

#### Day 20-22: Warmup Manager
**Files to Create**:
- `src/tools/email/warmup_manager.py`
- `src/config/warmup_schedule.yaml`

**Implementation**:
```python
# src/tools/email/warmup_manager.py
class EmailWarmupManager:
    def __init__(self, email_account):
        self.email_account = email_account
        self.warmup_schedule = self.load_warmup_schedule()

    def get_daily_send_limit(self, account_age_days):
        """Calculate send limit based on warmup phase"""
        for phase in self.warmup_schedule['phases']:
            if account_age_days in range(phase['day_start'], phase['day_end']):
                return phase['daily_limit']
        return self.warmup_schedule['max_daily_sends']

    def check_send_quota(self):
        """Check if account can send more today"""
        today_sends = self.count_sends_today()
        daily_limit = self.get_daily_send_limit(self.get_account_age())

        return today_sends < daily_limit

    def send_warmup_emails(self):
        """Send internal warmup emails"""
        seed_accounts = self.get_seed_accounts()
        warmup_content = self.generate_warmup_email()

        for seed in seed_accounts:
            self.send_email(seed, warmup_content)
            # Schedule auto-reply from seed account
            self.schedule_seed_reply(seed, delay_hours=random.randint(2, 8))
```

**Warmup Schedule**:
```yaml
# src/config/warmup_schedule.yaml
warmup_phases:
  - phase: 1
    day_start: 1
    day_end: 7
    daily_limit: 15
    engagement_rate: 0.8

  - phase: 2
    day_start: 8
    day_end: 14
    daily_limit: 30
    engagement_rate: 0.6

  - phase: 3
    day_start: 15
    day_end: 21
    daily_limit: 50
    engagement_rate: 0.5

  - phase: 4
    day_start: 22
    day_end: 30
    daily_limit: 100
    engagement_rate: 0.3

max_daily_sends: 150  # After warmup complete
```

---

#### Day 23-24: Deliverability Monitoring
**Files to Create**:
- `src/tools/email/deliverability_monitor.py`

**Implementation**:
```python
# src/tools/email/deliverability_monitor.py
class DeliverabilityMonitor:
    def calculate_deliverability_score(self, email_account):
        """Calculate health score for email account"""

        stats = self.get_account_stats(email_account, days=7)

        bounce_rate = stats['bounces'] / stats['sent']
        spam_rate = stats['spam_reports'] / stats['sent']
        open_rate = stats['opens'] / stats['delivered']

        # Score calculation
        score = 100
        if bounce_rate > 0.05:  # >5% bounces
            score -= 30
        if spam_rate > 0.001:  # >0.1% spam reports
            score -= 40
        if open_rate < 0.15:  # <15% opens
            score -= 20

        return {
            'score': max(0, score),
            'bounce_rate': bounce_rate,
            'spam_rate': spam_rate,
            'open_rate': open_rate,
            'recommendation': self.get_recommendation(score)
        }

    def get_recommendation(self, score):
        if score < 50:
            return "STOP SENDING - High risk of permanent blacklist"
        elif score < 70:
            return "REDUCE VOLUME - Deliverability issues detected"
        elif score < 85:
            return "MONITOR - Some issues present"
        else:
            return "HEALTHY - Continue current sending"
```

**Week 4 Deliverable**: ✅ Email warmup prevents deliverability issues

---

## Phase 1 Summary

**Completed Features**:
- ✅ Automated email sending (SendGrid)
- ✅ Email tracking (opens, clicks, replies)
- ✅ Reply monitoring (Gmail API)
- ✅ Automated responses (LLM-powered)
- ✅ Multi-touch sequences (5-step campaigns)
- ✅ Background jobs (Celery + Redis)
- ✅ Email warmup system
- ✅ Deliverability monitoring

**Tech Stack Added**:
- SendGrid (email infrastructure)
- PostgreSQL (email tracking)
- Redis (job queue)
- Celery (background workers)
- Gmail API (reply monitoring)

**Testing Checklist**:
- [ ] Send 100 test emails
- [ ] Verify open rate >20%
- [ ] Confirm replies are detected
- [ ] Test automated responses
- [ ] Verify sequences run on schedule
- [ ] Monitor deliverability score >85

---

## Phase 2: Multi-Channel & Optimization (Weeks 5-8)

### Week 5: LinkedIn Automation

#### Option A: Phantombuster Integration (Recommended)
**Files to Create**:
- `src/tools/linkedin/phantombuster_client.py`

**Implementation**:
```python
# src/tools/linkedin/phantombuster_client.py
import requests

class PhantombusterLinkedIn:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.phantombuster.com/api/v2"

    def send_connection_request(self, profile_url, message):
        """Send LinkedIn connection request"""
        payload = {
            "sessionCookie": os.getenv('LINKEDIN_SESSION_COOKIE'),
            "profileUrls": [profile_url],
            "message": message
        }

        response = requests.post(
            f"{self.base_url}/agents/launch",
            headers={"X-Phantombuster-Key": self.api_key},
            json=payload
        )

        return response.json()

    def send_message(self, profile_url, message):
        """Send direct message on LinkedIn"""
        # ... implement messaging logic
        pass
```

**Setup**:
- [ ] Sign up for Phantombuster ($69/month)
- [ ] Configure LinkedIn scraper agent
- [ ] Add LinkedIn session cookie
- [ ] Test connection requests

---

#### Option B: Browser Automation (Advanced)
**Files to Create**:
- `src/tools/linkedin/browser_automation.py`

**Implementation** (use cautiously):
```python
# src/tools/linkedin/browser_automation.py
from playwright.sync_api import sync_playwright

class LinkedInAutomation:
    def __init__(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)

    def login(self, email, password):
        """Login to LinkedIn"""
        page = self.browser.new_page()
        page.goto("https://www.linkedin.com/login")
        page.fill('input[name="session_key"]', email)
        page.fill('input[name="session_password"]', password)
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')

    def send_connection_request(self, profile_url, message):
        """Send connection request"""
        page = self.browser.new_page()
        page.goto(profile_url)
        page.click('button:has-text("Connect")')
        page.fill('textarea', message)
        page.click('button:has-text("Send")')
```

**⚠️ Warning**: Use official APIs or Phantombuster to avoid account restrictions

---

### Week 6: Calendar Integration

**Files to Create**:
- `src/tools/calendar/google_calendar_manager.py`
- `src/tools/calendar/booking_link_generator.py`

**Implementation**:
```python
# src/tools/calendar/google_calendar_manager.py
from googleapiclient.discovery import build

class CalendarManager:
    def __init__(self, credentials):
        self.service = build('calendar', 'v3', credentials=credentials)

    def find_free_slots(self, duration_minutes=30, days_ahead=14):
        """Find available time slots"""
        from datetime import datetime, timedelta

        start_time = datetime.utcnow()
        end_time = start_time + timedelta(days=days_ahead)

        # Get all events
        events = self.service.events().list(
            calendarId='primary',
            timeMin=start_time.isoformat() + 'Z',
            timeMax=end_time.isoformat() + 'Z',
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        # Calculate free slots
        free_slots = self.calculate_free_slots(events, duration_minutes)
        return free_slots

    def create_meeting(self, attendee_email, start_time, duration_minutes):
        """Create calendar event"""
        event = {
            'summary': 'Discovery Call',
            'description': 'Automated booking via AI SDR',
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': (start_time + timedelta(minutes=duration_minutes)).isoformat(),
                'timeZone': 'UTC',
            },
            'attendees': [
                {'email': attendee_email},
            ],
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},  # 24h before
                    {'method': 'popup', 'minutes': 60},  # 1h before
                ],
            },
        }

        event = self.service.events().insert(calendarId='primary', body=event).execute()
        return event['htmlLink']

# src/tools/calendar/booking_link_generator.py
class BookingLinkGenerator:
    def generate_calendly_style_link(self, lead_id, lead_email):
        """Generate unique booking link for lead"""
        import hashlib

        token = hashlib.sha256(f"{lead_id}:{lead_email}".encode()).hexdigest()[:16]
        booking_url = f"https://yourdomain.com/book/{token}"

        # Store in database for later lookup
        self.save_booking_token(token, lead_id, lead_email)

        return booking_url
```

---

### Week 7: Intent Signal Detection

**Files to Create**:
- `src/tools/intent/website_tracker.py`
- `src/tools/intent/intent_scorer.py`

**Implementation**:
```python
# src/tools/intent/intent_scorer.py
class IntentScorer:
    SIGNAL_WEIGHTS = {
        'website_visit': 5,
        'pricing_page_view': 20,
        'case_study_download': 15,
        'blog_post_read': 10,
        'demo_video_watch': 25,
        'linkedin_profile_view': 8,
        'email_link_click': 12,
        'recent_funding': 30,
        'job_posting': 15,
        'technology_adoption': 20
    }

    def calculate_intent_score(self, lead_id):
        """Calculate intent score from signals"""
        signals = self.get_lead_signals(lead_id)

        score = 0
        for signal in signals:
            weight = self.SIGNAL_WEIGHTS.get(signal['type'], 0)
            recency_multiplier = self.calculate_recency_multiplier(signal['timestamp'])
            score += weight * recency_multiplier

        return min(100, score)

    def calculate_recency_multiplier(self, timestamp):
        """Recent signals are more valuable"""
        from datetime import datetime, timedelta

        age_days = (datetime.now() - timestamp).days

        if age_days <= 1:
            return 1.0
        elif age_days <= 7:
            return 0.8
        elif age_days <= 30:
            return 0.5
        else:
            return 0.2
```

**Tracking Pixel for Website Visits**:
```html
<!-- Add to your website -->
<script>
(function() {
    const urlParams = new URLSearchParams(window.location.search);
    const leadId = urlParams.get('lead_id');

    if (leadId) {
        fetch('https://yourdomain.com/api/track', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                lead_id: leadId,
                event: 'website_visit',
                page: window.location.pathname,
                timestamp: new Date().toISOString()
            })
        });
    }
})();
</script>
```

---

### Week 8: Send-Time Optimization

**Files to Create**:
- `src/tools/email/send_time_optimizer.py`

**Implementation**:
```python
# src/tools/email/send_time_optimizer.py
import pytz
from datetime import datetime, timedelta

class SendTimeOptimizer:
    # Industry-specific optimal times (local time)
    INDUSTRY_SEND_TIMES = {
        'technology': {'hour': 9, 'day': 'tuesday'},
        'finance': {'hour': 7, 'day': 'wednesday'},
        'healthcare': {'hour': 10, 'day': 'thursday'},
        'retail': {'hour': 11, 'day': 'tuesday'},
        'default': {'hour': 9, 'day': 'tuesday'}
    }

    def calculate_optimal_send_time(self, lead_timezone, lead_industry):
        """Calculate when to send email in UTC"""

        industry_time = self.INDUSTRY_SEND_TIMES.get(
            lead_industry.lower(),
            self.INDUSTRY_SEND_TIMES['default']
        )

        # Find next occurrence of optimal day
        next_send_day = self.get_next_weekday(industry_time['day'])

        # Convert to lead's local time
        local_tz = pytz.timezone(lead_timezone)
        local_time = local_tz.localize(datetime(
            next_send_day.year,
            next_send_day.month,
            next_send_day.day,
            industry_time['hour'],
            0
        ))

        # Convert to UTC for scheduling
        utc_time = local_time.astimezone(pytz.UTC)
        return utc_time

    def get_next_weekday(self, target_day):
        """Get next occurrence of target weekday"""
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
        target_idx = days.index(target_day.lower())

        today = datetime.now()
        days_ahead = target_idx - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7

        return today + timedelta(days=days_ahead)
```

---

## Phase 2 Summary (Weeks 5-8)

**Completed Features**:
- ✅ LinkedIn connection requests
- ✅ LinkedIn message automation
- ✅ Google Calendar integration
- ✅ One-click meeting booking
- ✅ Intent signal tracking
- ✅ Behavioral scoring
- ✅ Send-time optimization (timezone-aware)

**Tech Stack Added**:
- Phantombuster (LinkedIn automation)
- Google Calendar API
- Intent tracking system

**Testing**:
- [ ] Send LinkedIn connection to 10 test profiles
- [ ] Verify calendar booking flow
- [ ] Test intent score calculation
- [ ] Confirm send-time optimization works across timezones

---

## Phase 3: Analytics & Intelligence (Weeks 9-12)

### Week 9-10: Real-Time Dashboard

**Tech Stack**: Streamlit or Dash

**Files to Create**:
- `src/dashboard/app.py`
- `src/dashboard/metrics.py`
- `src/dashboard/charts.py`

**Implementation** (Streamlit):
```python
# src/dashboard/app.py
import streamlit as st
import pandas as pd
from src.dashboard.metrics import DashboardMetrics

st.set_page_config(page_title="AI SDR Dashboard", layout="wide")

metrics = DashboardMetrics()

# Header
st.title("🤖 AI SDR Performance Dashboard")

# KPIs
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Emails Sent (7d)", metrics.get_emails_sent(), delta="+12%")
with col2:
    st.metric("Open Rate", f"{metrics.get_open_rate():.1f}%", delta="+2.3%")
with col3:
    st.metric("Reply Rate", f"{metrics.get_reply_rate():.1f}%", delta="+5.1%")
with col4:
    st.metric("Meetings Booked", metrics.get_meetings_booked(), delta="+3")

# Charts
col1, col2 = st.columns(2)
with col1:
    st.subheader("Email Performance Over Time")
    st.line_chart(metrics.get_email_performance_timeseries())

with col2:
    st.subheader("Reply Sentiment Distribution")
    st.bar_chart(metrics.get_reply_sentiment_distribution())

# Lead Pipeline
st.subheader("Lead Pipeline")
pipeline_df = metrics.get_pipeline_status()
st.dataframe(pipeline_df)

# Hot Leads Alert
hot_leads = metrics.get_hot_leads()
if len(hot_leads) > 0:
    st.warning(f"🔥 {len(hot_leads)} hot leads need attention!")
    st.dataframe(hot_leads)
```

**Run Dashboard**:
```bash
streamlit run src/dashboard/app.py
```

---

### Week 11: A/B Testing Framework

**Files to Create**:
- `src/experiments/ab_test_manager.py`
- `src/experiments/variants/email_variants.yaml`

**Implementation**:
```python
# src/experiments/ab_test_manager.py
class ABTestManager:
    def create_experiment(self, experiment_name, variants, traffic_split):
        """Create A/B test"""
        self.db.execute("""
            INSERT INTO experiments (name, variants, traffic_split, status)
            VALUES (%s, %s, %s, 'active')
        """, (experiment_name, variants, traffic_split))

    def assign_variant(self, lead_id, experiment_name):
        """Randomly assign lead to variant"""
        import random

        experiment = self.get_experiment(experiment_name)
        variants = experiment['variants']
        traffic_split = experiment['traffic_split']

        # Weighted random selection
        variant = random.choices(
            list(variants.keys()),
            weights=list(traffic_split.values())
        )[0]

        self.log_assignment(lead_id, experiment_name, variant)
        return variants[variant]

    def calculate_winner(self, experiment_name, metric='reply_rate'):
        """Determine winning variant"""
        results = self.get_experiment_results(experiment_name)

        best_variant = max(results, key=lambda x: x[metric])
        return best_variant
```

**Example Experiment**:
```yaml
# src/experiments/variants/email_variants.yaml
experiment_name: "subject_line_test_v1"
variants:
  A:
    subject: "Quick question about {{company_name}}"
    description: "Personalized company name"
  B:
    subject: "Improving your content strategy"
    description: "Value-focused"
  C:
    subject: "{{first_name}}, saw your recent post..."
    description: "Personal reference"

traffic_split:
  A: 0.33
  B: 0.33
  C: 0.34

duration_days: 14
success_metric: "reply_rate"
```

---

### Week 12: Continuous Learning Pipeline

**Files to Create**:
- `src/learning/feedback_collector.py`
- `src/learning/model_tuner.py`

**Implementation**:
```python
# src/learning/feedback_collector.py
class FeedbackCollector:
    def collect_successful_examples(self, min_reply_rate=0.20):
        """Extract high-performing email examples"""

        successful_emails = self.db.query("""
            SELECT
                e.subject,
                e.body,
                e.lead_id,
                r.sentiment,
                l.industry
            FROM email_sends e
            JOIN email_replies r ON e.send_id = r.send_id
            JOIN leads l ON e.lead_id = l.id
            WHERE r.sentiment IN ('positive', 'question')
            AND e.sent_at >= NOW() - INTERVAL '30 days'
        """)

        return self.prepare_training_data(successful_emails)

    def prepare_training_data(self, examples):
        """Format for fine-tuning"""
        training_data = []

        for example in examples:
            training_data.append({
                "messages": [
                    {"role": "system", "content": "You are an expert sales email writer."},
                    {"role": "user", "content": f"Write email for lead in {example['industry']}"},
                    {"role": "assistant", "content": example['body']}
                ]
            })

        return training_data

# src/learning/model_tuner.py
class ModelTuner:
    def fine_tune_model(self, training_data, base_model="gpt-4o-mini"):
        """Fine-tune OpenAI model on successful examples"""
        import openai

        # Upload training file
        training_file = openai.File.create(
            file=training_data,
            purpose='fine-tune'
        )

        # Start fine-tuning job
        fine_tune_job = openai.FineTuningJob.create(
            training_file=training_file.id,
            model=base_model
        )

        return fine_tune_job.id
```

**Learning Schedule**:
- Collect feedback weekly
- Retrain model monthly
- Deploy improved model after validation

---

## Phase 3 Summary (Weeks 9-12)

**Completed Features**:
- ✅ Real-time dashboard (Streamlit)
- ✅ A/B testing framework
- ✅ Continuous learning pipeline
- ✅ Model fine-tuning automation
- ✅ Performance analytics

---

## Final Checklist: Production Readiness

### Security & Compliance
- [ ] GDPR compliance (opt-out mechanism)
- [ ] CAN-SPAM compliance (unsubscribe links)
- [ ] Data encryption (at rest and in transit)
- [ ] Audit logging (all data access)
- [ ] Rate limiting (API protection)

### Infrastructure
- [ ] Docker containerization
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Monitoring (Sentry for errors)
- [ ] Backup strategy (database backups)
- [ ] Scalability testing (handle 1000+ leads/day)

### Documentation
- [ ] API documentation
- [ ] Deployment guide
- [ ] Configuration guide
- [ ] Troubleshooting guide

---

## Deployment Options

### Option 1: Self-Hosted (Lowest Cost)
**Infrastructure**: Railway, Render, or DigitalOcean
**Cost**: ~$50-100/month
**Pros**: Full control, cheapest
**Cons**: Requires maintenance

### Option 2: Managed Services (Easiest)
**Infrastructure**: Heroku + managed Redis/PostgreSQL
**Cost**: ~$100-200/month
**Pros**: Minimal DevOps
**Cons**: Higher cost

### Option 3: Serverless (Scalable)
**Infrastructure**: AWS Lambda + S3 + RDS
**Cost**: ~$50-150/month (usage-based)
**Pros**: Auto-scaling
**Cons**: Complex setup

---

## Success Metrics (12-Week Goals)

| Metric | Target | Benchmark |
|--------|--------|-----------|
| Email Open Rate | >25% | Industry avg: 20% |
| Reply Rate | >15% | Industry avg: 8% |
| Positive Reply Rate | >60% | N/A |
| Meeting Booked Rate | >5% | Floworks: ~10% |
| Cost per Lead | <$0.15 | Floworks: $0.50-1.00 |
| System Uptime | >99% | Critical |

---

## Timeline Summary

- **Weeks 1-4**: Email automation core (sending, tracking, follow-ups)
- **Weeks 5-8**: Multi-channel (LinkedIn, calendar, intent signals)
- **Weeks 9-12**: Analytics & optimization (dashboard, A/B tests, learning)

**Total**: 12 weeks to full AI SDR capability
**MVP**: 4 weeks (Phase 1 only)
**Competitive Parity**: 8 weeks (Phases 1-2)

---

**Next Step**: Start Week 1, Day 1 - SendGrid setup and email sending infrastructure!
