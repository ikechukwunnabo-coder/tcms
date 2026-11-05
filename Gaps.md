# TCMS vs Axis Gap Analysis

## Document control

- **Status:** Phase 1 complete — OPITO taxonomy, expiry rules, document storage, certificate/ID-card actions, staff course UI, role-gated document actions and portal certificate download; Phase 2+ pending
- **Date:** 2026-11-05
- **Repository:** `C:\Users\tolma\OneDrive\Desktop\ERP_Project\Pre-Tascl\tcms`
- **Baseline commit:** `0485294 Fix CI dependency audit and deploy check`
- **Worktree:** Phase 1 changes in progress (backend, frontend, portal, migrations); `Gaps.md` tracks remaining work
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

- `/` — operations dashboard
- `/workflow` — approval workflow
- `/learners` — learner list
- `/courses` — course setup, certificate type and ID-card text
- `/scheduling` — sessions
- `/enrolments` — enrolments
- `/certificates` — certificate issue/sign/release list
- `/billing` — invoices, payments, corporate accounts
- `/medicals` — medicals
- `/reports` — generic reporting
- `/users` — staff/team access, admin-only

Implemented navigation is a flat 10-item sidebar (`frontend/src/components/AppShell.tsx`). There are no grouped Axis-style navigation sections, role-filtered home cards, pending-tasks page, course/reference setup pages, profile page, backup page, OPITO page, public verification page, or report sub-pages.

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

Portal web dashboard (`apps/portal_web/templates/portal/dashboard.html`) currently shows:

- Corporate nominees, read-only, for corporate leads.
- The caller’s bookings with course, session, venue, and state.
- CJI view/resend actions when a current CJI exists.
- The caller’s certificates with issued/expiry/state.

The portal has broad tests for registration, verification, password reset, login, dashboard scoping, CJI access, and corporate nominee rules (`apps/portal/tests.py`, `apps/portal_web/tests.py`).

### Axis target

Observed Axis structure and behavior:

- Grouped navigation: **Tasks**, **Operations**, **Course Setup**, **Reference Data**, **Access**, **Admin Tools**.
- Routes include `/pending-tasks`, `/my-activity`, `/opito-files`, `/learners`, `/trainings`, `/courses`, `/course-modules`, `/course-items`, `/companies`, `/states`, `/nationalities`, `/users`, `/roles`, `/reporting`, `/backup`, report subroutes, and public `/verify/:id`.
- Role-filtered home cards.
- Pending-task calendar/status filters, bulk approve/cancel, floating approve/reject actions.
- Flow-status backlog thresholds: `15` backlog, `25` critical.
- Seven reported report cards: Training Records, Courses by Month, Delegates by Month, Courses Treemap, Top Training Courses, Role Activity, OPITO Monthly.
- Certificate/ID-card issuance differentiates generated versus uploaded documents.
- OPITO certificate type is `4`; the TCMS seed only defines `1` and `2`.

## Executive summary

The TCMS staff console already has the core operational backbone: learners, sessions, enrolments, approvals, certificates, medicals, billing, and reporting exports. It also exceeds the visible Axis surface in finance/payroll and some portal capabilities.

The largest remaining parity gaps are:

1. **Certificate and ID-card lifecycle** — OPITO type, uploaded versus generated certificates, PDF existence checks, re-generation/re-upload, ID-card templates, ID-card rendering, and print-state handling.
2. **Operational shell** — grouped navigation, role-filtered home cards, pending tasks, course/reference setup pages, profile, activity, backup, OPITO files, and public verification.
3. **Data capture around training records** — instructor assignment date/module, FOET scan, per-day medical BP, payment proof, welcome letter, and document upload/download.
4. **Reporting** — Axis-specific report endpoints, year filters, charts, XLSX/PDF exports, and richer flow-status metrics.
5. **Relationship/data APIs** — course-module-item relationships, user-role relationships, and `vantage_id`.

The TCMS learner portal is strongest where Axis staff parity is weakest in this repo: public registration, email verification, password reset, corporate nominees, and CJI delivery. Its main gaps are:

- No certificate PDF download or ID-card access, even though the dashboard lists certificates.
- No self-service booking or payment-proof upload, despite landing-page copy that promises booking.
- Corporate account/nominee mutation exists only through the API; the web dashboard is read-only for nominees.
- No profile editing, no certificate verification, and no OPITO visibility.
- Several document features are metadata-only; there is no shared upload/download artefact contract.

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
| P1 | Instructor capture | Assignment includes date and module | `TrainingInstructor` only links record + instructor (`delivery/models.py:67`); serializer omits it (`delivery/serializers.py:12`) | Add module/date fields, expose nested instructors, UI |
| P1 | FOET and medical evidence | FOET scan upload; per-course-day BP readings | Medicals exist, but no FOET document workflow; learner documents are metadata-only | Add document kinds/upload/download and medical BP day model/UI |
| P1 | Payment proof / welcome letter | Upload payment proof; generate/upload welcome letter | Billing and notifications exist; no staff upload/generate UI for these artefacts | Add document actions and UI, reuse existing billing/notification services |
| P1 | Learner profile | `vantage_id`, photo, learner-ID scan, contacts, training history, ID-card preview | `Learner` lacks `vantage_id` (`learners/models.py:8`); contacts/documents exist; frontend profile is limited | Add field, profile sections, photo/ID-scan surfaces, training-history aggregate |
| P1 | Reporting | Seven chart/report pages, year min/max, XLSX/PDF, flow thresholds | Generic report defs, CSV export, basic flow counts (`reporting/views.py:54`) | Add report endpoints, chart datasets, exports, threshold logic |
| P1 | Shell/nav/home | Grouped nav, role-filtered home cards, missing routes | Flat 10-item nav (`AppShell.tsx:44`); core routes only (`App.tsx:95`) | Add grouped nav, home cards, role guards, missing pages |
| P1 | Pending tasks / activity | Calendar-filtered pending tasks, bulk approve/cancel, my activity | Single-record workflow actions exist; no bulk endpoint or page | Add bulk actions, filters, pending-tasks page, activity endpoint/page |
| P1 | Public verification | `/verify/:id` public certificate check | Only `CERTIFICATE_VERIFY_URL` rendering setting; no route/endpoint | Add public verification endpoint and portal/standalone page |
| P1 | OPITO file workflow | Generate/validate/upload OPITO file | Only `Course.opito_reg_code`; no OPITO workflow | Add OPITO file generation/validation/upload services and page |
| P1 | Profile/backup | Self password, dark mode, manuals, backup UI | Staff users are admin-only; no self-service profile or backup surface | Add profile/password endpoint and UI, backup endpoint/page |
| P1 | Relationship APIs | `/course-item-rel`, `/course-module-rel`, `/user-role` | `CourseModuleItem` model exists (`catalogue/models.py:71`) but no route; no user-role route | Add nested serializers, viewsets, admin/UI support |
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
| Identity | Admin-only staff users/roles | Self-registration, email verification, password reset | Shared `User`/`Learner` backend; staff still lacks self-service profile/password |
| Learner data | Full learner CRUD and contacts/documents API | Own learner record or corporate nominees, read-only in web UI | Shared schema gap: no `vantage_id`, photo, ID scan, or profile editing |
| Certificates | Issue, sign, release, list | Lists certificate number, dates, state | Neither surface supports PDF download; no ID-card surface |
| ID cards | Model/CRUD only | None | Shared backend gap; needs renderer/issue/print and portal access |
| Bookings | Sessions, enrolments, scheduling | Lists bookings; cannot create or change bookings | Clarify portal scope; landing copy promises booking but dashboard says coordinator books |
| Payments | Invoices, payments, corporate accounts | No payment-proof upload or payment view | Decide whether portal needs payment-proof upload or remains coordinator-driven |
| CJI | Backend service only; no frontend | View/resend current CJI | Add staff visibility/resend from enrolment/training record |
| Corporate | Corporate accounts in billing UI | API supports account/nominee/bundle; web UI is read-only nominees | Build a unified corporate workspace or add portal mutation UI |
| Verification | Email verification only | Email verification only | Public certificate verification is absent from both surfaces |
| Documents | Learner-document metadata API | None | `Document` is metadata-only (`documents/views.py:17`); need real storage/download contract |
| OPITO | `opito_reg_code` on course only | None | Shared OPITO issuance/status gap |
| Reports | Generic reports/CSV | None | Axis-specific reports remain a staff-console gap |

### Cross-surface shared gaps

These should be fixed once in shared services/APIs, not separately in React and Django templates:

1. **Certificate and ID-card artefact service** — render, upload, download, HEAD/existence, re-generate/re-upload, print marking, permissions.
2. **Document storage/upload contract** — actual file persistence and streaming/signed download, replacing metadata-only `Document` and learner-document APIs.
3. **Learner profile extensions** — `vantage_id`, photo, learner-ID scan, FOET scan, and training-history aggregation.
4. **Corporate workspace** — nominees, certificate bundles, certificate access, and corporate account context shared by staff and portal.
5. **Public certificate verification** — one canonical endpoint used by a standalone `/verify/:id` page and/or portal route.
6. **Reporting/export service** — XLSX/PDF exports and report datasets usable by staff UI and future portal reporting.
7. **Role/status display policy** — Axis labels versus TCMS’s extra `REJECTED=14` state.

### Portal-specific inconsistencies to resolve

- The landing page says “Book your training,” but the dashboard says courses are booked through the training coordinator and exposes no booking action.
- `portal/base.html` metadata mentions downloading certificates, but the dashboard has no certificate download action.
- Corporate nominee mutation and certificate bundling exist in the API but not in the web portal UI.
- The portal lists certificates but cannot retrieve the PDF or ID card.
- Portal login is email-based; staff console login is username-based. This is workable but should be documented as intentional.
- There is no public certificate verification page; “verification” in the portal currently means email verification only.
- There is no profile page, no dark-mode/manual surface, and no OPITO status visibility.

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

### Phase 3 — reporting and flow intelligence (P1)

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

### Phase 4 — auxiliary parity (P2)

1. Public certificate verification endpoint + `/verify/:id` page.
2. OPITO file generation, validation, and upload.
3. Staff profile: self password change, dark mode, role manuals.
4. Backup page/endpoint.
5. Relationship APIs: `/course-item-rel`, `/course-module-rel`, `/user-role`.
6. Corporate workspace: nominees, bundles, certificate access.
7. Portal profile editing and certificate verification entry point.

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
- `frontend/src/components/AppShell.tsx` — flat navigation.
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
- `C:\Users\tolma\AppData\Local\Temp\opencode\axis-pretty\Backup-DJPuL__x.js`
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

Use the same commands for subsequent slices:
