"""
Pydantic models for self-service request types.
Each model maps to a Jira request form.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ─── Base ────────────────────────────────────────────────────────────────────

class InfraRequest(BaseModel):
    """Common fields every self-service request must have."""

    jira_ticket_key: str = Field(..., description="e.g. INFRA-123")
    requester_email: str = ""
    account_id: str = Field(default="", description="AWS account ID (12 digits, if applicable)")
    environment: str = Field(default="", description="dev/staging/prod (if applicable)")
    team_name: str = ""
    cost_center: str = ""

    # GitHub — the team's own org/group and repo where infra code lives
    github_group: str = Field(..., description="Team's GitHub org/group, e.g. 'payments-team'")
    github_repo: str = Field(default="infra", description="Team's infra repo name, e.g. 'infra'")


# ─── 1. EKS Cluster ─────────────────────────────────────────────────────────

class EKSClusterRequest(InfraRequest):
    """Form: Create a dedicated EKS cluster."""

    request_type: str = "eks-cluster"
    account_id: str = Field(..., pattern=r"^\d{12}$", description="AWS account ID")
    environment: str = Field(..., pattern=r"^(dev|staging|prod)$")
    cluster_name: str = Field(..., pattern=r"^[a-z][a-z0-9\-]{2,39}$")
    cluster_version: str = Field(default="1.31")
    vpc_cidr: str = Field(default="10.0.0.0/16")
    node_instance_type: str = Field(default="m6i.xlarge")
    node_min_size: int = Field(default=2, ge=1, le=100)
    node_max_size: int = Field(default=10, ge=1, le=500)
    node_desired_size: int = Field(default=3, ge=1, le=100)
    enable_karpenter: bool = True
    private_cluster: bool = True
    github_team_slug: str = Field(..., description="GitHub team for ArgoCD RBAC")

    # Addons
    enable_argocd: bool = True
    enable_alb_controller: bool = True
    enable_external_secrets: bool = True
    enable_cert_manager: bool = True


# ─── 2. RDS Database ────────────────────────────────────────────────────────

class RDSDatabaseRequest(InfraRequest):
    """Form: Provision a managed RDS database."""

    request_type: str = "rds-database"
    account_id: str = Field(..., pattern=r"^\d{12}$")
    environment: str = Field(..., pattern=r"^(dev|staging|prod)$")
    db_name: str = Field(..., pattern=r"^[a-z][a-z0-9_]{2,39}$")
    engine: str = Field(default="postgres", pattern=r"^(postgres|mysql)$")
    engine_version: str = Field(default="16.4")
    instance_class: str = Field(default="db.r6g.large")
    allocated_storage: int = Field(default=100, ge=20, le=65536)
    multi_az: bool = True
    deletion_protection: bool = True
    backup_retention_days: int = Field(default=30, ge=1, le=35)
    existing_vpc_id: str = Field(default="", description="VPC to deploy into (if using shared VPC)")


# ─── 3. S3 Bucket ───────────────────────────────────────────────────────────

class S3BucketRequest(InfraRequest):
    """Form: Create a managed S3 bucket."""

    request_type: str = "s3-bucket"
    bucket_name: str = Field(..., pattern=r"^[a-z0-9][a-z0-9.\-]{1,61}[a-z0-9]$")
    versioning: bool = True
    enable_lifecycle: bool = True
    lifecycle_ia_days: int = Field(default=90, ge=30)
    lifecycle_glacier_days: int = Field(default=365, ge=90)
    enable_cloudfront: bool = False
    cors_allowed_origins: list[str] = Field(default_factory=list)


# ─── 4. ECS Fargate Service ─────────────────────────────────────────────────

class ECSServiceRequest(InfraRequest):
    """Form: Deploy a containerized service on ECS Fargate."""

    request_type: str = "ecs-service"
    service_name: str = Field(..., pattern=r"^[a-z][a-z0-9\-]{2,39}$")
    container_image: str
    container_port: int = Field(default=8080, ge=1, le=65535)
    cpu: int = Field(default=512)
    memory: int = Field(default=1024)
    desired_count: int = Field(default=2, ge=1, le=50)
    enable_autoscaling: bool = True
    autoscaling_max: int = Field(default=10, ge=1, le=100)
    health_check_path: str = "/health"
    existing_vpc_id: str = ""
    existing_alb_arn: str = ""


# ─── 5. ElastiCache Redis ───────────────────────────────────────────────────

class RedisRequest(InfraRequest):
    """Form: Provision a managed Redis cluster."""

    request_type: str = "redis"
    cluster_name: str = Field(..., pattern=r"^[a-z][a-z0-9\-]{2,39}$")
    node_type: str = Field(default="cache.r7g.large")
    num_nodes: int = Field(default=2, ge=1, le=6)
    engine_version: str = Field(default="7.1")
    multi_az: bool = True
    existing_vpc_id: str = ""


# ─── 6. Lambda Function ─────────────────────────────────────────────────────

class LambdaRequest(InfraRequest):
    """Form: Create a Lambda function scaffold."""

    request_type: str = "lambda"
    function_name: str = Field(..., pattern=r"^[a-z][a-z0-9\-]{2,39}$")
    runtime: str = Field(default="python3.12")
    memory_size: int = Field(default=256, ge=128, le=10240)
    timeout: int = Field(default=30, ge=1, le=900)
    enable_vpc: bool = False
    enable_api_gateway: bool = False
    existing_vpc_id: str = ""


# ─── 7. DynamoDB Table ──────────────────────────────────────────────────────

class DynamoDBRequest(InfraRequest):
    """Form: Create a DynamoDB table."""

    request_type: str = "dynamodb"
    table_name: str = Field(..., pattern=r"^[a-zA-Z][a-zA-Z0-9_\-]{2,254}$")
    partition_key: str
    partition_key_type: str = Field(default="S", pattern=r"^[SNB]$")
    sort_key: str = ""
    sort_key_type: str = Field(default="S", pattern=r"^[SNB]$")
    billing_mode: str = Field(default="PAY_PER_REQUEST", pattern=r"^(PAY_PER_REQUEST|PROVISIONED)$")
    enable_streams: bool = False
    enable_point_in_time_recovery: bool = True


# ─── 8. MSK Kafka Cluster ───────────────────────────────────────────────────

class MSKRequest(InfraRequest):
    """Form: Create a managed Kafka cluster."""

    request_type: str = "msk"
    cluster_name: str = Field(..., pattern=r"^[a-z][a-z0-9\-]{2,39}$")
    kafka_version: str = Field(default="3.7.x.kraft")
    broker_instance_type: str = Field(default="kafka.m7g.large")
    number_of_brokers: int = Field(default=3, ge=3, le=30)
    storage_per_broker_gb: int = Field(default=100, ge=1, le=16384)
    existing_vpc_id: str = ""


# ─── 9. Route53 Hosted Zone ─────────────────────────────────────────────────

class Route53Request(InfraRequest):
    """Form: Create a Route53 hosted zone."""

    request_type: str = "route53"
    domain_name: str
    private_zone: bool = False
    existing_vpc_id: str = Field(default="", description="Required for private zones")


# ─── 10. VPC Network ────────────────────────────────────────────────────────

class VPCRequest(InfraRequest):
    """Form: Create a standalone VPC."""

    request_type: str = "vpc"
    vpc_name: str = Field(..., pattern=r"^[a-z][a-z0-9\-]{2,39}$")
    vpc_cidr: str = Field(default="10.0.0.0/16")
    enable_nat_gateway: bool = True
    single_nat_gateway: bool = False
    enable_vpn_gateway: bool = False


# ─── 11. XCR Onboarding (Cluster Onboarding Request) ────────────────────────

class XCROnboardingRequest(InfraRequest):
    """Form: XCR Onboarding — Cluster Onboarding Request from FDSOne Help Center."""

    request_type: str = "xcr-onboarding"
    summary: str = Field(..., description="Request summary")
    business_unit: str = Field(..., description="Business Unit/Segment")
    client_services: str = Field(..., description="Client Services")
    team_name: str = Field(..., description="Team Name")
    component: str = Field(..., description="Component")
    primary_contact_email: str = Field(..., description="Primary Contact Email")
    description: str = Field(default="", description="Description")
    cloud: str = Field(..., description="Cloud provider (e.g. AWS, Azure, GCP)")
    cluster_type: str = Field(..., description="Cluster Type")
    release_type: str = Field(..., description="Release Type")
    size: str = Field(..., description="Cluster size")
    connectivity: str = Field(..., description="Connectivity type")
    keycloak_group_name: str = Field(..., description="Keycloak Group Name for RBAC")


# ─── 12. SRE Onboarding (Observability Stack) ───────────────────────────────

class SREOnboardingRequest(InfraRequest):
    """
    Form: Onboard a team's EKS cluster to the central SRE platform.

    Provisions:
    1. VPC Peering — team VPC <-> central monitoring VPC
    2. Prometheus Agent — remote-write to central AMP/Mimir
    3. OpenTelemetry Collector — traces + metrics pipeline
    4. kube-state-metrics — Kubernetes object metrics
    5. node-exporter — OS-level node metrics
    6. Grafana folder + datasource for the team
    7. SLO/SLI definitions — error budget, latency, availability targets
    8. Incident management — PagerDuty/Opsgenie integration, escalation policies
    9. Runbooks — auto-generated operational runbooks in wiki
    10. On-call schedule — rotation setup in incident management tool
    """

    request_type: str = "sre-onboarding"
    account_id: str = Field(..., pattern=r"^\d{12}$", description="AWS account ID")
    environment: str = Field(..., pattern=r"^(dev|staging|prod)$")

    # Cluster info
    cluster_name: str = Field(..., pattern=r"^[a-z][a-z0-9\-]{2,39}$",
                              description="Name of the EKS cluster to onboard")
    cluster_endpoint: str = Field(default="", description="EKS cluster API endpoint (auto-discovered if empty)")

    # Central monitoring stack
    central_monitoring_vpc_id: str = Field(..., description="VPC ID of the central monitoring stack")
    central_monitoring_vpc_cidr: str = Field(default="10.0.0.0/16",
                                             description="CIDR of the central monitoring VPC")
    central_monitoring_account_id: str = Field(default="", description="AWS account ID of the monitoring account")
    prometheus_remote_write_url: str = Field(...,
        description="AMP or Mimir remote write endpoint")

    # Team's VPC
    team_vpc_id: str = Field(..., description="VPC ID of the team's EKS cluster")
    team_vpc_cidr: str = Field(default="", description="CIDR of the team's VPC")

    # Collector options
    enable_otel_collector: bool = Field(default=True, description="Deploy OpenTelemetry Collector")
    enable_tracing: bool = Field(default=False, description="Enable distributed tracing via OTel")
    tracing_endpoint: str = Field(default="", description="OTLP tracing endpoint (if enable_tracing=true)")
    enable_logging: bool = Field(default=False, description="Ship logs to central Loki/CloudWatch")
    logging_endpoint: str = Field(default="", description="Loki push endpoint (if enable_logging=true)")

    # Scrape config
    scrape_interval: str = Field(default="30s", description="Prometheus scrape interval")
    metrics_retention_hours: int = Field(default=2, ge=1, le=24,
        description="Local WAL retention before remote-write (hours)")

    # Grafana
    grafana_org_name: str = Field(default="", description="Grafana org/folder for the team (defaults to team_name)")

    # ── SLO / SLI Definitions ──────────────────────────────────────────────
    slo_availability_target: float = Field(default=99.9, ge=90.0, le=100.0,
        description="Availability SLO target (e.g. 99.9%)")
    slo_latency_p99_ms: int = Field(default=500, ge=10, le=60000,
        description="P99 latency SLO target in milliseconds")
    slo_error_rate_threshold: float = Field(default=0.1, ge=0.0, le=100.0,
        description="Error rate SLI threshold (e.g. 0.1%)")
    error_budget_burn_alert: bool = Field(default=True,
        description="Enable burn-rate alerts when error budget is consumed")

    # ── Incident Management ────────────────────────────────────────────────
    incident_tool: str = Field(default="pagerduty",
        pattern=r"^(pagerduty|opsgenie|incident\.io|none)$",
        description="Incident management tool to integrate")
    pagerduty_service_id: str = Field(default="",
        description="PagerDuty service ID (if incident_tool=pagerduty)")
    opsgenie_team_id: str = Field(default="",
        description="Opsgenie team ID (if incident_tool=opsgenie)")
    escalation_policy: str = Field(default="default",
        description="Escalation policy name for incident routing")
    oncall_rotation_name: str = Field(default="",
        description="On-call rotation name (auto-created if empty)")
    oncall_primary_email: str = Field(default="",
        description="Primary on-call engineer email")
    oncall_secondary_email: str = Field(default="",
        description="Secondary on-call engineer email")

    # ── Runbooks & Docs ────────────────────────────────────────────────────
    enable_runbooks: bool = Field(default=True,
        description="Auto-generate operational runbooks in Confluence/wiki")
    runbook_wiki_space: str = Field(default="SRE",
        description="Wiki space for generated runbooks")
    notification_slack_channel: str = Field(default="",
        description="Slack channel for alerts and incident notifications")
    notification_email: str = Field(default="",
        description="Email distribution list for alerts")


# ─── 14. EKS Cluster Upgrade ────────────────────────────────────────────────

class EKSUpgradeRequest(InfraRequest):
    """Initiated from Keystone Portal — upgrades a deployed EKS cluster version.

    NOT a Jira webhook request. Platform engineers trigger this directly.
    Upgrade proceeds through 4 stages via Terraform/Terragrunt:
      1. Control Plane — EKS API server version bump
      2. Addons — VPC CNI, CoreDNS, kube-proxy, karpenter
      3. Node Groups — rolling update with new AMI
      4. Post-Checks — validation + load test
    """

    request_type: str = "eks-upgrade"
    cluster_name: str = Field(..., description="Name of the EKS cluster to upgrade")
    current_version: str = Field(..., description="Current Kubernetes version")
    target_version: str = Field(..., description="Target Kubernetes version (N+1 only)")
    source_request_key: str = Field(default="", description="Jira key of the original EKS cluster request")

    # Upgrade configuration
    upgrade_strategy: str = Field(default="rolling", pattern=r"^(rolling|blue-green)$")
    node_max_unavailable: int = Field(default=1, ge=1, le=10)
    drain_timeout_seconds: int = Field(default=300, ge=60, le=3600)

    # Safety
    skip_pre_checks: bool = Field(default=False)
    enable_auto_rollback: bool = Field(default=True)
    lower_env_validated: bool = Field(default=False, description="Has lower env been validated for 2+ weeks?")

    # Notifications
    notification_slack_channel: str = Field(default="")
    notification_email: str = Field(default="")


# ─── 15. AWS Account Request ────────────────────────────────────────────────

class AWSAccountRequest(InfraRequest):
    """
    Form: Request a dedicated AWS account for a team.

    Product owner submits this. After admin approval the platform:
    1. Creates the AWS account in Organizations
    2. Applies baseline (OIDC role, state bucket, security defaults)
    3. Creates the team's GitHub infra repo
    4. Registers the team → account mapping
    """

    request_type: str = "aws-account"
    # Don't require account_id/environment — they don't exist yet
    account_id: str = Field(default="", description="Will be assigned after creation")
    environment: str = Field(default="dev", pattern=r"^(dev|staging|prod)$")

    # Team info
    team_name: str = Field(..., pattern=r"^[a-z][a-z0-9-]{2,39}$",
                           description="Team slug (lowercase, hyphens ok)")
    team_display_name: str = Field(..., description="Human-readable team name")
    product_owner_email: str = Field(..., description="Product owner email (will be account admin)")
    business_unit: str = Field(default="", description="Business unit / segment")
    cost_center: str = Field(default="", description="Cost center for billing")

    # AWS
    ou_path: str = Field(default="Workloads",
                         description="Organizational Unit path (e.g. Workloads, Sandbox)")
    account_email_prefix: str = Field(default="",
                                      description="Prefix for root email; auto-generated if empty")

    # GitHub
    github_group: str = Field(..., description="GitHub org where the team's infra repo will live")
    github_repo: str = Field(default="infra", description="Infra repo name to create")

    # What to bootstrap
    enable_vpc: bool = Field(default=True, description="Create a default VPC in the account")
    vpc_cidr: str = Field(default="10.0.0.0/16", description="CIDR for the default VPC")
    enable_guardduty: bool = Field(default=True, description="Enable GuardDuty")
    enable_cloudtrail: bool = Field(default=True, description="Enable CloudTrail")


# ─── 16. DocumentDB Database ─────────────────────────────────────────────────

class DocumentDBRequest(InfraRequest):
    """Form: Provision a managed DocumentDB (MongoDB-compatible) cluster.

    Creates a multi-instance DocumentDB cluster with:
    - KMS encryption at rest
    - TLS encryption in transit
    - Secrets Manager for credentials
    - Automated backups
    - Deletion protection
    - CloudWatch logging (audit + profiler)
    """

    request_type: str = "documentdb-database"
    account_id: str = Field(..., pattern=r"^\d{12}$")
    environment: str = Field(..., pattern=r"^(dev|staging|prod)$")
    cluster_name: str = Field(..., pattern=r"^[a-z][a-z0-9\-]{2,39}$",
                              description="DocumentDB cluster name")
    engine_version: str = Field(default="5.0", pattern=r"^(4\.0|5\.0|6\.0)$",
                                description="MongoDB compatibility version")
    instance_class: str = Field(default="db.r6g.large",
                                description="Instance class for cluster members")
    num_instances: int = Field(default=3, ge=1, le=16,
                               description="Number of cluster instances (min 3 for prod)")
    master_username: str = Field(default="docdbadmin", pattern=r"^[a-zA-Z][a-zA-Z0-9_]{2,62}$")
    deletion_protection: bool = True
    backup_retention_days: int = Field(default=30, ge=1, le=35)
    existing_vpc_id: str = Field(default="", description="VPC to deploy into (if using shared VPC)")


# ─── 17. ArgoCD GitOps Onboarding ────────────────────────────────────────────

class ArgocdOnboardingRequest(InfraRequest):
    """Initiated from Keystone Portal — sets up ArgoCD GitOps for a team's
    services on a deployed EKS cluster.

    Generates:
      - ArgoCD AppProject with RBAC
      - ApplicationSet with matrix generator (envs × services)
      - Helm chart scaffolding per service (Chart.yaml, values.yaml, templates/)
      - Per-environment value overrides (values/<env>/<service>.yaml)
    """

    request_type: str = "argocd-onboarding"
    project_name: str = Field(..., pattern=r"^[a-z][a-z0-9\-]{2,39}$",
                              description="ArgoCD project name")
    namespace: str = Field(..., pattern=r"^[a-z][a-z0-9\-]{1,62}$",
                           description="Base Kubernetes namespace for deployments")
    source_cluster_key: str = Field(...,
                                    description="Jira key of the deployed EKS cluster")
    cluster_name: str = Field(default="",
                              description="Name of the target EKS cluster")
    cluster_endpoint: str = Field(default="",
                                  description="EKS cluster API endpoint")
    services: list[str] = Field(..., min_length=1, max_length=20,
                                description="List of service names to onboard")
    environments: list[str] = Field(default=["dev", "staging", "prod"],
                                    description="Target environments")
    image_registry: str = Field(default="",
                                description="Container image registry (e.g. 123456789.dkr.ecr.us-east-1.amazonaws.com)")


# ─── 18. Iceberg Data Lake ───────────────────────────────────────────────────

class IcebergTableRequest(InfraRequest):
    """Form: Create an Apache Iceberg table on AWS Glue Data Catalog with S3 storage.

    Creates:
    - Glue Database (if not exists)
    - Glue Table with Iceberg table format
    - S3 bucket for data lake storage
    - KMS encryption for data at rest
    """

    request_type: str = "iceberg-table"
    account_id: str = Field(..., pattern=r"^\d{12}$")
    environment: str = Field(..., pattern=r"^(dev|staging|prod)$")
    database_name: str = Field(..., pattern=r"^[a-z][a-z0-9_]{2,59}$",
                               description="Glue database name")
    table_name: str = Field(..., pattern=r"^[a-z][a-z0-9_]{2,59}$",
                            description="Iceberg table name")
    s3_bucket_name: str = Field(default="", description="Existing S3 bucket (auto-created if empty)")
    file_format: str = Field(default="parquet", pattern=r"^(parquet|orc|avro)$")
    compression: str = Field(default="snappy", pattern=r"^(snappy|gzip|zstd|lz4)$")
    partition_columns: list[str] = Field(default_factory=list,
                                         description="Partition column names")


# ─── 19. Vector Store ────────────────────────────────────────────────────────

class VectorStoreRequest(InfraRequest):
    """Form: Provision a vector database for AI/ML embeddings.

    Creates either:
    - RDS PostgreSQL with pgvector extension, or
    - OpenSearch Serverless collection for vector search
    """

    request_type: str = "vector-store"
    account_id: str = Field(..., pattern=r"^\d{12}$")
    environment: str = Field(..., pattern=r"^(dev|staging|prod)$")
    store_name: str = Field(..., pattern=r"^[a-z][a-z0-9\-]{2,39}$",
                            description="Vector store name")
    engine: str = Field(default="pgvector", pattern=r"^(pgvector|opensearch-serverless)$",
                        description="Vector database engine")
    dimensions: int = Field(default=1536, ge=1, le=16000,
                            description="Embedding dimensions (e.g. 1536 for OpenAI)")
    distance_metric: str = Field(default="cosine",
                                 pattern=r"^(cosine|euclidean|inner_product)$")
    instance_class: str = Field(default="db.r6g.large",
                                description="Instance class (pgvector only)")
    existing_vpc_id: str = Field(default="", description="VPC to deploy into")


# ─── 20. Lake Formation ─────────────────────────────────────────────────────

class LakeFormationRequest(InfraRequest):
    """Form: Set up AWS Lake Formation data governance.

    Creates:
    - Lake Formation settings and admin configuration
    - Data lake S3 location registrations
    - LF-Tags for column-level security
    - Database and table permissions
    """

    request_type: str = "lake-formation"
    account_id: str = Field(..., pattern=r"^\d{12}$")
    environment: str = Field(..., pattern=r"^(dev|staging|prod)$")
    data_lake_name: str = Field(..., pattern=r"^[a-z][a-z0-9\-]{2,39}$",
                                description="Data lake identifier")
    admin_arn: str = Field(..., description="IAM ARN for Lake Formation admin")
    s3_locations: list[str] = Field(..., min_length=1,
                                    description="S3 bucket ARNs to register as data lake locations")
    lf_tags: dict[str, list[str]] = Field(default_factory=dict,
                                           description="LF-Tags (key → allowed values)")
    catalog_id: str = Field(default="", description="Glue Catalog ID (defaults to account)")


# ─── 21. Data Access Provisioning ────────────────────────────────────────────

class DataAccessRequest(InfraRequest):
    """Form: Provision IAM roles and policies for data resource access.

    Creates:
    - IAM role with least-privilege policy
    - Resource-specific policy (S3, RDS, DynamoDB, MSK, etc.)
    - Optional cross-account trust relationship
    """

    request_type: str = "data-access"
    account_id: str = Field(..., pattern=r"^\d{12}$")
    environment: str = Field(..., pattern=r"^(dev|staging|prod)$")
    access_name: str = Field(..., pattern=r"^[a-z][a-z0-9\-]{2,39}$",
                             description="Access provisioning name")
    target_resource_type: str = Field(...,
        pattern=r"^(s3|rds|dynamodb|msk|documentdb|glue|redshift)$",
        description="Type of data resource")
    target_resource_arn: str = Field(..., description="ARN of the target resource")
    principal_arns: list[str] = Field(..., min_length=1,
                                      description="IAM ARNs to grant access")
    access_level: str = Field(default="readonly",
                              pattern=r"^(readonly|readwrite|admin)$")
    enable_cross_account: bool = Field(default=False,
                                        description="Enable cross-account trust")


# ─── 22. Data Classification ────────────────────────────────────────────────

class DataClassificationRequest(InfraRequest):
    """Form: Classify and tag data sensitivity using Macie + Glue classifiers.

    Creates:
    - Macie classification job
    - Glue custom classifiers
    - SNS notifications for findings
    - Sensitivity tags on resources
    """

    request_type: str = "data-classification"
    account_id: str = Field(..., pattern=r"^\d{12}$")
    environment: str = Field(..., pattern=r"^(dev|staging|prod)$")
    classification_name: str = Field(..., pattern=r"^[a-z][a-z0-9\-]{2,39}$",
                                     description="Classification job name")
    target_bucket_arns: list[str] = Field(..., min_length=1,
                                          description="S3 bucket ARNs to classify")
    sensitivity_level: str = Field(default="confidential",
                                   pattern=r"^(public|internal|confidential|restricted)$")
    enable_pii_detection: bool = Field(default=True,
                                        description="Enable PII detection (SSN, credit cards, etc.)")
    schedule_frequency: str = Field(default="weekly",
                                    pattern=r"^(daily|weekly|monthly)$")
    notification_email: str = Field(default="", description="Email for classification findings")


# ─── 23. Cross-Account Data Sharing ─────────────────────────────────────────

class CrossAccountShareRequest(InfraRequest):
    """Form: Share data resources across AWS accounts via RAM.

    Creates:
    - RAM resource share
    - Principal associations (target accounts)
    - Resource policies
    - KMS key grants for encrypted resources
    """

    request_type: str = "cross-account-share"
    account_id: str = Field(..., pattern=r"^\d{12}$")
    environment: str = Field(..., pattern=r"^(dev|staging|prod)$")
    share_name: str = Field(..., pattern=r"^[a-z][a-z0-9\-]{2,39}$",
                            description="Resource share name")
    resource_arns: list[str] = Field(..., min_length=1,
                                     description="ARNs of resources to share")
    target_account_ids: list[str] = Field(..., min_length=1,
                                          description="Target AWS account IDs")
    permission_type: str = Field(default="readonly",
                                 pattern=r"^(readonly|readwrite)$")
    enable_external_sharing: bool = Field(default=False,
                                           description="Allow sharing outside the Organization")


# ─── Registry: maps request_type → model class ──────────────────────────────

REQUEST_TYPE_MAP: dict[str, type[InfraRequest]] = {
    "eks-cluster": EKSClusterRequest,
    "rds-database": RDSDatabaseRequest,
    "s3-bucket": S3BucketRequest,
    "ecs-service": ECSServiceRequest,
    "redis": RedisRequest,
    "lambda": LambdaRequest,
    "dynamodb": DynamoDBRequest,
    "msk": MSKRequest,
    "route53": Route53Request,
    "vpc": VPCRequest,
    "xcr-onboarding": XCROnboardingRequest,
    "sre-onboarding": SREOnboardingRequest,
    "eks-upgrade": EKSUpgradeRequest,
    "aws-account": AWSAccountRequest,
    "argocd-onboarding": ArgocdOnboardingRequest,
    "documentdb-database": DocumentDBRequest,
    "iceberg-table": IcebergTableRequest,
    "vector-store": VectorStoreRequest,
    "lake-formation": LakeFormationRequest,
    "data-access": DataAccessRequest,
    "data-classification": DataClassificationRequest,
    "cross-account-share": CrossAccountShareRequest,
}
