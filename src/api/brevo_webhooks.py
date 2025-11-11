"""
Brevo Webhook Handler
Processes email events: delivered, opened, clicked, bounced, etc.
"""

from fastapi import FastAPI, Request, HTTPException
import psycopg2
from datetime import datetime
import os
import hmac
import hashlib

app = FastAPI()


def verify_brevo_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify Brevo webhook signature.
    Note: Brevo may not send signatures for all webhooks.
    Check your webhook configuration.
    """
    if not signature or not secret:
        return True  # Skip verification if not configured

    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected)


@app.post("/webhooks/brevo")
async def brevo_webhook(request: Request):
    """
    Handle Brevo transactional email webhooks.

    Brevo sends events to this endpoint when configured.
    Event types:
    - request: Email request received
    - delivered: Email delivered
    - hard_bounce / soft_bounce: Bounced
    - invalid_email: Invalid recipient
    - deferred: Temporarily deferred
    - click: Link clicked
    - opened: Email opened (if tracking enabled)
    - spam: Marked as spam
    - blocked: Blocked by Brevo
    - unsubscribe: User unsubscribed
    """

    # Get payload
    payload = await request.body()
    signature = request.headers.get("X-Brevo-Signature", "")

    # Verify signature (optional, configure in Brevo)
    webhook_secret = os.getenv("BREVO_WEBHOOK_SECRET", "")
    if webhook_secret and not verify_brevo_signature(payload, signature, webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse event
    event_data = await request.json()

    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    cur = conn.cursor()

    try:
        # Brevo webhook structure
        event_type = event_data.get('event')
        email = event_data.get('email')
        message_id = event_data.get('message-id')  # Brevo message ID
        timestamp = datetime.fromtimestamp(event_data.get('ts', 0))

        # Optional fields
        link = event_data.get('link')  # For click events
        reason = event_data.get('reason')  # For bounces
        tag = event_data.get('tag')  # Custom tag

        # Find email send record by Brevo message ID
        cur.execute("""
            SELECT send_id FROM email_sends
            WHERE sendgrid_message_id = %s
        """, (message_id,))

        result = cur.fetchone()
        if not result:
            print(f"⚠️ Email send not found for message_id: {message_id}")
            return {"status": "ignored", "reason": "send_id not found"}

        send_id = result[0]

        # Log event to email_events table
        cur.execute("""
            INSERT INTO email_events
            (send_id, event_type, event_timestamp, link_url, user_agent, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            send_id,
            event_type,
            timestamp,
            link,
            event_data.get('user_agent'),
            event_data.get('ip')
        ))

        # Update email_sends table based on event type
        if event_type == 'delivered':
            cur.execute("""
                UPDATE email_sends
                SET status = 'delivered', delivered_at = %s
                WHERE send_id = %s
            """, (timestamp, send_id))

        elif event_type == 'opened':
            # Brevo tracks opens if enabled
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

        elif event_type in ['hard_bounce', 'soft_bounce', 'invalid_email', 'blocked']:
            cur.execute("""
                UPDATE email_sends
                SET status = 'bounced'
                WHERE send_id = %s
            """, (send_id,))

        elif event_type == 'spam':
            cur.execute("""
                UPDATE email_sends
                SET status = 'spam'
                WHERE send_id = %s
            """, (send_id,))

        elif event_type == 'unsubscribe':
            # Mark lead as unsubscribed
            cur.execute("""
                UPDATE leads
                SET outreach_status = 'unsubscribed'
                WHERE email = %s
            """, (email,))

        conn.commit()

        print(f"✅ Processed Brevo event: {event_type} for {email}")

        return {
            "status": "success",
            "event": event_type,
            "send_id": str(send_id)
        }

    except Exception as e:
        conn.rollback()
        print(f"❌ Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cur.close()
        conn.close()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "brevo-webhooks"}


# To run locally:
# uvicorn src.api.brevo_webhooks:app --reload --port 8000
#
# For production, use:
# uvicorn src.api.brevo_webhooks:app --host 0.0.0.0 --port 8000
