# Senior App Development Syllabus

This syllabus is tailored to the gaps found from your Codex session history. The goal is not to memorize syntax. The goal is to become capable of supervising app development at a senior level: defining the work, understanding the tradeoffs, reviewing Codex changes, debugging failures, and protecting the codebase from regressions.

Your current strength is domain thinking. You describe factory workflows, Excel needs, IFS behavior, reports, labels, machine rules, and operational problems clearly. The missing layer is the software engineering model that turns those workflows into durable app architecture.

## Core Mental Model

Every app feature should be understood as a chain:

```text
User action
-> HTML/UI state
-> JavaScript handler
-> HTTP request
-> FastAPI route
-> service/use-case logic
-> database / Excel / IFS / file system
-> response
-> UI render / report / print / export
-> tests and logs
```

Most of the gaps in your history live inside this chain.

## Phase 1: Web App Mental Model

**Duration:** 1 week

**Goal:** Understand what an app actually is end to end.

Learn:

- Frontend, backend, database, API, server, client, and deployment.
- `localhost` vs LAN IP vs public domain vs cloud server.
- What happens when you type a URL into your phone.
- Which files the browser can see and which files stay private on the server.
- Why you cannot download private server-side files from a public website.
- Why a cloud app cannot automatically read a file from your desktop.

Practice:

- Draw your app architecture from memory.
- Mark which parts run on your phone, which run on the office PC, and which run in IFS.
- Explain why `127.0.0.1` works on the PC but not from the phone.
- Explain why cloud hosting changes file access, database access, and internal network access.

Senior bar:

- You can classify a bug as browser, network, backend, database, filesystem, cache, or external API.

## Phase 2: Local Development Environment

**Duration:** 1 week

**Goal:** Stop being dependent on Codex for basic runtime control.

Learn:

- Python installation and version checks.
- Virtual environments.
- `pip`, `requirements.txt`, and `pyproject.toml`.
- Running FastAPI with Uvicorn.
- Environment variables.
- `.env` and `.env.example`.
- PATH basics on Windows.
- Finding and killing running server processes.
- Port conflicts.

Commands to master:

```powershell
python --version
where python
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 80
netstat -ano | findstr :80
taskkill /PID <pid> /F
```

Practice:

- Start the app without Codex.
- Find the active server process.
- Change the port from `80` to `8000` and explain what changed.
- Open `/health` from the PC and from the phone.
- Confirm whether the active server is running the newest code.

Senior bar:

- You can tell whether a problem is code, process, port, firewall, Wi-Fi, or stale server state.

## Phase 3: HTTP, APIs, And Request Lifecycle

**Duration:** 2 weeks

**Goal:** Understand how frontend actions become backend behavior.

Learn:

- HTTP methods: `GET`, `POST`, `PUT`, `DELETE`.
- Status codes: `200`, `400`, `401`, `403`, `404`, `409`, `500`.
- Request body vs query parameters vs path parameters.
- JSON shape.
- Form submissions.
- Browser Network tab.
- FastAPI route handlers.
- Pydantic request and response models.
- Validation errors.

Practice:

- Pick one button in your app.
- Trace exactly which JavaScript function runs.
- Trace which API endpoint it calls.
- Trace which backend route receives the request.
- Trace which service function runs next.
- Trace what response comes back.
- Write the request and response shape by hand.

Example trace:

```text
Button: Kontrol et
Frontend handler: packageLabelChecklist.js -> handleCheck()
API: POST /api/package-label/check
Payload: { job_order_no, label_no }
Backend route: package_label_router.py
Service: resolve_machine_code()
Response: { rows: [...], machine_code, status }
```

Senior bar:

- Before implementing a feature, you can define its API contract.

## Phase 4: Data Contracts And Schema Thinking

**Duration:** 2 weeks

**Goal:** Stop UI/backend/Excel/IFS mismatch bugs.

Learn:

