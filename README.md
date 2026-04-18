# Keystone Portal — Infrastructure Self-Service Platform

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Terraform-1.10+-7B42BC?logo=terraform&logoColor=white" alt="Terraform">
  <img src="https://img.shields.io/badge/Terragrunt-0.55+-E7473C" alt="Terragrunt">
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/Alpine.js-3.x-8BC0D0?logo=alpinedotjs&logoColor=white" alt="Alpine.js">
  <img src="https://img.shields.io/badge/Tailwind_CSS-CDN-06B6D4?logo=tailwindcss&logoColor=white" alt="Tailwind">
  <img src="https://img.shields.io/badge/ArgoCD-GitOps-EF7B4D?logo=argo&logoColor=white" alt="ArgoCD">
  <img src="https://img.shields.io/badge/Helm-Charts-0F1689?logo=helm&logoColor=white" alt="Helm">
</p>

---

## What is Keystone Portal?

**Keystone Portal** is an internal developer platform (IDP) that enables engineering teams to self-service provision AWS infrastructure through a simple Jira ticket — no Terraform expertise required.

It bridges the gap between **Jira workflows**, **GitHub pull requests**, and **Terraform/Terragrunt IaC**, providing a unified dashboard to track the full lifecycle of every infrastructure request from submission to deployment.

Beyond provisioning, Keystone provides **Day-2 operations** — EKS cluster upgrades with zero-downtime rollout, ArgoCD GitOps onboarding with automated Helm chart scaffolding, SRE onboarding with full observability stacks, and an interactive **Service Catalog** documenting every offering.

### The Problem It Solves

In most organizations, requesting infrastructure follows a slow, manual process:

1. Engineer fills a Jira form → waits for infra team
2. Infra engineer writes Terraform → creates PR manually
3. Review, approval, merge, apply → days/weeks of elapsed time
4. No visibility into what's happening or where it's stuck
5. Day-2 operations (upgrades, GitOps, observability) are even more manual and error-prone

**Keystone automates the entire lifecycle** — from initial provisioning through Day-2 operations. A Jira ticket triggers automated Terraform code generation, a GitHub PR, security scans, and deployment — all within minutes instead of days. Post-deployment, teams self-serve cluster upgrades, GitOps onboarding, and SRE stack setup directly from the portal.

---

## Architecture

```
┌──────────┐     Webhook      ┌──────────────────────────────────────────────┐
│          │ ──────────────▶  │           Keystone Portal API                │
│   JIRA   │                  │                                              │
│  (Forms) │  ◀── Comment ──  │  FastAPI · SQLAlchemy · Jinja2 · PyGithub    │
└──────────┘                  │                                              │
                              │  ┌────────────┐  ┌───────────┐  ┌────────┐  │
                              │  │  Webhooks   │  │ Renderer  │  │  Auth  │  │
                              │  │  Router     │  │ (Jinja2)  │  │ (JWT)  │  │
                              │  └─────┬──────┘  └─────┬─────┘  └────────┘  │
                              │        │               │                     │
                              │  ┌─────▼───────────────▼─────┐              │
                              │  │     GitHub PR Service      │              │
                              │  │  (PyGithub — create PR)    │              │
                              │  └─────────────┬─────────────┘              │
                              │                │                             │
                              │  ┌─────────────▼─────────────┐              │
                              │  │     Day-2 Operations       │              │
                              │  │  Upgrades · GitOps · SRE   │              │
                              │  └───────────────────────────┘              │
                              └────────────────│─────────────────────────────┘
                                               │
                              ┌────────────────▼─────────────────────────────┐
                              │            GitHub Repo                       │
                              │  PR with terragrunt.hcl files auto-created  │
                              └────────────────┬─────────────────────────────┘
                                               │ merge
                              ┌────────────────▼─────────────────────────────┐
                              │         GitHub Actions CI/CD                 │
                              │  tfsec → checkov → plan → apply              │
                              │                                              │
                              │  Callback ──▶ POST /api/requests/{key}/status│
                              └──────────────────────────────────────────────┘
```

---

## Key Features

