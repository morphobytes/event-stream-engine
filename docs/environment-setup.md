# Environment Configuration Guide

## Development Environment Files

This project uses separate environment files for different configuration aspects:

### `.env.dev` - Flask Application Configuration
Contains Flask app settings, database connections, Redis/Celery configuration, and Twilio integration settings for development.

### `.env.db` - Database Configuration  
Contains PostgreSQL-specific settings, connection pool configuration, and SQLAlchemy options.

### `.env.example` - Template for Production
Template file for production environment variables. Copy to `.env` and update with real values.

### `.env` - Production/Local Override
Local environment file with actual credentials (ignored by git).

## Quick Setup

1. **For Local Development (Docker Compose):**
   ```bash
   # Files .env.dev and .env.db are already configured with placeholder values
   # Update Twilio credentials in .env.dev with your sandbox values
   docker-compose up -d
   ```

2. **For Production Deployment:**
   ```bash
   # Copy template and update with real values
   cp .env.example .env
   # Edit .env with production values
   ```

3. **For Local Testing (Alternative):**
   ```bash
   # Copy template for local testing with real credentials
   cp .env.example .env
   # Edit .env with your actual Twilio sandbox credentials
   ```

## Key Configuration Values

### Twilio Integration
- Update `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` with your sandbox credentials
- Set `TWILIO_WEBHOOK_URL` to your ngrok or public URL for webhook testing
- Use `TWILIO_PHONE_NUMBER` from your Twilio sandbox

### Database Connection
- Database URL format: `postgresql://user:password@host:port/database`
- Connection pooling configured for optimal performance

### Rate Limiting & Business Rules
- `RATE_LIMIT_PER_MINUTE`: Messages per minute limit
- `QUIET_HOURS_START/END`: Campaign quiet hours (24-hour format)

## Security Notes

⚠️ **Never commit real credentials to version control**
- `.env.dev` and `.env.db` contain placeholder values only
- Real secrets should go in `.env` (ignored by git)
- Use proper secret management for production deployments