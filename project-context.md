# 🛠️ TECHNICAL ASSESSMENT: EVENT-DRIVEN MESSAGING PLATFORM

---

## PROJECT GOAL (FOUNDING DATA ARCHITECT)

Design and implement a production-grade, event-driven messaging platform to deliver personalized WhatsApp messages. The architecture must handle real-time ingestion, complex business logic (orchestration), and maintain auditable logs for compliance and reporting.

**Core Stack:** Flask (Python), PostgreSQL (Cloud SQL), Redis (Broker/Cache), Docker/GCP.

---

## 1. WHATSAPP INTEGRATION (TWILIO SANDBOX)

The Flask service must manage real-time communication with the Twilio API.

### 1.1 Webhooks Required:
* [cite_start]**INBOUND:** Process user commands (e.g., START, STOP, SUBSCRIBE <topic>, UNSUBSCRIBE <topic>) and persist **raw** + **normalized** records[cite: 106].
* [cite_start]**STATUS CALLBACKS:** Track message lifecycle and delivery state (queued, sending, sent, delivered, read, failed, undelivered) with error codes[cite: 107].

### 1.2 Minimum Provider Fields to Support:
* [cite_start]**Inbound:** `From`, `WaId`, `Body`, `MessageSid`, `Timestamp`[cite: 109].
* [cite_start]**Status Callback:** `MessageSid`, `MessageStatus`, `ErrorCode` (nullable), `Timestamp`[cite: 110].

---

## 2. DATA MODEL & CONTRACTS (DDL)

Define the database schema (DDL) and enforce data contracts for the following core entities:

* [cite_start]**USERS:** `E.164 phone` as **Primary Key (PK)**, `attributes` (JSON), `consent state` (e.g., OPT_IN/OPT_OUT)[cite: 114].
* [cite_start]**SUBSCRIPTIONS:** Link between a `user` and a `topic`[cite: 115].
* [cite_start]**SEGMENTS:** Stores the `definition` (JSON/DSL rules used for recipient targeting)[cite: 116].
* [cite_start]**TEMPLATES:** Stores channel (`whatsapp`), `locale`, and message content with `{placeholders}`[cite: 117].
* [cite_start]**CAMPAIGNS:** Stores the `topic`, `template`, `schedule`, `status`, **rate limit**, and **quiet hours** rules[cite: 118].
* [cite_start]**MESSAGES:** Materialized per recipient; acts as the **state machine** (tracking state progression); records **provider SIDs** and **error codes**[cite: 119].
* [cite_start]**EVENTS_INBOUND, DELIVERY_RECEIPTS:** Stores **raw** and **normalized** data from webhooks[cite: 119].

---

## 3. DATA INGESTION

Define two distinct ingestion paths:

* **BULK USER INGEST:** Accept **CSV and JSON user files**. [cite_start]Must **validate E.164**, **dedupe**, merge `attributes`, and **record data-quality results**[cite: 121].
* [cite_start]**TRIGGER EVENTS:** Ingest **JSONL trigger events** (e.g., product/price alerts) with a **segment rule** to resolve recipients[cite: 122].

---

## 4. OUTBOUND ORCHESTRATION (THE CAMPAIGN RUNNER)

Implement a background **campaign runner** (Celery/RQ worker) that executes complex logic:

1.  [cite_start]Evaluates **segments** to resolve recipients[cite: 124].
2.  [cite_start]Renders **templates**[cite: 124].
3.  [cite_start]Enforces **consent/STOP** and **quiet hours**[cite: 125].
4.  [cite_start]Enforces **rate limits** and **retries**[cite: 125].
5.  [cite_start]Writes **auditable decisions** for every send attempt[cite: 125].

---

## 5. PUBLIC API + FRONT END

Expose a **versioned REST API** and a minimal UI for management and monitoring.

### 5.1 Versioned API Endpoints:
* [cite_start]CRUD/search for `users`, `segments`, `templates`, `campaigns`[cite: 129].
* [cite_start]Trigger/schedule a campaign[cite: 130].
* [cite_start]Message status (per recipient) and **aggregates** (delivery %, failures by code, opt-outs)[cite: 131].

### 5.2 Minimal Web UI:
* [cite_start]Demonstrates: **user ingest**, **create/preview a campaign**, **launch and monitor sends**, view **inbound messages**, and ability to reply via API[cite: 132].

---

## DELIVERABLES (QA & Submission)

* [cite_start]Public Git repository URL[cite: 135].
* [cite_start]**Production-grade code**[cite: 136].
* [cite_start]Documentation (README, Tests details)[cite: 137, 138].
* **Tests:** **Unit tests** for validation/transforms; [cite_start]**one end-to-end test** covering webhook $\rightarrow$ campaign $\rightarrow$ status[cite: 139, 140].
* [cite_start]Screen recording demonstrating the full flow[cite: 141].