### Self-Service Infrastructure Provisioning
- **15 resource types** supported across infrastructure, Day-2 operations, and account management
- Jira form submission → automated PR creation with Terraform code → CI/CD plan/apply
- **Zero Terraform knowledge** required for requesting teams
- Template-based code generation using **15 Jinja2 blueprints** with 30+ template files

### EKS Cluster Upgrades (Day-2)
- Portal-initiated zero-downtime EKS version upgrades
- **N→N+1 enforcement** — no version skipping allowed
- **5-stage pipeline**: Pre-Checks → Control Plane → Addons → Node Groups → Post-Checks
- Pre-flight validation: cluster health, version skew, PDB coverage, subnet IP availability
- **Addon compatibility matrix** for EKS 1.27–1.32 (CoreDNS, VPC-CNI, kube-proxy, EBS CSI, Pod Identity)
- Auto-rollback on failure with full audit trail

### ArgoCD GitOps Onboarding (Day-2)
- One-click GitOps setup on existing deployed EKS clusters
- Generates **ArgoCD AppProject** with team RBAC, namespace restrictions, role-based policies
- Creates **ApplicationSet** with matrix generator (environments × services)
- Scaffolds **Helm charts** per service: Chart.yaml, deployment, service, ingress, HPA, PDB, ServiceAccount
- Per-environment value overrides (dev/staging/prod) with environment-aware defaults
- Supports up to 20 services per project with multi-source ApplicationSet

### SRE Onboarding (Day-2)
- Full observability stack deployment: Prometheus, Grafana, AlertManager, OpenTelemetry Collector
- VPC peering setup between application and monitoring VPCs
- PagerDuty integration with on-call schedule configuration
- SLO target configuration per service

### Multi-Account AWS Account Vending
- Product Owners request new AWS accounts via Jira
- Admin approval workflow with status tracking
- Automated provisioning: AWS Organizations account creation → OIDC setup → state bucket → security baseline
- Team registry: subsequent resource requests auto-lookup team's account ID

### 22 Production-Grade Terraform Modules

| Module | Description |
|--------|-------------|
| `vpc` | VPC, subnets (public/private/database), NAT, flow logs, NACLs |
| `eks` | EKS cluster, managed node groups, IRSA, KMS encryption |
| `eks-addons` | CoreDNS, VPC-CNI, Karpenter, External DNS, Cert Manager, ALB Controller |
| `rds` | RDS PostgreSQL, Multi-AZ, encryption, Performance Insights |
| `s3` | S3 buckets with versioning, lifecycle, encryption, replication |
| `lambda` | Lambda functions with IAM, VPC config, API Gateway integration |
| `dynamodb` | DynamoDB tables with autoscaling, PITR, encryption |
| `ecs-fargate` | ECS Fargate services with ALB, autoscaling, logging |
| `elasticache` | Redis/Valkey clusters with replication, encryption |
| `msk` | MSK Kafka clusters with multi-AZ, encryption |
| `route53` | DNS zones and records management |
| `ecr` | Container registries with lifecycle policies |
| `alb` | Application Load Balancers with WAF integration |
| `api-gateway` | API Gateway REST/HTTP APIs |
| `cloudfront` | CloudFront distributions with custom origins |
| `ec2` | EC2 instances with SSM, EBS encryption |
| `efs` | Elastic File System with encryption, backups |
| `transit-gateway` | Cross-VPC/account network connectivity |
| `waf` | WAF WebACLs with managed rule groups |
| `oidc-github` | GitHub OIDC provider + IAM deploy role |
| `account-factory` | AWS Organizations account creation + SSO |
| `account-baseline` | OIDC, state bucket, CloudTrail, security defaults for new accounts |

### Keystone Portal Dashboard
- **Login page** with JWT authentication (bcrypt password hashing)
- **Dashboard** — real-time stats, request breakdown by type/team, recent activity
- **Requests view** — filterable/searchable table with status badges, drill-down to detail
- **Request detail** — full configuration, deployment outputs (ARNs, endpoints), file list, error messages, timeline with colored status dots
- **SRE Onboarding** — onboarded teams overview, observability stack status, SLO targets
- **Cluster Upgrades** — EKS cluster list with version info, upgrade initiation, 5-stage progress tracking
- **GitOps Onboarding** — deployed cluster selector, multi-service form, generated project overview
- **Service Catalog** — interactive documentation for all 15 service offerings with field definitions, prerequisites, and expected outputs
- **Team Accounts** — account registry with approve/reject workflow, account detail view with AWS/GitHub/OIDC info
- **Command Palette** — Ctrl+K quick navigation to any view
- **Toast notifications** — real-time feedback for user actions

