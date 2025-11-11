# Core AI SDR Engine - 4-Week Build Plan

## 🎯 Goal

Transform your current system from:
- ❌ Manual email generation → ✅ **Autonomous 24/7 operation**
- ❌ One-time execution → ✅ **Continuous monitoring & follow-ups**
- ❌ Static reports → ✅ **Dynamic conversation management**

---

## Phase 1: Foundation Setup (Days 1-3)

### Day 1: Environment Setup

#### 1.1 Install Dependencies

```bash
# Add to requirements.txt
sendgrid==6.11.0
psycopg2-binary==2.9.9
celery==5.3.4
redis==5.0.1
python-dotenv==1.0.0
sqlalchemy==2.0.23
alembic==1.13.1
```

Install:
```bash
pip install -r requirements.txt
```

---

#### 1.2 Set Up Local PostgreSQL

**Option A: Docker (Easiest)**
```bash
# Create docker-compose.yml
docker-compose up -d
```

**docker-compose.yml**:
```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: ai_sdr
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

**Option B: Install Locally**
- Windows: Download PostgreSQL installer
- Mac: `brew install postgresql redis`
- Linux: `sudo apt install postgresql redis-server`

---

#### 1.3 Database Migration Setup

Create database schema:

```bash
# Create migrations folder
mkdir -p database/migrations
```

**File: `database/schema.sql`**
```sql
-- Core email tracking tables
CREATE TABLE IF NOT EXISTS email_sends (
    send_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id VARCHAR(255) NOT NULL,
    lead_email VARCHAR(255) NOT NULL,

    -- Email content
    subject VARCHAR(500),
    body_html TEXT,

    -- Tracking
    tracking_pixel_token VARCHAR(100) UNIQUE,
    sendgrid_message_id VARCHAR(255),

    -- Status
    status VARCHAR(50) DEFAULT 'queued',  -- queued, sent, delivered, bounced, failed
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP,

    -- Engagement
    opened_at TIMESTAMP,
    open_count INT DEFAULT 0,
    clicked_at TIMESTAMP,
    click_count INT DEFAULT 0,
    replied_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_email_lead ON email_sends(lead_id);
CREATE INDEX idx_tracking_token ON email_sends(tracking_pixel_token);

---

CREATE TABLE IF NOT EXISTS email_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    send_id UUID NOT NULL REFERENCES email_sends(send_id) ON DELETE CASCADE,

    event_type VARCHAR(50) NOT NULL,  -- open, click, bounce, spam, delivered
    event_timestamp TIMESTAMP DEFAULT NOW(),

    user_agent TEXT,
    ip_address VARCHAR(50),
    link_url TEXT
);

CREATE INDEX idx_event_send ON email_events(send_id);
CREATE INDEX idx_event_type ON email_events(event_type);

---