- What a data model is.
- UI labels vs internal field names.
- Database schema vs Excel columns vs API payload.
- Required vs optional fields.
- Null values.
- Derived fields.
- Stable IDs vs display names.
- Backward compatibility.

Practice:

- Take one feature and create a contract table.
- Use the table for machine code, product name, raw material, job order, label number, cycle time, and receipt date.

Contract table format:

```text
UI label | JS field | API field | Backend model | DB/Excel/IFS source | Required?
```

Senior bar:

- You no longer say, "add this column to UI and backend."
- You say, "add field X to the contract, validate it here, persist it there, display it here, and test these cases."

## Phase 5: FastAPI Backend Architecture

**Duration:** 3 weeks

**Goal:** Understand professional backend structure.

Learn:

- `main.py` app startup.
- Routers.
- Services and use cases.
- Repositories and data access.
- Schemas and models.
- Config modules.
- Dependency injection basics.
- Error handling.
- Logging.
- File paths and path configuration.
- Separating business logic from route handlers.

Target structure:

```text
app/
  main.py
  core/
    config.py
    security.py
  features/
    package_label/
      router.py
      schemas.py
      service.py
      repository.py
      tests/
  templates/
  static/
tests/
```

Practice:

- Refactor one small route mentally into route, schema, service, repository, and test.
- Explain why route handlers should stay thin.
- Explain where Excel-reading logic belongs.
- Explain where IFS-calling logic belongs.
- Explain where business rules belong.

Senior bar:

- You can look at a file and know whether it has too many responsibilities.

## Phase 6: Frontend Architecture For Internal Tools

**Duration:** 2 weeks

**Goal:** Become comfortable with UI wiring, modules, and static assets.

Learn:

- HTML structure.
- Forms and buttons.
- DOM selectors.
- Event listeners.
- ES modules.
- State in the browser.
- Rendering tables.
- Loading, empty, success, and error states.
- Print views.
- Cache busting.
- Service worker and PWA basics if your app uses them.

Practice:

- Pick one page and map its template file, JavaScript file, CSS file, API endpoints, and events.
- Add a fake test button locally and wire it to `console.log`.
- Use browser DevTools to confirm which JavaScript file version loaded.
- Inspect Network tab and disable cache.
- Explain what `STATIC_ASSET_VERSION` or equivalent cache busting does.

Senior bar:

- If a button does nothing, you know how to check HTML id, JS import, event listener, console error, network request, and backend route.

## Phase 7: Debugging Like A Senior

**Duration:** 3 weeks

**Goal:** Stop treating bugs as mysteries.

Debugging loop:

```text
1. Reproduce
2. State expected behavior
3. State actual behavior
4. Locate layer
5. Inspect logs/network/data
6. Form hypothesis
7. Make smallest fix
8. Add regression test
9. Verify
```

Practice on real bug types:

- Button does nothing.
- API returns `404`.
- Report gives wrong rows.
- Machine code is `Belirsiz`.
- Excel file is not found.
- Phone cannot access app.
- Static JavaScript is stale.
- IFS returns empty data.
- Report is slow.
- A date boundary gives wrong production rows.

Senior bar:

- Before asking Codex to fix a bug, you can say, "My hypothesis is the bug is between service X and data source Y because Z."

## Phase 8: Testing Strategy

**Duration:** 3 weeks

**Goal:** Learn what to test, not just how to run tests.

Learn:

- Unit tests.
- Integration tests.
- API tests.
- Regression tests.
- Frontend smoke tests.
- Fixture data.
- Mocking IFS/API responses.
- Testing date windows.
- Testing report generation.
- Testing cache-sensitive UI wiring.

For every feature, define:

```text
Happy path
Missing input
Invalid input
External API empty
External API error
Date boundary
Duplicate request
UI render check
```

Tests to practice with your app:

- Package label machine-code resolution.
- Production loss date logic.
- Cycle report matching.
- Excel path missing.
- IFS timeout/fallback.
- Print checklist rendering.
- Static asset version updated when frontend changes.
- UI button wired to the expected API endpoint.

Senior bar:

- Every bug fix gets a regression test unless there is a clear reason not to.

## Phase 9: Git And Change Control

**Duration:** 1 week

**Goal:** Use Codex without losing control of the codebase.

Learn:

```powershell
git status
git diff
git add
git commit
git log
git branch
git switch
git restore
git stash
```

Practice:

- Before Codex changes anything, run `git status`.
- After Codex changes something, inspect `git diff`.
- Commit small changes with clear messages.
- Create a branch for risky refactors.
- Revert one file without resetting everything.
- Identify unrelated changes and avoid mixing them into a commit.

Senior bar:

- You never accept AI-generated code blindly. You inspect the diff and understand the risk.

## Phase 10: Deployment And Operations

**Duration:** 2 weeks

**Goal:** Understand what production really means.

Learn:

- Local server vs production server.
- Cloud hosting limitations.
- Why local Excel files do not work automatically in cloud.
- SQLite vs Postgres.
- Backups.
- Logs.
- Uptime.
- HTTPS.
- Domains.
- Firewalls.
- Internal network access.
- Offline-first workflow.
- Sync queues.

Practice:

- Write a production-readiness checklist for your app.
- Decide what must move from Excel to a database.
- Decide what can stay local.
- Design an offline queue for phone data entry.
- Explain how sync conflicts should be handled.
- Explain what happens when the office PC is off.

Senior bar:

- You can say whether a deployment idea is technically possible, secure, reliable, and maintainable.

## Phase 11: Security, Auth, And Secrets

**Duration:** 2 weeks

**Goal:** Stop treating secrets and auth as magic.

Learn:

- Password storage basics.
- Sessions.
- Cookies.
- `SESSION_SECRET`.
- CSRF concept.
- Environment variables.
- API tokens.
- OAuth basics.
- Service accounts.
- Least privilege.
- Secret rotation.
- Why credentials should not be pasted into chats or committed to code.

Practice:

- Identify every secret your app uses.
- Move secrets into `.env`.
- Make sure `.env` is ignored by Git.
- Create or review `.env.example`.
- Explain what happens if `SESSION_SECRET` changes.
- Explain the difference between user login and API token.

Senior bar:

- You can review a feature and ask: "Who is allowed to do this, how do we know, and where is the secret stored?"

## Phase 12: IFS, OData, And Enterprise API Integration

**Duration:** 4 weeks

**Goal:** Build a stable mental model of IFS data access.

Learn:

- What IFS projections are.
- OData entities.
- Query filters.
- Pagination.
- `$select`, `$filter`, `$expand`, `$top`.
- Auth and token flow.
- API Explorer.
- Difference between UI screen, projection, entity, and database table.
- Mapping business concepts to API objects.
- Handling partial or missing IFS data.
- Rate limits and timeouts.

Practice:

- For each IFS feature, create a mapping doc.

Mapping doc format:

```text
Business concept:
IFS screen:
Projection:
Entity:
Important fields:
Filters:
Example URL:
Example response:
App service using it:
Tests/mocks:
```

Create mapping docs for:

- Job order.
- Machine.
- Operation history.
- Inventory part in stock.
- Labels/packages.
- Receipt date.
- Production timestamps.

Senior bar:

- You do not ask, "Which IFS endpoint do I need?" blindly.
- You first define the business object, likely projection, key fields, filters, and fallback behavior.

## Phase 13: UI/UX For Dense Factory Tools

**Duration:** 2 weeks

**Goal:** Design internal tools that are clear, fast, and hard to misuse.

Learn:

- Information hierarchy.
- Table design.
- Filters.
- Empty states.
- Error states.
- Confirmation states.
- Print layout.
- Mobile-first data entry.
- Reducing scrolling.
- Grouping by workflow.
- Designing for factory conditions.

