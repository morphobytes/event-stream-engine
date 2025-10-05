# Monitoring & Analytics

## 🎯 Overview

Comprehensive monitoring, analytics, and performance tracking capabilities of the Event Stream Engine, including real-time dashboards, reporting systems, and operational metrics.

## 📊 System Monitoring Dashboard

### **Real-Time System Health**
The Event Stream Engine provides a comprehensive monitoring dashboard accessible at `/monitoring` with auto-refresh capabilities.

#### **Key Performance Indicators (KPIs)**
- **Active Campaigns**: Currently running message campaigns
- **Total Users**: Complete user database size
- **Opt-In Rate**: Percentage of users with active consent
- **24h Message Volume**: Messages sent in last 24 hours
- **Delivery Rate**: Successful message delivery percentage
- **System Uptime**: Application availability metrics

#### **Real-Time Metrics Display**
```javascript
// Auto-refresh dashboard every 30 seconds
setInterval(function() {
    fetch('/api/v1/monitoring/dashboard')
        .then(response => response.json())
        .then(data => updateDashboard(data));
}, 30000);
```

### **System Health Monitoring**
```json
{
  "system_health": {
    "active_campaigns": 12,
    "total_users": 25000,
    "opted_in_users": 23500,
    "opted_out_users": 1500,
    "system_uptime_hours": 720,
    "database_connections": 8,
    "redis_memory_usage_mb": 45.2
  },
  "performance_metrics": {
    "average_response_time_ms": 150,
    "requests_per_minute": 125,
    "error_rate_percent": 0.5,
    "webhook_processing_time_ms": 85
  }
}
```

---

## 📈 Campaign Analytics

### **Campaign Performance Metrics**

#### **Delivery Analytics**
- **Messages Sent**: Total campaign volume
- **Delivery Rate**: Percentage successfully delivered
- **Failure Rate**: Failed delivery percentage with error breakdown
- **Average Delivery Time**: Time from send to delivery confirmation
- **Engagement Tracking**: Read receipts and response rates

#### **Campaign Summary Report**
```json
{
  "campaign_performance": {
    "campaign_id": "550e8400-e29b-41d4-a716-446655440000",
    "campaign_name": "Spring Promotion 2024",
    "execution_summary": {
      "total_recipients": 5000,
      "messages_sent": 4950,
      "messages_delivered": 4750,
      "messages_failed": 200,
      "delivery_rate_percent": 95.96,
      "execution_duration_minutes": 125
    },
    "performance_breakdown": {
      "DELIVERED": 4750,
      "SENT": 50,
      "FAILED": 150,
      "UNDELIVERED": 50
    },
    "timing_analysis": {
      "average_delivery_time_seconds": 145,
      "fastest_delivery_seconds": 12,
      "slowest_delivery_seconds": 600,
      "delivery_time_percentiles": {
        "p50": 120,
        "p75": 180,
        "p90": 300,
        "p95": 450
      }
    }
  }
}
```

### **Error Analysis & Troubleshooting**
```json
{
  "error_analysis": {
    "error_breakdown": {
      "21211": {
        "description": "Invalid 'To' phone number",
        "count": 25,
        "percentage": 12.5,
        "resolution": "Validate E.164 format before sending"
      },
      "21614": {
        "description": "'To' number is not a valid mobile number",
        "count": 15,
        "percentage": 7.5,
        "resolution": "Verify mobile vs landline number type"
      },
      "30001": {
        "description": "Queue overflow", 
        "count": 10,
        "percentage": 5.0,
        "resolution": "Reduce send rate or increase rate limits"
      }
    },
    "top_error_countries": [
      {"country": "US", "error_count": 35},
      {"country": "CA", "error_count": 15}
    ],
    "error_trends": {
      "last_24h": 50,
      "previous_24h": 75,
      "trend": "decreasing"
    }
  }
}
```

---

## 📱 User Analytics

### **User Engagement Metrics**

#### **Consent & Opt-Out Analysis**
```sql
-- User consent state distribution
SELECT 
    consent_state,
    COUNT(*) as user_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM users), 2) as percentage
FROM users 
GROUP BY consent_state;
```

**Results**:
```json
{
  "consent_analytics": {
    "opt_in_users": 23500,
    "opt_out_users": 1200,
    "stop_users": 300,
    "consent_rates": {
      "opt_in_rate": 94.0,
      "opt_out_rate": 4.8,
      "stop_rate": 1.2
    },
    "consent_trends": {
      "daily_opt_outs": {
        "today": 5,
        "yesterday": 8,
        "trend": "improving"
      },
      "stop_commands_24h": 2
    }
  }
}
```

#### **User Attribute Analysis**
```json
{
  "user_demographics": {
    "by_city": {
      "San Francisco": 5200,
      "New York": 4800,
      "Austin": 2100,
      "Seattle": 1900
    },
    "by_tier": {
      "premium": 8500,
      "standard": 14200,
      "trial": 2300
    },
    "signup_trends": {
      "last_30_days": 1250,
      "growth_rate": "+15%"
    }
  }
}
```