### CI/CD Pipeline
- **PR trigger**: format check → validate → tfsec → checkov → terragrunt plan (posted as PR comment)
- **Merge trigger**: security gates → dev apply → prod apply (sequential)
- **Destroy**: manual trigger with reverse DAG ordering
- **Callback**: CI/CD posts deployment status + outputs back to Keystone API

### Multi-Repo Architecture
- Template-based code generation using Jinja2
- Module sources use `git::https://` with version pinning (`?ref=v1.0.0`)
- Each team has their own infra repo — Keystone creates PRs across repos

---

## Supported Request Types

| # | Type | Key | Description |
|---|------|-----|-------------|
| 1 | EKS Cluster | `eks-cluster` | Kubernetes cluster with managed node groups, addons, Karpenter |
| 2 | RDS Database | `rds-database` | Managed PostgreSQL/MySQL, Multi-AZ, encryption, backups |
| 3 | S3 Bucket | `s3-bucket` | Object storage with versioning, lifecycle, CloudFront option |
| 4 | ECS Service | `ecs-service` | Fargate service with ALB, autoscaling, logging |
| 5 | Redis Cache | `redis` | ElastiCache Redis cluster, multi-AZ, replication |
| 6 | Lambda Function | `lambda` | Serverless with optional API Gateway integration |
| 7 | DynamoDB Table | `dynamodb` | NoSQL with autoscaling, PITR, encryption |
| 8 | MSK Cluster | `msk` | Managed Kafka, multi-AZ, TLS encryption |
| 9 | Route53 DNS | `route53` | DNS zones (public/private) and records |
| 10 | VPC | `vpc` | VPC with subnets, NAT, flow logs |
| 11 | XCR Onboarding | `xcr-onboarding` | Cross-account cluster onboarding |
| 12 | SRE Onboarding | `sre-onboarding` | Full observability stack: Prometheus, Grafana, OTel, PagerDuty |
| 13 | EKS Upgrade | `eks-upgrade` | In-portal zero-downtime EKS version upgrade |
| 14 | AWS Account | `aws-account` | Account vending via AWS Organizations + security baseline |
| 15 | ArgoCD Onboarding | `argocd-onboarding` | GitOps setup: AppProject, ApplicationSet, Helm scaffolding |

---

## Jinja2 Template Engine

Keystone uses a **blueprint-based rendering engine** to generate production-grade IaC code. Each request type maps to a blueprint defining which template directories to render:

```python
BLUEPRINTS = {
    "eks-cluster":       ["vpc", "eks", "eks-addons"],
    "rds-database":      ["rds"],
    "s3-bucket":         ["s3"],
    "ecs-service":       ["vpc", "ecs-fargate", "alb"],
    "redis":             ["elasticache"],
    "lambda":            ["lambda"],
    "dynamodb":          ["dynamodb"],
    "msk":               ["vpc", "msk"],
    "route53":           ["route53"],
    "vpc":               ["vpc"],
    "xcr-onboarding":    ["xcr-onboarding"],
    "sre-onboarding":    ["vpc-peering", "observability-stack"],
    "eks-upgrade":       ["control-plane", "addons", "node-groups"],
    "aws-account":       ["account-factory", "account-baseline"],
    "argocd-onboarding": ["argocd-project", "argocd-applicationset", "helm-charts", "env-values"],
}
```

Templates are stored in `app/templates/` organized by request type, with each subdirectory containing Jinja2 `.j2` files that render to Terraform/Terragrunt HCL, Helm charts, or Kubernetes manifests.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12, FastAPI 0.115, async SQLAlchemy 2.0, Pydantic 2.x |
| **Database** | PostgreSQL 16 (asyncpg driver) |
| **Auth** | JWT (python-jose), bcrypt (passlib) |
| **Frontend** | Alpine.js 3.x, Tailwind CSS, Inter font |
| **Templates** | Jinja2 (Terraform/Terragrunt/Helm code generation) |
| **GitHub** | PyGithub (PR creation, branch management) |
| **IaC** | Terraform >= 1.10, Terragrunt >= 0.55, S3 native state locking |
| **GitOps** | ArgoCD ApplicationSets, Helm Charts |
| **Infra** | Docker Compose (local), AWS (production) |
| **CI/CD** | GitHub Actions (reusable workflows) |
| **Security** | OIDC auth (no static keys), tfsec, checkov |

---

## Running Locally

```bash
cd self-service
docker compose up --build -d

# Seed demo data (4 teams, 18 requests, admin user)
curl -X POST http://localhost:8080/api/seed

# Open the portal
# http://localhost:8080
# Login: admin@keystone.io / admin123
```

### Demo Data Included

The seed endpoint creates realistic sample data:

**4 Team Accounts:**

| Team | Account ID | Business Unit | Status |
|------|-----------|---------------|--------|
| Payments Platform | 381492057329 | Financial Services | Active |
| Data Engineering | 529104738261 | Data & Analytics | Active |
| ML Platform | 647382910583 | Data & Analytics | Active |
| Mobile Backend | — | Consumer Products | Pending Approval |

**18 infrastructure requests** across these teams:
- Infrastructure: EKS clusters, RDS databases, S3 buckets, Lambda functions, DynamoDB tables, MSK clusters, Redis, VPC
- Day-2 Operations: EKS upgrades (1.30→1.31), SRE onboarding (Prometheus + Grafana + OTel + PagerDuty), ArgoCD GitOps onboarding
- Mix of statuses: deployed, provisioning, upgrading, awaiting approval, pending, failed
- Full timeline events (83 events) and deployment outputs (ARNs, endpoints, security groups)

---

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/login` | Authenticate (email + password → JWT) |
| `POST` | `/api/auth/register` | Register new user (first user = admin) |
| `GET` | `/api/auth/me` | Validate token, get current user |

### Infrastructure Requests
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/webhooks/jira` | Jira webhook receiver (auto-creates PR) |
| `GET` | `/api/requests` | List requests (filters: status, type, team, env, search) |
| `GET` | `/api/requests/{key}` | Request detail with timeline events |
| `GET` | `/api/requests/{key}/events` | Timeline events for a request |
| `POST` | `/api/requests/{key}/status` | CI/CD callback (update status + outputs) |
| `GET` | `/api/stats` | Dashboard statistics |

### Team Accounts
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/accounts` | List team accounts |
| `GET` | `/api/accounts/stats` | Account statistics |
| `GET` | `/api/accounts/{team}` | Team account detail |
| `POST` | `/api/accounts` | Register new account request |
| `POST` | `/api/accounts/{team}/approve` | Admin approve/reject account |
| `POST` | `/api/accounts/{team}/status` | Provisioning callback |
| `GET` | `/api/accounts/lookup/{team}` | Quick lookup (account_id, github info) |

### EKS Cluster Upgrades
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/upgrades/clusters` | List deployed EKS clusters with upgrade eligibility |
| `GET` | `/api/upgrades` | List all upgrade operations with stage progress |
| `GET` | `/api/upgrades/{key}` | Full upgrade detail with 5-stage breakdown |
| `POST` | `/api/upgrades/initiate` | Initiate EKS upgrade (validates N→N+1) |
| `GET` | `/api/upgrades/versions/latest` | Latest EKS version + addon compatibility matrix |

### ArgoCD GitOps Onboarding
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/argocd/clusters` | List deployed EKS clusters eligible for GitOps |
| `GET` | `/api/argocd` | List all ArgoCD onboarding requests |
| `POST` | `/api/argocd/onboard` | Initiate ArgoCD onboarding for a cluster |

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/healthz` | Liveness probe |
| `GET` | `/readyz` | Readiness probe (DB connectivity) |
| `POST` | `/api/seed` | Populate demo data |

---

## Project Structure