Practice:

- Redesign one screen on paper before coding.
- Mark primary actions, secondary actions, and dangerous actions.
- Define what the operator sees first.
- Define what happens when data is missing.
- Define what should be printable.
- Define what must fit on a phone screen.

Senior bar:

- Your UI decisions support the workflow. They are not just attempts to make the page look professional.

## Phase 14: Working With Codex Like A Senior

**Duration:** Ongoing

**Goal:** Use AI as a force multiplier, not a crutch.

Weak prompt:

```text
Fix this professionally.
```

Strong prompt:

```text
Inspect the package label workflow end to end.

Goal:
Machine code should resolve from IFS operation data when a package label is checked.

Trace:
Frontend button -> API route -> service -> IFS client -> response render.

Do:
1. Identify root cause.
2. Explain which layer is wrong.
3. Propose long-term fix.
4. Add regression tests.
5. Do not change unrelated workflows.
6. Restart server only after tests pass.
```

Practice:

- For every Codex task, write the goal.
- Describe current behavior.
- Describe expected behavior.
- Name relevant files if known.
- Define acceptance criteria.
- Define test expectations.
- Say what should not change.

Senior bar:

- Codex becomes your junior engineer. You define the work, review the diff, and hold the quality bar.

## Weekly Study Structure

Use this rhythm:

```text
Day 1: Learn concept
Day 2: Inspect your app for that concept
Day 3: Modify or trace one small feature
Day 4: Write tests or a checklist
Day 5: Explain it back in your own words
Day 6: Ask Codex to challenge your understanding
Day 7: Rest / review / clean notes
```

The best exercise is not watching tutorials. It is taking your own app and repeatedly asking:

```text
Where does this data come from?
Where is it validated?
Where is it stored?
Where is it displayed?
What breaks if it is missing?
What test proves this works?
```

## Final Capstone

At the end, rebuild one feature professionally from scratch.

Recommended capstone:

- Package Label Checklist, or
- Production Loss Report.

Deliverables:

- One-page feature spec.
- API contract.
- Data source mapping.
- Backend service design.
- Frontend interaction flow.
- Error states.
- Test plan.
- Implementation.
- Regression tests.
- Deployment/runtime notes.
- Debugging checklist.

Success criteria:

- You can explain the whole feature without reading the code line by line.
- You can identify the likely failure points.
- You can review Codex's implementation diff.
- You can decide which tests prove the feature works.
- You can deploy or run it locally without guessing.

## Recommended Learning Order

1. Request lifecycle: browser -> JavaScript -> API -> service -> data source -> response.
2. Local server and networking basics.
3. Data contracts and schema design.
4. App structure: routers, services, repositories, frontend modules.
5. Debugging with logs, browser DevTools, and tests.
6. Deployment constraints.
7. Security, secrets, and auth.
8. IFS, OData, and API integration patterns.

## Personal Focus Areas

Based on the session history, these are your highest-return topics:

- Local server networking: phone access, ports, LAN IPs, firewalls, stale processes.
- Data contracts: keeping UI, backend, Excel, database, and IFS aligned.
- Debugging: tracing one failure through all layers before changing code.
- Tests: writing regression tests for every repeated bug.
- Architecture: keeping business logic out of routes and UI glue.
- Security: understanding sessions, tokens, secrets, and environment variables.
- IFS/OData: mapping business concepts to real API projections and fields.

## The Standard To Aim For

You are at the point where your domain knowledge is strong enough to build useful internal software. The next step is to stop thinking of Codex as "the thing that fixes the app" and start thinking of it as an engineer you supervise.

At senior level, you should be able to say:

```text
This feature touches these layers.
This is the contract.
These are the edge cases.
These are the tests.
This is the deployment risk.
This is what Codex may accidentally break.
```

When you can do that consistently, you are no longer just directing app development. You are leading it.
