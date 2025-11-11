# SaaS Architecture: Multi-Tenant AI SDR Platform

## 🏗️ System Architecture Overview

Transform your single-tenant LangGraph application into a **multi-tenant SaaS platform** with organization isolation, usage limits, and billing integration.

---

## Architecture Diagram

```
┌───────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                            │
├───────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐              │
│  │  Web App   │  │   API      │  │   Mobile   │              │
│  │ (Next.js)  │  │ Clients    │  │  (Future)  │              │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘              │
│        │               │               │                       │
│        └───────────────┴───────────────┘                       │
│                        ↓                                       │
├───────────────────────────────────────────────────────────────┤
│                     API GATEWAY                                │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  • Authentication (JWT + Clerk/Auth0)                  │   │
│  │  • Rate Limiting (per org, per tier)                   │   │
│  │  • Request Routing                                     │   │
│  │  • Logging & Monitoring                                │   │
│  └────────────────────────────────────────────────────────┘   │
│                        ↓                                       │
├───────────────────────────────────────────────────────────────┤
│                   APPLICATION LAYER                            │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                FastAPI Backend                          │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │  │
│  │  │ Organization │  │   Campaign   │  │   Lead       │ │  │
│  │  │   Service    │  │   Service    │  │  Service     │ │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘ │  │
│  │                                                          │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │  │
│  │  │    Email     │  │   Billing    │  │   Analytics  │ │  │
│  │  │   Service    │  │   Service    │  │   Service    │ │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘ │  │
│  └─────────────────────────────────────────────────────────┘  │
│                        ↓                                       │
├───────────────────────────────────────────────────────────────┤
│                  WORKFLOW ENGINE LAYER                         │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │         LangGraph Orchestration (Your Existing Code)    │  │
│  │                                                          │  │
│  │  [Research] → [Generate] → [Send] → [Monitor] → [Follow]│  │
│  │                                                          │  │
│  │  • Isolated per organization (org_id context)           │  │
│  │  • Resource limits per tier                             │  │
│  │  • Parallel execution (Celery workers)                  │  │
│  └─────────────────────────────────────────────────────────┘  │
│                        ↓                                       │
├───────────────────────────────────────────────────────────────┤
│                      DATA LAYER                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │  PostgreSQL  │  │    Redis     │  │    S3        │        │
│  │  (Supabase)  │  │  (Caching)   │  │  (Reports)   │        │
│  │              │  │  (Queues)    │  │              │        │
│  │  + RLS       │  │              │  │              │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
│                                                                 │
├───────────────────────────────────────────────────────────────┤
│                   INTEGRATION LAYER                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │   SendGrid   │  │   Stripe     │  │    OpenAI    │        │
│  │   (Email)    │  │  (Billing)   │  │    (LLM)     │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │   LinkedIn   │  │   HubSpot    │  │   Calendar   │        │
│  │  (Research)  │  │    (CRM)     │  │   (Google)   │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
└───────────────────────────────────────────────────────────────┘
```

---

## Database Schema (Multi-Tenant)

### Core Tables

