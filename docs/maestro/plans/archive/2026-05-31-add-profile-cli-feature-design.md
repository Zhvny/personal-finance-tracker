---
title: "Add Profile Feature in CLI"
created: "2026-05-31T12:00:00Z"
status: "approved"
authors: ["Maestro TechLead", "User"]
type: "design"
design_depth: "standard"
task_complexity: "medium"
---

# Add Profile Feature Design Document

## Problem Statement

The Finance Tracker CLI currently uses a hardcoded list of profiles ('personal', 'business'), which limits flexibility for users who need additional isolated environments (e.g., separate tracking for a second business, a specific project, or different family members). 

The goal of this feature is to implement a dynamic "Add Profile" capability that:
1. Replaces the hardcoded registry with a flexible `profiles.json` source of truth.
2. Provides a user-friendly CLI workflow to create and initialize new profile environments.
3. Maintains the strict data isolation and on-demand database initialization patterns that define the project's current architecture.

## Requirements

### Functional Requirements
1. **REQ-1**: Replace hardcoded `self.profiles` in `ProfileService` with a dynamic registry.
2. **REQ-2**: Implement a `profiles.json` file to store the list of available profiles.
3. **REQ-3**: Add an "Add Profile" option to the CLI Profile Management sub-menu.
4. **REQ-4**: Validate new profile names for alphanumeric safety and PostgreSQL compatibility.
5. **REQ-5**: Automatically create the base directory structure for new profiles.

### Non-Functional Requirements
1. **Compatibility**: Ensure names are valid filesystem paths and Postgres schema names.
2. **Robustness**: Prevent duplicate profile creation.

## Approach

### Selected Approach: Registry-Backed On-Demand Scaffolding
We will implement a dynamic profile management system centered around a `profiles.json` registry. 

**Key Components:**
- **Registry Implementation**: Create `apps/cli/profiles.json` to store the list of available profiles and metadata.
- **Service Evolution**: Refactor `ProfileService` to perform CRUD operations on `profiles.json` instead of using a hardcoded list.
- **CLI Integration**: Modify the "Switch Profile" menu (Option 8) into a "Profile Management" sub-menu with options to [1] Switch Profile and [2] Add New Profile.
- **Safe Initialization**: When a new profile is added, the system will create the base directory `apps/cli/profiles/{name}/`. Subdirectories and databases will be initialized on-demand by existing module logic.

### Decision Matrix

| Criterion | Weight | profiles.json | Dynamic Scanning |
|-----------|--------|---------------|------------------|
| Metadata Support | 30% | 5: Supports future feature flags/tags | 2: Difficult to store extra info |
| Complexity | 20% | 3: Requires file I/O and sync logic | 5: Simple directory listing |
| Reliability | 30% | 5: Explicit registry prevents accidental discovery | 3: Can pick up non-profile folders |
| Extensibility | 20% | 5: Easy to add profile-specific settings | 2: Hard to extend without sidecar files |
| **Weighted Total** | | **4.6** | **2.9** |

## Architecture

### Key Interfaces
- `ProfileService.add_profile(name: str)`: Validates name, creates directory, and updates `profiles.json`.
- `ProfileService.get_available_profiles()`: Reads from `profiles.json`.

**Rationale Annotations:**
- **Centralized Registry (`profiles.json`)** — *Ensures a single source of truth for all profiles, enabling future metadata like profile-specific themes or feature toggles.*
- **Strict Alphanumeric Validation** — *Prevents filesystem injection and ensures names are compatible with PostgreSQL schema identifiers without complex quoting.*
- **On-Demand Subdirectory Creation** — *Leverages existing lazy-initialization in Config/Repositories, reducing code duplication and ensuring profiles only contain necessary data.*

### Data Flow
1. User selects "Add Profile" in CLI.
2. CLI prompts for name.
3. `ProfileService` validates name against regex and existing registry.
4. `ProfileService` updates `profiles.json` and creates `apps/cli/profiles/{name}/`.
5. `Config` uses new profile name to resolve data paths dynamically.

## Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Naming Collisions | MEDIUM | LOW | Case-insensitive check against registry and existing directory before creation. |
| Invalid Name Formats | LOW | LOW | Enforce strict regex (^[a-zA-Z0-9_]+$) at the service layer. |
| Migration Failure | MEDIUM | LOW | Seed `profiles.json` with 'personal' and 'business' if it doesn't exist to prevent data loss. |

## Success Criteria
1. User can successfully add a new profile via the CLI menu.
2. `profiles.json` is updated with the new profile name.
3. A directory for the new profile is created under `apps/cli/profiles/`.
4. The user can switch to the new profile and perform a transaction, which initializes the relevant databases in the new directory.
