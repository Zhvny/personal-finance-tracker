# On-Call Rotation — Alpha Finance Tracker

## Overview

This document defines the on-call rotation and incident response procedures for the Alpha Finance Tracker platform.

## Current Setup

| Role | Contact | Responsibility |
|------|---------|----------------|
| Primary On-Call | (TODO: Set rotation) | First responder for P0/P1 alerts |
| Secondary On-Call | (TODO: Set rotation) | Backup if primary unreachable |
| Engineering Manager | (TODO: Set contact) | Escalation for prolonged outages |

## Rotation Schedule

On-call rotates weekly. The primary on-call is responsible for:
- Monitoring PagerDuty alerts
- Responding within SLA
- Escalating if unable to resolve

### Weekly Rotation Template

| Week | Primary | Secondary |
|------|---------|-----------|
| Week 1 | (TODO) | (TODO) |
| Week 2 | (TODO) | (TODO) |
| Week 3 | (TODO) | (TODO) |
| Week 4 | (TODO) | (TODO) |

## Response SLAs

| Severity | Response Time | Resolution Target |
|----------|--------------|------------------|
| P0 (Critical) | 15 minutes | 4 hours |
| P1 (High) | 30 minutes | 8 hours |
| P2 (Medium) | 4 hours | 24 hours |
| P3 (Low) | Next business day | 72 hours |

## Incident Severity Definitions

### P0 — Critical
- Complete platform outage
- All services down
- Data integrity risk
- Security breach

**Examples:**
- All Kubernetes pods crash looping
- Database unreachable
- Complete authentication failure

### P1 — High
- Major feature unavailable
- Significant performance degradation
- Single service down

**Examples:**
- Gateway returning 502 for all requests
- Payment processing failed
- Login system unavailable

### P2 — Medium
- Partial degradation
- Non-critical feature broken
- Performance issues

**Examples:**
- One upstream service unhealthy
- Slow response times (p95 > 5s)
- Dashboard loading issues

### P3 — Low
- Cosmetic issues
- Non-urgent bugs
- Feature requests

## Escalation Path

```
On-Call Engineer
    ↓ (no response in 15 min for P0)
Secondary On-Call
    ↓ (no response in 30 min)
Engineering Manager
    ↓ (no response in 1 hour)
CTO / VP Engineering
```

## Incident Response Process

1. **Alert Received** → Check PagerDuty/Slack
2. **Acknowledge** → Claim the incident in PagerDuty
3. **Assess** → Determine severity (P0-P3)
4. **Respond** → Follow runbook or initiate fix
5. **Communicate** → Post status updates
6. **Resolve** → Mark resolved in PagerDuty
7. **Review** → Schedule post-mortem for P0/P1

## Runbooks

| Alert | Runbook |
|-------|---------|
| AlphaServiceDown | [Link to runbook] |
| AlphaAllServicesDown | [Link to runbook] |
| AlphaHighErrorRate | [Link to runbook] |
| AlphaDatabaseConnectionPoolExhausted | [Link to runbook] |
| AlphaDiskSpaceWarning | [Link to runbook] |

## Status Page

Status updates during incidents should be posted to:
- Status page: (TODO: Set URL)
- Slack: #incidents

Template:
```
🚨 [INCIDENT] Service Issue - {time}
Affected: {services}
Impact: {description}
Status: Investigating
Next update: {time}
```

## Handoff Checklist

When handing off on-call:

- [ ] Review open incidents
- [ ] Check scheduled maintenance
- [ ] Verify contact info current
- [ ] Check backup coverage
- [ ] Review recent changes

## Checklist Items

- [ ] Set up PagerDuty rotation
- [ ] Configure Slack alerts channel
- [ ] Create status page account
- [ ] Write runbooks for top 5 alerts
- [ ] Test alert delivery quarterly