```sql
-- ============================================
-- ORGANIZATION & USER MANAGEMENT
-- ============================================

CREATE TABLE organizations (
    org_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_name VARCHAR(255) NOT NULL,
    org_slug VARCHAR(100) UNIQUE NOT NULL,  -- for URLs: app.yourdomain.com/acme-corp

    -- Subscription
    plan_tier VARCHAR(50) NOT NULL DEFAULT 'starter',  -- starter, growth, scale, enterprise
    stripe_customer_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255),

    -- Limits based on tier
    monthly_lead_limit INT NOT NULL DEFAULT 500,
    email_account_limit INT NOT NULL DEFAULT 1,
    user_seat_limit INT NOT NULL DEFAULT 1,

    -- Trial
    trial_ends_at TIMESTAMP,
    is_trial BOOLEAN DEFAULT TRUE,

    -- Status
    status VARCHAR(50) DEFAULT 'active',  -- active, suspended, cancelled, past_due

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP  -- soft delete
);

-- Indexes
CREATE INDEX idx_org_status ON organizations(status);
CREATE INDEX idx_org_trial ON organizations(is_trial, trial_ends_at);

---

CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(org_id) ON DELETE CASCADE,

    -- Authentication
    email VARCHAR(255) UNIQUE NOT NULL,
    clerk_user_id VARCHAR(255) UNIQUE,  -- if using Clerk

    -- Profile
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    avatar_url TEXT,

    -- Role
    role VARCHAR(50) NOT NULL DEFAULT 'member',  -- owner, admin, member

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    last_login_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_user_org ON users(org_id);
CREATE INDEX idx_user_email ON users(email);

---

-- ============================================
-- EMAIL ACCOUNTS (Multi-tenant)
-- ============================================

CREATE TABLE email_accounts (
    account_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(org_id) ON DELETE CASCADE,

    -- Email Config
    email_address VARCHAR(255) NOT NULL,
    smtp_host VARCHAR(255),
    smtp_port INT,
    smtp_username VARCHAR(255),
    smtp_password_encrypted TEXT,  -- encrypt before storing!

    -- SendGrid Alternative
    sendgrid_api_key_encrypted TEXT,

    -- Status
    status VARCHAR(50) DEFAULT 'pending',  -- pending, active, warming, suspended
    warmup_stage INT DEFAULT 1,  -- 1-4 (see warmup schedule)
    warmup_started_at TIMESTAMP,

    -- Limits
    daily_send_limit INT DEFAULT 50,
    current_daily_sends INT DEFAULT 0,
    last_send_date DATE,

    -- Health
    bounce_rate DECIMAL(5,2) DEFAULT 0.00,
    spam_rate DECIMAL(5,2) DEFAULT 0.00,
    deliverability_score INT DEFAULT 100,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_email_org ON email_accounts(org_id);
CREATE INDEX idx_email_status ON email_accounts(status);

---

-- ============================================
-- LEADS (Multi-tenant with RLS)
-- ============================================

CREATE TABLE leads (
    lead_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(org_id) ON DELETE CASCADE,

    -- Basic Info
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    company_name VARCHAR(255),
    job_title VARCHAR(255),

    -- Source
    source VARCHAR(100),  -- crm, csv_upload, manual, api
    crm_id VARCHAR(255),  -- HubSpot/Salesforce ID

    -- Research Data (JSON for flexibility)
    linkedin_profile JSONB,
    company_data JSONB,
    social_media_data JSONB,

    -- Scoring
    lead_score INT DEFAULT 0,
    intent_score INT DEFAULT 0,
    qualification_status VARCHAR(50) DEFAULT 'new',  -- new, qualified, unqualified

    -- Status
    outreach_status VARCHAR(50) DEFAULT 'new',  -- new, in_progress, contacted, replied, meeting_booked, closed

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_contacted_at TIMESTAMP
);

-- Row-Level Security (RLS)
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see leads from their org
CREATE POLICY tenant_isolation_leads ON leads
    FOR ALL
    USING (org_id = current_setting('app.current_org_id', TRUE)::UUID);

CREATE INDEX idx_lead_org ON leads(org_id);
CREATE INDEX idx_lead_email ON leads(email);
CREATE INDEX idx_lead_status ON leads(outreach_status);

---

-- ============================================
-- CAMPAIGNS (Multi-tenant)
-- ============================================

CREATE TABLE campaigns (
    campaign_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(org_id) ON DELETE CASCADE,
    created_by_user_id UUID REFERENCES users(user_id),

    -- Campaign Info
    campaign_name VARCHAR(255) NOT NULL,
    campaign_type VARCHAR(50) DEFAULT 'cold_outreach',  -- cold_outreach, follow_up, nurture

    -- Configuration
    sequence_config JSONB,  -- stores sequence steps
    email_account_id UUID REFERENCES email_accounts(account_id),

    -- Status
    status VARCHAR(50) DEFAULT 'draft',  -- draft, active, paused, completed

    -- Stats (denormalized for performance)
    leads_count INT DEFAULT 0,
    emails_sent INT DEFAULT 0,
    emails_opened INT DEFAULT 0,
    emails_clicked INT DEFAULT 0,
    emails_replied INT DEFAULT 0,
    meetings_booked INT DEFAULT 0,

    -- Schedule
    start_date TIMESTAMP,
    end_date TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_campaign_org ON campaigns(org_id);
CREATE INDEX idx_campaign_status ON campaigns(status);

---

-- ============================================
-- EMAIL TRACKING (Multi-tenant)
-- ============================================

CREATE TABLE email_sends (
    send_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(org_id) ON DELETE CASCADE,

    -- Relationships
    campaign_id UUID REFERENCES campaigns(campaign_id),
    lead_id UUID NOT NULL REFERENCES leads(lead_id),
    email_account_id UUID REFERENCES email_accounts(account_id),

    -- Email Content
    subject VARCHAR(500),
    body_html TEXT,
    body_text TEXT,

    -- Tracking
    sendgrid_message_id VARCHAR(255),
    tracking_pixel_token VARCHAR(100) UNIQUE,

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

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_email_org ON email_sends(org_id);
CREATE INDEX idx_email_campaign ON email_sends(campaign_id);
CREATE INDEX idx_email_lead ON email_sends(lead_id);
CREATE INDEX idx_email_status ON email_sends(status);
CREATE INDEX idx_tracking_token ON email_sends(tracking_pixel_token);

---

CREATE TABLE email_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    send_id UUID NOT NULL REFERENCES email_sends(send_id) ON DELETE CASCADE,

    -- Event Type
    event_type VARCHAR(50) NOT NULL,  -- open, click, bounce, spam, delivered, dropped
    event_timestamp TIMESTAMP DEFAULT NOW(),

    -- Metadata
    user_agent TEXT,
    ip_address VARCHAR(50),
    link_url TEXT,  -- for click events
    bounce_reason TEXT  -- for bounce events
);

CREATE INDEX idx_event_send ON email_events(send_id);
CREATE INDEX idx_event_type ON email_events(event_type);

---

-- ============================================
-- SEQUENCES & AUTOMATION
-- ============================================

CREATE TABLE lead_sequences (
    sequence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(org_id) ON DELETE CASCADE,

    -- Relationships
    lead_id UUID NOT NULL REFERENCES leads(lead_id),
    campaign_id UUID REFERENCES campaigns(campaign_id),

    -- Sequence State
    sequence_type VARCHAR(100) NOT NULL,  -- cold_outreach_5touch, follow_up_3touch
    current_step INT DEFAULT 1,
    total_steps INT NOT NULL,

    -- Schedule
    next_action_date TIMESTAMP,
    last_action_date TIMESTAMP,

    -- Status
    status VARCHAR(50) DEFAULT 'active',  -- active, paused, completed, stopped (reply received)
    stop_reason VARCHAR(100),  -- reply_received, unsubscribed, bounced

    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE INDEX idx_sequence_org ON lead_sequences(org_id);
CREATE INDEX idx_sequence_lead ON lead_sequences(lead_id);
CREATE INDEX idx_sequence_next_action ON lead_sequences(next_action_date, status);

---

-- ============================================
-- BILLING & USAGE
-- ============================================

CREATE TABLE usage_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(org_id) ON DELETE CASCADE,

    -- Usage Type
    usage_type VARCHAR(50) NOT NULL,  -- lead_processed, email_sent, api_call
    quantity INT DEFAULT 1,

    -- Metadata
    resource_id UUID,  -- campaign_id, lead_id, etc.
    logged_at TIMESTAMP DEFAULT NOW(),

    -- Billing Period
    billing_period VARCHAR(20)  -- 2025-01, 2025-02, etc.
);

CREATE INDEX idx_usage_org_period ON usage_logs(org_id, billing_period);

---

CREATE TABLE invoices (
    invoice_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(org_id),

    -- Stripe
    stripe_invoice_id VARCHAR(255),

    -- Amount
    amount_cents INT NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',

    -- Period
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,

    -- Status
    status VARCHAR(50) DEFAULT 'pending',  -- pending, paid, failed, refunded
    paid_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_invoice_org ON invoices(org_id);

---

-- ============================================
-- FEATURE FLAGS & EXPERIMENTS
-- ============================================

CREATE TABLE feature_flags (
    flag_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flag_name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,

    -- Rollout
    is_enabled BOOLEAN DEFAULT FALSE,
    rollout_percentage INT DEFAULT 0,  -- 0-100

    -- Targeting
    allowed_orgs UUID[],  -- specific org_ids
    allowed_plans VARCHAR[],  -- starter, growth, etc.

    created_at TIMESTAMP DEFAULT NOW()
);

---

CREATE TABLE ab_tests (
    test_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(org_id),  -- NULL = global test

    -- Test Config
    test_name VARCHAR(255) NOT NULL,
    hypothesis TEXT,

    -- Variants (JSON)
    variants JSONB NOT NULL,  -- {A: {...}, B: {...}}
    traffic_split JSONB NOT NULL,  -- {A: 0.5, B: 0.5}

    -- Metrics
    success_metric VARCHAR(100) NOT NULL,  -- reply_rate, meeting_rate

    -- Status
    status VARCHAR(50) DEFAULT 'draft',  -- draft, running, completed
    winner_variant VARCHAR(10),

    -- Duration
    started_at TIMESTAMP,
    ended_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW()
);

---

-- ============================================
-- FUNCTIONS & TRIGGERS
-- ============================================

-- Auto-update updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to all tables with updated_at
CREATE TRIGGER update_organizations_updated_at BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_leads_updated_at BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Add more as needed...
```

