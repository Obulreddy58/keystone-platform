# Self-Service Infrastructure Platform — Implementation Guide

## Is This Possible?

**Yes, 100%.** This is a proven pattern known as an **Internal Developer Platform (IDP)**. Companies like Spotify (Backstage), Netflix, Airbnb, and most enterprises with mature platform teams run exactly this. The architecture is:

```
Jira Service Management  →  Self-Service API  →  Fetch templates (iac org)  →  PR (team's repo)  →  CI/CD  →  AWS
      (frontend)              (middleware)         (template source)             (GitOps)            (pipeline)  (result)
```

Every piece of this exists today, uses stable APIs, and we've already built the code for it.

---

## What We Built

### The Core Idea — Multi-Repo Architecture

The platform follows a **multi-repo** pattern where templates and infrastructure live in separate repositories:

- **`iac` GitHub org** — contains one repo per Terraform module (e.g., `iac/terraform-aws-vpc`, `iac/terraform-aws-eks`). Each repo has a `template/` directory with Jinja2 (`.j2`) files that define how to consume that module via Terragrunt.
- **Team infra repos** — every team owns their own infra repo in their own GitHub group (e.g., `payments-team/infra`, `data-team/infra`). This is where rendered Terragrunt files live and where CI/CD runs.

The self-service API **bridges** these two worlds:

1. **Product owner** fills a Jira request form (e.g., "Create EKS Cluster") — includes their `github_group` and `github_repo`
2. **Jira webhook** fires `POST /webhook/jira` to our API
3. **API** fetches the relevant `.j2` templates from the `iac` org repos (e.g., `iac/terraform-aws-vpc/template/`, `iac/terraform-aws-eks/template/`)
4. **API** renders templates with Jinja2, injecting the user's values
5. **API** creates a PR **in the team's own repo** (e.g., `payments-team/infra`)
6. **CI/CD in the team's repo** runs `terraform plan` on the PR
7. **Platform team** reviews the plan, approves the PR
8. **Merge** triggers `terraform apply` — infrastructure deploys
9. **Jira ticket** gets updated with PR link and deployment status

### Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                      │
│   PRODUCT OWNER                                                                     │
│   fills Jira form (includes github_group + github_repo)                             │
│        │                                                                             │
│        ▼                                                                             │
│   ┌──────────────────┐                                                               │
│   │  JIRA SERVICE    │                                                               │
│   │  MANAGEMENT      │                                                               │
│   │                  │                                                               │
│   │  11 Request Forms│                                                               │
│   │  each includes:  │                                                               │
│   │  - github_group  │                                                               │
│   │  - github_repo   │                                                               │
│   │  - request fields│                                                               │
│   └───────┬──────────┘                                                               │
│           │                                                                          │
│           │  Webhook (POST)                                                          │
│           ▼                                                                          │
│   ┌───────────────────────────────────────────────────────────────────┐               │
│   │  SELF-SERVICE API  (FastAPI on EKS)                              │               │
│   │                                                                  │               │
│   │  POST /webhook/jira                                              │               │
│   │    │                                                             │               │
│   │    ├─ 1. Verify webhook signature (HMAC)                        │               │
│   │    ├─ 2. Parse Jira custom fields                               │               │
│   │    ├─ 3. Detect request_type → look up BLUEPRINT modules        │               │
│   │    ├─ 4. Validate with Pydantic model                           │               │
│   │    ├─ 5. Fetch .j2 templates from iac org repos (GitHub API)    │               │
│   │    ├─ 6. Render Jinja2 → HCL with user's values                │               │
│   │    ├─ 7. Create branch + PR in TEAM'S repo                     │               │
│   │    └─ 8. Update Jira with PR link + target repo                │               │
│   │                                                                  │               │
│   └──────┬──────────────────────────────┬────────────────────────────┘               │
│          │                              │                                            │
│          │ Fetch templates              │ Push rendered files                        │
│          ▼                              ▼                                            │
│   ┌─────────────────────────┐    ┌──────────────────────────────────┐                │
│   │  IAC ORG (template      │    │  TEAM'S REPO                    │                │
│   │  source)                │    │  (e.g., payments-team/infra)    │                │
│   │                         │    │                                  │                │
│   │  iac/terraform-aws-vpc  │    │  PR: "[INFRA-123] eks-cluster"  │                │
│   │    └── template/        │    │  Branch: self-service/INFRA-123 │                │
│   │        ├── vpc.hcl.j2   │    │                                  │                │
│   │        └── root.hcl.j2  │    │  Files added:                   │                │
│   │                         │    │  environments/prod/alpha/        │                │
│   │  iac/terraform-aws-eks  │    │    ├── terragrunt.hcl            │                │
│   │    └── template/        │    │    ├── vpc/terragrunt.hcl        │                │
│   │        └── eks.hcl.j2   │    │    ├── eks/terragrunt.hcl        │                │
│   │                         │    │    └── eks-addons/terragrunt.hcl │                │
│   │  iac/terraform-aws-rds  │    │                                  │                │
│   │    └── template/        │    └───────────┬──────────────────────┘                │
│   │        └── rds.hcl.j2   │                │                                      │
│   │                         │                │  PR triggers Team's CI/CD             │
│   │  ... (20 module repos)  │                ▼                                      │
│   └─────────────────────────┘    ┌──────────────────────────────────┐                │
│                                  │  CI/CD PIPELINE (team's repo)   │                │
│                                  │                                  │                │
│                                  │  On PR:                          │                │
│                                  │    ├── terraform fmt              │                │
│                                  │    ├── tfsec + checkov            │                │
│                                  │    └── terragrunt plan → comment  │                │
│                                  │                                  │                │
│                                  │  On Merge:                       │                │
│                                  │    └── terragrunt apply           │                │
│                                  └───────────┬──────────────────────┘                │
│                                              │                                      │
│                                              ▼                                      │
│                                  ┌──────────────────────────────────┐                │
│                                  │  AWS INFRASTRUCTURE              │                │
│                                  │  (in team's AWS account)         │                │
│                                  └──────────────────────────────────┘                │
│                                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Answering Your Specific Questions

### Q: "10 different forms = 10 different APIs?"

**No. 1 single API endpoint handles all 11 forms.**

The webhook endpoint `POST /webhook/jira` receives every request. The `request_type` custom field in the Jira form determines which Pydantic model validates the data and which Jinja2 template set renders the Terragrunt files.

```python
# In app/models/requests.py — the registry
REQUEST_TYPE_MAP = {
    "eks-cluster":     EKSClusterRequest,      # Form 1
    "rds-database":    RDSDatabaseRequest,      # Form 2
    "s3-bucket":       S3BucketRequest,         # Form 3
    "ecs-service":     ECSServiceRequest,       # Form 4
    "redis":           RedisRequest,            # Form 5
    "lambda":          LambdaRequest,           # Form 6
    "dynamodb":        DynamoDBRequest,         # Form 7
    "msk":             MSKRequest,              # Form 8
    "route53":         Route53Request,          # Form 9
    "vpc":             VPCRequest,              # Form 10
    "xcr-onboarding":  XCROnboardingRequest,    # Form 11 (FDSOne XCR)
}
```

Jira sends the same webhook to the same URL. The API routes internally based on the request type.

### Q: "Jira triggers the application via webhook?"

**Yes.** Jira Service Management has built-in webhook support:

- Go to **Jira Admin → System → Webhooks**
- Add webhook URL: `https://self-service.internal.yourcompany.com/webhook/jira`
- Select event: **Issue Created**
- Optionally filter by project (e.g., only `INFRA` project)

When someone submits a form, Jira POSTs the full issue payload (all fields) to your API.

### Q: "The application fetches details and uses our templates?"

**Yes.** The API fetches templates **from the `iac` org repos** at runtime. Each Terraform module repo (e.g., `iac/terraform-aws-vpc`) contains a `template/` directory with Jinja2 files. The flow:

```
Webhook received
    │
    ├── Extract custom field values from Jira payload
    │   (account_id, cluster_name, environment, github_group, github_repo, etc.)
    │
    ├── Validate against Pydantic model
    │   (catches invalid CIDRs, bad names, missing fields)
    │
    ├── Look up BLUEPRINT for this request_type
    │   e.g., "eks-cluster" → ["vpc", "eks", "eks-addons"]
    │
    ├── Fetch .j2 templates from iac org via GitHub API
    │   iac/terraform-aws-vpc/template/*.j2
    │   iac/terraform-aws-eks/template/*.j2
    │   iac/terraform-aws-eks-addons/template/*.j2
    │
    ├── Render templates with user's values (Jinja2)
    │
    └── Output: dict of {filepath: rendered_content}
```

Templates are **not** stored locally in the API. They live in the `iac` org repos, so module authors can update templates independently without redeploying the API.

Example: if the user enters `cluster_name = "team-alpha"`, `environment = "prod"`, `vpc_cidr = "10.50.0.0/16"`, the template:

```hcl
# In the Jinja2 template:
inputs = {
  name     = "{{ cluster_name }}"
  vpc_cidr = "{{ vpc_cidr }}"
}
```

Becomes:

```hcl
# Rendered output:
inputs = {
  name     = "team-alpha"
  vpc_cidr = "10.50.0.0/16"
}
```

### Q: "It will create the pull request automatically?"

**Yes.** The API uses PyGithub to create a PR **in the team's own repo** (not a central repo):

1. Connects to `{github_group}/{github_repo}` (e.g., `payments-team/infra`)
2. Creates a branch: `self-service/INFRA-123-eks-cluster`
3. Commits all rendered `.hcl` files to that branch
4. Opens a PR with a detailed body (table of all values, file list, Jira link, target repo)
5. Adds labels: `self-service`, `eks-cluster`, `prod`

The `github_group` and `github_repo` fields come from the Jira form, so each team's request goes to their own repo.

### Q: "Then we approve and the cluster gets created?"

**Exactly.** The PR triggers the CI/CD pipeline **in the team's repo**:

1. GitHub Actions runs `terraform plan` → posts the plan as a PR comment
2. Platform team reviews the plan (sees exactly what resources will be created)
3. Team approves and merges the PR
4. Merge triggers `terraform apply` → infrastructure deploys
5. Terragrunt DAG ensures correct order: VPC → EKS → eks-addons (ArgoCD, ALB Controller, etc.)

---

## Implementation Steps

### Phase 1: Prerequisites (Already Done)

- [x] Terraform modules (VPC, EKS, RDS, etc.) — **20 modules created**
- [x] Terragrunt environment structure (prod, dev)
- [x] CI/CD pipelines (plan on PR, apply on merge, manual destroy)
- [x] EKS addons module (ArgoCD, ALB Controller, Karpenter, ESO, cert-manager)
- [x] OIDC authentication (no access keys)

### Phase 2: Self-Service API (Already Built)

- [x] FastAPI application with webhook handler
- [x] 10 Pydantic request models with field validation
- [x] Jinja2 template renderer
- [x] GitHub PR service (branch + commit + PR creation)
- [x] Jira service (fetch issue, add comment, transition status)
- [x] Dockerfile
- [x] Helm chart with Ingress, HPA, ExternalSecret

### Phase 3: Deployment (Your Action Items)

#### Step 1: Store Secrets in AWS Secrets Manager

```bash
aws secretsmanager create-secret \
  --name infra/self-service \
  --secret-string '{
    "jira_api_token": "YOUR_JIRA_API_TOKEN",
    "jira_user_email": "automation@yourcompany.com",
    "jira_webhook_secret": "GENERATE_A_RANDOM_STRING",
    "github_token": "ghp_YOUR_GITHUB_PAT_OR_APP_TOKEN"
  }'
```

The GitHub token needs these permissions:
- `repo` (full control) — to read templates from `iac` org and create branches/PRs in team repos
- Or use a **GitHub App** installed on both the `iac` org (read) and team orgs (write) with `contents: read/write` and `pull_requests: write`

#### Step 2: Build and Push Docker Image

```bash
cd self-service/

# Build
docker build -t infra-self-service:1.0.0 .

# Tag for ECR
docker tag infra-self-service:1.0.0 \
  123456789012.dkr.ecr.us-east-1.amazonaws.com/infra-self-service:1.0.0

# Push
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/infra-self-service:1.0.0
```

#### Step 3: Deploy to EKS via ArgoCD or Helm

**Option A: ArgoCD (recommended)**

Create an ArgoCD Application that points to `self-service/chart/`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: infra-self-service
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/YOUR_ORG/infra.git
    targetRevision: main
    path: self-service/chart
    helm:
      values: |
        image:
          repository: 123456789012.dkr.ecr.us-east-1.amazonaws.com/infra-self-service
          tag: "1.0.0"
        env:
          SELF_SERVICE_JIRA_BASE_URL: "https://yourcompany.atlassian.net"
          SELF_SERVICE_IAC_GITHUB_ORG: "iac"
          SELF_SERVICE_IAC_REPO_PREFIX: "terraform-aws"
        ingress:
          annotations:
            alb.ingress.kubernetes.io/certificate-arn: "arn:aws:acm:us-east-1:123456789012:certificate/xxxxx"
          host: self-service.internal.yourcompany.com
  destination:
    server: https://kubernetes.default.svc
    namespace: self-service
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

**Option B: Helm**

```bash
helm install infra-self-service self-service/chart/ \
  --namespace self-service --create-namespace \
  --set image.repository=123456789012.dkr.ecr.us-east-1.amazonaws.com/infra-self-service \
  --set image.tag=1.0.0 \
  --set env.SELF_SERVICE_JIRA_BASE_URL=https://yourcompany.atlassian.net \
  --set env.SELF_SERVICE_IAC_GITHUB_ORG=iac
```

#### Step 4: Create ESO ClusterSecretStore

The ExternalSecret in the Helm chart references a `ClusterSecretStore`. Create it once per cluster:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: aws-secrets-manager
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets
            namespace: external-secrets
```

#### Step 5: Configure Jira Webhook

1. Go to **Jira Admin → System → Webhooks → Create**
2. **Name:** `Infrastructure Self-Service`
3. **URL:** `https://self-service.internal.yourcompany.com/webhook/jira`
4. **Secret:** Same value as `jira_webhook_secret` in Secrets Manager
5. **Events:** Issue → Created
6. **Filter:** Project = `INFRA` (your JSM project)

#### Step 6: Map Jira Custom Fields

Update `JIRA_FIELD_MAP` in `app/routers/webhooks.py` with your actual Jira custom field IDs:

1. In Jira, go to **Admin → Issues → Custom Fields**
2. Click each field → note the ID from the URL (e.g., `customfield_10100`)
3. Update the mapping dictionary

#### Step 7: Create Jira Request Forms

In Jira Service Management, create request types with these fields:

**Form: "Create EKS Cluster"**

| Field Name | Field Type | Required | Example |
|---|---|---|---|
| Request Type | Dropdown (hidden, auto-set) | Yes | `eks-cluster` |
| GitHub Group | Text | Yes | `payments-team` |
| GitHub Repo | Text (default: `infra`) | Yes | `infra` |
| AWS Account ID | Text (12 digits) | Yes | `123456789012` |
| Environment | Dropdown | Yes | `prod` / `dev` / `staging` |
| Cluster Name | Text | Yes | `team-alpha` |
| Team Name | Text | Yes | `alpha` |
| GitHub Team | Text | Yes | `team-alpha-devs` |
| Cost Center | Text | Yes | `CC-1234` |
| K8s Version | Text | Yes | `1.31` |
| VPC CIDR | Text | Yes | `10.50.0.0/16` |
| Node Instance Type | Dropdown | Yes | `m6i.xlarge` |
| Min Nodes | Number | Yes | `2` |
| Max Nodes | Number | Yes | `10` |
| Desired Nodes | Number | Yes | `3` |
| Private Cluster | Checkbox | No | `true` |
| Enable Karpenter | Checkbox | No | `true` |

**Form: "XCR Onboarding" (Cluster Onboarding Request — FDSOne)**

| Field Name | Field Type | Required | Example |
|---|---|---|---|
| Request Type | Hidden (auto-set) | Yes | `xcr-onboarding` |
| GitHub Group | Text | Yes | `my-team` |
| GitHub Repo | Text (default: `infra`) | Yes | `infra` |
| Summary | Text | Yes | `Onboard payments cluster` |
| Business Unit/Segment | Dropdown | Yes | `Client Services` |
| Client Services | Dropdown | Yes | `FDS` |
| Team Name | Dropdown | Yes | `payments-team` |
| Component | Text | Yes | `payments-api` |
| Primary Contact Email | Email | Yes | `dev@company.com` |
| Description | Textarea | No | `Need cluster for...` |
| Cloud | Dropdown | Yes | `AWS` / `Azure` / `GCP` |
| Cluster Type | Dropdown | Yes | `EKS` / `AKS` / `GKE` |
| Release Type | Dropdown | Yes | `stable` / `rapid` |
| Size | Dropdown | Yes | `small` / `medium` / `large` / `xlarge` |
| Connectivity | Dropdown | Yes | `private` / `public` / `hybrid` |
| Keycloak Group Name | Text | Yes | `payments-devs` |

---

## File Reference

```
self-service/
│
├── app/
│   ├── main.py                              # FastAPI entry point
│   ├── config.py                            # Environment variable config
│   │                                        #   iac_github_org, iac_repo_prefix,
│   │                                        #   iac_template_ref, iac_template_dir
│   │
│   ├── models/
│   │   └── requests.py                      # 11 Pydantic models
│   │       ├── InfraRequest (base)          # github_group, github_repo, team_name...
│   │       ├── EKSClusterRequest            # cluster_name, version, vpc_cidr, nodes...
│   │       ├── RDSDatabaseRequest           # db_name, engine, instance_class, multi_az...
│   │       ├── S3BucketRequest              # bucket_name, versioning, lifecycle...
│   │       ├── ECSServiceRequest            # service_name, image, cpu, memory...
│   │       ├── RedisRequest                 # cluster_name, node_type, num_nodes...
│   │       ├── LambdaRequest                # function_name, runtime, memory_size...
│   │       ├── DynamoDBRequest              # table_name, partition_key, billing_mode...
│   │       ├── MSKRequest                   # cluster_name, kafka_version, brokers...
│   │       ├── Route53Request               # domain_name, private_zone...
│   │       ├── VPCRequest                   # vpc_name, vpc_cidr, nat_gateway...
│   │       └── XCROnboardingRequest         # cloud, cluster_type, size, connectivity...
│   │
│   ├── routers/
│   │   ├── webhooks.py                      # POST /webhook/jira — core logic
│   │   └── health.py                        # GET /healthz, /readyz
│   │
│   └── services/
│       ├── renderer.py                      # BLUEPRINT lookup + Jinja2 rendering
│       │                                    #   fetches .j2 files from iac org repos
│       ├── github_pr.py                     # GitHub API — fetches templates from iac org,
│       │                                    #   creates PRs in team's repo
│       └── jira.py                          # Jira API (comment, transition)
│
├── chart/                                   # Helm chart for K8s deployment
│   ├── Chart.yaml
│   ├── values.yaml                          # env vars: IAC_GITHUB_ORG, IAC_REPO_PREFIX, etc.
│   └── templates/
│       ├── deployment.yaml                  # Pods, security context, env vars
│       ├── service.yaml                     # ClusterIP service
│       ├── ingress.yaml                     # ALB Ingress (internal)
│       ├── hpa.yaml                         # HorizontalPodAutoscaler
│       ├── external-secret.yaml             # ESO pulls creds from AWS SM
│       └── _helpers.tpl                     # Helm name template
│
├── Dockerfile                               # Python 3.12, non-root user
├── requirements.txt                         # Pinned dependencies
└── (this file) selfservice.md

TEMPLATE SOURCE (separate repo per module in iac org):

iac/terraform-aws-vpc/                       # Module repo in iac org
  ├── main.tf, variables.tf, outputs.tf      # Terraform module code
  └── template/                              # Jinja2 templates consumed by self-service API
      ├── root.hcl.j2
      └── vpc/terragrunt.hcl.j2

iac/terraform-aws-eks/
  ├── main.tf, variables.tf, outputs.tf
  └── template/
      └── eks/terragrunt.hcl.j2

iac/terraform-aws-rds/
  ├── main.tf, variables.tf, outputs.tf
  └── template/
      └── rds/terragrunt.hcl.j2

iac/terraform-aws-xcr-onboarding/
  ├── main.tf, variables.tf, outputs.tf
  └── template/
      └── xcr-onboarding/terragrunt.hcl.j2

... (one repo per module)
```

---

## Security Considerations

| Concern | Mitigation |
|---|---|
| Webhook authenticity | HMAC-SHA256 signature verification on every request |
| Secrets in code | None — all secrets in AWS Secrets Manager, pulled by ESO |
| GitHub token scope | `contents:write` + `pull_requests:write` on iac org (read) and team repos (write) |
| Network exposure | Internal ALB only (`alb.ingress.kubernetes.io/scheme: internal`) |
| Input validation | Pydantic models with regex patterns (e.g., account ID = 12 digits) |
| PR review gate | Infra changes always require human approval before merge |
| Container security | Non-root user, read-only filesystem, drop all capabilities |
| Audit trail | Every action is traceable: Jira ticket → PR → terraform plan → apply |

---

## Adding a New Self-Service Form

To add a 12th form (e.g., "Create CloudFront Distribution"):

1. **Add Pydantic model** in `app/models/requests.py`:
   ```python
   class CloudFrontRequest(InfraRequest):
       request_type: str = "cloudfront"
       distribution_name: str
       origin_domain: str
       # ... fields
   ```
   Add to `REQUEST_TYPE_MAP`.

2. **Add BLUEPRINT** in `app/services/renderer.py`:
   ```python
   BLUEPRINTS = {
       ...
       "cloudfront": ["cloudfront", "s3"],  # modules needed
   }
   ```

3. **Create Jinja2 templates** in the iac module repos:
   ```
   iac/terraform-aws-cloudfront/template/
   └── cloudfront/terragrunt.hcl.j2
   ```
   The API will fetch these automatically from the `iac` org.

4. **Create Jira form** with matching custom fields (include `github_group` and `github_repo`)

5. **Map fields** in `JIRA_FIELD_MAP` in `webhooks.py`

6. **Deploy** — ArgoCD auto-syncs, or run `helm upgrade`

No code changes to the webhook router, GitHub service, or renderer are needed. The registry + blueprint pattern handles routing automatically.

---

## Alternative Frontends

While we used Jira Service Management, the same API works with any frontend that can send a webhook/HTTP POST:

| Frontend | How It Connects |
|---|---|
| **Jira Service Management** | Webhook on issue creation (what we built) |
| **Backstage (Spotify)** | Software template calls the API |
| **ServiceNow** | Business rule triggers REST callout |
| **Slack Bot** | Slash command → API call |
| **Custom Web Portal** | React/Vue form → POST to API |
| **Terraform Cloud** | No-code workspace via API |
| **Port.io** | Self-service action triggers webhook |

The API is frontend-agnostic — as long as the payload contains the required fields, it works.

---

## Worked Examples — End to End

Below are two complete walkthroughs showing exactly what the product owner sees, what the API does, and what gets created.

---

### Example 1: Shared Cluster Namespace Onboarding

**Scenario:** Your company has a central shared EKS cluster. Teams don't get their own clusters — instead, they request a **namespace** on the shared cluster with proper RBAC, resource quotas, network policies, and ArgoCD project scoping.

#### Step A: Jira Form — "Onboard Team to Shared Cluster"

The product owner opens Jira Service Management and fills this form:

```
┌─────────────────────────────────────────────────────┐
│  JIRA SERVICE MANAGEMENT                            │
│  Request Type: Shared Cluster Onboarding            │
│                                                     │
│  ┌───────────────────────────────────────────┐      │
│  │  AWS Account ID:     [ 123456789012     ] │      │
│  │  Environment:        [ prod         ▼   ] │      │
│  │  Team Name:          [ payments         ] │      │
│  │  Cost Center:        [ CC-4567          ] │      │
│  │  Namespace Name:     [ payments-api     ] │      │
│  │  Cluster Name:       [ shared-prod      ] │      │
│  │  GitHub Team Slug:   [ payments-devs    ] │      │
│  │                                           │      │
│  │  Resource Limits:                         │      │
│  │    CPU Limit:        [ 8        ] cores   │      │
│  │    Memory Limit:     [ 16       ] Gi      │      │
│  │    Pod Limit:        [ 50       ]         │      │
│  │    PVC Storage:      [ 100      ] Gi      │      │
│  │                                           │      │
│  │  Access:                                  │      │
│  │    ☑ ArgoCD Project (GitOps deployments)  │      │
│  │    ☑ External Secrets Store               │      │
│  │    ☑ Network Policies (isolate namespace) │      │
│  │    ☐ Ingress (expose via ALB)             │      │
│  │                                           │      │
│  │  Secrets Path:                            │      │
│  │    [ prod/payments/* ] (SM pattern)       │      │
│  │                                           │      │
│  │              [ Submit Request ]           │      │
│  └───────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────┘
```

#### Step B: What Happens After Submit

```
1. Jira creates ticket INFRA-456
2. Jira fires webhook → POST /webhook/jira

3. API receives payload:
   {
     "issue": {
       "key": "INFRA-456",
       "fields": {
         "customfield_10100": {"value": "shared-cluster-onboard"},
         "customfield_10101": "123456789012",
         "customfield_10102": {"value": "prod"},
         "customfield_10103": "payments",
         "customfield_10140": "payments-team",     ← github_group
         "customfield_10141": "infra",             ← github_repo
         "customfield_10130": "payments-api",
         "customfield_10131": "shared-prod",
         "customfield_10111": "payments-devs",
         "customfield_10132": 8,
         "customfield_10133": 16,
         "customfield_10134": 50,
         ...
       }
     }
   }

4. API validates with SharedClusterOnboardRequest model
5. API fetches .j2 templates from iac org repos (via GitHub API)
6. API renders templates with user's values
7. API creates PR in payments-team/infra (team's own repo)
8. API comments on INFRA-456 with PR link + target repo
```

#### Step C: What the PR Contains

The API renders these Kubernetes manifests and creates a PR **in the team's repo** (`payments-team/infra`):

**PR: `[INFRA-456] shared-cluster-onboard: payments-api (prod)` — in `payments-team/infra`**

**File 1: `clusters/shared-prod/namespaces/payments-api/namespace.yaml`**
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: payments-api
  labels:
    team: payments
    cost-center: CC-4567
    managed-by: self-service
    jira-ticket: INFRA-456
```

**File 2: `clusters/shared-prod/namespaces/payments-api/resource-quota.yaml`**
```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: payments-api-quota
  namespace: payments-api
spec:
  hard:
    requests.cpu: "4"          # requests = half of limits
    requests.memory: 8Gi
    limits.cpu: "8"
    limits.memory: 16Gi
    pods: "50"
    persistentvolumeclaims: "10"
    requests.storage: 100Gi
```

**File 3: `clusters/shared-prod/namespaces/payments-api/limit-range.yaml`**
```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: payments-api-limits
  namespace: payments-api
spec:
  limits:
    - default:
        cpu: 500m
        memory: 512Mi
      defaultRequest:
        cpu: 100m
        memory: 128Mi
      type: Container
```

**File 4: `clusters/shared-prod/namespaces/payments-api/network-policy.yaml`**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: payments-api
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
  # Deny all traffic by default — team adds their own allow rules
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns-and-internal
  namespace: payments-api
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress:
    - to: []                    # Allow DNS
      ports:
        - protocol: UDP
          port: 53
    - to:                       # Allow traffic within namespace
        - podSelector: {}
```

**File 5: `clusters/shared-prod/namespaces/payments-api/rbac.yaml`**
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: payments-devs-edit
  namespace: payments-api
spec:
  roleRef:
    apiGroup: rbac.authorization.k8s.io
    kind: ClusterRole
    name: edit                   # Built-in K8s role: deploy, scale, view
  subjects:
    - apiGroup: rbac.authorization.k8s.io
      kind: Group
      name: payments-devs       # Mapped from GitHub team via OIDC
```

**File 6: `clusters/shared-prod/namespaces/payments-api/argocd-project.yaml`**
```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: payments-api
  namespace: argocd
spec:
  description: "ArgoCD project for payments team (INFRA-456)"
  sourceRepos:
    - "https://github.com/yourorg/payments-*"
  destinations:
    - namespace: payments-api    # Can ONLY deploy to their namespace
      server: https://kubernetes.default.svc
  clusterResourceWhitelist: []   # No cluster-level resources
  namespaceResourceBlacklist:
    - group: ""
      kind: ResourceQuota       # Can't modify their own quotas
    - group: networking.k8s.io
      kind: NetworkPolicy       # Can't delete network policies
```

**File 7: `clusters/shared-prod/namespaces/payments-api/external-secret-store.yaml`**
```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-sm
  namespace: payments-api
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: payments-api-eso   # Namespace-scoped SA
      # Can only read secrets matching this path:
      # arn:aws:secretsmanager:*:*:secret:prod/payments/*
```

#### Step D: What the Developer Sees

```
PR Comment (auto-posted by CI in payments-team/infra repo):

  ### Terragrunt Plan — shared-prod

  7 Kubernetes resources will be created:
  + Namespace: payments-api
  + ResourceQuota: payments-api-quota
  + LimitRange: payments-api-limits
  + NetworkPolicy: default-deny-all
  + NetworkPolicy: allow-dns-and-internal
  + RoleBinding: payments-devs-edit (→ GitHub team: payments-devs)
  + AppProject: payments-api (ArgoCD)
  + SecretStore: aws-sm (ESO, path: prod/payments/*)

Jira Comment (auto-posted by API):

  ✅ Infrastructure PR created!
  PR: https://github.com/payments-team/infra/pull/89
  Target Repo: payments-team/infra
  
  Next: Platform team reviews → merge → namespace ready in ~2 min
```

#### Step E: After Merge

ArgoCD on the shared cluster syncs the manifests. The payments team can immediately:
- Deploy apps via ArgoCD (only to `payments-api` namespace)
- Read secrets from AWS Secrets Manager (only `prod/payments/*` path)
- `kubectl` access with edit permissions (via GitHub team SSO)
- Resources capped at 8 CPU / 16Gi memory / 50 pods

---

### Example 2: IAM Role Request

**Scenario:** A developer needs an IAM role for their Lambda function to access specific S3 buckets and DynamoDB tables. Instead of a platform engineer hand-crafting the policy, the developer fills a form.

#### Step A: Jira Form — "Request IAM Role"

```
┌─────────────────────────────────────────────────────┐
│  JIRA SERVICE MANAGEMENT                            │
│  Request Type: IAM Role                             │
│                                                     │
│  ┌───────────────────────────────────────────┐      │
│  │  AWS Account ID:     [ 123456789012     ] │      │
│  │  Environment:        [ prod         ▼   ] │      │
│  │  Team Name:          [ data-pipeline    ] │      │
│  │  Cost Center:        [ CC-7890          ] │      │
│  │  Role Name:          [ etl-processor    ] │      │
│  │  Role Description:   [ ETL job that     ] │      │
│  │                      [ reads raw S3 and ] │      │
│  │                      [ writes to DDB    ] │      │
│  │                                           │      │
│  │  Trust Policy (who assumes this role):    │      │
│  │    ◉ Lambda Function                      │      │
│  │    ○ EC2 Instance                         │      │
│  │    ○ ECS Task                             │      │
│  │    ○ EKS Pod (IRSA)                       │      │
│  │    ○ Cross-Account Role                   │      │
│  │                                           │      │
│  │  EKS Cluster (if IRSA): [            ]   │      │
│  │  EKS Namespace (if IRSA): [          ]   │      │
│  │  EKS Service Account (if IRSA): [    ]   │      │
│  │                                           │      │
│  │  Permissions Needed:                      │      │
│  │  ┌─────────────────────────────────────┐  │      │
│  │  │ Service    Action      Resource ARN │  │      │
│  │  │ ────────── ─────────── ──────────── │  │      │
│  │  │ S3         GetObject   arn:aws:s3:: │  │      │
│  │  │                        :raw-data/*  │  │      │
│  │  │ S3         ListBucket  arn:aws:s3:: │  │      │
│  │  │                        :raw-data    │  │      │
│  │  │ DynamoDB   PutItem     arn:aws:dyna │  │      │
│  │  │            Query       modb:*:*:tab │  │      │
│  │  │            GetItem     le/etl-outpu │  │      │
│  │  │                        t            │  │      │
│  │  │ KMS        Decrypt     arn:aws:kms: │  │      │
│  │  │                        *:*:key/abc  │  │      │
│  │  │                                     │  │      │
│  │  │        [ + Add Permission ]         │  │      │
│  │  └─────────────────────────────────────┘  │      │
│  │                                           │      │
│  │  Max Session Duration: [ 3600 ] seconds   │      │
│  │                                           │      │
│  │  ☑ Enable CloudTrail logging              │      │
│  │  ☑ Add permissions boundary               │      │
│  │                                           │      │
│  │              [ Submit Request ]           │      │
│  └───────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────┘
```

#### Step B: What the API Produces

The API validates the request — importantly, it enforces guardrails:

- **Blocked actions:** `iam:*`, `sts:*`, `organizations:*` — no privilege escalation
- **Mandatory boundary:** Attaches a permissions boundary that caps what the role can ever do
- **Resource scoping:** Rejects `Resource: "*"` for write actions — must specify ARNs
- **Naming convention:** Prefixes role name with team and environment

After validation, it fetches the IAM role template from `iac/terraform-aws-iam-role/template/`, renders it, and creates a PR **in the team's repo** (`data-team/infra`):

**PR: `[INFRA-789] iam-role: etl-processor (prod)` — in `data-team/infra`**

**File: `environments/prod/iam-roles/etl-processor/terragrunt.hcl`**
```hcl
# -----------------------------------------------------------------------------
# IAM Role: etl-processor — Auto-generated
# Jira: INFRA-789
# Team: data-pipeline
# Trust: Lambda
# -----------------------------------------------------------------------------

include "root" {
  path = find_in_parent_folders()
}

terraform {
  source = "git::https://github.com/iac/terraform-aws-iam-role.git//?ref=main"
}

inputs = {
  role_name        = "data-pipeline-prod-etl-processor"
  role_description = "ETL job that reads raw S3 and writes to DDB"

  # Trust Policy — who can assume this role
  trusted_services = ["lambda.amazonaws.com"]

  # Permissions Boundary — caps maximum permissions
  permissions_boundary_arn = "arn:aws:iam::123456789012:policy/platform-boundary"

  max_session_duration = 3600

  # Inline policy — least privilege, resource-scoped
  policy_statements = [
    {
      sid       = "S3ReadRawData"
      effect    = "Allow"
      actions   = ["s3:GetObject"]
      resources = ["arn:aws:s3:::raw-data/*"]
    },
    {
      sid       = "S3ListRawBucket"
      effect    = "Allow"
      actions   = ["s3:ListBucket"]
      resources = ["arn:aws:s3:::raw-data"]
    },
    {
      sid       = "DynamoDBWriteOutput"
      effect    = "Allow"
      actions   = ["dynamodb:PutItem", "dynamodb:Query", "dynamodb:GetItem"]
      resources = ["arn:aws:dynamodb:us-east-1:123456789012:table/etl-output"]
    },
    {
      sid       = "KMSDecrypt"
      effect    = "Allow"
      actions   = ["kms:Decrypt"]
      resources = ["arn:aws:kms:us-east-1:123456789012:key/abc"]
    },
  ]

  tags = {
    Team       = "data-pipeline"
    CostCenter = "CC-7890"
    JiraTicket = "INFRA-789"
  }
}
```

#### Step C: What the PR Looks Like

```
PR #92 in data-team/infra: [INFRA-789] iam-role: etl-processor (prod)
Branch: self-service/INFRA-789-iam-role

| Field | Value |
|---|---|
| Jira Ticket | INFRA-789 |
| Request Type | iam-role |
| Environment | prod |
| Team | data-pipeline |
| Target Repo | data-team/infra |
| Role | data-pipeline-prod-etl-processor |
| Trust | lambda.amazonaws.com |
| Permissions Boundary | platform-boundary |

Permissions Summary:
  ✅ s3:GetObject        → arn:aws:s3:::raw-data/*
  ✅ s3:ListBucket       → arn:aws:s3:::raw-data
  ✅ dynamodb:PutItem    → ...table/etl-output
  ✅ dynamodb:Query      → ...table/etl-output
  ✅ dynamodb:GetItem    → ...table/etl-output
  ✅ kms:Decrypt         → ...key/abc

Files:
  - environments/prod/iam-roles/etl-processor/terragrunt.hcl
```

#### Step D: Security Review

The CI pipeline **in the team's repo** runs:
1. `terraform plan` → shows exactly 1 IAM role + 1 inline policy being created
2. `tfsec` → validates no overly permissive actions, no `*` resources on writes
3. `checkov` → confirms permissions boundary is attached

The platform/security team reviews the plan:
- Are the S3/DynamoDB ARNs correct for this team?  
- Is the trust policy scoped (only Lambda, not `*`)?
- Is the permissions boundary attached?

They approve → merge → role is created.

#### Step E: After Merge

```
Terraform applies:

  aws_iam_role.etl_processor:
    name: data-pipeline-prod-etl-processor
    trust: lambda.amazonaws.com
    boundary: platform-boundary
    
  aws_iam_role_policy.etl_processor:
    4 permission statements
    All resource-scoped ✓

Jira INFRA-789 updated:
  "✅ IAM Role created: data-pipeline-prod-etl-processor
   ARN: arn:aws:iam::123456789012:role/data-pipeline-prod-etl-processor
   
   Attach this role to your Lambda function configuration."
```

The developer copies the role ARN into their Lambda config. Done — no Slack messages, no waiting for a platform engineer to hand-craft a policy.

---

### Example Comparison: What Each Form Produces

| Form | Jira Fields | What Gets Created | Review Focus |
|---|---|---|---|
| **EKS Cluster** | cluster_name, version, CIDR, nodes, addons | VPC + EKS + ArgoCD + ALB Controller + Karpenter + ESO + cert-manager | Network design, node sizing, cost |
| **Shared Cluster Onboard** | namespace, team, quotas, GitHub team | Namespace + ResourceQuota + LimitRange + NetworkPolicy + RBAC + ArgoCD Project + SecretStore | Quota sizing, RBAC scope, secret path |
| **IAM Role** | role_name, trust, permissions, resources | IAM Role + Inline Policy + Permissions Boundary | Least privilege, resource scoping, trust |
| **RDS Database** | db_name, engine, class, storage, multi-AZ | RDS instance + subnet group + security group + Secrets Manager | Instance size, backup retention, cost |
| **S3 Bucket** | bucket_name, lifecycle, CORS, CloudFront | S3 bucket + KMS key + lifecycle rules + optional CDN | Public access, encryption, lifecycle |

Every form follows the same pipeline:

```
Jira Form → Webhook → Validate → Fetch Templates (iac org) → Render → PR (team's repo) → CI Plan → Review → Merge → Deploy
```

The only things that change are the **Pydantic model** (validation rules), the **BLUEPRINT mapping** (which iac modules to fetch), and the **Jira form fields** (what the user fills in). Every form also requires **`github_group`** and **`github_repo`** so the PR goes to the correct team repo.
