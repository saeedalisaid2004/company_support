# Multi-Company Support Platform 

A clean, modular Django REST Framework platform supporting multi-tenancy, custom ticket workflows, status transitions, role-based access control (RBAC), and analytical reports.

---

##  Architecture & Features

- **Multi-Company Isolation:** Data and workflows are strictly scoped per company.
- **Role-Based Access Control (RBAC):** `Manager`, `Agent`, and `Customer` roles with granular permission checks.
- **Custom Workflow Engine:** Dynamic statuses (`is_initial`, `is_terminal`) and atomic transitions using database locks (`select_for_update`).
- **Clean Modular Design:** Separated core functionalities into dedicated apps (`users`, `companies`, `tickets`, `workflows`, `reports`).
- **Containerized:** Ready-to-use Docker and Docker Compose environment with PostgreSQL.

---

##  Quick Start (Using Docker)

### 1. Build and Run Containers
```bash
docker-compose up --build