---

## Backend Structure (FastAPI)

### Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry point
│   │
│   ├── core/
│   │   ├── config.py              # Environment config
│   │   ├── security.py            # JWT, encryption
│   │   ├── database.py            # DB connection + RLS
│   │   └── dependencies.py        # FastAPI dependencies
│   │
│   ├── models/                    # SQLAlchemy models
│   │   ├── organization.py
│   │   ├── user.py
│   │   ├── lead.py
│   │   ├── campaign.py
│   │   └── email.py
│   │
│   ├── schemas/                   # Pydantic schemas
│   │   ├── organization.py
│   │   ├── user.py
│   │   └── campaign.py
│   │
│   ├── api/                       # API routes
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py           # Login, signup
│   │   │   ├── organizations.py   # Org management
│   │   │   ├── campaigns.py       # Campaign CRUD
│   │   │   ├── leads.py           # Lead CRUD
│   │   │   ├── emails.py          # Email operations
│   │   │   ├── analytics.py       # Metrics endpoints
│   │   │   └── webhooks.py        # SendGrid, Stripe webhooks
│   │
│   ├── services/                  # Business logic
│   │   ├── campaign_service.py
│   │   ├── lead_service.py
│   │   ├── email_service.py
│   │   ├── billing_service.py
│   │   └── langgraph_service.py   # Wrapper for your LangGraph code
│   │
│   ├── workers/                   # Background jobs
│   │   ├── celery_app.py
│   │   ├── tasks/
│   │   │   ├── email_sender.py
│   │   │   ├── email_monitor.py
│   │   │   ├── sequence_processor.py
│   │   │   └── warmup_manager.py
│   │
│   └── integrations/              # External APIs
│       ├── sendgrid_client.py
│       ├── stripe_client.py
│       ├── clerk_client.py
│       └── crm_clients/
│           ├── hubspot.py
│           └── salesforce.py
│
├── migrations/                    # Alembic migrations
├── tests/
└── requirements.txt
```

---

### Key Implementation Files

#### `app/core/database.py` - Multi-Tenant Database

```python
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
import os

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

