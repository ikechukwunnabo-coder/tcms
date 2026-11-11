# TCMS vs Axis Gap Analysis

## Document control

- **Status:** Phases 1-4 complete. Phase 1 delivered OPITO taxonomy, expiry rules, document storage, certificate/ID-card actions, staff course UI, role-gated document actions and portal certificate download; Phase 2 the operational workspace; Phase 3 reporting intelligence; Phase 4 public verification, OPITO file workflow, staff profile slice, backup console, Axis-compatible relationship APIs, portal profile and corporate workspace, and photo/ID-scan upload/download.
- **Date:** 2026-11-10
- **Repository:** `C:\Users\tolma\OneDrive\Desktop\ERP_Project\Pre-Tascl\tcms`
- **Baseline commit:** `4dd973d Implement Phase 1 certificate and ID-card parity`
- **Worktree:** Phase 1-4 changes complete
- **Scope:** TCMS staff operations console, TCMS learner portal, and the observable Axis staff console

## Scope and evidence

This report reconciles three surfaces:

1. **TCMS staff console** — React/Vite application in `frontend/`, authenticated against `/api/v1/auth/login`, backed by the DRF router in `apps/common/api.py`.
2. **TCMS learner portal** — Django-rendered portal mounted at `/portal/` (`apps/portal_web/`), with JSON endpoints under `/api/v1/auth/*`, `/api/v1/corporate/*`, and `/api/v1/bookings/*` (`apps/portal/`).
3. **Axis target** — the staff SPA at `https://axis.software-suites.com/`, inspected through screenshots and downloaded/prettified Vite assets.

Assumption: “TCMS portal” in this document means the in-repo learner portal at `/portal/`. If a separate TCM portal exists outside this repository, this section needs to be extended against that codebase.

Axis evidence is limited to the staff console. There were no Axis credentials, so authenticated API responses and any separate Axis learner portal were not inspected directly. Axis behavior below is inferred from bundles and screenshots.

## Current product surfaces

### TCMS staff console

Implemented routes (`frontend/src/App.tsx`):

- `/` — Axis-style role-filtered home tile catalogue with live operations analytics
- `/tasks` — pending tasks
- `/activity` — my activity
- `/training-records` — all training records, with `/workflow` retained as an alias view
- `/learners` — learner list
- `/courses` — course setup, certificate type and ID-card text
- `/modules`, `/items` — course modules and certificate line items
- `/companies`, `/states`, `/nationalities` — dedicated reference-data pages
- `/scheduling` — sessions
- `/enrolments` — enrolments
- `/certificates` — certificate issue/sign/release list
- `/billing` — invoices, payments, corporate accounts
- `/medicals` — medicals
- `/reports` - reporting index and Axis-parity report detail pages
- `/users` — staff/team directory, admin-only
- `/users/:id` — user data, assigned roles and account actions, admin-only
- `/roles` — role catalogue with member counts, admin-only

Phase 2 added `/tasks`, `/activity`, `/learners/:id`, `/training-records/:id`, `/modules`, `/items`, `/reference`, `/profile` and `/reports/:dataset`. The learner workspace shows profile, documents, training history, certificates, ID cards and medicals, with photo and ID-scan upload/download. `/courses` now includes a content editor for course-item and course-module relations. The training workspace covers delivery dates, instructors/modules, FOET/payment/welcome documents, daily BP observations, current CJI/resend, certification output and status history.

Phase 3 added the reporting index and eight detail views: `/reports/training-records`, `/reports/course-by-month`, `/reports/learner-by-month`, `/reports/top-training-courses`, `/reports/courses-treemap`, `/reports/role-activity`, `/reports/opito-monthly` and `/reports/flow-status`, with charts, filters, year range and CSV/XLSX/PDF exports.

Phase 4 added the public verification pages and the OPITO files workflow at `/opito-files`, backed by `/api/v1/opito-files/` cohort, validation, content, generation, and download endpoints. The staff profile slice adds self-service password change at `/api/v1/auth/password`, persisted light/dark theme, and role manuals at `/manuals/:file` with links from `/profile`. The backup slice adds system-admin-only `/backup/backup` and `/backup/test` endpoints and the `/backup` console page; zip, push, unzip and restore controls remain intentionally disabled to mirror the observable Axis surface. Axis-compatible relation endpoints now cover `/api/v1/course-item-rel`, `/api/v1/course-module-rel` and `/api/v1/user-role`, with course-content and user-role management surfaces. The Users slice now follows the Axis pattern with a card directory, `/users/:id` detail, dedicated assigned/available role management, emailed password-reset links, delete safeguards, and System Admin role protection.

