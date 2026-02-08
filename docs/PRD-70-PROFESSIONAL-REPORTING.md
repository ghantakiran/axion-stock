# PRD-70: Professional Reporting

## Overview
Professional-grade reporting system with customizable templates, scheduled generation, white-label branding, and multi-format export (PDF, Excel, HTML, CSV).

## Components

### 1. Report Generator (`src/enterprise/reporting.py`)
- **ReportGenerator** — Multi-format report generation (PDF, Excel, HTML) with configurable sections
- **ReportScheduler** — Automated report scheduling with frequency, recipients, and cancellation
- **ReportData** — Structured report data with performance metrics, attribution, holdings, risk analysis
- **ReportSection** — Custom section support with title, content type, and data payload
- Quarterly performance reports with executive summary, attribution, holdings, risk, factor exposures, trade activity

### 2. Configuration (`src/enterprise/config.py`)
- **ReportConfig** — Output directory, format, generation timeout
- Subscription tier gating:
  - FREE: No custom reports
  - PRO: Basic custom reports, no white-label
  - ENTERPRISE: Full reports + white-label branding

### 3. Enums (`src/db/models.py`)
- **ReportTypeEnum** — PERFORMANCE, HOLDINGS, ATTRIBUTION, TRADE_ACTIVITY, RISK, CUSTOM
- **ReportFormatEnum** — PDF, EXCEL, HTML, CSV
- **ReportFrequencyEnum** — DAILY, WEEKLY, MONTHLY, QUARTERLY, ANNUAL
- **ReportStatusEnum** — PENDING, GENERATING, COMPLETED, FAILED

## Database Tables
- `report_templates` — Template configurations with sections, metrics, charts, branding settings
- `generated_reports` — Report instances with file path, content hash, status, generation time
- `scheduled_reports` — Automated scheduling with frequency, recipients, next_run tracking
- `report_distributions` — Email delivery log with sent/delivered/opened/failed tracking
- `report_sections` — Custom sections within templates with ordering
- `report_branding` — White-label branding (company name, logo, colors, disclaimer, contact info)

## Dashboard
5-tab Streamlit dashboard (`app/pages/reports.py`):
1. **Generated Reports** — List, filter, download with metrics display
2. **Generate New** — Report creation form with template/format/period selection
3. **Templates** — Template CRUD with section management
4. **Schedules** — Schedule creation, pause/resume, run history
5. **Branding** — White-label settings (colors, company name, logo, disclaimer, contact)

## Test Coverage
40 tests in `tests/test_reporting.py` covering report generation (PDF/Excel/HTML), data structures, scheduling, subscription limits, ORM models, and enum validation.