@contextmanager
def get_db_session(org_id: str = None):
    """
    Database session with automatic Row-Level Security (RLS) context.
    Sets current_org_id for tenant isolation.
    """
    session = SessionLocal()
    try:
        if org_id:
            # Set RLS context for this session
            session.execute(f"SET app.current_org_id = '{org_id}'")

        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

---

#### `app/core/dependencies.py` - Auth & Org Context

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import os

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Validate JWT token and extract user info.
    Works with Clerk, Auth0, or custom JWT.
    """
    token = credentials.credentials

    try:
        # Decode JWT
        payload = jwt.decode(
            token,
            os.getenv("JWT_SECRET"),
            algorithms=["HS256"]
        )

        user_id: str = payload.get("sub")
        org_id: str = payload.get("org_id")

        if user_id is None or org_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )

        return {
            "user_id": user_id,
            "org_id": org_id,
            "email": payload.get("email"),
            "role": payload.get("role", "member")
        }

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

async def get_current_org(
    current_user: dict = Depends(get_current_user)
) -> str:
    """Extract organization ID from current user."""
    return current_user["org_id"]

async def check_tier_limits(
    current_user: dict = Depends(get_current_user)
):
    """
    Check if organization is within tier limits.
    Raise exception if quota exceeded.
    """
    from app.services.billing_service import BillingService

    billing_service = BillingService()
    usage = billing_service.get_current_usage(current_user["org_id"])
    limits = billing_service.get_tier_limits(current_user["org_id"])

    if usage["leads_this_month"] >= limits["monthly_leads"]:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Monthly lead quota exceeded. Please upgrade your plan."
        )
```

---

#### `app/api/v1/campaigns.py` - Campaign API

```python
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.core.dependencies import get_current_org, check_tier_limits
from app.services.campaign_service import CampaignService
from app.schemas.campaign import CampaignCreate, CampaignResponse

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

@router.post("/", response_model=CampaignResponse)
async def create_campaign(
    campaign: CampaignCreate,
    org_id: str = Depends(get_current_org),
    _ = Depends(check_tier_limits)  # Check quota
):
    """
    Create a new campaign.
    Automatically queues leads for research and email generation.
    """
    service = CampaignService(org_id)

    # Create campaign
    new_campaign = service.create_campaign(campaign.dict())

    # Queue leads for processing (async with Celery)
    from app.workers.tasks.campaign_processor import process_campaign_leads
    process_campaign_leads.delay(campaign_id=new_campaign.id, org_id=org_id)

    return new_campaign

@router.get("/", response_model=List[CampaignResponse])
async def list_campaigns(
    org_id: str = Depends(get_current_org)
):
    """
    List all campaigns for the organization.
    Row-Level Security automatically filters by org_id.
    """
    service = CampaignService(org_id)
    return service.list_campaigns()

@router.get("/{campaign_id}/analytics")
async def get_campaign_analytics(
    campaign_id: str,
    org_id: str = Depends(get_current_org)
):
    """
    Get detailed analytics for a campaign.
    """
    service = CampaignService(org_id)
    analytics = service.get_analytics(campaign_id)

    if not analytics:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return {
        "campaign_id": campaign_id,
        "emails_sent": analytics["emails_sent"],
        "open_rate": analytics["emails_opened"] / analytics["emails_sent"] if analytics["emails_sent"] > 0 else 0,
        "reply_rate": analytics["emails_replied"] / analytics["emails_sent"] if analytics["emails_sent"] > 0 else 0,
        "meeting_rate": analytics["meetings_booked"] / analytics["emails_sent"] if analytics["emails_sent"] > 0 else 0,
        "timeline_data": analytics["timeline"]
    }
```

---

#### `app/services/langgraph_service.py` - LangGraph Integration

```python
from src.graph import OutReachAutomation
from src.tools.leads_loader.supabase_loader import SupabaseLeadLoader

class LangGraphService:
    """
    Wrapper for your existing LangGraph automation.
    Adds org_id context for multi-tenancy.
    """

    def __init__(self, org_id: str):
        self.org_id = org_id

        # Initialize with org-specific loader
        loader = SupabaseLeadLoader(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY"),
            table_name="leads",
            org_id_filter=org_id  # ← Filter by organization
        )

        self.automation = OutReachAutomation(loader)

    def process_lead(self, lead_id: str):
        """
        Run LangGraph workflow for a single lead.
        """
        inputs = {"leads_ids": [lead_id]}
        config = {
            'recursion_limit': 1000,
            'org_id': self.org_id  # Pass to nodes for context
        }

        output = self.automation.app.invoke(inputs, config)
        return output

    def process_campaign_leads(self, campaign_id: str, lead_ids: List[str]):
        """
        Run LangGraph workflow for all leads in a campaign.
        Processes in batches to avoid memory issues.
        """
        batch_size = 10

        for i in range(0, len(lead_ids), batch_size):
            batch = lead_ids[i:i+batch_size]
            inputs = {"leads_ids": batch}
            config = {
                'recursion_limit': 1000,
                'org_id': self.org_id,
                'campaign_id': campaign_id
            }

            self.automation.app.invoke(inputs, config)
```

---

## Authentication Integration

### Option 1: Clerk (Recommended - Easiest)

```python
# Install: pip install clerk-backend-api

from clerk_backend_api import Clerk

clerk = Clerk(bearer_auth=os.getenv("CLERK_SECRET_KEY"))

# In your signup endpoint
@router.post("/signup")
async def signup(email: str, password: str, org_name: str):
    # Create user in Clerk
    clerk_user = clerk.users.create(
        email_address=[email],
        password=password
    )

    # Create organization in your DB
    org = create_organization(org_name)

    # Link user to org
    create_user(
        clerk_user_id=clerk_user.id,
        org_id=org.id,
        email=email,
        role="owner"
    )

    return {"org_id": org.id, "user_id": clerk_user.id}
```

### Option 2: Auth0 (Enterprise-grade)

```python
# Similar integration with Auth0 Management API
```

### Option 3: Custom JWT (Most control)

```python
from jose import jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(user_id: str, org_id: str, role: str):
    expire = datetime.utcnow() + timedelta(hours=24)

    to_encode = {
        "sub": user_id,
        "org_id": org_id,
        "role": role,
        "exp": expire
    }

    encoded_jwt = jwt.encode(
        to_encode,
        os.getenv("JWT_SECRET"),
        algorithm="HS256"
    )

    return encoded_jwt
```

---

## Billing Integration (Stripe)

```python
# app/services/billing_service.py
import stripe
import os

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

class BillingService:
    PLAN_PRICES = {
        "starter": "price_1AbCdEfGhIjKlMnO",  # Stripe price ID
        "growth": "price_2XyZaBcDeFgHiJkL",
        "scale": "price_3QwErTyUiOpAsDfG"
    }

    def create_subscription(self, org_id: str, email: str, plan_tier: str):
        """Create Stripe customer and subscription."""

        # Create Stripe customer
        customer = stripe.Customer.create(
            email=email,
            metadata={"org_id": org_id}
        )

        # Create subscription
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{"price": self.PLAN_PRICES[plan_tier]}],
            trial_period_days=14
        )

        # Update organization
        update_organization(
            org_id=org_id,
            stripe_customer_id=customer.id,
            stripe_subscription_id=subscription.id
        )

        return subscription

    def handle_webhook(self, event):
        """Handle Stripe webhook events."""

        if event.type == "invoice.payment_succeeded":
            # Payment successful → keep subscription active
            pass

        elif event.type == "invoice.payment_failed":
            # Payment failed → suspend organization
            customer_id = event.data.object.customer
            suspend_organization_by_stripe_customer(customer_id)

        elif event.type == "customer.subscription.deleted":
            # Subscription cancelled → mark org as cancelled
            cancel_organization_by_subscription(event.data.object.id)
```

**Webhook endpoint**:
```python
@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
        )

        billing_service = BillingService()
        billing_service.handle_webhook(event)

        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

---

## Deployment Strategy

### Development Environment
```yaml
Frontend: localhost:3000 (Next.js)
Backend: localhost:8000 (FastAPI)
Database: localhost:5432 (PostgreSQL)
Redis: localhost:6379
Celery Worker: Local process
```

### Production Deployment

**Option 1: Railway (Easiest)**
```yaml
Services:
  - FastAPI Backend (auto-scaling)
  - PostgreSQL (managed)
  - Redis (managed)
  - Celery Worker (separate service)

Cost: ~$50-100/month (starter scale)
Setup time: 30 minutes
```

**Option 2: AWS (Scalable)**
```yaml
- EC2/ECS for backend
- RDS for PostgreSQL
- ElastiCache for Redis
- S3 for file storage
- CloudFront for CDN

Cost: ~$100-300/month (optimized)
Setup time: 1-2 days
```

---

## Next Steps

1. **Week 1**: Implement multi-tenant database schema
2. **Week 2**: Set up authentication (Clerk) + billing (Stripe)
3. **Week 3-4**: Build API endpoints with org isolation
4. **Week 5**: Integrate your existing LangGraph code
5. **Week 6**: Build frontend (Next.js dashboard)
6. **Week 7-8**: Testing + beta launch

**Ready to start building? Let me know which part you want to tackle first!** 🚀