Implemented navigation now follows the Axis catalogue: **Tasks**, **Operations**, **Course Setup**, **Reference Data**, **Access** and **Admin Tools**, with Home above the groups and a **Centre tools** continuation for scheduling, enrolments, certificates, medicals and billing (`frontend/src/navigation/axis.ts`, `frontend/src/components/AppShell.tsx`). The home page renders the same role-filtered Axis tile catalogue above the live dashboard (`frontend/src/pages/DashboardPage.tsx`).

The backend is substantially broader than the staff console UI: billing, payroll, medicals, scheduling, notifications, integration/outbox, audit, document metadata, certificate rendering, and expiry reminders all exist. The main gap is not backend breadth; it is Axis workflow/UX parity and a few missing domain primitives.

### TCMS learner portal

Web routes (`apps/portal_web/urls.py`):

- `/portal/` — public landing page
- `/portal/register/`
- `/portal/registered/`
- `/portal/verify-email/` and `/portal/verify-email/<token>/`
- `/portal/login/`
- `/portal/logout/`
- `/portal/password-reset/`, `/portal/password-reset/done/`, `/portal/password-reset/<uidb64>/<token>/`
- `/portal/resend-verification/` and `/portal/resend-verification/email/`
- `/portal/dashboard/`
- `/portal/profile/`
- `/portal/corporate/`
- `/portal/corporate/nominees/<pk>/edit/`
- `/portal/corporate/nominees/<pk>/remove/`
- `/portal/certificates/<pk>/download/`
- `/portal/verify/` and `/portal/verify/<identifier>/`
- `/portal/bookings/<pk>/cji/`
- `/portal/bookings/<pk>/cji/resend/`

