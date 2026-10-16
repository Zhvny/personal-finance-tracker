Last Updated: 29-05-2026 (14:30)

# Design Document: Fullstack Monorepo Scaffold (Finance Tracker)

**Date:** 2026-05-24
**Status:** Approved
**Topic:** Monorepo Refactoring & Fullstack Scaffolding

---

## 1. Executive Summary
This project refactors the `finance-tracker` codebase into a polyglot fullstack monorepo. It centralizes business logic into a shared Python package, implements a Next.js frontend, a FastAPI backend, and uses Prisma with PostgreSQL for data persistence. Turborepo orchestrates the build and development lifecycle.

---

## 2. Architecture & Components

### 2.1 Workspace Structure (pnpm + Turborepo)
The monorepo is organized into `apps` (deployable services) and `packages` (shared logic/config).

- **Apps**:
  - `apps/web`: Next.js (TypeScript, Tailwind CSS) - User Interface.
  - `apps/api`: FastAPI (Python) - REST API.
  - `apps/cli`: Existing Finance Tracker CLI (Python) - Local Management.
- **Packages**:
  - `packages/core`: Shared Python library containing Domain Models (Pydantic), Financial Logic, and Business Rules.
  - `packages/database`: Prisma schema (Single Source of Truth) and Docker Compose (PostgreSQL).
  - `packages/types`: Automatically generated TypeScript interfaces from `packages/core` Pydantic models.
  - `packages/ui`: Shared React component library (shadcn/ui or custom).

### 2.2 Data Layer
- **Database**: PostgreSQL (Dockerized).
- **ORM**: Prisma (SSOT for schema management).
- **Python Client**: `prisma-client-py` used by both `apps/api` and `apps/cli`.

### 2.3 Business Logic Centralization
- All financial calculations (CAGR, FIFO, Risk) and validation logic reside in `packages/core`.
- `apps/api` and `apps/cli` import these modules, ensuring identical behavior across interfaces.

---

## 3. Fullstack Bridge (Type Sharing)

### 3.1 Pydantic to TypeScript
- A generation script in `packages/core` converts Pydantic models into TypeScript interfaces.
- Interfaces are written to `packages/types/index.ts`.
- `apps/web` consumes these types to maintain end-to-end type safety.

---

## 4. Automation & Pipeline (turbo.json)

- **`dev`**: Starts PostgreSQL (Docker), then launches FastAPI and Next.js in parallel.
- **`generate`**: Runs `prisma generate` and the Pydantic-to-TS script.
- **`build`**: Builds the Next.js application and compiles Python assets.

---

## 5. Success Criteria
1. `pnpm dev` launches the entire stack (Postgres, API, Web).
2. The CLI can perform transactions against the same Postgres DB.
3. Adding a field to a Pydantic model in `core` updates the TS types in `web` after a `generate` run.
4. Shared financial logic produces identical results in CLI and Web.

---

## 6. Self-Review Notes
- **Scope**: Focused on scaffolding and refactoring the monorepo structure.
- **Isolation**: Services are decoupled via REST (Web/API) and local imports (CLI/Core).
- **Ambiguity**: Naming follows established project conventions (`apps/`, `packages/`).
