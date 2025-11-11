# Brevo (Sendinblue) Setup Guide

Complete setup guide for using Brevo as your email service provider.

---

## Why Brevo?

✅ **300 emails/day FREE forever** (vs SendGrid's 100/day)
✅ **Built-in email warmup** tools
✅ **Transactional + Marketing** in one platform
✅ **Better pricing** for startups ($25/mo for 20K emails)
✅ **Excellent deliverability** (98%+ inbox rate)
✅ **Built-in CRM** for contact management
✅ **SMS included** (for future multi-channel)

---

## Step 1: Create Brevo Account

### 1.1 Sign Up

Go to: https://www.brevo.com/

- Click "Sign up free"
- Enter email and create password
- Verify your email address

**Free Plan Includes**:
- 300 emails per day
- Unlimited contacts
- Email campaigns
- Transactional emails
- Drag & drop editor
- Basic reporting

---

### 1.2 Complete Account Setup

1. **Business Information**:
   - Company name
   - Website URL
   - Phone number (optional)

2. **Verify Your Identity**:
   - Brevo may ask for identity verification
   - Upload ID or business documents
   - Usually approved within 24 hours

---

## Step 2: Verify Sender Domain

### 2.1 Add Sender Email

1. Go to **Senders & IP** → **Senders**
2. Click **Add a sender**
3. Enter:
   - Email: `noreply@yourdomain.com`
   - Name: `Your Company Name`

Brevo will send verification email → Click link

---

### 2.2 Authenticate Domain (Required for Production)

**Why?** Improves deliverability and prevents spam folder

1. Go to **Senders & IP** → **Domains**
2. Click **Authenticate a domain**
3. Enter your domain: `yourdomain.com`

**DNS Records to Add**:

Brevo provides 3 DNS records:

**SPF Record** (TXT):
```
v=spf1 include:spf.sendinblue.com ~all
```

**DKIM Record** (TXT):
```
k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC...
```

**DMARC Record** (TXT):
```
v=DMARC1; p=none; rua=mailto:dmarc@yourdomain.com
```

**Where to Add DNS Records**:
- **Namecheap**: Advanced DNS → Add New Record
- **GoDaddy**: DNS Management → Add
- **Cloudflare**: DNS → Add record
- **Google Domains**: DNS → Custom records

**Verification**: Takes 24-48 hours for DNS propagation

---

### 2.3 Check Authentication Status

Go to **Domains** page:
- ✅ Green checkmark = Authenticated
- ⏳ Orange = Pending verification
- ❌ Red = Failed (check DNS records)

---

## Step 3: Get API Key

### 3.1 Create API Key

1. Go to **Settings** (top right)
2. Click **SMTP & API**
3. Go to **API Keys** tab
4. Click **Generate a new API key**

**Key Details**:
- Name: `AI SDR Production`
- Choose: **v3 API key** (latest version)

**⚠️ Important**: Copy the API key immediately (shown only once!)

---

### 3.2 Add to .env File

```env
# Brevo API Configuration
BREVO_API_KEY=xkeysib-abc123def456...

# Sender Configuration
SENDER_EMAIL=noreply@yourdomain.com
SENDER_NAME=Your Company Name

# Tracking Domain
TRACKING_DOMAIN=https://yourdomain.com

# Webhook Secret (optional, set in Step 4)
BREVO_WEBHOOK_SECRET=your-random-secret-key
```

---

## Step 4: Configure Webhooks

### 4.1 Set Up Webhook URL

**For Local Development** (use ngrok):
```bash
# Install ngrok
brew install ngrok  # Mac
# or download from https://ngrok.com

# Start your FastAPI app
uvicorn src.api.brevo_webhooks:app --reload --port 8000

# In another terminal, start ngrok
ngrok http 8000

# Copy the HTTPS URL: https://abc123.ngrok.io
```

**For Production**:
```
https://api.yourdomain.com/webhooks/brevo
```

---

### 4.2 Configure in Brevo Dashboard

1. Go to **Settings** → **Webhooks**
2. Click **Add a new webhook**
3. Enter:
   - **URL**: `https://your-domain.com/webhooks/brevo`
   - **Events to track**:
     - ✅ Email delivered
     - ✅ Email opened
     - ✅ Email clicked
     - ✅ Hard bounces
     - ✅ Soft bounces
     - ✅ Spam reports
     - ✅ Unsubscribed

4. Click **Save**

**Test Webhook**:
- Brevo provides "Test" button
- Should return `200 OK`

---

## Step 5: Install Python SDK

### 5.1 Install Dependencies

```bash
pip install sib-api-v3-sdk psycopg2-binary fastapi uvicorn
```

### 5.2 Update requirements.txt

```txt
# Add these lines
sib-api-v3-sdk==7.6.0
fastapi==0.104.1
uvicorn==0.24.0
psycopg2-binary==2.9.9
```

---

## Step 6: Test Email Sending

### 6.1 Test Script

Create: `tests/test_brevo_sending.py`

```python
import os
from dotenv import load_dotenv
from src.tools.email.brevo_sender import BrevoEmailSender

load_dotenv()

def test_brevo():
    sender = BrevoEmailSender()

    # Check domain verification
    verification = sender.verify_sender_domain()
    print(f"Domain verified: {verification}")

    # Send test email
    send_id, success = sender.send_email(
        lead_id="test-lead-123",
        to_email="your-email@gmail.com",  # ← Your email
        to_name="Test User",
        subject="Test Email from AI SDR (Brevo)",
        html_content="""
        <html>
        <body>
            <h2>Hello from AI SDR!</h2>
            <p>This is a test email via Brevo.</p>
            <p><a href="https://example.com">Click here</a> to test tracking.</p>
            <br>
            <p style="color: #888; font-size: 12px;">
                Sent via Brevo Email API
            </p>
        </body>
        </html>
        """
    )

    print(f"\n✅ Test Results:")
    print(f"   Send ID: {send_id}")
    print(f"   Success: {success}")

    # Wait and check status
    import time
    time.sleep(5)

    status = sender.get_send_status(send_id)
    print(f"\n📊 Email Status:")
    print(f"   Status: {status['status']}")
    print(f"   Sent at: {status['sent_at']}")

    # Get account stats
    stats = sender.get_account_stats(days=7)
    print(f"\n📈 Account Stats (Last 7 Days):")
    print(f"   Sent: {stats.get('sent', 0)}")
    print(f"   Open Rate: {stats.get('open_rate', 0):.1f}%")
    print(f"   Click Rate: {stats.get('click_rate', 0):.1f}%")

if __name__ == "__main__":
    test_brevo()
```

Run:
```bash
python tests/test_brevo_sending.py
```

---

### 6.2 Expected Output

```
Domain verified: {'verified': True, 'email': 'noreply@yourdomain.com', 'name': 'Your Company'}
✅ Email sent via Brevo. Message ID: <abc123@smtp-relay.brevo.com>

✅ Test Results:
   Send ID: 123e4567-e89b-12d3-a456-426614174000
   Success: True

📊 Email Status:
   Status: sent
   Sent at: 2025-01-11 10:30:45

📈 Account Stats (Last 7 Days):
   Sent: 1
   Open Rate: 0.0%
   Click Rate: 0.0%
```

---

### 6.3 Check Your Inbox

1. **Verify email received**
2. **Open the email** → Check database:
   ```sql
   SELECT * FROM email_events WHERE event_type = 'opened';
   ```
3. **Click the link** → Check database:
   ```sql
   SELECT * FROM email_events WHERE event_type = 'click';
   ```

---

## Step 7: Brevo vs SendGrid Comparison

### Pricing Comparison

| Volume | Brevo | SendGrid |
|--------|-------|----------|
| **Free Tier** | 300/day (9K/month) | 100/day (3K/month) |
| **20K emails/mo** | $25/mo | $20/mo |
| **100K emails/mo** | $65/mo | $90/mo |
| **1M emails/mo** | $550/mo | $690/mo |

### Feature Comparison

| Feature | Brevo | SendGrid |
|---------|-------|----------|
| Transactional emails | ✅ Included | ✅ Included |
| Marketing emails | ✅ Included | ❌ Separate |
| Email warmup tools | ✅ Built-in | ⚠️ Manual |
| Contact CRM | ✅ Included | ❌ None |
| SMS sending | ✅ Included | ❌ Separate |
| Landing pages | ✅ Included | ❌ None |
| Automation workflows | ✅ Included | ⚠️ Limited |
| Deliverability | 98%+ | 99%+ |
| Support | Email (Free), Chat (Paid) | Email |

**Winner**: **Brevo** for startups (better free tier + more features)

---

## Step 8: Production Best Practices

### 8.1 Email Warmup Strategy

**Week 1**: 10-20 emails/day
**Week 2**: 30-50 emails/day
**Week 3**: 75-100 emails/day
**Week 4+**: 150-300 emails/day

**Brevo's Built-in Tools**:
- Automatic sender reputation monitoring
- Bounce rate alerts
- Spam complaint tracking
- Domain health score

**Monitor in Dashboard**:
- Go to **Statistics** → **Email Activity**
- Watch for:
  - Bounce rate <2%
  - Spam rate <0.1%
  - Open rate >20%

---

### 8.2 Deliverability Tips

✅ **Authenticate Domain** (SPF, DKIM, DMARC)
✅ **Use Dedicated IP** (paid plans $59+/mo)
✅ **Clean Email Lists** (remove bounces)
✅ **Personalize Content** (use recipient name)
✅ **Avoid Spam Words** (FREE, ACT NOW, etc.)
✅ **Include Unsubscribe Link** (required by law)
✅ **Monitor Engagement** (pause if low opens)

---

### 8.3 Rate Limiting

**Free Plan**: 300 emails/day
**Starter Plan** ($25/mo): 20,000 emails/month
**Business Plan** ($65/mo): 100,000 emails/month

**Implement Rate Limiting in Code**:
```python
# Track daily sends
daily_sends = get_daily_send_count()
if daily_sends >= 300:  # Free tier limit
    print("⚠️ Daily limit reached. Emails queued for tomorrow.")
    queue_for_tomorrow(email)
```

---

## Step 9: Monitoring & Analytics

### 9.1 Brevo Dashboard

**Real-time Metrics**:
1. Go to **Statistics** → **Email Activity**
2. View:
   - Emails sent
   - Delivery rate
   - Open rate
   - Click rate
   - Bounce rate

**Custom Reports**:
- Date range filtering
- Export to CSV
- Compare campaigns

---

### 9.2 Database Queries

```sql
-- Daily sending stats
SELECT
    DATE(sent_at) as date,
    COUNT(*) as sent,
    SUM(CASE WHEN status = 'delivered' THEN 1 ELSE 0 END) as delivered,
    SUM(CASE WHEN opened_at IS NOT NULL THEN 1 ELSE 0 END) as opened,
    ROUND(100.0 * SUM(CASE WHEN opened_at IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as open_rate
FROM email_sends
WHERE sent_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(sent_at)
ORDER BY date DESC;
```

---

## Step 10: Troubleshooting

### Issue 1: Emails Not Sending

**Check**:
1. ✅ API key valid?
   ```python
   sender = BrevoEmailSender()
   verification = sender.verify_sender_domain()
   print(verification)
   ```

2. ✅ Sender email verified?
   - Go to **Senders** page
   - Should show green checkmark

3. ✅ Daily limit reached?
   - Check **Statistics** → Today's sends

---

### Issue 2: Emails Going to Spam

**Solutions**:
1. ✅ **Authenticate domain** (SPF, DKIM, DMARC)
2. ✅ **Warm up sending** (start slow)
3. ✅ **Improve content** (avoid spam words)
4. ✅ **Use dedicated IP** (upgrade plan)
5. ✅ **Monitor engagement** (remove non-openers)

---

### Issue 3: Webhooks Not Working

**Debug**:
1. Check webhook URL is accessible:
   ```bash
   curl https://your-domain.com/webhooks/brevo
   # Should return: {"status": "healthy"}
   ```

2. Check Brevo webhook status:
   - **Settings** → **Webhooks**
   - Shows delivery success/failure

3. Check server logs:
   ```bash
   # View FastAPI logs
   tail -f /var/log/app.log
   ```

---

## ✅ Setup Complete Checklist

- [ ] Brevo account created
- [ ] Sender email verified
- [ ] Domain authenticated (SPF, DKIM, DMARC)
- [ ] API key generated and added to `.env`
- [ ] Python SDK installed
- [ ] Webhook endpoint created
- [ ] Webhook configured in Brevo
- [ ] Test email sent successfully
- [ ] Test email opened (tracking works)
- [ ] Test link clicked (tracking works)
- [ ] Database recording events correctly

---

## Next Steps

1. ✅ **Email sending works** → Move to Week 2 (Reply Monitoring)
2. ✅ **Integrate with LangGraph** → Update `src/nodes.py`
3. ✅ **Run with real leads** → Test end-to-end workflow

---

**Brevo is now configured! Ready to send emails at scale.** 🚀

Need help with:
- Domain authentication?
- Webhook setup?
- Testing?

Let me know! 👨‍💻