Portal API routes (`apps/portal/urls.py`):

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/verify-email`
- `POST /api/v1/auth/resend-verification`
- `POST /api/v1/corporate/accounts`
- `GET|POST /api/v1/corporate/nominees`
- `PATCH|DELETE /api/v1/corporate/nominees/<pk>`
- `POST /api/v1/corporate/certificates/bundle`
- `GET /api/v1/corporate/certificates/batches`
- `GET /api/v1/bookings/<pk>/cji`
- `POST /api/v1/bookings/<pk>/cji/resend`

Portal models (`apps/portal/models.py`):

- `PortalAccount` — links a `User` to a `Learner` and optional corporate account.
- `EmailVerification` — single-use hashed verification token.
- `JoiningInstruction` — versioned CJI payload, delivery state, and merge data.

Portal web dashboard (`apps/portal_web/templates/portal/dashboard.html`) shows:

- Corporate nominees with links to the corporate workspace for add/edit/remove and bundle delivery.
- The caller’s bookings with course, session, venue, and state.
- CJI view/resend actions when a current CJI exists.
- The caller’s certificates with issued/expiry/state and PDF download.

The portal profile page edits names, sex, birth date, bio, contacts and references through shared learner records. The corporate workspace supports account creation, nominee management and certificate-bundle delivery. The portal has broad tests for registration, verification, password reset, login, dashboard scoping, CJI access, profile/corporate flows and corporate nominee rules (`apps/portal/tests.py`, `apps/portal_web/tests.py`).

### Axis target

Observed Axis structure and behavior:

- Grouped navigation: **Tasks**, **Operations**, **Course Setup**, **Reference Data**, **Access**, **Admin Tools**.
- Routes include `/pending-tasks`, `/my-activity`, `/opito-files`, `/learners`, `/trainings`, `/courses`, `/course-modules`, `/course-items`, `/companies`, `/states`, `/nationalities`, `/users`, `/roles`, `/reporting`, `/backup`, report subroutes, and public `/verify/:id`.
- Role-filtered home cards.
- Pending-task calendar/status filters, bulk approve/cancel, floating approve/reject actions.
- Flow-status backlog thresholds: `15` backlog, `25` critical.
- Eight report cards: Training Records, Courses by Month, Delegates by Month, Courses Treemap, Top Training Courses, Role Activity, OPITO Monthly, and Flow Status.
- Certificate/ID-card issuance differentiates generated versus uploaded documents.
- OPITO certificate type is `4`; the TCMS seed only defines `1` and `2`.

## Executive summary

The TCMS staff console already has the core operational backbone: learners, sessions, enrolments, approvals, certificates, medicals, billing, and reporting exports. It also exceeds the visible Axis surface in finance/payroll and some portal capabilities.

The largest remaining parity gaps are:

1. **Certificate and ID-card lifecycle** — OPITO type, uploaded versus generated certificates, PDF existence checks, re-generation/re-upload, ID-card templates, ID-card rendering, and print-state handling.
2. **Operational shell** — grouped navigation, role-filtered home cards, pending tasks, course/reference setup pages, profile, activity, backup, OPITO files, and public verification.
3. **Data capture around training records** — instructor assignment date/module, FOET scan, per-day medical BP, payment proof, welcome letter, and document upload/download.
4. **Reporting** — Axis-specific report endpoints, year filters, charts, XLSX/PDF exports, and richer flow-status metrics.
5. **Relationship/data APIs** — course-module-item relationships, user-role relationships, and `vantage_id` are implemented.

The TCMS learner portal now matches or exceeds the staff console for public registration, email verification, password reset, corporate nominees, certificate download, certificate verification and CJI delivery. Its remaining gaps are:

- No portal ID-card access and no OPITO visibility.
- No self-service booking or payment-proof upload, despite landing-page copy that promises booking.
- The generic `Document` API remains metadata-only, although learner photo/ID-scan documents now use real storage and download.

The highest-leverage fix is a shared issuance/document service used by both the staff console and the learner portal. That avoids implementing certificate rendering/download logic twice.

## Staff console gap matrix

| Priority | Gap | Axis target | TCMS now | Required change |
|---|---|---|---|---|
| P0 | Certificate taxonomy | `OPITO=4`; OPITO certificates are uploaded | `CertificateTypeCode` only `STANDARD=1`, `NIMASA=2` (`apps/common/enums.py:42`); seed only 1/2 (`seed_data.py:54`) | Add OPITO enum/seed, migrate/label existing OPITO courses, tests |
| P0 | OPITO course classification | OPITO courses use OPITO certificate behavior | OPITO courses such as `BOSIET`, `HUET`, `FOET` are seeded with `cert_type_id=1` (`seed_data.py:67-85`) | Data migration or reseed based on OPITO registration codes; preserve existing records |
| P0 | Course ID-card template | `front_id_text`, `back_id_text` on course | Absent from `Course` (`apps/catalogue/models.py:18`) and serializer | Add fields, migration, serializer/admin, ID-card renderer inputs |
| P0 | Certificate issuance | Check PDF existence; generate/re-generate or upload/re-upload | Only `POST /certificates/issue/` (`apps/certification/views.py:34`); no document actions | Add PDF HEAD/download/generate/upload actions, permissions, tests |
| P0 | Uploaded certificate storage | Uploaded PDF is the certificate artefact | `Certificate.object_key` is rendered if present (`rendering.py:26`), but no upload endpoint or storage workflow | Add upload/validation endpoint and storage handling |
| P0 | ID cards | Generate, preview, re-generate, mark printed | `IDCard` model/CRUD only (`models.py:162`, `views.py:106`); no renderer/service/UI | Add ID-card PDF renderer, issue/print actions, frontend, tests |
| P0 | Expiry semantics | `0` no expiry, `1` auto-calculated, `2` FOET expiry | `ExpiryTypeCode` only `CALCULATED=1` (`enums.py:47`); `expiry_type` field is a free small integer | Add explicit enum choices and expiry/FOET calculation rules |
| Complete | Instructor capture | Assignment includes date and module | `TrainingInstructor` now stores module and training date; workspace exposes nested assignments | No further action in Phase 2 |
| Complete | FOET and medical evidence | FOET scan upload; per-course-day BP readings | `TrainingRecord` links FOET/payment/welcome documents; `DailyMedicalCheck` captures per-day systolic/diastolic readings; workspace supports upload and BP entry | No further action in Phase 2 |
| P1 | Payment proof / welcome letter | Upload payment proof; generate/upload welcome letter | Billing and notifications exist; no staff upload/generate UI for these artefacts | Add document actions and UI, reuse existing billing/notification services |
| Complete | Learner profile | `vantage_id`, photo, learner-ID scan, contacts, training history, ID-card preview | `Learner.vantage_id` and `/learners/:id` workspace cover contacts, documents, training history, certificates, ID cards and medicals; photo/ID-scan upload/download is implemented in the staff workspace and learner document API | No further action in Phase 4 |
| Complete | Reporting | Seven chart/report pages, year min/max, XLSX/PDF, flow thresholds | Report APIs, year range, charts, role activity, OPITO monthly, flow thresholds and dual-format exports are implemented | No further action in Phase 3 |
| Complete | Shell/nav/home | Grouped nav, role-filtered home cards, missing routes | Grouped role-filtered sidebar and home workspace cards; Phase 2 routes added | Remaining auxiliary pages belong to Phases 3-4 |
| Complete | Pending tasks / activity | Calendar-filtered pending tasks, bulk approve/cancel, my activity | Bulk approve/reject/cancel, date/status filters, pending-tasks and my-activity pages | Calendar view can be added in a later refinement |
| Complete | Public verification | `/verify/:id` public certificate check | Anonymous API, standalone React pages and portal page implemented | No further action in Phase 4 |
| Complete | OPITO file workflow | Generate/validate/upload OPITO file | OPITO cohort cards, Vantage-ID validation, CSV generation/download and audit implemented at `/opito-files` | No further action in Phase 4 |
| Complete | Staff profile | Self password, dark mode, role manuals | `/profile` supports password change with server-side validation and audit, persisted light/dark theme, role-filtered manual links, and manual pages at `/manuals/:file` | No further action in Phase 4 |
| Complete | Backup console | Backup data and test files | System-admin `/backup` page, gzipped JSON snapshots in `BACKUP_DIR`, storage probe and audit events implemented; zip/push/restore remain disabled as in Axis | No further action in Phase 4 |
| Complete | Relationship APIs | `/course-item-rel`, `/course-module-rel`, `/user-role` | Axis-compatible collection/detail/available/delete endpoints, relation models and admin inlines, plus course-content and user-role UI | No further action in Phase 4 |
| Decision | Role/status parity | Axis uses QA naming and statuses 1–13 | TCMS uses `DUE_DILIGENCE=7` and `REJECTED=14`; IDs otherwise align | Decide whether to keep internal 14 or migrate; at minimum align UI labels |

## TCMS learner portal reconciliation

### What the portal already does well

- Registration with 18+ gate and rate limiting.
- Single-use, time-limited email verification that creates a `Learner` only after confirmation.
- Login with email, staff/portal shared account model, and password reset.
- Corporate account creation and nominee CRUD through the API.
- Corporate certificate ZIP bundle creation/listing through the API.
- Versioned CJI generation, delivery, resend, bounce state, and access control.
- Read-only dashboard for bookings and certificates.
- Broad automated coverage for the above.

### Staff console vs portal capability matrix

| Capability | Staff console | Learner portal | Reconciliation |
|---|---|---|---|
| Identity | Admin-managed staff users/roles; self-service password and manuals | Self-registration, email verification, password reset | Shared `User`/`Learner` backend; staff now has self-service password, theme and role manuals |
| Complete | Learner data | Full learner CRUD, contacts/documents API, Vantage ID and learner workspace | Profile editing, own learner record, corporate nominees, contacts, references and photo/ID-scan documents | Shared learner profile and document storage implemented |
| Complete | Certificates | Issue, sign, release, list | Lists certificate number, dates, state and downloads the PDF | Portal certificate download implemented |
| Partial | ID cards | Model/CRUD only | None | Shared backend gap; needs renderer/issue/print and portal access |
| Partial | Bookings | Sessions, enrolments, scheduling | Lists bookings; cannot create or change bookings | Clarify portal scope; landing copy promises booking but dashboard says coordinator books |
| Partial | Payments | Invoices, payments, corporate accounts | No payment-proof upload or payment view | Decide whether portal needs payment-proof upload or remains coordinator-driven |
| Complete | CJI | Staff visibility/resend | Training workspace shows current CJI state and resends it when an enrolment exists | No further action in Phase 2 |
| Complete | Corporate | Corporate accounts in billing UI | Workspace supports account creation, nominee add/edit/remove and certificate bundles | Portal corporate workspace implemented |
| Complete | Verification | Public certificate check | Public certificate verification at `/portal/verify/` and email verification | No further action in Phase 4 |
| Partial | Documents | Learner-document upload/download | Learner photo/ID-scan upload/download | Generic `Document` API remains metadata-only (`documents/views.py:17`) |
| Partial | OPITO | OPITO files workflow with cohort validation and CSV export | None | Staff workflow is complete; portal OPITO visibility remains optional |
| Complete | Reports | Axis-specific reports, charts, year filters and CSV/XLSX/PDF | None | Phase 3 reporting surface is implemented |

### Cross-surface shared gaps

These should be fixed once in shared services/APIs, not separately in React and Django templates:

1. **[PARTIAL] Certificate and ID-card artefact service** — certificate render/upload/download and verification exist; ID-card rendering and print marking remain.
2. **[PARTIAL] Document storage contract** — learner photo/ID-scan documents persist and stream; generic `Document` records remain metadata-only.
3. **[COMPLETE] Learner profile extensions** — `vantage_id`, portal profile editing, photo, learner-ID scan and training-history aggregation.
4. **[COMPLETE] Corporate workspace** — nominees, certificate bundles, certificate access and account context shared by staff and portal.
5. **[COMPLETE] Public certificate verification** — anonymous API plus standalone `/verify/:id` and `/portal/verify/` routes.
6. **[COMPLETE] Reporting/export service** — XLSX/PDF exports and report datasets usable by staff UI and future portal reporting.
7. **[OPEN] Role/status display policy** — Axis labels versus TCMS’s extra `REJECTED=14` state.

### Portal-specific inconsistencies to resolve

- The landing page says “Book your training,” but the dashboard says courses are booked through the training coordinator and exposes no booking action.
- The portal lists and downloads certificate PDFs but has no ID-card access.
- Portal login is email-based and limited to users with a `PortalAccount`; staff console login is username-based, and portal staff links point to `STAFF_APP_URL`.
- The portal has no OPITO status visibility and no payment-proof upload.

## Execution plan to close the gaps

### Phase 0 — lock decisions before coding

1. **Portal booking scope** — coordinator-only, or learner self-booking plus payment-proof upload?
2. **Certificate access** — authenticated portal download, public tokenized link, or both?
3. **Public verification fields** — validity only, or learner/course details?
4. **OPITO migration rule** — which existing courses become `cert_type=OPITO`? Current seed marks BOSIET/HUET/FOET as `Standard`.
5. **Role/status policy** — keep TCMS `REJECTED=14` internally and display Axis labels, or migrate to Axis 1–13?
6. **Document storage target** — local `default_storage`, S3-compatible, or another backend.

**Implementation defaults for this slice**

- **Portal bookings:** keep coordinator-led booking; no learner self-booking in Phase 1.
- **Certificate access:** authenticated portal download; tokenized public links and public verification stay in Phase 4.
- **Public verification:** show validity, learner name and course, matching Axis; do not expose medical or payment data.
- **OPITO migration:** any course with a non-empty `opito_reg_code` becomes `cert_type=4` (OPITO); the seed marks BOSIET, BOSIET-R, HUET and FOET as OPITO.
- **Roles/statuses:** keep TCMS `REJECTED=14` internally, retain Axis-compatible IDs `1–13`, and label the statuses consistently in new UI.
- **Document storage:** use Django `default_storage` (local media by default, S3-compatible when configured) behind a shared storage service.
- **OPITO numbering:** uploaded OPITO certificates use the external certificate number and do not consume `CertificateSequence`.

### Phase 1 — shared certificate/ID-card core (P0)

1. **Certificate taxonomy**
   - Add `CertificateTypeCode.OPITO = 4`.
   - Add the OPITO seed row.
   - Update existing OPITO courses from `cert_type_id=1` to `4`.
   - Keep generated certificates on the local certificate sequence.
   - OPITO uploaded certificates use the external certificate number and must not consume the local sequence.
   - Add tests for certificate type and OPITO course classification.

2. **Course ID-card template**
   - Add `Course.front_id_text` and `Course.back_id_text`.
   - Add migration, serializer, admin, and course form.
   - Render these fields into the ID-card PDF.

3. **Expiry rules**
   - Add explicit expiry choices: `0=no expiry`, `1=calculated`, `2=FOET`.
   - Implement FOET expiry calculation and tests.
   - Wire the rules into certificate issue/renewal.

4. **Certificate document actions**
   - Add endpoints for existence check, download PDF, generate/re-generate, upload/re-upload, and mark printed.
   - Suggested routes:
     - `HEAD /certificates/{id}/document`
     - `GET /certificates/{id}/document`
     - `POST /certificates/{id}/generate`
     - `POST /certificates/{id}/upload`
     - `POST /certificates/{id}/print`
   - Add OPITO learner ID/external-reference storage.
   - Enforce role permissions and audit every action.

5. **ID-card service**
   - Add a renderer for the front/back card PDF.
   - Add issue/generate/download/print/reprint actions.
   - Define card-number allocation.
   - Mark `IDCard.printed_at` and advance the workflow print stage.
   - Auto-complete when both certificate and ID-card print stages are done.
   - Add tests for rendering, numbering, permissions, and workflow transitions.

6. **Real document storage**
   - Replace metadata-only handling with actual file persistence, hash, MIME, size, uploader, and download/streaming.
   - Reuse this for certificates, ID cards, FOET scans, learner IDs, payment proof, welcome letters, and photos.
   - Do not return binary payloads inside JSON.
   - Add storage/permission tests.

7. **Frontend staff workspace**
   - Certificate panel: state, PDF exists, Generate/Re-generate, Upload/Re-upload, Download.
   - ID-card panel: Generate, preview/download, Mark printed, Re-print.
   - Course form: ID-card front/back text.
   - Hide actions based on role.

8. **Portal certificate access**
   - Add a Download action to the portal certificate table.
   - Call the same shared endpoint used by the staff console.
   - Add ID-card access only if the chosen access policy allows it.

**Phase 1 acceptance:** OPITO course uploads a certificate; non-OPITO course generates one; ID cards generate independently; print states advance correctly; portal can download; tests cover permissions and workflow transitions.

### Phase 2 — operational workspace (P1)

1. **Backend data**
   - Add `Learner.vantage_id`.
   - Add instructor module/date to `TrainingInstructor`.
   - Expose nested instructors in training-record payloads.
   - Add FOET scan, payment proof, welcome letter, and per-day medical BP.
   - Add a training-record aggregate endpoint for the workspace.

2. **Pending tasks**
   - Add date-range and status filters.
   - Add bulk approve/cancel.
   - Add a my-activity endpoint.
   - Preserve existing single-record approve/reject behavior.

3. **Frontend shell**
   - Replace the flat sidebar with Axis-style groups.
   - Add role-filtered home cards.
   - Add routes for pending tasks, my activity, courses, modules, items, reference data, profile, and reporting sub-pages.

4. **Learner/training workspace**
   - Learner profile sections: bio, contacts, photo, ID scan, vantage ID, training history, certificates, ID cards.
   - Training-record sections: instructors, items, FOET, medical BP, payment proof, welcome letter, CJI, certificate/ID-card actions.

5. **Portal reconciliation**
   - Add staff CJI visibility/resend.
   - If self-service booking is approved, add portal booking and payment-proof upload.
   - Add corporate nominee management UI if the API-only workflow is not acceptable.

### Phase 3 - reporting and flow intelligence (P1) - COMPLETE

Implemented and verified on 2026-11-06; the checklist below is retained as the delivered scope.

1. Add report datasets/endpoints for:
   - Training Records
   - Courses by Month
   - Delegates by Month
   - Courses Treemap
   - Top Training Courses
   - Role Activity
   - OPITO Monthly
2. Add year min/max selection.
3. Add XLSX and PDF exports.
4. Extend flow-status with:
   - terminal/active split
   - `15` backlog and `25` critical thresholds
   - next-role aggregation
5. Add frontend report pages, charts, filters, and role guards.

### Phase 4 — auxiliary parity (P2) — COMPLETE

Public certificate verification is complete (2026-11-07): anonymous API at
`/api/v1/verify/<identifier>/`, standalone React routes `/verify` and
`/verify/:identifier`, and portal `/portal/verify/`. Lookup accepts a certificate
number (case-insensitive) or an Axis-compatible training-record ID and exposes only
validity, status, certificate number, learner name, course, issue and expiry.

1. [COMPLETE] Public certificate verification endpoint + `/verify/:id` page.
2. [COMPLETE] OPITO file generation, validation, content preview, and CSV download.
3. [COMPLETE] Staff profile: self password change, dark mode, role manuals.
4. [COMPLETE] Backup page/endpoint.
5. [COMPLETE] Relationship APIs: `/course-item-rel`, `/course-module-rel`, `/user-role`.
6. [COMPLETE] Corporate workspace: nominees, bundles, certificate access.
7. [COMPLETE] Portal profile editing and certificate verification entry point.

### Definition of done for every slice

- Migration.
- Serializer/API contract.
- Permissions and audit.
- Backend tests.
- Frontend/portal UI.
- OpenAPI schema update.
- `Gaps.md` status update.

## Parity decisions and open questions

1. **Role 7 naming**
   - TCMS: `DUE_DILIGENCE = 7`, `DUE_DILIGENCE_DONE = 8`.
   - Axis: QA role/step at the same IDs.
   - Recommendation: keep IDs stable, display Axis-compatible labels in the new UI, and decide separately whether to rename the domain model.

2. **Rejected state**
   - TCMS adds `REJECTED = 14` with re-entry support.
   - Axis frontend enumerates statuses 1–13.
   - Recommendation: keep 14 internally if it improves rejection handling, but do not expose it as a separate Axis-style funnel column unless required.

3. **Portal booking scope**
   - Should learners self-book and upload payment proof, or should bookings remain coordinator-driven?
   - Current landing copy and dashboard behavior disagree.

4. **Certificate download/verification access**
   - Should certificate PDFs be downloadable from the authenticated portal, via a public tokenized link, or both?
   - Should public verification expose only validity, or also learner/course details?

5. **Axis evidence limits**
   - Authenticated Axis APIs and any Axis learner portal were not inspected.
   - Validate the inferred behavior before implementing high-risk workflow changes.

## Evidence index

### Staff console and backend

- `frontend/src/App.tsx` — staff routes and role guards.
- `frontend/src/components/AppShell.tsx` — grouped, role-filtered navigation.
- `frontend/src/pages/ProfilePage.tsx` — identity, password change, theme toggle and role-manual links.
- `frontend/src/pages/ManualPage.tsx`, `frontend/src/lib/manuals.ts` — role manual content and routing.
- `frontend/src/theme/context.ts`, `frontend/src/theme/ThemeProvider.tsx` — persisted light/dark theme.
- `frontend/src/pages/BackupPage.tsx` — system-admin backup and storage-test console.
- `apps/common/backup.py`, `apps/common/backup_views.py` — gzipped database snapshots, storage probe and backup API.
- `apps/accounts/views.py` — staff login, logout and self-service password change.
- `frontend/src/pages/CertificatesPage.tsx` — issue/sign/release UI; no PDF/ID-card actions.
- `apps/common/enums.py` — role/status/certificate/expiry enums.
- `apps/catalogue/models.py` — course fields, missing ID-card text, `CourseModuleItem`.
- `apps/catalogue/serializers.py` — course/certificate-type payloads.
- `apps/certification/models.py` — `Certificate`, `IDCard`, `CertificateSequence`.
- `apps/certification/services.py` — certificate issue, renewal, reminders, batches.
- `apps/certification/rendering.py` — stored `object_key` or ReportLab certificate rendering.
- `apps/certification/views.py` — certificate/ID-card API surface.
- `apps/certification/serializers.py` — certificate/ID-card serializers.
- `apps/delivery/models.py` — `TrainingRecord`, `TrainingInstructor`.
- `apps/delivery/serializers.py` — record payload; instructors omitted.
- `apps/delivery/views.py` — training-record/item/instructor viewsets.
- `apps/learners/models.py` — learner schema; no `vantage_id`.
- `apps/learners/serializers.py` — learner/contact/document payloads.
- `apps/reporting/views.py` — basic flow-status and report viewsets.
- `apps/reporting/analytics.py` — dashboard and CSV datasets.
- `apps/common/api.py` — registered API routes.
- `apps/common/urls.py` — auth/dashboard/export routes.
- `config/urls.py` — `/admin/`, `/portal/`, `/api/v1/`.
- `apps/documents/views.py` — metadata-only document API.
- `apps/workflow/models.py`, `services.py`, `views.py` — 14-stage chain and actions.
- `apps/integration/management/commands/seed_data.py` — certificate types, OPITO course seed rows.
- `apps/integration/management/commands/seed_roles.py` — role/status seed mapping.

### Learner portal

- `apps/portal/urls.py` — portal API routes.
- `apps/portal/views.py` — registration, verification, corporate, CJI, bundle endpoints.
- `apps/portal/models.py` — portal identity, verification, CJI models.
- `apps/portal/services.py` — registration, verification, corporate nominee rules.
- `apps/portal/cji.py` — CJI rendering, delivery, resend, access control.
- `apps/portal/serializers.py` — portal API payloads.
- `apps/portal_web/urls.py` — learner web routes.
- `apps/portal_web/views.py` — web registration/login/dashboard/CJI.
- `apps/portal_web/templates/portal/dashboard.html` — bookings/certificates/CJI display.
- `apps/portal_web/templates/portal/base.html` — portal shell and navigation.
- `apps/portal/tests.py`, `apps/portal_web/tests.py` — portal coverage.

### Axis evidence

- `C:\Users\tolma\AppData\Local\Temp\opencode\axis-index-pretty.js`
- `C:\Users\tolma\AppData\Local\Temp\opencode\axis-pretty\Training-Cxz5t6WO.js`
- `C:\Users\tolma\AppData\Local\Temp\opencode\axis-pretty\Course-DZgz_Dpi.js`
- `C:\Users\tolma\AppData\Local\Temp\opencode\axis-pretty\TrainingRecords-1mSCsww6.js`
- `C:\Users\tolma\AppData\Local\Temp\opencode\axis-pretty\PendingTasks-DDVcXruH.js`
- `C:\Users\tolma\AppData\Local\Temp\opencode\axis-pretty\FlowStatus-u6n2BTXB.js`
- `C:\Users\tolma\AppData\Local\Temp\opencode\axis-pretty\Home-BWPIVYse.js`
- `C:\Users\tolma\AppData\Local\Temp\opencode\axis-pretty\Reporting-Di5Jff6H.js`
- `C:\Users\tolma\AppData\Local\Temp\opencode\axis-pretty\TopTrainingCourses-B-KJBXGn.js`
- `C:\Users\tolma\AppData\Local\Temp\opencode\axis-pretty\LearnerByMonth-Bv_2Ps1D.js`
- `C:\Users\tolma\AppData\Local\Temp\opencode\axis-pretty\CourseByMonth-8seAplD7.js`
- `C:\Users\tolma\AppData\Local\Temp\opencode\axis-pretty\CoursesTreemap-CDqsbokr.js`
- `C:\Users\tolma\AppData\Local\Temp\opencode\axis-pretty\OpitoFileGenerate-DSAOOFDj.js`
- `C:\Users\tolma\AppData\Local\Temp\opencode\axis-pretty\Verify-CeEzTKee.js`
- `C:\Users\tolma\AppData\Local\Temp\opencode\axis-assets\Backup-DJPuL__x.js`
- `C:\Users\tolma\AppData\Local\Temp\opencode\axis-pretty\MyActivity-CzIqz20k.js`
- `C:\Users\tolma\AppData\Local\Temp\opencode\axis-pretty\Profile-BZ3UytuR.js`
- `C:\Users\tolma\AppData\Local\Temp\opencode\axis-pretty\User-B6hR42dq.js`
- `C:\Users\tolma\OneDrive\Desktop\ERP_Project\Pre-Tascl\screenshot\1` — 17 Axis screenshots OCR’d for structural analysis.

## Verification

Phase 1 was verified on 2026-11-05:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py spectacular --validate --file %TEMP%\tcms-schema.yaml
python -m ruff check apps config
python manage.py test -v 1
cd frontend
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
```

