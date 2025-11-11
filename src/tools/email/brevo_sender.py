"""
Brevo (Sendinblue) Email Sender
Handles transactional email sending with tracking via Brevo API
"""

import os
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
import uuid
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor


class BrevoEmailSender:
    def __init__(self):
        # Configure Brevo API
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = os.getenv('BREVO_API_KEY')

        self.api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )

        # Email config
        self.sender_email = os.getenv('SENDER_EMAIL')
        self.sender_name = os.getenv('SENDER_NAME', 'AI SDR')
        self.tracking_domain = os.getenv('TRACKING_DOMAIN')

        # Database connection
        self.db_url = os.getenv('DATABASE_URL')

    def _get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(self.db_url)

    def generate_tracking_pixel(self, tracking_token):
        """Generate tracking pixel HTML"""
        pixel_url = f"{self.tracking_domain}/track/{tracking_token}/open.gif"
        return f'<img src="{pixel_url}" width="1" height="1" alt="" style="display:none;" />'

    def send_email(self, lead_id, to_email, to_name, subject, html_content, reply_to_email=None):
        """
        Send email via Brevo with tracking.

        Args:
            lead_id: Lead identifier
            to_email: Recipient email
            to_name: Recipient name
            subject: Email subject
            html_content: HTML email body
            reply_to_email: Optional reply-to email

        Returns:
            tuple: (send_id, success)
        """

        # Generate unique tracking token
        tracking_token = str(uuid.uuid4())[:16]

        # Add tracking pixel to email
        tracking_pixel = self.generate_tracking_pixel(tracking_token)
        html_with_tracking = html_content + tracking_pixel

        # Prepare email
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            sender={"name": self.sender_name, "email": self.sender_email},
            to=[{"email": to_email, "name": to_name}],
            subject=subject,
            html_content=html_with_tracking,
            tags=["ai_sdr", "cold_outreach", f"lead_{lead_id}"],
            # Enable tracking
            params={
                "tracking_token": tracking_token,
                "lead_id": lead_id
            }
        )

        # Add reply-to if specified
        if reply_to_email:
            send_smtp_email.reply_to = {"email": reply_to_email}

        try:
            # Send via Brevo
            api_response = self.api_instance.send_transac_email(send_smtp_email)

            # Brevo returns message-id
            brevo_message_id = api_response.message_id

            print(f"✅ Email sent via Brevo. Message ID: {brevo_message_id}")

            # Log to database
            send_id = self._log_email_send(
                lead_id=lead_id,
                lead_email=to_email,
                subject=subject,
                body_html=html_content,
                tracking_token=tracking_token,
                brevo_message_id=brevo_message_id,
                status='sent'
            )

            return send_id, True

        except ApiException as e:
            print(f"❌ Brevo API Error: {e}")

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
                       tracking_token, brevo_message_id=None, status='queued'):
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
                brevo_message_id,  # Using same column for Brevo ID
                status,
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

    def get_account_stats(self, days=7):
        """
        Get sending statistics from Brevo API.

        Returns:
            dict: Statistics including sent, delivered, opened, clicked
        """
        try:
            # Use Brevo's statistics API
            from datetime import timedelta

            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            stats_api = sib_api_v3_sdk.EmailCampaignsApi(
                sib_api_v3_sdk.ApiClient(configuration)
            )

            # Note: Brevo's stats API is primarily for campaigns
            # For transactional emails, use webhook data or database queries
            conn = self._get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                SELECT
                    COUNT(*) as total_sent,
                    SUM(CASE WHEN status = 'delivered' THEN 1 ELSE 0 END) as delivered,
                    SUM(CASE WHEN opened_at IS NOT NULL THEN 1 ELSE 0 END) as opened,
                    SUM(CASE WHEN clicked_at IS NOT NULL THEN 1 ELSE 0 END) as clicked,
                    SUM(CASE WHEN replied_at IS NOT NULL THEN 1 ELSE 0 END) as replied,
                    SUM(CASE WHEN status = 'bounced' THEN 1 ELSE 0 END) as bounced
                FROM email_sends
                WHERE sent_at >= NOW() - INTERVAL '%s days'
            """, (days,))

            stats = cur.fetchone()
            cur.close()
            conn.close()

            return {
                'sent': stats['total_sent'],
                'delivered': stats['delivered'],
                'opened': stats['opened'],
                'clicked': stats['clicked'],
                'replied': stats['replied'],
                'bounced': stats['bounced'],
                'open_rate': (stats['opened'] / stats['total_sent'] * 100) if stats['total_sent'] > 0 else 0,
                'click_rate': (stats['clicked'] / stats['total_sent'] * 100) if stats['total_sent'] > 0 else 0,
                'reply_rate': (stats['replied'] / stats['total_sent'] * 100) if stats['total_sent'] > 0 else 0
            }

        except Exception as e:
            print(f"Error getting stats: {e}")
            return {}

    def verify_sender_domain(self):
        """
        Check if sender domain is verified in Brevo.
        This is required before sending.
        """
        try:
            senders_api = sib_api_v3_sdk.SendersApi(
                sib_api_v3_sdk.ApiClient(configuration)
            )

            senders = senders_api.get_senders()

            for sender in senders.senders:
                if sender.email == self.sender_email:
                    return {
                        'verified': True,
                        'email': sender.email,
                        'name': sender.name
                    }

            return {'verified': False, 'message': 'Sender not found'}

        except ApiException as e:
            print(f"Error checking sender: {e}")
            return {'verified': False, 'error': str(e)}


# Backwards compatibility alias
EmailSender = BrevoEmailSender
