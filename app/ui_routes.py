"""
UI Blueprint for Event Stream Engine Web Interface
Provides minimal web UI for demonstrating the platform capabilities
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
import requests
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

# API base URL (internal)
API_BASE = "http://localhost:8000/api/v1"


@ui.route("/")
def dashboard():
    """Dashboard with system overview"""
    try:
        # Get dashboard metrics from API
        response = requests.get(f"{API_BASE}/monitoring/dashboard")
        if response.status_code == 200:
            dashboard_data = response.json()
        else:
            dashboard_data = {
                "active_campaigns": 0,
                "total_users": 0,
                "messages_sent_24h": 0,
                "overall_delivery_rate": 0.0,
                "recent_errors": [],
            }

        return render_template(
            "dashboard.html", active_tab="dashboard", data=dashboard_data
        )
    except Exception as e:
        flash(f"Error loading dashboard: {str(e)}", "error")
        return render_template("dashboard.html", active_tab="dashboard", data={})


@ui.route("/users")
def users():
    """User management and bulk upload page"""
    try:
        # Get users list from API
        response = requests.get(f"{API_BASE}/users")
        if response.status_code == 200:
            users_data = response.json()
        else:
            users_data = {"users": []}

        return render_template(
            "users.html", active_tab="users", users=users_data.get("users", [])
        )
    except Exception as e:
        flash(f"Error loading users: {str(e)}", "error")
        return render_template("users.html", active_tab="users", users=[])


@ui.route("/campaigns")
def campaigns():
    """Campaign management page"""
    try:
        # Get campaigns list from API
        response = requests.get(f"{API_BASE}/campaigns")
        if response.status_code == 200:
            campaigns_data = response.json()
        else:
            campaigns_data = {"campaigns": []}

        # Get templates for campaign creation
        templates_response = requests.get(f"{API_BASE}/templates")
        if templates_response.status_code == 200:
            templates_data = templates_response.json()
        else:
            templates_data = {"templates": []}

        return render_template(
            "campaigns.html",
            active_tab="campaigns",
            campaigns=campaigns_data.get("campaigns", []),
            templates=templates_data.get("templates", []),
        )
    except Exception as e:
        flash(f"Error loading campaigns: {str(e)}", "error")
        return render_template(
            "campaigns.html", active_tab="campaigns", campaigns=[], templates=[]
        )


@ui.route("/monitoring")
def monitoring():
    """Monitoring and inbound events page"""
    try:
        # Get recent inbound events
        inbound_response = requests.get(f"{API_BASE}/monitoring/inbound?limit=50")
        if inbound_response.status_code == 200:
            inbound_data = inbound_response.json()
        else:
            inbound_data = {"events": []}

        # Get campaign summaries for active campaigns
        campaigns_response = requests.get(f"{API_BASE}/campaigns")
        campaign_summaries = []

        if campaigns_response.status_code == 200:
            campaigns = campaigns_response.json().get("campaigns", [])
            for campaign in campaigns[:5]:  # Limit to 5 recent campaigns
                summary_response = requests.get(
                    f'{API_BASE}/reporting/campaigns/{campaign["id"]}/summary'
                )
                if summary_response.status_code == 200:
                    campaign_summaries.append(summary_response.json())

        return render_template(
            "monitoring.html",
            active_tab="monitoring",
            inbound_events=inbound_data.get("events", []),
            campaign_summaries=campaign_summaries,
        )
    except Exception as e:
        flash(f"Error loading monitoring data: {str(e)}", "error")
        return render_template(
            "monitoring.html",
            active_tab="monitoring",
            inbound_events=[],
            campaign_summaries=[],
        )


@ui.route("/campaign/<int:campaign_id>/summary")
def campaign_summary(campaign_id):
    """Detailed campaign summary page"""
    try:
        # Get campaign summary from API
        response = requests.get(f"{API_BASE}/reporting/campaigns/{campaign_id}/summary")
        if response.status_code == 200:
            summary_data = response.json()
        else:
            flash("Campaign not found or error loading summary", "error")
            return redirect(url_for("ui.campaigns"))

        return render_template("campaign_summary.html", summary=summary_data)
    except Exception as e:
        flash(f"Error loading campaign summary: {str(e)}", "error")
        return redirect(url_for("ui.campaigns"))


# API proxy routes for AJAX calls
@ui.route("/api/trigger-campaign/<int:campaign_id>", methods=["POST"])
def trigger_campaign_proxy(campaign_id):
    """Proxy for campaign trigger API call"""
    try:
        response = requests.post(f"{API_BASE}/campaigns/{campaign_id}/trigger", json={})
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ui.route("/api/dashboard-refresh")
def dashboard_refresh():
    """API endpoint for dashboard auto-refresh"""
    try:
        response = requests.get(f"{API_BASE}/monitoring/dashboard")
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"error": "Failed to get dashboard data"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