### **Inbound Message Analytics**
```json
{
  "inbound_analytics": {
    "volume_metrics": {
      "total_inbound_24h": 245,
      "unique_senders": 198,
      "messages_per_user_avg": 1.24,
      "peak_hour": "14:00-15:00",
      "peak_volume": 28
    },
    "content_analysis": {
      "stop_commands": 3,
      "help_requests": 25,
      "order_inquiries": 45,
      "general_responses": 172
    },
    "response_patterns": {
      "immediate_responses": 89,
      "delayed_responses": 156,
      "auto_reply_triggered": 12
    }
  }
}
```

---

## 📊 Performance Analytics

### **Database Performance Monitoring**
```sql
-- Query performance analysis
SELECT 
    query,
    calls,
    total_time,
    mean_time,
    rows
FROM pg_stat_statements 
WHERE query LIKE '%users%' OR query LIKE '%campaigns%'
ORDER BY total_time DESC 
LIMIT 10;
```

#### **Performance Metrics**
```json
{
  "database_performance": {
    "query_metrics": {
      "average_query_time_ms": 45.2,
      "slowest_query_ms": 1250,
      "fastest_query_ms": 2.1,
      "total_queries_24h": 125000
    },
    "connection_pool": {
      "active_connections": 8,
      "idle_connections": 2,
      "max_connections": 20,
      "connection_wait_time_ms": 5.2
    },
    "index_efficiency": {
      "index_hit_ratio": 99.2,
      "table_scan_ratio": 0.8,
      "index_usage_optimal": true
    }
  }
}
```

### **Application Performance**
```json
{
  "application_performance": {
    "api_metrics": {
      "requests_per_second": 125.5,
      "average_response_time_ms": 180,
      "error_rate_percent": 0.5,
      "throughput_24h": 2500000
    },
    "endpoint_performance": {
      "/api/v1/users": {"avg_time_ms": 120, "requests": 50000},
      "/api/v1/campaigns": {"avg_time_ms": 200, "requests": 15000},
      "/webhooks/inbound": {"avg_time_ms": 45, "requests": 8000}
    },
    "resource_utilization": {
      "cpu_usage_percent": 15.2,
      "memory_usage_mb": 245.8,
      "disk_io_ops_sec": 125
    }
  }
}
```

---

## 🔍 Operational Monitoring

### **Real-Time Event Tracking**

#### **Live Activity Feed**
```json
{
  "live_events": [
    {
      "timestamp": "2024-01-25T16:45:12Z",
      "event_type": "message_delivered",
      "campaign_name": "Welcome Series",
      "recipient": "+14155551234",
      "delivery_time_seconds": 125
    },
    {
      "timestamp": "2024-01-25T16:45:08Z",
      "event_type": "inbound_message",
      "from_phone": "+14155555678",
      "message_body": "Thank you for the update!",
      "auto_response": false
    },
    {
      "timestamp": "2024-01-25T16:45:02Z",
      "event_type": "campaign_started",
      "campaign_name": "Flash Sale Alert",
      "estimated_recipients": 2500
    }
  ]
}
```

### **Alert System & Notifications**

#### **System Health Alerts**
```json
{
  "alert_configuration": {
    "error_rate_threshold": 5.0,
    "response_time_threshold_ms": 1000,
    "delivery_rate_threshold": 90.0,
    "disk_usage_threshold": 85.0
  },
  "active_alerts": [
    {
      "alert_id": "ALT001",
      "severity": "warning",
      "message": "Campaign delivery rate below threshold",
      "current_value": 88.5,
      "threshold": 90.0,
      "triggered_at": "2024-01-25T16:30:00Z"
    }
  ]
}
```

### **Compliance Monitoring**
```json
{
  "compliance_metrics": {
    "consent_verification": {
      "total_messages_sent": 50000,
      "consent_verified_count": 50000,
      "compliance_rate": 100.0
    },
    "quiet_hours_compliance": {
      "messages_during_quiet_hours": 0,
      "messages_rescheduled": 125,
      "compliance_rate": 100.0
    },
    "rate_limit_adherence": {
      "rate_limit_violations": 0,
      "average_send_rate": 2.3,
      "peak_send_rate": 4.8,
      "compliance_status": "excellent"
    },
    "audit_trail_completeness": {
      "events_logged": 125000,
      "missing_audit_entries": 0,
      "audit_coverage": 100.0
    }
  }
}
```

---

## 📋 Reporting & Exports

### **Automated Report Generation**

#### **Daily Performance Report**
```json
{
  "report_type": "daily_performance",
  "date": "2024-01-25",
  "summary": {
    "campaigns_executed": 8,
    "total_messages_sent": 12500,
    "delivery_rate": 95.2,
    "error_rate": 2.1,
    "new_users_added": 125,
    "opt_out_requests": 8
  },
  "top_performing_campaigns": [
    {
      "campaign_name": "Welcome Series",
      "delivery_rate": 98.5,
      "messages_sent": 500
    }
  ],
  "areas_for_improvement": [
    "Reduce delivery time for Campaign ID 12345",
    "Address error code 21211 occurrences"
  ]
}
```