Result: `check`, migration check, schema validation, Ruff, frontend typecheck, lint and build passed; the full backend suite passed with **256 tests**. Local migrations `catalogue.0002` and `certification.0005` were applied and `seed_data` re-run to classify the seeded OPITO/FOET courses.

Phase 2 was verified on 2026-11-06:

```powershell
python manage.py check
python -m ruff check apps config
python manage.py spectacular --validate --file NUL
python manage.py test -v 1 --noinput
cd frontend
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
```

Result: `check`, Ruff, OpenAPI schema validation, frontend typecheck, lint and production build passed; the full backend suite passed with **264 tests**. Phase 2 migrations `delivery.0003_traininginstructor_module_and_more` and `learners.0003_learner_vantage_id_alter_learnerdocument_kind` were applied. Focused workspace coverage includes filters, bulk approvals, my activity, CJI resend failure, daily medical checks, clinical-role enforcement and instructor assignment.

Phase 3 was verified on 2026-11-06:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py spectacular --file schema.yml --validate
python -m ruff check apps config
python manage.py test -v 1 --noinput
cd frontend
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
```

Result: `check`, migration check, OpenAPI schema validation, Ruff, frontend typecheck, lint and production build passed; the full backend suite passed with **264 tests**, including the new reporting-intelligence coverage. "format" query selection now uses `URL_FORMAT_OVERRIDE="export_format"` so `format=csv|xlsx|pdf` does not collide with DRF content negotiation.

Phase 4 public verification slice was verified on 2026-11-07: `check`, migration
check, OpenAPI schema validation, Ruff, frontend typecheck, lint, production build
and the full backend suite passed with **276 tests**. Coverage includes
certificate-number and training-record lookup, case-insensitive numbers, latest
certificate selection, expired/void/not-issued states, 404 handling, portal rendering
and portal rate limiting.

Phase 4 OPITO file workflow was verified on 2026-11-07: `check`, migration check,
OpenAPI schema validation, Ruff, frontend typecheck, targeted ESLint, production
build and the certification suite passed with **54 tests**, including generation,
regeneration, Vantage-ID validation, CSV headers/rows, role denial, and download
streaming.

Phase 4 staff profile slice was verified on 2026-11-08: `check`, migration check,
OpenAPI schema validation, Ruff, frontend typecheck, targeted ESLint, production
build and the full backend suite passed with **286 tests**. Coverage includes
self-service password validation, current-password rejection, mismatch/reuse
handling, audit attribution, token preservation, role manual routing and theme
persistence.

Phase 4 backup console slice was verified on 2026-11-08: `check`, migration check,
OpenAPI schema validation, Ruff, frontend typecheck, targeted ESLint, production
build and the full backend suite passed with **289 tests**. Coverage includes
snapshot creation and gzip decoding, system-admin-only access, writable-storage
probe cleanup, audit events, schema validation and the `/backup` route.

Phase 4 completion slice was verified on 2026-11-09:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py spectacular --validate --file schema-check.yaml
python -m ruff check apps config
python manage.py test -v 1 --noinput
cd frontend
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
```

