# Original User Request

## Initial Request — 2026-08-06T01:56:10+01:00

# Teamwork Project Prompt — Draft

> Status: Launched
> Goal: Craft prompt → get user approval → delegate to teamwork_preview

Thoroughly test all functionalities of the EpicSync web app using a headed browser, identify bugs, and find missing features that should be implemented, returning a comprehensive QA and Feature Audit report.

Working directory: ~/teamwork_projects/epicsync_qa_audit
Integrity mode: development

## Requirements

### R1. End-to-End Functional Testing
Navigate to the live EpicSync application at `https://epic-yt-gab.web.app` using the `chrome-devtools` MCP server or browser tools. Log in using the provided credentials (Email: `gabrielyoutubeautomation@gmail.com`, Password: `Airpyk98` or `GabrielNjoku`). Test every single available feature in the UI to ensure they work as expected. 

### R2. Missing Feature Identification
Evaluate the application from a user's perspective and identify obvious missing features, broken UX flows, or incomplete functionalities that should be in a production-ready YouTube automation SaaS.

### R3. QA & Feature Report
Compile a detailed markdown report (`qa_audit_report.md`) listing all confirmed bugs, steps to reproduce them, and a prioritized list of missing features that the main engineering agent needs to build.

## Acceptance Criteria

### Testing Coverage
- [ ] Successfully log in with the provided credentials.
- [ ] Interact with at least 5 distinct interactive elements/pages across the application.

### Deliverables
- [ ] A written report (`qa_audit_report.md`) is generated containing a list of bugs found and a list of missing features.
