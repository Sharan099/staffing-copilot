# Data Processing Record — AI Staffing Copilot

This document describes personal data in the system, what is sent to external LLM providers, and compliance prerequisites for production use.

## Personal data fields in the system

| Field | Storage | Classification |
|-------|---------|----------------|
| `first_name`, `last_name` | `staffing_bosch_style.db` → `employees` | Personal data |
| `email` | `employees` | Personal data |
| `location`, `country` | `employees` | Professional context (office location) |
| `title`, `department`, `seniority_level` | `employees` | Professional data |
| `hire_date`, `years_experience` | `employees` | Professional data |
| `german_fluency`, `english_fluency` | `employees` | Professional data |
| `last_performance_rating` | `employees` | Sensitive HR data — **never sent to LLM** |
| `cost_center` | `employees` | Internal finance — **never sent to LLM** |
| `manager_id` | `employees` | Internal reference |
| Skills, certifications, project history | Related tables | Professional data |
| Manager username | `users.db` | Account data |
| Manager API keys | `users.db` (encrypted) | Credentials — **never sent in LLM payload** |
| Staffing reports, rejections | `reports.db` | Contains employee names and manager notes |
| LLM audit log | `reports.db` → `llm_request_log` | Redacted payloads only (names/emails replaced with `candidate#ID`) |

## Data sent to external LLM APIs

The application calls **Anthropic** and/or **Groq** (manager-configured) for three tasks:

| Endpoint | Provider call | Data included |
|----------|---------------|---------------|
| `extract_request` | Criteria extraction | Manager request text; known location list in system prompt. **No employee PII.** |
| `search_summary` | Ranked-candidate narrative | Request text; criteria; per-candidate `candidate_id`, title, location, experience, availability, scores, judgment flags. **No names or emails.** |
| `fit_summary` | Approval justification | Request text; minimized candidate profile keyed by `candidate_id`; scores; judgment flags. **No names or emails.** |

All outbound payloads are logged in `llm_request_log` with names and emails redacted to internal IDs before persistence.

## Data not sent to LLM

- Email addresses
- Full names (replaced with `candidate#ID` in prompts; resolved to real names in backend after response)
- Salary, cost center, performance ratings
- Home addresses or personal contact details
- Full HR profiles, certification details, or bench reason narratives

Candidate search, scoring, and ranking run entirely in the local backend. The LLM is used only for text extraction and summaries.

## Providers and subprocessors

| Provider | Purpose | Data location |
|----------|---------|---------------|
| Anthropic (Claude) | LLM inference when selected in Model Settings | United States (verify current DPA / SCCs) |
| Groq | LLM inference when selected in Model Settings | United States (verify current DPA / SCCs) |

## Zero Data Retention (ZDR)

ZDR cannot be verified via this application's API. Your `.env` flags record **admin confirmation** that you have arranged or enabled ZDR with each provider — they are not auto-detected.

### Anthropic (Claude API)

**There is no self-serve “turn on ZDR” switch** in the Claude Console for most accounts.

Per [Anthropic's API and data retention docs](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention):

- **ZDR** is a commercial arrangement: customer data is not stored at rest after the API response is returned (except where required by law or abuse prevention).
- ZDR applies to the **Claude Messages API** and **Token Counting API** (the APIs this app uses).
- To request ZDR, **contact the Anthropic sales team or your account representative**. They enable it **per organization** after eligibility review.
- Some models (e.g. designated “Covered Models”) require 30-day retention and are **not** available under org-wide ZDR unless you opt specific workspaces into 30-day retention.

**Without a ZDR arrangement**, standard commercial API retention applies (see Anthropic's commercial data retention policy). Review that policy before processing employee data in production.

After Anthropic confirms ZDR is active on your organization, set `ANTHROPIC_ZDR_CONFIRMED=true` in `.env`.

### Groq (GroqCloud)

Groq documents a **Data Controls** page in the GroqCloud console where organization admins can enable Zero Data Retention (globally or per feature). See [Your Data in GroqCloud](https://console.groq.com/docs/your-data).

Path (may vary by account): **GroqCloud Console → Settings / Data Controls**.

After enabling ZDR (or signing equivalent enterprise terms), set `GROQ_ZDR_CONFIRMED=true` in `.env`.

### Application behavior

If either flag is `false`, the Settings page shows a warning banner and the server logs a startup reminder. This does not block API calls — it is a compliance checklist for your team.

## Audit and erasure

- **Audit:** Every LLM request is logged to `llm_request_log` (timestamp, manager ID, endpoint, redacted payload).
- **Right to erasure:** `DELETE /api/candidates/{id}/gdpr-delete` removes the employee record, related rows, LLM logs referencing that ID, and writes a non-PII entry to `gdpr_erasure_log`.

## Production requirements

Before production use with real employee data:

1. Execute a **Data Processing Agreement (DPA)** with each LLM provider whose API key will be used (Anthropic and/or Groq).
2. **Anthropic:** Request ZDR via sales/account team (not a console toggle). **Groq:** Enable ZDR in GroqCloud Data Controls (or negotiate enterprise terms).
3. Set `ANTHROPIC_ZDR_CONFIRMED` / `GROQ_ZDR_CONFIRMED` in environment configuration after your team confirms each arrangement.
4. Restrict manager access via authentication; API keys are per-manager and encrypted at rest (`MASTER_KEY`).
5. Review this document with legal/compliance and align retention policies for `reports.db` and `llm_request_log`.