Result: all commands passed; the full backend suite passed with **299 tests**.
Coverage includes Axis relation-payload variants and relation lifecycles, `/user-role`
permissions and deletion, learner photo/ID-scan upload/download and unauthorised
rejection, portal profile updates and underage rejection, corporate account
creation, nominee add/edit/remove, certificate-bundle dispatch, and the earlier
Phase 1-4 suites.

The Users parity slice was verified on 2026-11-10 with the same commands. The full
backend suite passed with **303 tests**, including own-account deletion protection,
System Admin role removal/deactivation protection, and emailed password-reset
links. Coverage also confirms the card directory, `/users/:id` detail, role
assignment/removal, delete confirmation and responsive user-detail styling.

The Axis home/navigation slice was verified on 2026-11-10 with frontend
`typecheck`, `lint` and `build`. All three passed. Backend code was unchanged, so
the 303-test suite remains the latest backend result.

The Axis pending-tasks slice was verified on 2026-11-11: `check`, OpenAPI schema
validation, Ruff, frontend typecheck, lint and production build passed; the full
backend suite passed with **304 tests**. Coverage includes search across learner,
company and course fields, exact-date filtering, paginated `pending-tasks`
responses, invalid-date rejection, `course_name`/`company_name` serialization and
the Axis-style bulk approve/return table.

The portal sign-in guard was verified on 2026-11-11 with `check`, Ruff and the
full backend suite, which passed with **307 tests**. Staff accounts without a
`PortalAccount` are rejected by the learner portal, authenticated staff are sent
to the configured staff console, and the portal’s “Staff sign-in” link no longer
targets Django admin. `STAFF_APP_URL` configures the target.

Use the same commands for subsequent slices:
