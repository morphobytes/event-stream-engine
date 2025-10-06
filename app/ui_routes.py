"""
UI Blueprint for Event Stream Engine Web Interface
Provides minimal web UI for demonstrating the platform capabilities
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
import json
from datetime import datetime

# Create UI Blueprint
ui = Blueprint(
    "ui",
    __name__,
    template_folder="../client/templates",
    static_folder="../client/static",
    static_url_path="/ui/static",
)


@ui.route("/")
def dashboard():
    """Dashboard with system overview"""
    try:
        # Get dashboard metrics directly from database to avoid circular requests
        from flask import current_app
        from app.core.data_model import User, Campaign
        
        with current_app.app_context():
            total_users = User.query.count()
            # Mock data for now since we don't have monitoring endpoints yet
            dashboard_data = {
                "active_campaigns": 0,
                "total_users": total_users,
                "messages_sent_24h": 0,
                "overall_delivery_rate": 0.0,
                "recent_errors": [],
            }

        return render_template(
            "dashboard.html", active_tab="dashboard", data=dashboard_data
        )
    except Exception as e:
        # Provide fallback HTML if template fails
        return f"""
        <html>
        <head><title>Event Stream Engine Dashboard</title></head>
        <body>
            <h1>Event Stream Engine Dashboard</h1>
            <p>Dashboard temporarily unavailable</p>
            <p>API Status: <a href="/health">Check Health</a></p>
            <p>Users API: <a href="/api/v1/users">View Users</a></p>
            <p>Error: {str(e)}</p>
        </body>
        </html>
        """, 200


@ui.route("/users")
def users():
    """User management and bulk upload page"""
    try:
        # Get users list directly from database to avoid circular requests
        from flask import current_app
        from app.core.data_model import User
        
        users_list = []
        
        with current_app.app_context():
            users_query = User.query.paginate(page=1, per_page=20, error_out=False)
            
            for user in users_query.items:
                users_list.append({
                    'phone_e164': user.phone_e164,
                    'consent_state': user.consent_state.value if user.consent_state else 'UNKNOWN',
                    'attributes': user.attributes or {},
                    'created_at': user.created_at,  # Keep as datetime object for template
                    'updated_at': user.updated_at   # Keep as datetime object for template
                })

        # Debug: log the data being passed to template
        current_app.logger.info(f"Rendering users template with {len(users_list)} users")

        return render_template(
            "users.html", active_tab="users", users=users_list
        )
    except Exception as e:
        # Log the actual error for debugging
        from flask import current_app
        current_app.logger.error(f"Users page error: {str(e)}", exc_info=True)
        
        # Provide fallback HTML if template fails
        return f"""
        <html>
        <head><title>Event Stream Engine - Users</title></head>
        <body>
            <h1>Event Stream Engine - Users</h1>
            <p>User management temporarily unavailable</p>
            <p><a href="/">← Back to Dashboard</a></p>
            <p>API Status: <a href="/health">Check Health</a></p>
            <p>Users API: <a href="/api/v1/users">View Users API</a></p>
            <p>Error: {str(e)}</p>
        </body>
        </html>
        """, 200


@ui.route("/campaigns")
def campaigns():
    """Campaign management page"""
    try:
        # Get campaigns, templates, and segments from database to avoid circular requests
        from flask import current_app
        from app.core.data_model import Campaign, Template, Segment
        
        with current_app.app_context():
            # Get campaigns from database
            campaigns_list = Campaign.query.order_by(Campaign.created_at.desc()).all()
            
            # Get templates from database
            templates_list = Template.query.order_by(Template.created_at.desc()).all()
            
            # Get segments from database
            segments_list = Segment.query.order_by(Segment.created_at.desc()).all()

        return render_template(
            "campaigns.html",
            active_tab="campaigns",
            campaigns=campaigns_list,
            templates=templates_list,
            segments=segments_list,
        )
    except Exception as e:
        # Provide fallback HTML if template fails
        return f"""
        <html>
        <head><title>Event Stream Engine - Campaigns</title></head>
        <body>
            <h1>Event Stream Engine - Campaigns</h1>
            <p>Campaign management temporarily unavailable</p>
            <p><a href="/">← Back to Dashboard</a></p>
            <p>Error: {str(e)}</p>
        </body>
        </html>
        """, 200


@ui.route("/monitoring")
def monitoring():
    """Monitoring and inbound events page"""
    try:
        # Get recent inbound events directly from database to avoid circular requests
        from flask import current_app
        from app.core.data_model import InboundEvent
        
        with current_app.app_context():
            # Get recent inbound events
            recent_events = InboundEvent.query.order_by(InboundEvent.processed_at.desc()).limit(50).all()
            
            events_list = []
            for event in recent_events:
                events_list.append({
                    'id': event.id,
                    'from_phone': event.from_phone,
                    'message_sid': event.message_sid,
                    'provider_sid': event.message_sid,  # Use message_sid as provider_sid for template compatibility
                    'normalized_body': event.normalized_body,
                    'channel_type': event.channel_type,
                    'processed_at': event.processed_at.isoformat() if event.processed_at else None
                })
            
            # Mock campaign summaries for now
            campaign_summaries = []

        return render_template(
            "monitoring.html",
            active_tab="monitoring",
            inbound_events=events_list,
            campaign_summaries=campaign_summaries,
        )
    except Exception as e:
        # Log the actual error for debugging
        from flask import current_app
        current_app.logger.error(f"Monitoring page error: {str(e)}", exc_info=True)
        
        # Provide fallback HTML if template fails
        return f"""
        <html>
        <head><title>Event Stream Engine - Monitoring</title></head>
        <body>
            <h1>Event Stream Engine - Monitoring</h1>
            <p>Monitoring page temporarily unavailable</p>
            <p><a href="/">← Back to Dashboard</a></p>
            <p>Error: {str(e)}</p>
        </body>
        </html>
        """, 200


@ui.route("/campaign/<int:campaign_id>/summary")
def campaign_summary(campaign_id):
    """Detailed campaign summary page"""
    try:
        # Get campaign summary directly from database to avoid circular requests
        from flask import current_app
        
        with current_app.app_context():
            # Mock summary data for now since Campaign model might not be fully implemented
            summary_data = {
                "campaign_id": campaign_id,
                "name": f"Campaign {campaign_id}",
                "status": "completed",
                "total_recipients": 0,
                "messages_sent": 0,
                "delivery_rate": 0.0
            }

        return render_template("campaign_summary.html", summary=summary_data)
    except Exception as e:
        return f"""
        <html>
        <head><title>Campaign Summary</title></head>
        <body>
            <h1>Campaign Summary - Error</h1>
            <p>Campaign summary temporarily unavailable</p>
            <p><a href="/campaigns">← Back to Campaigns</a></p>
            <p>Error: {str(e)}</p>
        </body>
        </html>
        """, 200


# API proxy routes for AJAX calls
@ui.route("/api/trigger-campaign/<int:campaign_id>", methods=["POST"])
def trigger_campaign_proxy(campaign_id):
    """Trigger campaign directly without circular HTTP calls"""
    try:
        from flask import current_app
        # For now, return success - integrate with campaign orchestrator later
        current_app.logger.info(f"Campaign {campaign_id} trigger requested via UI")
        return jsonify({"message": f"Campaign {campaign_id} trigger queued", "status": "success"}), 200
    except Exception as e:
        current_app.logger.error(f"Campaign trigger error: {str(e)}")
        return jsonify({"error": str(e)}), 500


@ui.route("/api/dashboard-refresh")
def dashboard_refresh():
    """API endpoint for dashboard auto-refresh - using direct DB queries to avoid circular requests"""
    try:
        from flask import current_app
        from app.core.data_model import User, Campaign, Message, InboundEvent
        
        with current_app.app_context():
            # Get dashboard data directly from database
            user_count = User.query.count()
            campaign_count = Campaign.query.count()
            message_count = Message.query.count()
            recent_events = InboundEvent.query.order_by(InboundEvent.processed_at.desc()).limit(5).all()
            
            events_data = []
            for event in recent_events:
                events_data.append({
                    'id': event.id,
                    'from_phone': event.from_phone,
                    'processed_at': event.processed_at.isoformat() if event.processed_at else None,
                    'channel_type': event.channel_type
                })
            
            return jsonify({
                'users': user_count,
                'campaigns': campaign_count,
                'messages': message_count,
                'recent_events': events_data
            })
            
    except Exception as e:
        current_app.logger.error(f"Dashboard refresh error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500