#### **Weekly Analytics Summary**
```json
{
  "report_period": "2024-01-19 to 2024-01-25",
  "weekly_metrics": {
    "total_messages": 87500,
    "delivery_rate_avg": 94.8,
    "user_growth": "+5.2%",
    "campaign_performance": "excellent",
    "system_uptime": "99.97%"
  },
  "trends": {
    "delivery_rate_trend": "+2.1%",
    "error_rate_trend": "-15%",
    "user_engagement_trend": "+8.5%"
  }
}
```

### **Custom Analytics Queries**

#### **Campaign ROI Analysis**
```sql
-- Campaign effectiveness by segment
SELECT 
    c.name as campaign_name,
    s.name as segment_name,
    COUNT(m.id) as messages_sent,
    COUNT(CASE WHEN dr.message_status = 'delivered' THEN 1 END) as delivered,
    ROUND(
        COUNT(CASE WHEN dr.message_status = 'delivered' THEN 1 END) * 100.0 / COUNT(m.id), 
        2
    ) as delivery_rate
FROM campaigns c
JOIN segments s ON c.segment_id = s.id
JOIN messages m ON c.id = m.campaign_id
LEFT JOIN delivery_receipts dr ON m.provider_sid = dr.message_sid
WHERE c.created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY c.id, c.name, s.name
ORDER BY delivery_rate DESC;
```

#### **User Engagement Funnel**
```sql
-- User journey analysis
WITH user_journey AS (
    SELECT 
        u.phone_e164,
        u.created_at as signup_date,
        COUNT(m.id) as messages_received,
        COUNT(ie.id) as responses_sent,
        u.consent_state
    FROM users u
    LEFT JOIN messages m ON u.phone_e164 = m.recipient_phone
    LEFT JOIN inbound_events ie ON u.phone_e164 = ie.from_phone
    WHERE u.created_at >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY u.phone_e164, u.created_at, u.consent_state
)
SELECT 
    consent_state,
    COUNT(*) as users,
    AVG(messages_received) as avg_messages_received,
    AVG(responses_sent) as avg_responses,
    ROUND(AVG(responses_sent) / NULLIF(AVG(messages_received), 0) * 100, 2) as engagement_rate
FROM user_journey
GROUP BY consent_state;
```

---

## 🚨 Alerting & Incident Management

### **Automated Monitoring Alerts**

#### **Performance Degradation Alerts**
- **High Error Rate**: >5% message failure rate triggers immediate alert
- **Slow Response Time**: API response time >1000ms triggers warning
- **Low Delivery Rate**: Campaign delivery rate <90% triggers investigation
- **System Resource**: CPU >80% or Memory >85% triggers scaling alert

#### **Business Logic Alerts**
- **Compliance Violation**: Any consent bypass or quiet hours violation
- **Rate Limit Exceeded**: Campaign sending faster than configured limits
- **Webhook Processing Delays**: Twilio callback processing >30 seconds
- **Database Connection Issues**: Connection pool exhaustion or timeouts

### **Incident Response Workflow**
```json
{
  "incident_management": {
    "severity_levels": {
      "critical": "System down or major functionality unavailable",
      "high": "Significant performance degradation or feature impairment", 
      "medium": "Minor performance issues or non-critical feature problems",
      "low": "Cosmetic issues or enhancement requests"
    },
    "response_times": {
      "critical": "15 minutes",
      "high": "1 hour",
      "medium": "4 hours",
      "low": "24 hours"
    },
    "escalation_path": [
      "On-call Engineer",
      "Technical Lead", 
      "Engineering Manager",
      "CTO"
    ]
  }
}
```

---

## 📈 Performance Optimization Insights

### **Optimization Recommendations**

#### **Database Optimization**
```sql
-- Index usage analysis
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE idx_scan < 100
ORDER BY idx_scan ASC;
```

#### **Campaign Performance Optimization**
- **Segment Size Analysis**: Identify optimal segment sizes for delivery efficiency
- **Template Performance**: Track which message templates have highest delivery rates
- **Timing Optimization**: Analyze best send times by user timezone and demographics
- **Rate Limit Tuning**: Optimize send rates based on carrier feedback and delivery success

### **Capacity Planning**
```json
{
  "capacity_metrics": {
    "current_utilization": {
      "daily_message_volume": 25000,
      "peak_hourly_rate": 2500,
      "database_growth_mb_day": 45.2,
      "storage_usage_percent": 35.8
    },
    "projected_growth": {
      "3_month_projection": {
        "daily_volume": 50000,
        "storage_needs_gb": 12.5,
        "additional_users": 15000
      },
      "scaling_recommendations": [
        "Increase database connection pool to 25",
        "Add read replica for reporting queries", 
        "Implement Redis cluster for high availability"
      ]
    }
  }
}
```

---

*This comprehensive monitoring and analytics system provides complete visibility into Event Stream Engine operations, enabling proactive optimization, compliance assurance, and data-driven decision making for messaging platform management.*
