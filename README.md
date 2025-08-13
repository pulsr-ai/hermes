# Hermes - Transactional Email Service

A complete transactional email service built with FastAPI, featuring inbound/outbound email handling, Jinja2 templating, DKIM signing, and webhook notifications.

## Features

- **Outbound Email**: Send transactional emails with or without templates
- **Inbound Email**: Receive emails on catch-all address via SMTP server
- **Jinja2 Templates**: Store and manage email templates in database
- **DKIM Signing**: Sign outbound emails for better deliverability
- **Webhooks**: Register webhooks for email events (received, sent, failed)
- **RESTful API**: Complete FastAPI interface for all operations
- **Database Storage**: PostgreSQL storage for emails, templates, and webhooks

## Quick Start

### Using Docker

1. Clone the repository
2. Build the Docker image:
   ```bash
   docker build -t hermes .
   ```
3. Generate DKIM keys (optional):
   ```bash
   mkdir dkim
   openssl genrsa -out dkim/private.key 2048
   openssl rsa -in dkim/private.key -pubout -out dkim/public.key
   ```
4. Run the container:
   ```bash
   docker run -d \
     -p 8000:8000 \
     -p 25:25 \
     -e DATABASE_URL="your-database-url" \
     -e API_KEY="your-secure-api-key" \
     -v ./dkim:/app/dkim \
     hermes
   ```

The service will be available at:
- API: http://localhost:8000
- SMTP: localhost:25 (for receiving external mail)
- API Documentation: http://localhost:8000/docs

### Manual Installation

1. Install Poetry (if not already installed):
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. Install dependencies:
   ```bash
   poetry install
   ```

3. Set up PostgreSQL database

4. Configure environment variables in `.env`

5. Run migrations:
   ```bash
   poetry run alembic upgrade head
   ```

6. Start the service:
   ```bash
   poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

## API Authentication

All API endpoints require authentication via API key header:
```
X-API-Key: your-secure-api-key-here
```

## API Endpoints

### Templates
- `POST /api/templates/` - Create email template
- `GET /api/templates/` - List templates
- `GET /api/templates/{id}` - Get template by ID
- `GET /api/templates/name/{name}` - Get template by name
- `PATCH /api/templates/{id}` - Update template
- `DELETE /api/templates/{id}` - Delete template
- `POST /api/templates/{id}/preview` - Preview rendered template

### Emails
- `POST /api/emails/send` - Send email
- `GET /api/emails/` - List all emails
- `GET /api/emails/received` - List received emails
- `GET /api/emails/{id}` - Get email by ID
- `GET /api/emails/message/{message_id}` - Get email by message ID
- `POST /api/emails/{id}/resend` - Resend email
- `DELETE /api/emails/{id}` - Delete email

### Webhooks
- `POST /api/webhooks/` - Create webhook
- `GET /api/webhooks/` - List webhooks
- `GET /api/webhooks/{id}` - Get webhook
- `PATCH /api/webhooks/{id}` - Update webhook
- `DELETE /api/webhooks/{id}` - Delete webhook
- `GET /api/webhooks/{id}/deliveries` - Get webhook deliveries
- `POST /api/webhooks/{id}/test` - Test webhook

## Sending Emails

### Using Template
```json
POST /api/emails/send
{
  "to_email": "recipient@example.com",
  "template_name": "welcome",
  "template_variables": {
    "name": "John Doe",
    "company": "Acme Corp"
  }
}
```

### Without Template
```json
POST /api/emails/send
{
  "to_email": "recipient@example.com",
  "from_email": "sender@example.com",
  "subject": "Test Email",
  "html_content": "<h1>Hello World</h1>",
  "text_content": "Hello World"
}
```

## Receiving Emails

Configure your domain's MX records to point to your server, then emails sent to any address at your domain will be:
1. Received via SMTP on port 25 (standard SMTP port for mail delivery)
2. Stored in the database
3. Trigger webhooks if configured

**Important for Production:**
- Ensure port 25 is open in your firewall/security group
- For cloud providers that block port 25, consider using a mail relay service
- Scaleway: Use Container Instances or regular Instances (Serverless Containers don't support SMTP)

## Template Variables

Templates support Jinja2 syntax:
```html
<h1>Welcome {{ name }}!</h1>
<p>Thank you for joining {{ company }}.</p>
```

## Webhook Events

- `email.received` - Triggered when email is received
- `email.sent` - Triggered when email is sent successfully
- `email.failed` - Triggered when email sending fails

## Email Delivery Options

The service supports three methods for sending outbound emails:

### 1. Direct Delivery (Default)
When no `OUTBOUND_SMTP_HOST` is configured, the service sends emails directly to recipient mail servers:
- Automatically looks up MX records
- Connects directly to recipient's mail server
- No third-party dependencies

**Note**: Direct delivery requires:
- Valid PTR (reverse DNS) records for your IP
- IP not on blacklists
- Proper SPF, DKIM, and DMARC configuration
- Generally works best from VPS/cloud servers, not residential IPs

### 2. External SMTP Server
Configure an external SMTP server (Gmail, SendGrid, AWS SES, etc.):
```env
OUTBOUND_SMTP_HOST=smtp.gmail.com
OUTBOUND_SMTP_PORT=587
OUTBOUND_SMTP_USER=your-email@gmail.com
OUTBOUND_SMTP_PASSWORD=your-app-password
```

### 3. Local SMTP Relay
Install and configure a local mail server like Postfix, then leave `OUTBOUND_SMTP_HOST` empty.

## Environment Variables

- `DATABASE_URL` - PostgreSQL connection string
- `SMTP_HOST` - SMTP server host for receiving emails (default: 0.0.0.0)
- `SMTP_PORT` - SMTP server port for receiving (default: 25)
- `SMTP_DOMAIN` - Your email domain
- `OUTBOUND_SMTP_HOST` - Optional: External SMTP server for sending
- `OUTBOUND_SMTP_PORT` - Outbound SMTP port (default: 587)
- `OUTBOUND_SMTP_USER` - SMTP authentication user
- `OUTBOUND_SMTP_PASSWORD` - SMTP authentication password
- `DKIM_PRIVATE_KEY_PATH` - Path to DKIM private key
- `DKIM_SELECTOR` - DKIM selector (default: "default")
- `API_KEY` - API authentication key

## License

GNU General Public License v3.0 - see [LICENSE](LICENSE) for details