CREATE TABLE IF NOT EXISTS email_replies (
    reply_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    send_id UUID REFERENCES email_sends(send_id),
    lead_id VARCHAR(255) NOT NULL,

    -- Reply content
    reply_content TEXT,
    replied_at TIMESTAMP DEFAULT NOW(),

    -- Analysis
    sentiment VARCHAR(50),  -- positive, negative, neutral, question
    intent VARCHAR(100),  -- interested, not_interested, need_more_info, ready_to_meet
    requires_response BOOLEAN DEFAULT TRUE,

    -- Response tracking
    response_generated TEXT,
    response_sent_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_reply_lead ON email_replies(lead_id);

---

CREATE TABLE IF NOT EXISTS lead_sequences (
    sequence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id VARCHAR(255) NOT NULL,

    -- Sequence config
    sequence_type VARCHAR(100) NOT NULL,  -- cold_outreach_3touch, cold_outreach_5touch
    current_step INT DEFAULT 1,
    total_steps INT NOT NULL,

    -- Schedule
    next_action_date TIMESTAMP,
    last_action_date TIMESTAMP,

    -- Status
    status VARCHAR(50) DEFAULT 'active',  -- active, paused, completed, stopped
    stop_reason VARCHAR(100),  -- reply_received, unsubscribed, bounced

    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE INDEX idx_sequence_lead ON lead_sequences(lead_id);
CREATE INDEX idx_sequence_next_action ON lead_sequences(next_action_date, status);
```

Run migration:
```bash
psql -U postgres -d ai_sdr -f database/schema.sql
```

---

#### 1.4 Update .env Configuration

Add to `.env`:
```env
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/ai_sdr

# Redis (for Celery)
REDIS_URL=redis://localhost:6379/0

# SendGrid
SENDGRID_API_KEY=your-sendgrid-api-key
SENDER_EMAIL=noreply@yourdomain.com
SENDER_NAME=Your Company

# Tracking (for webhooks)
TRACKING_DOMAIN=https://yourdomain.com  # or ngrok for local testing
WEBHOOK_SECRET=your-random-secret-key
```

---

### Day 2: Email Sending Infrastructure

#### 2.1 Create Email Sender Module

**File: `src/tools/email/email_sender.py`**

```python
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, TrackingSettings, ClickTracking, OpenTracking
import uuid
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

class EmailSender:
    def __init__(self):
        self.client = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
        self.sender_email = os.getenv('SENDER_EMAIL')
        self.sender_name = os.getenv('SENDER_NAME')
        self.tracking_domain = os.getenv('TRACKING_DOMAIN')

        # Database connection
        self.db_url = os.getenv('DATABASE_URL')

    def _get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(self.db_url)

    def generate_tracking_pixel(self, tracking_token):
        """Generate tracking pixel HTML"""
        pixel_url = f"{self.tracking_domain}/track/{tracking_token}/open.gif"
        return f'<img src="{pixel_url}" width="1" height="1" alt="" />'

    def send_email(self, lead_id, to_email, subject, html_content):
        """
        Send email with tracking.
        Returns: (send_id, status)
        """

        # Generate unique tracking token
        tracking_token = str(uuid.uuid4())[:16]

        # Add tracking pixel to email
        tracking_pixel = self.generate_tracking_pixel(tracking_token)
        html_with_tracking = html_content + tracking_pixel

        # Create SendGrid message
        message = Mail(
            from_email=(self.sender_email, self.sender_name),
            to_emails=to_email,
            subject=subject,
            html_content=html_with_tracking
        )

        # Enable click tracking
        message.tracking_settings = TrackingSettings(
            click_tracking=ClickTracking(enable=True, enable_text=True),
            open_tracking=OpenTracking(enable=True)
        )

        try:
            # Send via SendGrid
            response = self.client.send(message)

            # Log to database
            send_id = self._log_email_send(
                lead_id=lead_id,
                lead_email=to_email,
                subject=subject,
                body_html=html_content,
                tracking_token=tracking_token,
                sendgrid_message_id=response.headers.get('X-Message-Id'),
                status='sent' if response.status_code == 202 else 'failed'
            )

            return send_id, response.status_code == 202

        except Exception as e:
            print(f"Error sending email: {str(e)}")
            # Log failure
            send_id = self._log_email_send(
                lead_id=lead_id,
                lead_email=to_email,
                subject=subject,
                body_html=html_content,
                tracking_token=tracking_token,
                status='failed'
            )
            return send_id, False

    def _log_email_send(self, lead_id, lead_email, subject, body_html,
                       tracking_token, sendgrid_message_id=None, status='queued'):
        """Log email send to database"""
        conn = self._get_db_connection()
        cur = conn.cursor()

        try:
            cur.execute("""
                INSERT INTO email_sends
                (lead_id, lead_email, subject, body_html, tracking_pixel_token,
                 sendgrid_message_id, status, sent_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING send_id
            """, (
                lead_id, lead_email, subject, body_html, tracking_token,
                sendgrid_message_id, status,
                datetime.now() if status == 'sent' else None
            ))

            send_id = cur.fetchone()[0]
            conn.commit()
            return send_id

        finally:
            cur.close()
            conn.close()

    def get_send_status(self, send_id):
        """Get email send status and engagement"""
        conn = self._get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        try:
            cur.execute("""
                SELECT
                    send_id, lead_id, lead_email, subject, status,
                    sent_at, delivered_at, opened_at, clicked_at, replied_at,
                    open_count, click_count
                FROM email_sends
                WHERE send_id = %s
            """, (send_id,))

            return cur.fetchone()

        finally:
            cur.close()
            conn.close()
```

---

#### 2.2 Create Webhook Handler

**File: `src/api/webhooks.py`** (FastAPI endpoint)

```python
from fastapi import FastAPI, Request, HTTPException
import hmac
import hashlib
import psycopg2
from datetime import datetime

app = FastAPI()

def verify_webhook_signature(payload, signature, secret):
    """Verify SendGrid webhook signature"""
    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected_signature)

@app.post("/webhooks/sendgrid")
async def sendgrid_webhook(request: Request):
    """
    Handle SendGrid event webhooks.
    Events: delivered, open, click, bounce, spam_report
    """

    # Verify signature
    payload = await request.body()
    signature = request.headers.get("X-Twilio-Email-Event-Webhook-Signature")

    if not verify_webhook_signature(payload, signature, os.getenv("WEBHOOK_SECRET")):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse events
    events = await request.json()

    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    cur = conn.cursor()

    try:
        for event in events:
            event_type = event.get('event')
            sendgrid_message_id = event.get('sg_message_id')
            timestamp = datetime.fromtimestamp(event.get('timestamp'))

            # Find email send record
            cur.execute("""
                SELECT send_id FROM email_sends
                WHERE sendgrid_message_id = %s
            """, (sendgrid_message_id,))

            result = cur.fetchone()
            if not result:
                continue

            send_id = result[0]

            # Log event
            cur.execute("""
                INSERT INTO email_events
                (send_id, event_type, event_timestamp, user_agent, ip_address, link_url)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                send_id, event_type, timestamp,
                event.get('useragent'), event.get('ip'), event.get('url')
            ))

            # Update email_sends table based on event
            if event_type == 'delivered':
                cur.execute("""
                    UPDATE email_sends
                    SET status = 'delivered', delivered_at = %s
                    WHERE send_id = %s
                """, (timestamp, send_id))

            elif event_type == 'open':
                cur.execute("""
                    UPDATE email_sends
                    SET opened_at = COALESCE(opened_at, %s),
                        open_count = open_count + 1
                    WHERE send_id = %s
                """, (timestamp, send_id))

            elif event_type == 'click':
                cur.execute("""
                    UPDATE email_sends
                    SET clicked_at = COALESCE(clicked_at, %s),
                        click_count = click_count + 1
                    WHERE send_id = %s
                """, (timestamp, send_id))

            elif event_type in ['bounce', 'dropped']:
                cur.execute("""
                    UPDATE email_sends
                    SET status = 'bounced'
                    WHERE send_id = %s
                """, (send_id,))

        conn.commit()
        return {"status": "success", "processed": len(events)}

    finally:
        cur.close()
        conn.close()

# Run with: uvicorn src.api.webhooks:app --reload --port 8000
```

**For local testing, use ngrok**:
```bash
ngrok http 8000
# Copy the HTTPS URL to SendGrid webhook settings
```

---

#### 2.3 Integrate with LangGraph

**File: `src/nodes_email.py`** (New file)

```python
from colorama import Fore, Style
from src.tools.email.email_sender import EmailSender
from src.state import GraphState

class EmailNodes:
    def __init__(self):
        self.email_sender = EmailSender()

    def send_personalized_email(self, state: GraphState):
        """
        Send email generated in previous step.
        Tracks sending in database.
        """
        print(Fore.YELLOW + "----- Sending Personalized Email -----\n" + Style.RESET_ALL)

        lead = state["current_lead"]
        email_body = state["personalized_email"]

        # Generate subject line
        subject = self._generate_subject(lead, email_body)

        # Send via SendGrid
        send_id, success = self.email_sender.send_email(
            lead_id=lead.id,
            to_email=lead.email,
            subject=subject,
            html_content=email_body
        )

        if success:
            print(Fore.GREEN + f"✅ Email sent successfully to {lead.email}" + Style.RESET_ALL)
        else:
            print(Fore.RED + f"❌ Failed to send email to {lead.email}" + Style.RESET_ALL)

        return {
            "email_send_id": send_id,
            "email_sent_success": success
        }

    def _generate_subject(self, lead, email_body):
        """Generate subject line from email body or use default"""
        # Extract first line or use LLM to generate
        lines = email_body.split('\n')
        for line in lines:
            if line.strip() and not line.startswith('<'):
                return line.strip()[:100]

        # Default subject
        return f"Quick question about {lead.company_name if hasattr(lead, 'company_name') else 'your business'}"
```

**Update `src/graph.py`**:

```python
from src.nodes_email import EmailNodes

class OutReachAutomation:
    def __init__(self, loader: LeadLoaderBase):
        self.app = self.build_graph(loader)

    def build_graph(self, loader):
        graph = StateGraph(GraphState)

        nodes = OutReachAutomationNodes(loader)
        email_nodes = EmailNodes()  # ← Add this

        # ... existing nodes ...

        # Add email sending node
        graph.add_node("send_personalized_email", email_nodes.send_personalized_email)

        # Update edges
        graph.add_edge("generate_personalized_email", "send_personalized_email")
        graph.add_edge("send_personalized_email", "await_reports_creation")

        return graph.compile()
```

**Update `src/state.py`**:

```python
class GraphState(TypedDict):
    # ... existing fields ...
    email_send_id: str  # UUID of email send record
    email_sent_success: bool
```

---

### Day 3: Testing Email Sending

#### Test Script

**File: `tests/test_email_sending.py`**

```python
import os
from dotenv import load_dotenv
from src.tools.email.email_sender import EmailSender

load_dotenv()

def test_send_email():
    sender = EmailSender()

    # Test with your personal email
    test_email = "your-email@gmail.com"  # ← Change this

    send_id, success = sender.send_email(
        lead_id="test-lead-123",
        to_email=test_email,
        subject="Test Email from AI SDR",
        html_content="""
        <html>
        <body>
            <h2>Hello from AI SDR!</h2>
            <p>This is a test email to verify SendGrid integration.</p>
            <p><a href="https://example.com">Click here</a> to test click tracking.</p>
        </body>
        </html>
        """
    )

    print(f"Send ID: {send_id}")
    print(f"Success: {success}")

    # Check status
    import time
    time.sleep(5)

    status = sender.get_send_status(send_id)
    print(f"Status: {status}")

if __name__ == "__main__":
    test_send_email()
```

Run:
```bash
python tests/test_email_sending.py
```

**Expected Output**:
```
Send ID: 123e4567-e89b-12d3-a456-426614174000
Success: True
Status: {'status': 'sent', 'opened_at': None, 'open_count': 0, ...}
```

**Check your email**:
1. Verify email received
2. Open it (should track open)
3. Click link (should track click)
4. Check database: `SELECT * FROM email_events;`

---

## ✅ Day 1-3 Checklist

- [ ] PostgreSQL installed and running
- [ ] Redis installed and running
- [ ] Database schema created
- [ ] SendGrid API key obtained and verified
- [ ] `email_sender.py` module created
- [ ] Webhook endpoint created (`webhooks.py`)
- [ ] ngrok running for local webhook testing
- [ ] SendGrid webhook configured
- [ ] Test email sent successfully
- [ ] Open tracking working
- [ ] Click tracking working
- [ ] Database recording events

---

**When ready, I'll create Day 4-7 (Reply Monitoring) and Day 8-14 (Sequences & Follow-ups)!**

Would you like me to continue with:
1. 📧 **Reply monitoring & automated responses** (Days 4-7)
2. 🔄 **Follow-up sequences & automation** (Days 8-14)
3. 🔥 **Email warmup system** (Days 15-21)
4. ⚡ **All of the above** (complete 4-week plan)

Let me know and I'll create detailed implementation guides for each phase! 🚀
