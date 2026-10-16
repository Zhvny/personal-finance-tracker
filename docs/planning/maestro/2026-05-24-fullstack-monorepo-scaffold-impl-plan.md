Last Updated: 29-05-2026 (14:30)

# Fullstack Monorepo Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor finance-tracker into a polyglot monorepo with centralized logic, FastAPI backend, Next.js frontend, and PostgreSQL.

**Architecture:** Approach 1 (Integrated Turborepo). Centralized logic in `packages/core`, shared DB via Prisma in `packages/database`, and automated TS type generation.

**Tech Stack:** pnpm, Turborepo, FastAPI, Next.js, Prisma, PostgreSQL, Docker.

---

## Phase 1: Workspace Foundation
**Objective:** Initialize monorepo structure and Turborepo orchestration.
**Agent:** devops_engineer

- [ ] **Step 1: Create `pnpm-workspace.yaml`**
- [ ] **Step 2: Configure root `package.json` with scripts**
- [ ] **Step 3: Create `turbo.json` with dev/build pipelines**
- [ ] **Step 4: Verify workspace with `pnpm install`**

---

## Phase 2: Shared Core & Data Layer
**Objective:** Centralize business logic and set up PostgreSQL with Prisma.
**Agent:** data_engineer

- [ ] **Step 1: Initialize `packages/core` as a Python package**
- [ ] **Step 2: Create `packages/database` with Docker Compose for PostgreSQL**
- [ ] **Step 3: Define core schema in `packages/database/schema.prisma`**
- [ ] **Step 4: Generate Prisma client for Python**
- [ ] **Step 5: Migrate existing models from CLI to `packages/core/models.py`**

---

## Phase 3: Backend API & Type Bridge
**Objective:** Scaffold FastAPI and implement Pydantic-to-TypeScript generation.
**Agent:** coder

- [ ] **Step 1: Initialize `apps/api` with FastAPI and Prisma integration**
- [ ] **Step 2: Implement type generator script in `packages/core/scripts/generate_types.py`**
- [ ] **Step 3: Run generator to produce `packages/types/index.ts`**
- [ ] **Step 4: Create basic health check and data endpoints in `apps/api`**

---

## Phase 4: Frontend Scaffolding
**Objective:** Initialize Next.js app and consume shared types.
**Agent:** coder

- [ ] **Step 1: Create `apps/web` using Next.js (TS, Tailwind)**
- [ ] **Step 2: Link `packages/types` in `apps/web`**
- [ ] **Step 3: Create a dashboard view that displays data from the API**
- [ ] **Step 4: Verify Turborepo `dev` command starts both API and Web**

---

## Phase 5: CLI Integration
**Objective:** Update the existing CLI to use the new shared core and database.
**Agent:** integration_engineer

- [ ] **Step 1: Refactor `apps/cli` to import models from `packages/core`**
- [ ] **Step 2: Update CLI database connection to use the centralized Postgres instance**
- [ ] **Step 3: Verify CLI and Web app operate on the same data source**

---

## Validation Strategy
- **Unit Tests:** Run `pytest` in `packages/core` and `apps/api`.
- **E2E:** Create a transaction in the CLI and verify it appears in the Web dashboard.
- **Types:** Verify TS errors occur in `apps/web` if a field is removed from a Pydantic model.