```
self-service/
├── app/
│   ├── main.py                    # FastAPI app, lifespan, router registration
│   ├── config.py                  # Settings from env vars (12-factor)
│   ├── database.py                # Async SQLAlchemy engine + session
│   │
│   ├── models/
│   │   ├── db_models.py           # ORM: InfraRequestRecord, RequestEvent, TeamAccount, User
│   │   ├── requests.py            # Pydantic: 15 request type validators
│   │   └── schemas.py             # Pydantic: API response schemas
│   │
│   ├── routers/
│   │   ├── auth.py                # Login, register, JWT validation
│   │   ├── webhooks.py            # Jira webhook → validate → render → PR
│   │   ├── api.py                 # Requests CRUD, stats, CI/CD callbacks
│   │   ├── accounts.py            # Team account lifecycle
│   │   ├── upgrades.py            # EKS cluster upgrade orchestration
│   │   ├── argocd.py              # ArgoCD GitOps onboarding
│   │   ├── seed.py                # Demo data population (18 requests, 83 events)
│   │   └── health.py              # Healthz / readyz
│   │
│   ├── services/
│   │   ├── renderer.py            # Jinja2 template engine (15 blueprints)
│   │   └── github_pr.py           # PyGithub PR creation service
│   │
│   ├── templates/                 # Jinja2 templates (30+ files)
│   │   ├── eks-cluster/           #   VPC + EKS + addons (Karpenter, External DNS)
│   │   ├── rds-database/          #   RDS PostgreSQL
│   │   ├── s3-bucket/             #   S3 with lifecycle
│   │   ├── ecs-service/           #   ECS Fargate + ALB
│   │   ├── lambda/                #   Lambda + API Gateway
│   │   ├── dynamodb/              #   DynamoDB with autoscaling
│   │   ├── msk/                   #   Managed Kafka
│   │   ├── redis/                 #   ElastiCache Redis
│   │   ├── route53/               #   DNS zones and records
│   │   ├── vpc/                   #   Standalone VPC
│   │   ├── xcr-onboarding/        #   Cross-account cluster onboarding
│   │   ├── sre-onboarding/        #   VPC peering + observability stack
│   │   │   ├── vpc-peering/
│   │   │   └── observability-stack/
│   │   ├── eks-upgrade/           #   Control plane + addons + node groups
│   │   │   ├── control-plane/
│   │   │   ├── addons/
│   │   │   └── node-groups/
│   │   ├── aws-account/           #   Account Factory + Baseline
│   │   │   ├── account-factory/
│   │   │   └── account-baseline/
│   │   └── argocd-onboarding/     #   GitOps: AppProject + ApplicationSet + Helm
│   │       ├── argocd-project/
│   │       ├── argocd-applicationset/
│   │       ├── helm-charts/       #   Chart.yaml, deployment, service, ingress,
│   │       │                      #   HPA, PDB, ServiceAccount, _helpers.tpl
│   │       └── env-values/        #   Per-env overrides (dev/staging/prod)
│   │
│   └── static/
│       └── index.html             # SPA dashboard (Alpine.js + Tailwind CSS)
│
├── docker-compose.yaml            # App + PostgreSQL 16
├── Dockerfile                     # Python 3.12-slim, non-root user
└── requirements.txt               # 17 dependencies
```

---

## Portal Views

| View | Description |
|------|-------------|
| **Dashboard** | Real-time stats cards, request breakdown by type/status/team, recent activity feed |
| **Requests** | Filterable table (status, type, team, env, search), status badges, drill-down to detail |
| **Request Detail** | Full config, deployment outputs, generated file list, error messages, timeline events |
| **SRE Onboarding** | Onboarded teams, observability stack status, SLO targets, incident management |
| **Cluster Upgrades** | EKS cluster list with versions, upgrade eligibility, 5-stage progress tracking |
| **GitOps Onboarding** | Deployed cluster selector, multi-service form, generated ArgoCD project overview |
| **Service Catalog** | Interactive docs for all 15 services — fields, outputs, prereqs, Terraform modules |
| **Team Accounts** | Account registry, approve/reject workflow, AWS/GitHub/OIDC detail view |

---

## Resume Bullet Points

Use these one-liners on your resume under a project or experience section:

### Senior / Lead Level
> **Built "Keystone Portal" — an internal developer platform (IDP) enabling self-service AWS infrastructure provisioning and Day-2 operations for 20+ teams, reducing infrastructure request lead time from 5 days to under 30 minutes through automated Terraform code generation, ArgoCD GitOps onboarding, zero-downtime EKS upgrades, and a real-time tracking dashboard.**

### Mid-Level
> **Designed and developed a full-stack self-service infrastructure platform (FastAPI + PostgreSQL + Alpine.js) with JWT auth, Jira integration, automated Terraform/Terragrunt code generation via 15 Jinja2 blueprints, ArgoCD GitOps onboarding, EKS cluster upgrade orchestration, and GitHub PR automation — supporting 15 resource types across multi-account AWS environments.**

### DevOps / Platform Engineer Focus
> **Architected a multi-account AWS platform with 22 production-grade Terraform modules, account vending via AWS Organizations, OIDC-based CI/CD (zero static credentials), ArgoCD GitOps onboarding with Helm chart scaffolding, zero-downtime EKS upgrade pipeline, and a self-service portal that automates infrastructure provisioning from Jira ticket to deployed resources with full audit trail.**

### Short (1-line for tight resumes)
> **Built an internal developer platform (IDP) automating AWS infrastructure provisioning and Day-2 operations — Jira-to-Terraform pipeline with 22 modules, ArgoCD GitOps onboarding, EKS upgrades, multi-account vending, and a real-time portal dashboard.**

---

## LinkedIn Post

Copy-paste ready. Customize the parts in `[brackets]`:

---

**🚀 Built an Internal Developer Platform from Scratch — Keystone Portal**

Over the past [few weeks/months], I built **Keystone Portal** — a self-service infrastructure platform that lets engineering teams provision AWS resources through a simple Jira ticket, with zero Terraform knowledge required.

**The problem:** Infrastructure requests were bottlenecked — engineers waited days for manual provisioning, with no visibility into progress. Day-2 operations (upgrades, GitOps setup, observability) were even more manual and error-prone.

**The solution:** An end-to-end automated platform that:

🔹 Takes a Jira form submission and auto-generates production-grade Terraform code
🔹 Creates a GitHub PR with proper module sourcing and version pinning
🔹 Runs security scans (tfsec + checkov) and Terraform plan automatically
🔹 Deploys on merge and posts outputs (ARNs, endpoints) back to the dashboard
🔹 Tracks every request with a full audit timeline

**Day-2 operations, fully automated:**

🔹 **EKS Cluster Upgrades** — zero-downtime 5-stage pipeline (pre-checks → control plane → addons → node groups → post-checks) with auto-rollback
🔹 **ArgoCD GitOps Onboarding** — one-click setup generates AppProject, ApplicationSet (matrix generator), and full Helm chart scaffolding per service
🔹 **SRE Onboarding** — Prometheus, Grafana, OpenTelemetry, PagerDuty integration with VPC peering

**What's under the hood:**

• 22 Terraform modules (EKS, RDS, S3, Lambda, DynamoDB, MSK, VPC, and more)
• 15 Jinja2 blueprints generating Terraform, Helm charts, and Kubernetes manifests
• Multi-account AWS architecture with automated account vending (Organizations + OIDC + security baseline)
• FastAPI backend with async PostgreSQL, JWT auth, Jinja2 template engine
• Real-time portal with 8 views: dashboard, requests, upgrades, GitOps, SRE, service catalog, team accounts
• CI/CD via GitHub Actions with OIDC — zero static credentials anywhere

**The result:** Infrastructure request lead time dropped from ~5 days to under 30 minutes. Teams self-serve provisioning AND Day-2 operations. Platform engineers focus on modules, not tickets.

This was a deep-dive into platform engineering, IaC at scale, and building developer experience from the ground up.

Would love to hear how others are approaching internal platforms — what's worked for your team?

#PlatformEngineering #DevOps #Terraform #AWS #InfrastructureAsCode #InternalDeveloperPlatform #IDP #CloudEngineering #FastAPI #SelfService #ArgoCD #GitOps #Kubernetes #EKS

---

## License

Internal use only. Not for redistribution.
