/**
 * Keystone Service Registry — Single Source of Truth
 *
 * Every service is defined ONCE here. The portal automatically generates:
 *   - Service Catalog cards  (catalog)
 *   - Request form fields    (fields)
 *   - Documentation pages    (docs)
 *   - Access guides          (accessGuide)
 *
 * To add a new service:
 *   1. Add a block below following the same shape
 *   2. Add a matching Pydantic model in app/models/requests.py
 *   3. That's it — catalog, form, docs, and access guide appear automatically
 */

var SERVICE_REGISTRY = {

// ═══════════════════════════════════════════════════════════════════════════
// COMPUTE
// ═══════════════════════════════════════════════════════════════════════════

'eks-cluster': {
  name: 'EKS Cluster',
  icon: '\u2638\uFE0F',
  category: 'Compute',
  description: 'Managed Kubernetes with Karpenter and ArgoCD',

  fields: [
    {name:'cluster_name',label:'Cluster Name',type:'text',required:true,placeholder:'my-cluster'},
    {name:'cluster_version',label:'Kubernetes Version',type:'select',options:['1.28','1.29','1.30','1.31','1.32']},
    {name:'vpc_cidr',label:'VPC CIDR',type:'text',placeholder:'10.0.0.0/16'},
    {name:'node_instance_type',label:'Node Instance Type',type:'select',options:['m6i.large','m6i.xlarge','m6i.2xlarge','m7i.xlarge','r6i.xlarge']},
    {name:'node_min_size',label:'Min Nodes',type:'number',min:1,max:100},
    {name:'node_max_size',label:'Max Nodes',type:'number',min:1,max:500},
    {name:'node_desired_size',label:'Desired Nodes',type:'number',min:1,max:100},
    {name:'enable_karpenter',label:'Enable Karpenter',type:'checkbox',desc:'Auto-scaling with Karpenter'},
    {name:'private_cluster',label:'Private Cluster',type:'checkbox',desc:'Private API server endpoint'},
    {name:'github_team_slug',label:'GitHub Team Slug',type:'text',required:true,placeholder:'my-team'},
    {name:'enable_argocd',label:'Enable ArgoCD',type:'checkbox'},
    {name:'enable_alb_controller',label:'Enable ALB Controller',type:'checkbox'},
    {name:'enable_external_secrets',label:'Enable External Secrets',type:'checkbox',desc:'Sync secrets from AWS Secrets Manager'},
    {name:'enable_cert_manager',label:'Enable cert-manager',type:'checkbox',desc:'Automated TLS certificates'},
  ],

  docs: {
    updated: '2026-04-15',
    overview: 'Amazon EKS (Elastic Kubernetes Service) provides a fully managed Kubernetes control plane. Keystone provisions production-ready clusters with Karpenter auto-scaling, ArgoCD GitOps, ALB Ingress Controller, and IRSA (IAM Roles for Service Accounts). Each cluster is deployed into a dedicated VPC with private subnets, encrypted with a KMS key, and integrated with the platform observability stack.',
    useCases: [
      'Running containerized microservices in production',
      'Machine learning training and inference workloads',
      'Batch processing and data pipeline orchestration',
      'Multi-tenant internal platform hosting',
      'CI/CD runner infrastructure (GitHub Actions self-hosted runners)',
    ],
    prerequisites: [
      'An active AWS account registered in Keystone (Team Accounts page)',
      'A GitHub team slug for RBAC mapping',
      'A VPC CIDR range that does not conflict with existing VPCs',
      'Cost center approved for compute workloads',
    ],
    howToProvision: [
      'Navigate to Service Catalog and click "EKS Cluster"',
      'Fill in common fields: Team Name, GitHub Group, AWS Account ID, Environment',
      'Enter a Cluster Name (must be unique within the account)',
      'Select the Kubernetes version (1.30 recommended for production)',
      'Choose node instance type and set min/max/desired node counts',
      'Enable Karpenter for intelligent auto-scaling (recommended)',
      'Enable ArgoCD if you want GitOps-based deployments',
      'Enable ALB Controller for AWS Load Balancer integration',
      'Click "Submit Request" — a PR will be created in your infra repo',
      'After approval and merge, Terraform provisions the cluster automatically',
    ],
    configOptions: [
      { param: 'cluster_name', desc: 'Unique name for the EKS cluster. Used in resource tags and DNS.' },
      { param: 'cluster_version', desc: 'Kubernetes version. Supported: 1.28–1.32. Use latest stable for new clusters.' },
      { param: 'vpc_cidr', desc: 'CIDR block for the new VPC (e.g., 10.0.0.0/16). Must not overlap with peered VPCs.' },
      { param: 'node_instance_type', desc: 'EC2 instance type for managed node group. m6i.large is a good default.' },
      { param: 'node_min/max/desired_size', desc: 'Auto-scaling boundaries. Karpenter overrides max when enabled.' },
      { param: 'enable_karpenter', desc: 'Deploys Karpenter for just-in-time node provisioning. Reduces costs by 30-50%.' },
      { param: 'private_cluster', desc: 'When enabled, the API server endpoint is only accessible within the VPC.' },
      { param: 'enable_argocd', desc: 'Installs ArgoCD and configures ApplicationSets for your team namespace.' },
      { param: 'enable_alb_controller', desc: 'Installs AWS Load Balancer Controller for Ingress resources.' },
    ],
    faqs: [
      { q: 'How long does EKS provisioning take?', a: 'Typically 15-20 minutes after the Terraform apply starts. The control plane creation takes ~10 minutes, followed by node group bootstrapping.' },
      { q: 'Can I change the Kubernetes version later?', a: 'Yes, use the "EKS Upgrade" service in the catalog. It performs a rolling upgrade with zero downtime.' },
      { q: 'How do I access the cluster?', a: 'After deployment, update your kubeconfig: aws eks update-kubeconfig --name <cluster_name> --region us-east-1. RBAC is mapped to your GitHub team.' },
      { q: 'What if provisioning fails?', a: 'Check the request detail page for error messages. Common causes: CIDR conflicts, insufficient IAM permissions, or service quota limits.' },
    ],
  },

  accessGuide: function(r, o, env, region, name, acct, endpoint) {
    return [
      {title:'Configure AWS Credentials', desc:'Ensure your AWS CLI is configured with the correct account and region.', commands:[
        {label:'Set your AWS profile', code:'aws configure --profile keystone-'+env+'\n# Access Key ID: <from your team admin>\n# Secret Access Key: <from your team admin>\n# Region: '+region},
        {label:'Verify identity', code:'aws sts get-caller-identity --profile keystone-'+env}
      ]},
      {title:'Update Kubeconfig', desc:'Add the EKS cluster to your local kubeconfig so kubectl can connect.', commands:[
        {code:'aws eks update-kubeconfig \\\n  --name '+name+' \\\n  --region '+region+' \\\n  --profile keystone-'+env}
      ]},
      {title:'Verify Cluster Access', commands:[
        {label:'List nodes', code:'kubectl get nodes'},
        {label:'Check namespaces', code:'kubectl get namespaces'},
        {label:'Get cluster info', code:'kubectl cluster-info'}
      ], notes:['If access is denied, ask your team admin to add your IAM role to the aws-auth ConfigMap.']},
      {title:'IDE Integration (VS Code)', desc:'Install the Kubernetes extension for a visual cluster experience.', commands:[
        {label:'Install extension', code:'code --install-extension ms-kubernetes-tools.vscode-kubernetes-tools'},
        {label:'Open Kubernetes panel', code:'Ctrl+Shift+P \u2192 "Kubernetes: Set Kubeconfig"'}
      ], notes:['The cluster will appear automatically in the Kubernetes sidebar after kubeconfig is updated.','For Lens IDE: File \u2192 Add Cluster \u2192 paste kubeconfig path.']}
    ];
  },
},

'ecs-service': {
  name: 'ECS Fargate',
  icon: '\u{1F433}',
  category: 'Compute',
  description: 'Serverless containers with ALB and auto-scaling',

  fields: [
    {name:'service_name',label:'Service Name',type:'text',required:true,placeholder:'my-api'},
    {name:'container_image',label:'Container Image',type:'text',required:true,placeholder:'123456789012.dkr.ecr.us-east-1.amazonaws.com/my-app:latest'},
    {name:'container_port',label:'Container Port',type:'number',min:1,max:65535},
    {name:'cpu',label:'CPU Units',type:'select',options:['256','512','1024','2048','4096']},
    {name:'memory',label:'Memory (MB)',type:'select',options:['512','1024','2048','4096','8192']},
    {name:'desired_count',label:'Task Count',type:'number',min:1,max:50},
    {name:'enable_autoscaling',label:'Enable Auto Scaling',type:'checkbox',desc:'Scale tasks based on CPU/memory'},
    {name:'autoscaling_max',label:'Max Tasks (Autoscaling)',type:'number',min:1,max:100},
    {name:'health_check_path',label:'Health Check Path',type:'text',placeholder:'/health'},
    {name:'existing_vpc_id',label:'Existing VPC ID',type:'text',desc:'Leave empty to create new',placeholder:'vpc-0abc123'},
  ],

  docs: {
    updated: '2026-04-15',
    overview: 'Amazon ECS Fargate provides serverless container hosting. Keystone provisions ECS services with an Application Load Balancer (ALB), auto-scaling policies, CloudWatch logging, and integration with ECR for container images. No EC2 instances to manage.',
    useCases: [
      'Simple web APIs and microservices that do not need Kubernetes',
      'Background workers and queue processors',
      'Cost-effective services with predictable traffic patterns',
      'Quick deployment of containerized applications without cluster management',
    ],
    prerequisites: [
      'An active AWS account registered in Keystone',
      'A container image pushed to ECR or a public registry',
      'A VPC with private subnets (or request a VPC first)',
    ],
    howToProvision: [
      'Navigate to Service Catalog and click "ECS Fargate"',
      'Fill in common fields: Team, AWS Account, Environment',
      'Enter a Service Name and Container Port',
      'Select CPU and Memory allocation for your tasks',
      'Set the desired task count (number of running containers)',
      'Click "Submit Request"',
      'After PR approval, Terraform creates the ECS service, ALB, target group, and CloudWatch log group',
    ],
    configOptions: [
      { param: 'service_name', desc: 'Name for your ECS service. Used in resource naming and DNS.' },
      { param: 'container_port', desc: 'The port your container listens on (e.g., 8080, 3000).' },
      { param: 'cpu', desc: 'CPU units: 256 (0.25 vCPU) to 4096 (4 vCPU). 512 is good for most APIs.' },
      { param: 'memory', desc: 'Memory in MB. Must be compatible with CPU selection (see AWS docs).' },
      { param: 'desired_count', desc: 'Number of running tasks. Auto-scaling adjusts this based on load.' },
    ],
    faqs: [
      { q: 'ECS vs EKS \u2014 which should I choose?', a: 'Use ECS for simple services that do not need Kubernetes features. Use EKS for complex workloads, service mesh, or when your team already uses Kubernetes.' },
      { q: 'How do I deploy new versions?', a: 'Push a new image to ECR and update the task definition. ArgoCD or a CI/CD pipeline can automate this.' },
    ],
  },

  accessGuide: function(r, o, env, region, name, acct, endpoint) {
    return [
      {title:'View Service Status', commands:[
        {label:'Describe service', code:'aws ecs describe-services \\\n  --cluster '+(r.cluster_name||'keystone-'+env)+' \\\n  --services '+name+' \\\n  --region '+region},
        {label:'List running tasks', code:'aws ecs list-tasks \\\n  --cluster '+(r.cluster_name||'keystone-'+env)+' \\\n  --service-name '+name}
      ]},
      {title:'View Logs', commands:[
        {code:'aws logs tail /ecs/'+name+' --follow --profile keystone-'+env}
      ]},
      {title:'Exec Into Container', desc:'Requires ECS Exec to be enabled on the service.', commands:[
        {code:'TASK_ARN=$(aws ecs list-tasks --cluster '+(r.cluster_name||'keystone-'+env)+' --service-name '+name+' --query "taskArns[0]" --output text)\n\naws ecs execute-command \\\n  --cluster '+(r.cluster_name||'keystone-'+env)+' \\\n  --task $TASK_ARN \\\n  --container '+name+' \\\n  --interactive \\\n  --command "/bin/sh"'}
      ], notes:['You need the Session Manager plugin installed for ECS Exec.']},
      {title:'Local Development', commands:[
        {label:'Pull and run container locally', code:'aws ecr get-login-password --region '+region+' | docker login --username AWS --password-stdin '+acct+'.dkr.ecr.'+region+'.amazonaws.com\ndocker pull '+acct+'.dkr.ecr.'+region+'.amazonaws.com/'+name+':latest\ndocker run -p 8080:8080 '+acct+'.dkr.ecr.'+region+'.amazonaws.com/'+name+':latest'}
      ]}
    ];
  },
},

'lambda': {
  name: 'Lambda Function',
  icon: '\u26A1',
  category: 'Compute',
  description: 'Serverless function with API Gateway',

  fields: [
    {name:'function_name',label:'Function Name',type:'text',required:true,placeholder:'my-function'},
    {name:'runtime',label:'Runtime',type:'select',options:['python3.12','nodejs20.x','java21','dotnet8']},
    {name:'memory_size',label:'Memory (MB)',type:'number',min:128,max:10240},
    {name:'timeout',label:'Timeout (seconds)',type:'number',min:1,max:900},
    {name:'enable_api_gateway',label:'Enable API Gateway',type:'checkbox',desc:'Create REST API trigger'},
    {name:'enable_vpc',label:'Deploy in VPC',type:'checkbox',desc:'Place Lambda inside a VPC'},
    {name:'existing_vpc_id',label:'VPC ID',type:'text',desc:'Required if VPC enabled',placeholder:'vpc-0abc123'},
  ],

  docs: {
    updated: '2026-04-15',
    overview: 'AWS Lambda lets you run code without provisioning servers. Keystone provisions Lambda functions with API Gateway integration, IAM execution roles, CloudWatch logging, and optional VPC connectivity. Supports Python, Node.js, Java, and .NET runtimes.',
    useCases: [
      'Event-driven processing (S3 uploads, SQS messages, DynamoDB streams)',
      'REST API endpoints with low traffic or bursty patterns',
      'Scheduled tasks and cron jobs',
      'Data transformation and ETL glue logic',
    ],
    prerequisites: [
      'An active AWS account registered in Keystone',
      'Your function code packaged as a ZIP or container image',
    ],
    howToProvision: [
      'Navigate to Service Catalog and click "Lambda Function"',
      'Fill in common fields: Team, AWS Account, Environment',
      'Enter a Function Name and select the Runtime',
      'Set Memory (128\u201310240 MB) and Timeout (1\u2013900 seconds)',
      'Click "Submit Request"',
      'Upload your code after the function is provisioned',
    ],
    configOptions: [
      { param: 'function_name', desc: 'Unique name for the Lambda function.' },
      { param: 'runtime', desc: 'Language runtime: python3.12, nodejs20.x, java21, or dotnet8.' },
      { param: 'memory_size', desc: 'Memory in MB. CPU scales proportionally. 256 MB is a good starting point.' },
      { param: 'timeout', desc: 'Maximum execution time in seconds. API Gateway has a 29s hard limit.' },
    ],
    faqs: [
      { q: 'What are cold starts?', a: 'The first invocation after idle time takes longer (100ms\u20132s) because AWS needs to initialize the execution environment. Use provisioned concurrency for latency-sensitive functions.' },
      { q: 'Can Lambda access my VPC resources?', a: 'Yes. Contact the platform team to enable VPC connectivity for your function. This adds ~1s to cold starts.' },
    ],
  },

  accessGuide: function(r, o, env, region, name, acct, endpoint) {
    return [
      {title:'Invoke the Function', commands:[
        {label:'Invoke with payload', code:'aws lambda invoke \\\n  --function-name '+(r.function_name||name)+' \\\n  --payload \'{"key":"value"}\' \\\n  --cli-binary-format raw-in-base64-out \\\n  --region '+region+' \\\n  --profile keystone-'+env+' \\\n  output.json && cat output.json'},
        {label:'Check function configuration', code:'aws lambda get-function-configuration \\\n  --function-name '+(r.function_name||name)+' \\\n  --region '+region}
      ]},
      {title:'View Logs', commands:[
        {label:'Tail live logs', code:'aws logs tail /aws/lambda/'+(r.function_name||name)+' --follow --profile keystone-'+env},
        {label:'Recent logs', code:'aws logs tail /aws/lambda/'+(r.function_name||name)+' --since 1h'}
      ]},
      {title:'Local Development with SAM', commands:[
        {label:'Install AWS SAM CLI', code:'brew install aws-sam-cli   # macOS\n# or: pip install aws-sam-cli'},
        {label:'Invoke locally', code:'sam local invoke '+(r.function_name||name)+' -e event.json'}
      ], notes:['If API Gateway is enabled, the invoke URL will be in deployment outputs.','Use SAM or the Serverless Framework for local iteration.']}
    ];
  },
},


// ═══════════════════════════════════════════════════════════════════════════
// DATA
// ═══════════════════════════════════════════════════════════════════════════

'rds-database': {
  name: 'RDS Database',
  icon: '\u{1F5C4}\uFE0F',
  category: 'Data',
  description: 'PostgreSQL/MySQL with Multi-AZ and encryption',

  fields: [
    {name:'db_name',label:'Database Name',type:'text',required:true,placeholder:'payments-db'},
    {name:'engine',label:'Engine',type:'select',options:['postgres','mysql']},
    {name:'engine_version',label:'Engine Version',type:'text',placeholder:'16.4'},
    {name:'instance_class',label:'Instance Class',type:'select',options:['db.t3.micro','db.t3.medium','db.r6g.large','db.r6g.xlarge','db.r6g.2xlarge']},
    {name:'allocated_storage',label:'Storage (GB)',type:'number',min:20,max:65536},
    {name:'multi_az',label:'Multi-AZ',type:'checkbox',desc:'High availability across availability zones'},
    {name:'backup_retention_days',label:'Backup Retention (days)',type:'number',min:1,max:35},
    {name:'deletion_protection',label:'Deletion Protection',type:'checkbox',desc:'Prevent accidental deletion'},
    {name:'existing_vpc_id',label:'Existing VPC ID',type:'text',desc:'Leave empty to create new',placeholder:'vpc-0abc123'},
  ],

  docs: {
    updated: '2026-04-15',
    overview: 'Amazon RDS provides managed relational databases. Keystone provisions RDS instances with encryption at rest (KMS), automated backups, Multi-AZ failover, performance monitoring, and security group configuration. Supports PostgreSQL and MySQL engines.',
    useCases: [
      'Application databases for web services and APIs',
      'Relational data storage requiring ACID compliance',
      'Data warehousing for structured analytics',
      'Legacy application migration from on-premises databases',
    ],
    prerequisites: [
      'An active AWS account with a VPC (request a VPC first if needed)',
      'Database schema design completed',
      'Estimated storage requirements known',
    ],
    howToProvision: [
      'Navigate to Service Catalog and click "RDS Database"',
      'Fill in common fields: Team, AWS Account, Environment',
      'Enter a Database Name and select the Engine (PostgreSQL recommended)',
      'Choose an Instance Class based on your workload',
      'Set Allocated Storage in GB',
      'Enable Multi-AZ for production environments',
      'Set Backup Retention period (7 days minimum for production)',
      'Enable Deletion Protection for production databases',
      'Click "Submit Request"',
      'After provisioning, connection details appear in the Deployment Outputs section',
    ],
    configOptions: [
      { param: 'db_name', desc: 'Logical database name. Used in connection strings.' },
      { param: 'engine', desc: 'PostgreSQL (recommended) or MySQL.' },
      { param: 'engine_version', desc: 'Engine version. Use latest stable (e.g., 16.4 for PostgreSQL).' },
      { param: 'instance_class', desc: 'Instance size. db.t3.medium for dev, db.r6g.large+ for production.' },
      { param: 'allocated_storage', desc: 'Storage in GB. Can be increased later (not decreased).' },
      { param: 'multi_az', desc: 'Enables a standby replica in another AZ. Required for production.' },
      { param: 'backup_retention_days', desc: 'Number of days to retain automated backups (1\u201335).' },
      { param: 'deletion_protection', desc: 'Prevents accidental deletion. Must be disabled manually before destroying.' },
    ],
    faqs: [
      { q: 'How do I connect to my database?', a: 'After deployment, find the endpoint in Deployment Outputs. Use the master username and retrieve the password from AWS Secrets Manager.' },
      { q: 'Can I restore from a backup?', a: 'Yes. Use the AWS Console to restore from an automated backup or manual snapshot to a new instance.' },
      { q: 'How do I scale up?', a: 'Submit a new request to change the instance class. RDS performs a rolling modification with brief downtime.' },
    ],
  },

  accessGuide: function(r, o, env, region, name, acct, endpoint) {
    return [
      {title:'Prerequisites', desc:'Install the PostgreSQL/MySQL client for your database engine.', commands:[
        {label:'PostgreSQL client (Ubuntu/Debian)', code:'sudo apt-get install postgresql-client'},
        {label:'PostgreSQL client (macOS)', code:'brew install libpq && brew link --force libpq'},
        {label:'MySQL client', code:'brew install mysql-client   # or: sudo apt-get install mysql-client'}
      ]},
      {title:'Set Up Port Forwarding (Private DB)', desc:'RDS instances in private subnets require a bastion or SSM tunnel.', commands:[
        {label:'SSM port forward through bastion', code:'aws ssm start-session \\\n  --target <bastion-instance-id> \\\n  --document-name AWS-StartPortForwardingSessionToRemoteHost \\\n  --parameters \'{"host":["'+(endpoint||name+'.cluster-xxxxx.'+region+'.rds.amazonaws.com')+'"],"portNumber":["'+(r.engine==='mysql'?'3306':'5432')+'"],"localPortNumber":["'+(r.engine==='mysql'?'3306':'5432')+'"]}\' \\\n  --profile keystone-'+env}
      ], notes:['You need the SSM Session Manager plugin installed.']},
      {title:'Connect to Database', commands:[
        {label:'PostgreSQL', code:'psql -h localhost -p 5432 -U '+(r.master_username||'admin')+' -d '+(r.database_name||name)},
        {label:'Or use a connection string', code:(r.engine==='mysql'?'mysql':'postgresql')+'://'+(r.master_username||'admin')+':****@localhost:'+(r.engine==='mysql'?'3306':'5432')+'/'+(r.database_name||name)}
      ]},
      {title:'IDE Integration', desc:'Connect from your IDE\'s database explorer.', commands:[
        {label:'VS Code \u2014 Install SQL Tools', code:'code --install-extension mtxr.sqltools\ncode --install-extension mtxr.sqltools-driver-pg   # PostgreSQL\ncode --install-extension mtxr.sqltools-driver-mysql # MySQL'}
      ], notes:['In SQLTools: Add Connection \u2192 use localhost + forwarded port.','For DataGrip / DBeaver: create a new data source using the same localhost + port.']}
    ];
  },
},

'documentdb-database': {
  name: 'DocumentDB',
  icon: '\u{1F4C4}',
  category: 'Data',
  description: 'MongoDB-compatible document database',

  fields: [
    {name:'cluster_name',label:'Cluster Name',type:'text',required:true,placeholder:'my-docdb'},
    {name:'engine_version',label:'Engine Version',type:'select',options:['4.0','5.0','6.0']},
    {name:'instance_class',label:'Instance Class',type:'select',options:['db.t3.medium','db.r6g.large','db.r6g.xlarge']},
    {name:'num_instances',label:'Instance Count',type:'number',min:1,max:16},
    {name:'master_username',label:'Master Username',type:'text',placeholder:'docdbadmin'},
    {name:'deletion_protection',label:'Deletion Protection',type:'checkbox'},
    {name:'backup_retention_days',label:'Backup Retention (days)',type:'number',min:1,max:35},
    {name:'existing_vpc_id',label:'Existing VPC ID',type:'text',desc:'Leave empty to create new',placeholder:'vpc-0abc123'},
  ],

  docs: {
    updated: '2026-04-15',
    overview: 'Amazon DocumentDB is a MongoDB-compatible document database. Keystone provisions DocumentDB clusters with encryption, automated backups, and configurable instance counts for read replicas.',
    useCases: [
      'Applications using MongoDB drivers that need a managed service',
      'Document-oriented data with flexible schemas',
      'Content management and catalog systems',
    ],
    prerequisites: [
      'An active AWS account with a VPC',
      'Application compatible with MongoDB 5.0 or 6.0 API',
    ],
    howToProvision: [
      'Navigate to Service Catalog and click "DocumentDB"',
      'Fill in common fields',
      'Enter Cluster Name and select Engine Version',
      'Choose Instance Class and Instance Count',
      'Enable Deletion Protection for production',
      'Click "Submit Request"',
    ],
    configOptions: [
      { param: 'cluster_name', desc: 'Name for the DocumentDB cluster.' },
      { param: 'engine_version', desc: 'MongoDB compatibility version: 5.0.0 or 6.0.0.' },
      { param: 'instance_class', desc: 'Instance size. db.r6g.large recommended for production.' },
      { param: 'instance_count', desc: 'Number of instances (1 primary + N-1 read replicas).' },
    ],
    faqs: [
      { q: 'Is it fully MongoDB compatible?', a: 'DocumentDB supports most MongoDB 5.0/6.0 APIs but not all features. Check the AWS compatibility matrix for your use case.' },
      { q: 'How do I connect?', a: 'Use the cluster endpoint from Deployment Outputs with your MongoDB driver. TLS is required by default.' },
    ],
  },

  accessGuide: function(r, o, env, region, name, acct, endpoint) {
    return [
      {title:'Install mongosh', commands:[
        {label:'macOS', code:'brew install mongosh'},
        {label:'Ubuntu', code:'sudo apt-get install -y mongodb-mongosh'}
      ]},
      {title:'Download TLS Certificate', desc:'DocumentDB requires TLS connections.', commands:[
        {code:'wget https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem'}
      ]},
      {title:'Port Forward & Connect', commands:[
        {label:'SSM tunnel', code:'aws ssm start-session \\\n  --target <bastion-instance-id> \\\n  --document-name AWS-StartPortForwardingSessionToRemoteHost \\\n  --parameters \'{"host":["'+(endpoint||name+'.cluster-xxxxx.'+region+'.docdb.amazonaws.com')+'"],"portNumber":["27017"],"localPortNumber":["27017"]}\' \\\n  --profile keystone-'+env},
        {label:'Connect with mongosh', code:'mongosh "mongodb://admin:****@localhost:27017/'+(r.database_name||name)+'?tls=true&tlsCAFile=global-bundle.pem&replicaSet=rs0&readPreference=secondaryPreferred&retryWrites=false"'}
      ]},
      {title:'IDE Integration', commands:[
        {label:'MongoDB for VS Code', code:'code --install-extension mongodb.mongodb-vscode'}
      ], notes:['In MongoDB VS Code extension: Add Connection \u2192 paste the connection string with localhost.']}
    ];
  },
},

'dynamodb': {
  name: 'DynamoDB',
  icon: '\u26A1',
  category: 'Data',
  description: 'Serverless NoSQL with auto-scaling',

  fields: [
    {name:'table_name',label:'Table Name',type:'text',required:true,placeholder:'my-table'},
    {name:'partition_key',label:'Partition Key',type:'text',required:true,placeholder:'pk'},
    {name:'partition_key_type',label:'Partition Key Type',type:'select',options:['S','N','B']},
    {name:'sort_key',label:'Sort Key',type:'text',placeholder:'sk'},
    {name:'sort_key_type',label:'Sort Key Type',type:'select',options:['S','N','B']},
    {name:'billing_mode',label:'Billing Mode',type:'select',options:['PAY_PER_REQUEST','PROVISIONED']},
    {name:'enable_streams',label:'Enable DynamoDB Streams',type:'checkbox',desc:'Stream changes for event processing'},
    {name:'enable_point_in_time_recovery',label:'Point-in-Time Recovery',type:'checkbox',desc:'Continuous backups for recovery'},
  ],

  docs: {
    updated: '2026-04-15',
    overview: 'Amazon DynamoDB is a serverless NoSQL key-value and document database. Keystone provisions DynamoDB tables with encryption, optional Point-in-Time Recovery, and configurable billing modes. Scales automatically to handle any traffic level.',
    useCases: [
      'High-throughput key-value lookups (session stores, caches)',
      'Serverless applications needing zero-maintenance storage',
      'Event sourcing and audit logs',
      'IoT data ingestion at scale',
    ],
    prerequisites: [
      'An active AWS account registered in Keystone',
      'Partition key and optional sort key designed for your access patterns',
    ],
    howToProvision: [
      'Navigate to Service Catalog and click "DynamoDB"',
      'Fill in common fields',
      'Enter Table Name and Partition Key (hash_key)',
      'Optionally set a Sort Key (range_key)',
      'Select Billing Mode (PAY_PER_REQUEST for most use cases)',
      'Enable Point-in-Time Recovery for production',
      'Click "Submit Request"',
    ],
    configOptions: [
      { param: 'table_name', desc: 'Name for the DynamoDB table.' },
      { param: 'hash_key', desc: 'Partition key attribute name. Choose based on your query patterns.' },
      { param: 'range_key', desc: 'Optional sort key for composite primary keys.' },
      { param: 'billing_mode', desc: 'PAY_PER_REQUEST (serverless, recommended) or PROVISIONED (predictable workloads).' },
      { param: 'enable_pitr', desc: 'Point-in-Time Recovery. Allows restoring to any second in the last 35 days.' },
    ],
    faqs: [
      { q: 'PAY_PER_REQUEST vs PROVISIONED?', a: 'PAY_PER_REQUEST scales automatically and you pay per operation. PROVISIONED is cheaper for steady, predictable workloads but requires capacity planning.' },
    ],
  },

  accessGuide: function(r, o, env, region, name, acct, endpoint) {
    return [
      {title:'CLI Access', commands:[
        {label:'Describe table', code:'aws dynamodb describe-table --table-name '+(r.table_name||name)+' --region '+region},
        {label:'Scan (first 10 items)', code:'aws dynamodb scan --table-name '+(r.table_name||name)+' --max-items 10 --region '+region},
        {label:'Put item', code:'aws dynamodb put-item \\\n  --table-name '+(r.table_name||name)+' \\\n  --item \'{"'+(r.partition_key||'id')+'":{"S":"test-1"}}\' \\\n  --region '+region}
      ]},
      {title:'SDK Access (Python)', commands:[
        {code:'import boto3\n\ntable = boto3.resource("dynamodb", region_name="'+region+'").Table("'+(r.table_name||name)+'")\n\n# Put item\ntable.put_item(Item={"'+(r.partition_key||'id')+'": "test-1", "data": "hello"})\n\n# Get item\nresp = table.get_item(Key={"'+(r.partition_key||'id')+'": "test-1"})\nprint(resp["Item"])'}
      ]},
      {title:'IDE / GUI Tools', commands:[
        {label:'NoSQL Workbench', code:'# Download: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/workbench.html'}
      ], notes:['Use AWS Toolkit in VS Code for visual DynamoDB browsing.','For local development, use DynamoDB Local: docker run -p 8000:8000 amazon/dynamodb-local']}
    ];
  },
},

's3-bucket': {
  name: 'S3 Bucket',
  icon: '\u{1FAA3}',
  category: 'Data',
  description: 'Object storage with encryption and lifecycle',

  fields: [
    {name:'bucket_name',label:'Bucket Name',type:'text',required:true,placeholder:'my-data-bucket'},
    {name:'versioning',label:'Enable Versioning',type:'checkbox'},
    {name:'enable_lifecycle',label:'Enable Lifecycle',type:'checkbox',desc:'Auto-transition to cheaper storage'},
    {name:'lifecycle_ia_days',label:'IA Transition (days)',type:'number',min:30,placeholder:'90'},
    {name:'lifecycle_glacier_days',label:'Glacier Transition (days)',type:'number',min:90,placeholder:'365'},
    {name:'enable_cloudfront',label:'Enable CloudFront CDN',type:'checkbox',desc:'Serve content via CloudFront'},
  ],

  docs: {
    updated: '2026-04-15',
    overview: 'Amazon S3 provides highly durable object storage. Keystone provisions S3 buckets with server-side encryption (KMS), versioning, lifecycle policies, and public access blocking. Used for data lakes, backups, static assets, and application storage.',
    useCases: [
      'Data lake storage for analytics and ML',
      'Application file uploads and media storage',
      'Terraform state backend and CI/CD artifact storage',
      'Log archival and compliance retention',
    ],
    prerequisites: [
      'An active AWS account registered in Keystone',
      'A globally unique bucket name planned',
    ],
    howToProvision: [
      'Navigate to Service Catalog and click "S3 Bucket"',
      'Fill in common fields',
      'Enter a Bucket Name (must be globally unique across all AWS)',
      'Enable Versioning to protect against accidental deletes',
      'Enable Lifecycle rules for automatic storage class transitions',
      'Block Public Access is enabled by default (strongly recommended)',
      'Click "Submit Request"',
    ],
    configOptions: [
      { param: 'bucket_name', desc: 'Globally unique bucket name. Convention: {team}-{purpose}-{env}.' },
      { param: 'versioning', desc: 'Enables object versioning. Required for compliance and backup use cases.' },
      { param: 'enable_lifecycle', desc: 'Auto-transitions objects to cheaper storage tiers (IA after 30d, Glacier after 90d).' },
      { param: 'block_public_access', desc: 'Blocks all public access. Should always be enabled unless hosting a public website.' },
    ],
    faqs: [
      { q: 'How do I share a bucket with another team?', a: 'Use the "Cross-Account Share" service to grant cross-account access with proper IAM permissions.' },
      { q: 'Can I host a static website?', a: 'Yes, but you must disable public access blocking and configure website hosting. Consider CloudFront for HTTPS.' },
    ],
  },

  accessGuide: function(r, o, env, region, name, acct, endpoint) {
    return [
      {title:'Configure AWS CLI', commands:[
        {label:'Set profile', code:'export AWS_PROFILE=keystone-'+env+'\nexport AWS_REGION='+region}
      ]},
      {title:'Basic Bucket Operations', commands:[
        {label:'List contents', code:'aws s3 ls s3://'+(r.bucket_name||name)+'/'},
        {label:'Upload a file', code:'aws s3 cp ./myfile.txt s3://'+(r.bucket_name||name)+'/prefix/'},
        {label:'Download a file', code:'aws s3 cp s3://'+(r.bucket_name||name)+'/prefix/myfile.txt ./'},
        {label:'Sync a directory', code:'aws s3 sync ./local-dir s3://'+(r.bucket_name||name)+'/prefix/'}
      ]},
      {title:'SDK Configuration (Python)', commands:[
        {code:'import boto3\n\ns3 = boto3.client("s3", region_name="'+region+'")\n\n# List objects\nresp = s3.list_objects_v2(Bucket="'+(r.bucket_name||name)+'")\nfor obj in resp.get("Contents", []):\n    print(obj["Key"])'}
      ]},
      {title:'IDE Integration', commands:[
        {label:'VS Code AWS Toolkit', code:'code --install-extension amazonwebservices.aws-toolkit-vscode'}
      ], notes:['Open AWS Explorer sidebar \u2192 S3 \u2192 browse and manage objects visually.']}
    ];
  },
},

'redis': {
  name: 'ElastiCache Redis',
  icon: '\u{1F534}',
  category: 'Data',
  description: 'In-memory cache with cluster mode',

  fields: [
    {name:'cluster_name',label:'Cluster Name',type:'text',required:true,placeholder:'my-cache'},
    {name:'node_type',label:'Node Type',type:'select',options:['cache.t3.micro','cache.t3.medium','cache.r7g.large','cache.r7g.xlarge']},
    {name:'num_nodes',label:'Number of Nodes',type:'number',min:1,max:6},
    {name:'engine_version',label:'Engine Version',type:'select',options:['7.0','7.1']},
    {name:'multi_az',label:'Multi-AZ',type:'checkbox',desc:'Automatic failover across AZs'},
    {name:'existing_vpc_id',label:'Existing VPC ID',type:'text',desc:'Leave empty to create new',placeholder:'vpc-0abc123'},
  ],

  docs: {
    updated: '2026-04-15',
    overview: 'Amazon ElastiCache Redis provides a managed in-memory data store. Keystone provisions Redis clusters with encryption in transit and at rest, automatic failover, and configurable node types.',
    useCases: [
      'Application caching (database query results, API responses)',
      'Session storage for web applications',
      'Real-time leaderboards and counters',
      'Pub/Sub messaging between services',
    ],
    prerequisites: [
      'An active AWS account with a VPC',
      'Application configured to use Redis protocol',
    ],
    howToProvision: [
      'Navigate to Service Catalog and click "ElastiCache Redis"',
      'Fill in common fields',
      'Enter Cluster Name, select Node Type',
      'Set Number of Nodes (1 for dev, 2+ for production HA)',
      'Click "Submit Request"',
    ],
    configOptions: [
      { param: 'cluster_name', desc: 'Name for the Redis cluster.' },
      { param: 'node_type', desc: 'Instance type. cache.t3.micro for dev, cache.r6g.large for production.' },
      { param: 'num_nodes', desc: 'Number of nodes. 2+ enables automatic failover.' },
      { param: 'engine_version', desc: 'Redis version. 7.0 recommended for latest features.' },
    ],
    faqs: [
      { q: 'Redis vs DynamoDB DAX?', a: 'Redis is general-purpose. DAX is specific to DynamoDB query caching. Use Redis for application-level caching.' },
    ],
  },

  accessGuide: function(r, o, env, region, name, acct, endpoint) {
    return [
      {title:'Install Redis CLI', commands:[
        {label:'macOS', code:'brew install redis'},
        {label:'Ubuntu/Debian', code:'sudo apt-get install redis-tools'}
      ]},
      {title:'Port Forward to Redis', desc:'ElastiCache runs in private subnets; use SSM tunnel.', commands:[
        {code:'aws ssm start-session \\\n  --target <bastion-instance-id> \\\n  --document-name AWS-StartPortForwardingSessionToRemoteHost \\\n  --parameters \'{"host":["'+(endpoint||name+'.xxxxx.'+region+'.cache.amazonaws.com')+'"],"portNumber":["6379"],"localPortNumber":["6379"]}\' \\\n  --profile keystone-'+env}
      ]},
      {title:'Connect', commands:[
        {label:'Redis CLI', code:'redis-cli -h localhost -p 6379'+(r.auth_token?' -a <auth-token>':'')},
        {label:'Quick test', code:'redis-cli -h localhost PING\n# Expected: PONG'}
      ]},
      {title:'Application Config', commands:[
        {code:'# Python (redis-py)\nimport redis\nr = redis.Redis(host="localhost", port=6379, decode_responses=True)\nr.set("key", "value")\nprint(r.get("key"))'}
      ], notes:['For production apps, use the actual ElastiCache endpoint, not localhost.','If TLS is enabled, add --tls to redis-cli and ssl=True in Python.']}
    ];
  },
},

'msk': {
  name: 'MSK (Kafka)',
  icon: '\u{1F4E8}',
  category: 'Data',
  description: 'Managed Kafka for event streaming',

  fields: [
    {name:'cluster_name',label:'Cluster Name',type:'text',required:true,placeholder:'events-kafka'},
    {name:'kafka_version',label:'Kafka Version',type:'select',options:['3.7.x.kraft','3.6.0','3.5.1']},
    {name:'broker_instance_type',label:'Broker Type',type:'select',options:['kafka.t3.small','kafka.m5.large','kafka.m7g.large','kafka.m5.xlarge']},
    {name:'number_of_brokers',label:'Number of Brokers',type:'number',min:3,max:30},
    {name:'storage_per_broker_gb',label:'Storage per Broker (GB)',type:'number',min:1,max:16384,placeholder:'100'},
    {name:'existing_vpc_id',label:'Existing VPC ID',type:'text',desc:'Leave empty to create new',placeholder:'vpc-0abc123'},
  ],

  docs: {
    updated: '2026-04-15',
    overview: 'Amazon MSK (Managed Streaming for Apache Kafka) provides fully managed Kafka clusters. Keystone provisions MSK with encryption, IAM authentication, and configurable broker counts. Used for event-driven architectures and real-time streaming.',
    useCases: [
      'Event streaming between microservices',
      'Real-time data pipelines and ETL',
      'Change data capture (CDC) from databases',
      'Log aggregation and metrics streaming',
    ],
    prerequisites: [
      'An active AWS account with a VPC',
      'Kafka topic design and partitioning strategy planned',
    ],
    howToProvision: [
      'Navigate to Service Catalog and click "MSK (Kafka)"',
      'Fill in common fields',
      'Enter Cluster Name and select Kafka Version',
      'Choose Broker Instance Type and Number of Brokers (minimum 2)',
      'Click "Submit Request"',
    ],
    configOptions: [
      { param: 'cluster_name', desc: 'Name for the MSK cluster.' },
      { param: 'kafka_version', desc: 'Apache Kafka version. 3.6.0+ recommended.' },
      { param: 'broker_instance_type', desc: 'Broker size. kafka.m5.large for most production workloads.' },
      { param: 'number_of_brokers', desc: 'Total brokers across AZs. Minimum 2, use 3+ for production.' },
    ],
    faqs: [
      { q: 'MSK vs SQS?', a: 'MSK (Kafka) is for high-throughput event streaming with replay capability. SQS is simpler for task queues and decoupling.' },
    ],
  },

  accessGuide: function(r, o, env, region, name, acct, endpoint) {
    return [
      {title:'Install Kafka CLI', commands:[
        {label:'Download Kafka binaries', code:'curl -O https://downloads.apache.org/kafka/3.7.0/kafka_2.13-3.7.0.tgz\ntar xzf kafka_2.13-3.7.0.tgz\nexport PATH=$PATH:$(pwd)/kafka_2.13-3.7.0/bin'}
      ]},
      {title:'Port Forward Bootstrap Server', commands:[
        {code:'aws ssm start-session \\\n  --target <bastion-instance-id> \\\n  --document-name AWS-StartPortForwardingSessionToRemoteHost \\\n  --parameters \'{"host":["'+(endpoint||'b-1.'+name+'.xxxxx.kafka.'+region+'.amazonaws.com')+'"],"portNumber":["9092"],"localPortNumber":["9092"]}\' \\\n  --profile keystone-'+env}
      ]},
      {title:'Produce & Consume Messages', commands:[
        {label:'List topics', code:'kafka-topics.sh --bootstrap-server localhost:9092 --list'},
        {label:'Create a topic', code:'kafka-topics.sh --bootstrap-server localhost:9092 --create --topic test-topic --partitions 3 --replication-factor 2'},
        {label:'Produce', code:'kafka-console-producer.sh --bootstrap-server localhost:9092 --topic test-topic'},
        {label:'Consume', code:'kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic test-topic --from-beginning'}
      ]},
      {title:'Application Config', commands:[
        {code:'# Python (confluent-kafka)\nfrom confluent_kafka import Producer, Consumer\n\nproducer = Producer({"bootstrap.servers": "localhost:9092"})\nproducer.produce("test-topic", value="hello")\nproducer.flush()'}
      ]}
    ];
  },
},

'iceberg-table': {
  name: 'Iceberg Data Lake',
  icon: '\u{1F9CA}',
  category: 'Data',
  description: 'Apache Iceberg table on Glue with S3',

  fields: [
    {name:'database_name',label:'Glue Database Name',type:'text',required:true,placeholder:'data_lake'},
    {name:'table_name',label:'Table Name',type:'text',required:true,placeholder:'events_raw'},
    {name:'s3_bucket_name',label:'Existing S3 Bucket',type:'text',desc:'Leave empty to auto-create',placeholder:'my-datalake-bucket'},
    {name:'file_format',label:'File Format',type:'select',options:['parquet','orc','avro']},
    {name:'compression',label:'Compression',type:'select',options:['snappy','gzip','zstd','lz4']},
    {name:'partition_columns',label:'Partition Columns',type:'text',desc:'Comma-separated column names',placeholder:'year,month,day'},
  ],

  docs: {
    updated: '2026-04-15',
    overview: 'Apache Iceberg provides an open table format for huge analytic datasets. Keystone provisions Iceberg tables on AWS Glue Data Catalog with S3 storage, KMS encryption, and support for time-travel queries. Ideal for data lakes that need ACID transactions.',
    useCases: [
      'Data lake tables with ACID transactions and schema evolution',
      'Time-travel queries for regulatory compliance',
      'Replacing legacy Hive tables with better performance',
      'CDC (Change Data Capture) sinks for streaming data',
    ],
    prerequisites: [
      'An active AWS account registered in Keystone',
      'A data lake strategy and naming convention agreed upon',
      'An existing S3 bucket (or let Keystone create one)',
    ],
    howToProvision: [
      'Navigate to Service Catalog and click "Iceberg Data Lake"',
      'Fill in common fields',
      'Enter Database Name (Glue catalog database)',
      'Enter Table Name',
      'Optionally specify an existing S3 bucket (auto-created if empty)',
      'Select File Format (Parquet recommended) and Compression (Snappy for speed, Zstd for size)',
      'Click "Submit Request"',
    ],
    configOptions: [
      { param: 'database_name', desc: 'Glue catalog database name. Groups related tables.' },
      { param: 'table_name', desc: 'Name of the Iceberg table.' },
      { param: 's3_bucket_name', desc: 'Existing S3 bucket for data files. Auto-created if empty.' },
      { param: 'file_format', desc: 'Data file format: Parquet (recommended), ORC, or Avro.' },
      { param: 'compression', desc: 'Compression codec: Snappy (fast), Gzip, Zstd (balanced), LZ4.' },
    ],
    faqs: [
      { q: 'How do I query Iceberg tables?', a: 'Use Amazon Athena with: SELECT * FROM "database_name"."table_name". Athena natively supports Iceberg.' },
      { q: 'Can I do time-travel?', a: 'Yes: SELECT * FROM table FOR TIMESTAMP AS OF TIMESTAMP \'2026-01-01 00:00:00\'.' },
    ],
  },

  accessGuide: function(r, o, env, region, name, acct, endpoint) {
    return [
      {title:'Query with Athena', commands:[
        {code:'aws athena start-query-execution \\\n  --query-string "SELECT * FROM '+(r.database_name||'keystone_db')+'.'+(r.table_name||name)+' LIMIT 10" \\\n  --work-group primary \\\n  --region '+region}
      ]},
      {title:'Spark / PySpark Access', commands:[
        {code:'from pyspark.sql import SparkSession\n\nspark = SparkSession.builder \\\n    .config("spark.sql.catalog.glue", "org.apache.iceberg.spark.SparkCatalog") \\\n    .config("spark.sql.catalog.glue.catalog-impl", "org.apache.iceberg.aws.glue.GlueCatalog") \\\n    .config("spark.sql.catalog.glue.warehouse", "'+(o.s3_location||'s3://'+name+'-warehouse/')+'") \\\n    .getOrCreate()\n\ndf = spark.read.table("glue.'+(r.database_name||'keystone_db')+'.'+(r.table_name||name)+'")\ndf.show()'}
      ]},
      {title:'Table Maintenance', commands:[
        {code:'-- Run in Athena / Spark SQL:\nCALL glue.'+(r.database_name||'keystone_db')+'.system.rewrite_data_files(table => "'+(r.table_name||name)+'")\nCALL glue.'+(r.database_name||'keystone_db')+'.system.expire_snapshots(table => "'+(r.table_name||name)+'", older_than => TIMESTAMP \'2024-01-01 00:00:00\')'}
      ]}
    ];
  },
},

'vector-store': {
  name: 'Vector Store',
  icon: '\u{1F9E0}',
  category: 'Data',
  description: 'pgvector or OpenSearch for embeddings',

  fields: [
    {name:'store_name',label:'Store Name',type:'text',required:true,placeholder:'embeddings-store'},
    {name:'engine',label:'Engine',type:'select',options:['pgvector','opensearch-serverless']},
    {name:'dimensions',label:'Vector Dimensions',type:'number',min:1,max:16000,placeholder:'1536'},
    {name:'distance_metric',label:'Distance Metric',type:'select',options:['cosine','euclidean','inner_product']},
    {name:'instance_class',label:'Instance Class',type:'select',desc:'pgvector only',options:['db.r6g.large','db.r6g.xlarge','db.r6g.2xlarge']},
    {name:'existing_vpc_id',label:'Existing VPC ID',type:'text',desc:'Leave empty to create new',placeholder:'vpc-0abc123'},
  ],

  docs: {
    updated: '2026-04-15',
    overview: 'Vector Store provides a managed vector database for storing and searching embeddings. Keystone supports two engines: pgvector (PostgreSQL extension) for simplicity, and OpenSearch for large-scale similarity search. Essential for AI/ML applications using RAG (Retrieval-Augmented Generation).',
    useCases: [
      'Semantic search over documents and knowledge bases',
      'RAG (Retrieval-Augmented Generation) for LLM applications',
      'Image and audio similarity search',
      'Recommendation engines based on embedding similarity',
    ],
    prerequisites: [
      'An active AWS account registered in Keystone',
      'Embedding model chosen (e.g., OpenAI ada-002 = 1536 dimensions)',
      'Understanding of vector dimensions and distance metrics',
    ],
    howToProvision: [
      'Navigate to Service Catalog and click "Vector Store"',
      'Fill in common fields',
      'Enter Store Name and select Engine (pgvector or OpenSearch)',
      'Set Vector Dimensions to match your embedding model',
      'Choose Distance Metric (cosine for text, L2 for images)',
      'Click "Submit Request"',
    ],
    configOptions: [
      { param: 'store_name', desc: 'Name for the vector store.' },
      { param: 'engine', desc: 'pgvector (simpler, lower cost) or OpenSearch (higher scale, more features).' },
      { param: 'dimensions', desc: 'Vector dimensions. Must match your embedding model (e.g., 1536 for OpenAI ada-002).' },
      { param: 'distance_metric', desc: 'cosine (text similarity), L2 (euclidean), inner_product (dot product).' },
    ],
    faqs: [
      { q: 'pgvector vs OpenSearch?', a: 'pgvector is great for <1M vectors and simple use cases. OpenSearch handles billions of vectors with k-NN search at scale.' },
      { q: 'How do I index embeddings?', a: 'For pgvector, use standard SQL INSERT. For OpenSearch, use the bulk API. Both support Python SDKs.' },
    ],
  },

  accessGuide: function(r, o, env, region, name, acct, endpoint) {
    return [
      {title:'Connect to OpenSearch Serverless', commands:[
        {code:'# Install opensearch-py\npip install opensearch-py requests-aws4auth\n\nfrom opensearchpy import OpenSearch, RequestsHttpConnection\nfrom requests_aws4auth import AWS4Auth\nimport boto3\n\ncreds = boto3.Session().get_credentials()\nauth = AWS4Auth(creds.access_key, creds.secret_key, "'+region+'", "aoss", session_token=creds.token)\n\nclient = OpenSearch(\n    hosts=[{"host": "'+(endpoint||name+'.'+region+'.aoss.amazonaws.com')+'", "port": 443}],\n    http_auth=auth, use_ssl=True, verify_certs=True,\n    connection_class=RequestsHttpConnection\n)\n\n# Index a vector document\nclient.index(index="'+(r.collection_name||name)+'", body={"embedding": [0.1, 0.2, ...], "text": "hello"})'}
      ]},
      {title:'Similarity Search', commands:[
        {code:'resp = client.search(index="'+(r.collection_name||name)+'", body={\n    "query": {"knn": {"embedding": {"vector": [0.1, 0.2, ...], "k": 5}}}\n})\nfor hit in resp["hits"]["hits"]:\n    print(hit["_source"]["text"], hit["_score"])'}
      ]}
    ];
  },
},

'lake-formation': {
  name: 'Lake Formation',
  icon: '\u{1F3E0}',
  category: 'Data',
  description: 'Data governance with LF-tags',

  fields: [
    {name:'data_lake_name',label:'Data Lake Name',type:'text',required:true,placeholder:'enterprise-lake'},
    {name:'admin_arn',label:'Admin IAM ARN',type:'text',required:true,placeholder:'arn:aws:iam::123456789012:role/LakeFormationAdmin'},
    {name:'s3_locations',label:'S3 Location ARNs',type:'text',required:true,desc:'Comma-separated S3 bucket ARNs',placeholder:'arn:aws:s3:::my-bucket'},
    {name:'catalog_id',label:'Glue Catalog ID',type:'text',desc:'Defaults to account ID if empty'},
  ],

  docs: {
    updated: '2026-04-15',
    overview: 'AWS Lake Formation provides centralized data governance for your data lake. Keystone provisions Lake Formation with LF-tag based access control, data catalog configuration, and admin role setup.',
    useCases: [
      'Centralizing data access governance across teams',
      'Column-level and row-level security for shared datasets',
      'Compliance with data access audit requirements',
    ],
    prerequisites: [
      'An active AWS account registered in Keystone',
      'Data lake architecture designed',
      'Data steward / admin identified',
    ],
    howToProvision: [
      'Navigate to Service Catalog and click "Lake Formation"',
      'Fill in common fields',
      'Enter Data Lake Name and Admin ARN',
      'Click "Submit Request"',
    ],
    configOptions: [
      { param: 'data_lake_name', desc: 'Identifier for this Lake Formation configuration.' },
      { param: 'admin_arn', desc: 'IAM ARN of the data lake administrator role.' },
    ],
    faqs: [
      { q: 'What are LF-tags?', a: 'Lake Formation tags are key-value labels applied to databases, tables, and columns. Access policies reference tags instead of individual resources.' },
    ],
  },

  accessGuide: function(r, o, env, region, name, acct, endpoint) {
    return [
      {title:'Check Permissions', commands:[
        {code:'aws lakeformation list-permissions \\\n  --principal \'{"DataLakePrincipalIdentifier":"arn:aws:iam::'+acct+':role/'+(r.principal_arn||'my-role')+'"}\' \\\n  --region '+region}
      ]},
      {title:'Verify Data Access', commands:[
        {code:'# Query the granted tables via Athena:\naws athena start-query-execution \\\n  --query-string "SELECT * FROM '+(r.database_name||'database')+'.'+(r.table_name||'table')+' LIMIT 5" \\\n  --work-group primary --region '+region}
      ], notes:['Lake Formation permissions may take a few minutes to propagate.']}
    ];
  },
},

'data-access': {
  name: 'Data Access',
  icon: '\u{1F511}',
  category: 'Data',
  description: 'IAM roles for least-privilege data access',

  fields: [
    {name:'access_name',label:'Access Name',type:'text',required:true,placeholder:'etl-reader'},
    {name:'target_resource_type',label:'Resource Type',type:'select',options:['s3','rds','dynamodb','msk','documentdb','glue','redshift']},
    {name:'target_resource_arn',label:'Resource ARN',type:'text',required:true,placeholder:'arn:aws:s3:::my-bucket'},
    {name:'principal_arns',label:'Principal ARNs',type:'text',required:true,desc:'Comma-separated IAM ARNs to grant access',placeholder:'arn:aws:iam::123456789012:role/MyRole'},
    {name:'access_level',label:'Access Level',type:'select',options:['readonly','readwrite','admin']},
    {name:'enable_cross_account',label:'Cross-Account Access',type:'checkbox',desc:'Enable cross-account trust relationship'},
  ],

  docs: {
    updated: '2026-04-15',
    overview: 'Data Access provisions least-privilege IAM roles for accessing data resources. Keystone creates IAM roles with scoped policies targeting specific S3 buckets, RDS instances, DynamoDB tables, or other data stores.',
    useCases: [
      'Granting an ETL pipeline read access to a specific S3 bucket',
      'Allowing a microservice to read/write a DynamoDB table',
      'Cross-service data access with audit trails',
    ],
    prerequisites: [
      'The target data resource must already be provisioned',
      'Know the resource ARN and required access level',
    ],
    howToProvision: [
      'Navigate to Service Catalog and click "Data Access"',
      'Fill in common fields',
      'Enter Access Name and select Target Resource Type',
      'Provide the Target Resource ARN',
      'Select Access Level (readonly, readwrite, or admin)',
      'Click "Submit Request"',
    ],
    configOptions: [
      { param: 'access_name', desc: 'Descriptive name for this access grant.' },
      { param: 'target_resource_type', desc: 'Type of resource: S3, RDS, DynamoDB, MSK, DocumentDB, Glue, or Redshift.' },
      { param: 'target_resource_arn', desc: 'Full ARN of the target resource.' },
      { param: 'access_level', desc: 'readonly (read/list), readwrite (read/write/delete), admin (full control).' },
    ],
    faqs: [
      { q: 'How is this different from regular IAM?', a: 'Keystone generates scoped IAM roles following least-privilege. You get a role ARN your service assumes, with only the exact permissions needed.' },
    ],
  },

  accessGuide: function(r, o, env, region, name, acct, endpoint) {
    return [
      {title:'Verify Access Grant', commands:[
        {code:'aws lakeformation list-permissions \\\n  --resource \'{"Table":{"DatabaseName":"'+(r.database_name||'db')+'","Name":"'+(r.table_name||'table')+'"}}\' \\\n  --region '+region}
      ]},
      {title:'Query Data', commands:[
        {code:'# Use Athena to query the granted data:\naws athena start-query-execution \\\n  --query-string "SELECT * FROM '+(r.database_name||'db')+'.'+(r.table_name||'table')+' LIMIT 10" \\\n  --work-group primary --region '+region}
      ]}
    ];
  },
},

'data-classification': {
  name: 'Data Classification',
  icon: '\u{1F50D}',
  category: 'Data',
  description: 'Macie PII/sensitive data scanning',

  fields: [
    {name:'classification_name',label:'Classification Job Name',type:'text',required:true,placeholder:'pii-scan-prod'},
    {name:'target_bucket_arns',label:'Target S3 Bucket ARNs',type:'text',required:true,desc:'Comma-separated bucket ARNs to classify',placeholder:'arn:aws:s3:::my-data-bucket'},
    {name:'sensitivity_level',label:'Sensitivity Level',type:'select',options:['public','internal','confidential','restricted']},
    {name:'enable_pii_detection',label:'Enable PII Detection',type:'checkbox',desc:'Detect SSN, credit cards, etc.'},
    {name:'schedule_frequency',label:'Scan Frequency',type:'select',options:['daily','weekly','monthly']},
    {name:'notification_email',label:'Findings Email',type:'text',placeholder:'security-team@company.com'},
  ],

  docs: {
    updated: '2026-04-15',
    overview: 'Data Classification provisions Amazon Macie jobs for PII and sensitive data scanning. Keystone configures automated scanning schedules, sensitivity classifications, and notification routing for findings.',
    useCases: [
      'Scanning S3 buckets for PII (names, emails, SSNs, credit cards)',
      'Compliance with GDPR, HIPAA, or PCI-DSS data handling requirements',
      'Preventing sensitive data from being stored in unencrypted locations',
    ],
    prerequisites: [
      'An active AWS account registered in Keystone',
      'S3 buckets to scan already provisioned',
    ],
    howToProvision: [
      'Navigate to Service Catalog and click "Data Classification"',
      'Fill in common fields',
      'Enter a Classification Name and select Sensitivity Level',
      'Enable PII Detection if needed',
      'Provide a Notification Email for scan results',
      'Click "Submit Request"',
    ],
    configOptions: [
      { param: 'classification_name', desc: 'Name for this classification configuration.' },
      { param: 'sensitivity_level', desc: 'Data sensitivity: low, medium, high, or critical.' },
      { param: 'enable_pii_detection', desc: 'Enables Amazon Macie PII detection jobs.' },
      { param: 'notification_email', desc: 'Email address to receive classification findings.' },
    ],
    faqs: [
      { q: 'How often does Macie scan?', a: 'By default, Macie runs daily scans. You can configure the schedule via the AWS Console after provisioning.' },
    ],
  },

  accessGuide: function(r, o, env, region, name, acct, endpoint) {
    return [
      {title:'View Classification Results', commands:[
        {code:'aws macie2 list-findings \\\n  --finding-criteria \'{"criterion":{"resourcesAffected.s3Bucket.name":{"eq":["'+(r.s3_path||name)+'"]}}}\' \\\n  --region '+region}
      ]},
      {title:'Check Glue Data Quality', commands:[
        {code:'aws glue get-data-quality-result \\\n  --result-id '+(o.quality_run_id||'<result-id>')+' \\\n  --region '+region}
      ], notes:['Classified data is tagged in the Glue Data Catalog. View tags in Lake Formation console.']}
    ];
  },
},

'cross-account-share': {
  name: 'Cross-Account Share',
  icon: '\u{1F91D}',
  category: 'Data',
  description: 'RAM + KMS cross-account sharing',

  fields: [
    {name:'share_name',label:'Share Name',type:'text',required:true,placeholder:'shared-data'},
    {name:'resource_arns',label:'Resource ARNs',type:'text',required:true,desc:'Comma-separated ARNs to share',placeholder:'arn:aws:s3:::shared-bucket'},
    {name:'target_account_ids',label:'Target Account IDs',type:'text',required:true,desc:'Comma-separated 12-digit account IDs',placeholder:'111222333444,555666777888'},
    {name:'permission_type',label:'Permission Type',type:'select',options:['readonly','readwrite']},
    {name:'enable_external_sharing',label:'External Sharing',type:'checkbox',desc:'Allow sharing outside Organization'},
  ],

  docs: {
    updated: '2026-04-15',
    overview: 'Cross-Account Share provisions AWS RAM (Resource Access Manager) shares with KMS key policies for secure cross-account resource sharing. Allows teams to share data resources across AWS accounts without copying data.',
    useCases: [
      'Sharing an S3 bucket with a data analytics team in a different account',
      'Granting cross-account access to RDS snapshots',
      'Sharing Glue Data Catalog databases across accounts for unified analytics',
    ],
    prerequisites: [
      'Both source and target AWS accounts registered in Keystone',
      'Resources to share already provisioned',
    ],
    howToProvision: [
      'Navigate to Service Catalog and click "Cross-Account Share"',
      'Fill in common fields',
      'Enter a Share Name and select Permission Type',
      'Choose whether to enable External Sharing (outside your org)',
      'Click "Submit Request"',
    ],
    configOptions: [
      { param: 'share_name', desc: 'Descriptive name for this sharing configuration.' },
      { param: 'permission_type', desc: 'readonly or readwrite access for the target account.' },
      { param: 'enable_external_sharing', desc: 'Allow sharing with AWS accounts outside your Organization.' },
    ],
    faqs: [
      { q: 'Is data copied to the other account?', a: 'No. RAM shares grant access to the original resource. No data is duplicated.' },
    ],
  },

  accessGuide: function(r, o, env, region, name, acct, endpoint) {
    return [
      {title:'Verify Share in Target Account', commands:[
        {code:'# In the target account:\naws ram get-resource-share-invitations --region '+region+'\n\n# Accept if pending:\naws ram accept-resource-share-invitation \\\n  --resource-share-invitation-arn <arn-from-above> \\\n  --region '+region}
      ]},
      {title:'Access Shared Resources', commands:[
        {code:'# List shared resources:\naws ram list-resources \\\n  --resource-owner OTHER-ACCOUNTS \\\n  --region '+region}
      ], notes:['Shared Lake Formation tables will appear in Glue Data Catalog of the target account.','Target account must accept the RAM invitation before resources are accessible.']}
    ];
  },
},


// ═══════════════════════════════════════════════════════════════════════════
// NETWORKING
// ═══════════════════════════════════════════════════════════════════════════

'vpc': {
  name: 'VPC Network',
  icon: '\u{1F310}',
  category: 'Networking',
  description: 'VPC with public/private subnets and NAT',

  fields: [
    {name:'vpc_name',label:'VPC Name',type:'text',required:true,placeholder:'main-vpc'},
    {name:'vpc_cidr',label:'CIDR Block',type:'text',placeholder:'10.0.0.0/16'},
    {name:'enable_nat_gateway',label:'NAT Gateway',type:'checkbox',desc:'Enable outbound internet from private subnets'},
    {name:'single_nat_gateway',label:'Single NAT Gateway',type:'checkbox',desc:'Use one NAT for all AZs (cheaper, less resilient)'},
    {name:'enable_vpn_gateway',label:'VPN Gateway',type:'checkbox',desc:'Attach a Virtual Private Gateway'},
  ],

  docs: {
    updated: '2026-04-15',
    overview: 'Amazon VPC (Virtual Private Cloud) provides an isolated network in AWS. Keystone provisions VPCs with public and private subnets across multiple Availability Zones, NAT Gateways for outbound internet access, and optional VPC Flow Logs for network monitoring.',
    useCases: [
      'Network foundation for EKS clusters, RDS databases, and other resources',
      'Network isolation between environments (dev, staging, prod)',
      'Compliance requirements for private network architecture',
    ],
    prerequisites: [
      'An active AWS account registered in Keystone',
      'A CIDR range planned that does not conflict with other VPCs or on-premises networks',
    ],
    howToProvision: [
      'Navigate to Service Catalog and click "VPC Network"',
      'Fill in common fields',
      'Enter a VPC Name and CIDR Block (e.g., 10.0.0.0/16)',
      'Enable NAT Gateway for private subnet internet access',
      'Enable VPC Flow Logs for network monitoring',
      'Click "Submit Request"',
    ],
    configOptions: [
      { param: 'vpc_name', desc: 'Name for the VPC. Used in resource tags.' },
      { param: 'vpc_cidr', desc: 'CIDR block (e.g., 10.0.0.0/16). Provides 65,536 IP addresses.' },
      { param: 'enable_nat_gateway', desc: 'NAT Gateway for private subnets to access the internet. Required for most workloads.' },
      { param: 'enable_flow_logs', desc: 'Captures network traffic metadata to CloudWatch Logs.' },
    ],
    faqs: [
      { q: 'How many subnets are created?', a: 'Keystone creates 3 public and 3 private subnets across 3 AZs.' },
      { q: 'Can I peer VPCs?', a: 'Yes. Contact the platform team to set up VPC peering after provisioning.' },
    ],
  },

  accessGuide: function(r, o, env, region, name, acct, endpoint) {
    return [
      {title:'Inspect VPC', commands:[
        {label:'Describe VPC', code:'aws ec2 describe-vpcs \\\n  --filters "Name=tag:Name,Values='+name+'" \\\n  --region '+region+' --profile keystone-'+env},
        {label:'List subnets', code:'aws ec2 describe-subnets \\\n  --filters "Name=vpc-id,Values='+(o.vpc_id||'<vpc-id>')+'" \\\n  --query "Subnets[].{ID:SubnetId,AZ:AvailabilityZone,CIDR:CidrBlock,Public:MapPublicIpOnLaunch}" \\\n  --output table --region '+region},
        {label:'List security groups', code:'aws ec2 describe-security-groups \\\n  --filters "Name=vpc-id,Values='+(o.vpc_id||'<vpc-id>')+'" \\\n  --output table --region '+region}
      ]},
      {title:'VPN / Peering Check', commands:[
        {code:'aws ec2 describe-vpc-peering-connections \\\n  --filters "Name=requester-vpc-info.vpc-id,Values='+(o.vpc_id||'<vpc-id>')+'" \\\n  --region '+region}
      ], notes:['Use the VPC ID from deployment outputs above to query subnets, routes, and NAT gateways.']}
    ];
  },
},

'route53': {
  name: 'Route53 DNS',
  icon: '\u{1F517}',
  category: 'Networking',
  description: 'DNS hosted zones with health checks',

  fields: [
    {name:'domain_name',label:'Domain Name',type:'text',required:true,placeholder:'api.example.com'},
    {name:'private_zone',label:'Private Zone',type:'checkbox',desc:'Internal DNS only (requires VPC)'},
    {name:'existing_vpc_id',label:'VPC ID',type:'text',desc:'Required for private zones',placeholder:'vpc-0abc123'},
  ],

  docs: {
    updated: '2026-04-15',
    overview: 'Amazon Route53 provides DNS management. Keystone provisions hosted zones with health checks, supporting both public (internet-facing) and private (VPC-internal) DNS zones.',
    useCases: [
      'Custom domain names for services (api.myteam.example.com)',
      'Service discovery within a VPC using private DNS',
      'DNS failover with health checks',
    ],
    prerequisites: [
      'An active AWS account registered in Keystone',
      'Domain name registered or delegated',
    ],
    howToProvision: [
      'Navigate to Service Catalog and click "Route53 DNS"',
      'Fill in common fields',
      'Enter Domain Name and select Zone Type (public or private)',
      'Click "Submit Request"',
    ],
    configOptions: [
      { param: 'domain_name', desc: 'The DNS domain name for the hosted zone.' },
      { param: 'zone_type', desc: 'public (internet-resolvable) or private (VPC-only).' },
    ],
    faqs: [
      { q: 'How do I add DNS records?', a: 'After provisioning, add records via the AWS Console or Terraform. Keystone creates the hosted zone; you manage records within it.' },
    ],
  },

  accessGuide: function(r, o, env, region, name, acct, endpoint) {
    return [
      {title:'Manage DNS Records', commands:[
        {label:'List hosted zones', code:'aws route53 list-hosted-zones --profile keystone-'+env},
        {label:'List records', code:'aws route53 list-resource-record-sets \\\n  --hosted-zone-id '+(o.zone_id||'<zone-id-from-outputs>')+' \\\n  --profile keystone-'+env}
      ]},
      {title:'Add a DNS Record', commands:[
        {code:'aws route53 change-resource-record-sets \\\n  --hosted-zone-id '+(o.zone_id||'<zone-id>')+' \\\n  --change-batch \'{\n  "Changes": [{\n    "Action": "UPSERT",\n    "ResourceRecordSet": {\n      "Name": "app.'+(r.zone_name||name)+'",\n      "Type": "A",\n      "TTL": 300,\n      "ResourceRecords": [{"Value": "1.2.3.4"}]\n    }\n  }]\n}\''}
      ]},
      {title:'Verify DNS', commands:[
        {code:'dig app.'+(r.zone_name||name)+' +short\nnslookup app.'+(r.zone_name||name)}
      ]}
    ];
  },
},


// ═══════════════════════════════════════════════════════════════════════════
// ONBOARDING
// ═══════════════════════════════════════════════════════════════════════════

'aws-account': {
  name: 'AWS Account',
  icon: '\u{1F3E2}',
  category: 'Onboarding',
  description: 'New AWS account with SSO and OIDC',

  fields: [
    {name:'team_display_name',label:'Team Display Name',type:'text',required:true,placeholder:'ML Platform Team'},
    {name:'product_owner_email',label:'Product Owner Email',type:'text',required:true,placeholder:'po@company.com'},
    {name:'business_unit',label:'Business Unit',type:'text',placeholder:'Engineering'},
    {name:'ou_path',label:'Organization Unit',type:'select',options:['Workloads','Sandbox','Security','Shared-Services']},
    {name:'enable_vpc',label:'Create Default VPC',type:'checkbox',desc:'Provision a VPC in the new account'},
    {name:'vpc_cidr',label:'VPC CIDR',type:'text',desc:'CIDR for the default VPC',placeholder:'10.0.0.0/16'},
    {name:'enable_guardduty',label:'Enable GuardDuty',type:'checkbox',desc:'Threat detection for the account'},
    {name:'enable_cloudtrail',label:'Enable CloudTrail',type:'checkbox',desc:'API audit logging'},
  ],

  docs: {
    updated: '2026-04-15',
    overview: 'AWS Account provisions a new AWS account within the organization. Keystone sets up SSO access, OIDC federation for CI/CD, a Terraform state bucket, and baseline security controls (GuardDuty, Config, CloudTrail).',
    useCases: [
      'Onboarding a new team to the platform',
      'Environment isolation (separate accounts for dev, staging, prod)',
      'Compliance requirements for account-level resource boundaries',
    ],
    prerequisites: [
      'Management approval for a new AWS account',
      'Product owner identified',
      'Budget and cost center allocated',
    ],
    howToProvision: [
      'Navigate to Service Catalog and click "AWS Account"',
      'Fill in common fields',
      'Enter Account Name and Product Owner Email',
      'Specify Business Unit',
      'Click "Submit Request"',
      'Account provisioning takes 5-10 minutes',
      'SSO access is automatically configured for the product owner',
    ],
    configOptions: [
      { param: 'account_name', desc: 'Name for the new AWS account (e.g., ml-platform-prod).' },
      { param: 'product_owner_email', desc: 'Email of the account owner. Gets SSO admin access.' },
      { param: 'business_unit', desc: 'Organizational unit for billing and governance.' },
    ],
    faqs: [
      { q: 'How long does account creation take?', a: 'The AWS account is created within 5 minutes. Full provisioning (SSO, OIDC, baseline) takes 10-15 minutes.' },
      { q: 'Can I delete an account?', a: 'Account closure requires management approval and a 90-day waiting period per AWS policy.' },
    ],
  },

  accessGuide: function(r, o, env, region, name, acct, endpoint) {
    return [
      {title:'Assume Role into New Account', commands:[
        {code:'aws sts assume-role \\\n  --role-arn arn:aws:iam::'+acct+':role/OrganizationAccountAccessRole \\\n  --role-session-name keystone-session \\\n  --profile keystone-management'}
      ]},
      {title:'Configure Named Profile', commands:[
        {code:'# Add to ~/.aws/config:\n[profile keystone-'+(r.account_name||name)+']\nrole_arn = arn:aws:iam::'+acct+':role/OrganizationAccountAccessRole\nsource_profile = keystone-management\nregion = '+region}
      ]},
      {title:'Verify Access', commands:[
        {code:'aws sts get-caller-identity --profile keystone-'+(r.account_name||name)+'\naws s3 ls --profile keystone-'+(r.account_name||name)}
      ], notes:['The account is managed under the '+(r.ou_path||'Workloads')+' OU.','GuardDuty and CloudTrail are enabled by default.']}
    ];
  },
},

'sre-onboarding': {
  name: 'SRE Onboarding',
  icon: '\u{1F52D}',
  category: 'Onboarding',
  description: 'Observability with Prometheus, Grafana, SLOs',
  clusterDependent: true,

  fields: [
    {name:'cluster_name',label:'EKS Cluster Name',type:'text',required:true,placeholder:'payments-eks-prod'},
    {name:'cluster_endpoint',label:'Cluster Endpoint',type:'text',desc:'Auto-discovered if empty',placeholder:'https://ABC123.gr7.us-east-1.eks.amazonaws.com'},
    {name:'team_vpc_id',label:'Team VPC ID',type:'text',required:true,placeholder:'vpc-0abc123def456'},
    {name:'team_vpc_cidr',label:'Team VPC CIDR',type:'text',placeholder:'10.1.0.0/16'},
    {name:'central_monitoring_vpc_id',label:'Central Monitoring VPC ID',type:'text',required:true,placeholder:'vpc-0mon123central'},
    {name:'central_monitoring_vpc_cidr',label:'Central Monitoring VPC CIDR',type:'text',placeholder:'10.0.0.0/16'},
    {name:'central_monitoring_account_id',label:'Central Monitoring Account ID',type:'text',desc:'Same account if empty',placeholder:'999888777666'},
    {name:'prometheus_remote_write_url',label:'Prometheus Remote Write URL',type:'text',required:true,desc:'AMP or Mimir endpoint',placeholder:'https://aps-workspaces.us-east-1.amazonaws.com/workspaces/ws-xxx/api/v1/remote_write'},
    {name:'scrape_interval',label:'Scrape Interval',type:'select',options:['15s','30s','60s']},
    {name:'metrics_retention_hours',label:'Local Metrics Retention (hours)',type:'number',min:1,max:24,placeholder:'2'},
    {name:'enable_otel_collector',label:'Enable OpenTelemetry Collector',type:'checkbox',desc:'Collect traces and logs via OTel'},
    {name:'enable_tracing',label:'Enable Distributed Tracing',type:'checkbox',desc:'Send traces to X-Ray / Tempo'},
    {name:'tracing_endpoint',label:'Tracing Endpoint',type:'text',desc:'Required if tracing enabled',placeholder:'https://xray.us-east-1.amazonaws.com'},
    {name:'enable_logging',label:'Enable Log Collection',type:'checkbox',desc:'Ship logs to Loki / CloudWatch'},
    {name:'logging_endpoint',label:'Logging Endpoint',type:'text',desc:'Required if logging enabled',placeholder:'https://loki.internal:3100/loki/api/v1/push'},
    {name:'grafana_org_name',label:'Grafana Org Name',type:'text',desc:'Defaults to team name if empty',placeholder:'payments-team'},
    {name:'slo_availability_target',label:'Availability SLO (%)',type:'text',placeholder:'99.9'},
    {name:'slo_latency_p99_ms',label:'Latency P99 Threshold (ms)',type:'number',min:10,max:60000,placeholder:'500'},
    {name:'slo_error_rate_threshold',label:'Error Rate Threshold (%)',type:'text',placeholder:'0.1'},
    {name:'error_budget_burn_alert',label:'Error Budget Burn Alert',type:'checkbox',desc:'Alert on multi-window burn rate'},
    {name:'incident_tool',label:'Incident Tool',type:'select',options:['pagerduty','opsgenie','incident.io','none']},
    {name:'pagerduty_service_id',label:'PagerDuty Service ID',type:'text',desc:'Required if PagerDuty selected',placeholder:'P1ABC2D'},
    {name:'opsgenie_team_id',label:'Opsgenie Team ID',type:'text',desc:'Required if Opsgenie selected',placeholder:'team-12345'},
    {name:'escalation_policy',label:'Escalation Policy',type:'select',options:['default','critical','business-hours']},
    {name:'oncall_rotation_name',label:'On-Call Rotation Name',type:'text',placeholder:'payments-oncall'},
    {name:'oncall_primary_email',label:'Primary On-Call Email',type:'text',placeholder:'sre-lead@company.com'},
    {name:'oncall_secondary_email',label:'Secondary On-Call Email',type:'text',placeholder:'sre-backup@company.com'},
    {name:'enable_runbooks',label:'Auto-generate Runbooks',type:'checkbox',desc:'Create troubleshooting guides in wiki'},
    {name:'runbook_wiki_space',label:'Runbook Wiki Space',type:'text',placeholder:'SRE'},
    {name:'notification_slack_channel',label:'Alert Slack Channel',type:'text',placeholder:'#payments-alerts'},
    {name:'notification_email',label:'Alert Email',type:'text',placeholder:'sre-team@company.com'},
  ],

  docs: {
    updated: '2026-04-15',
    overview: 'SRE Onboarding provisions a complete observability stack for your service: Prometheus monitoring, Grafana dashboards, Pyrra SLO tracking, alerting to Slack, and pre-configured ServiceMonitor and PrometheusRule resources.',
    useCases: [
      'Setting up monitoring for a new service from day one',
      'Defining SLOs (Service Level Objectives) with automated tracking',
      'Getting Slack alerts when error rates or latency exceed thresholds',
    ],
    prerequisites: [
      'A service deployed on EKS (Prometheus scrapes Kubernetes pods)',
      'Prometheus metrics exposed on a /metrics endpoint',
      'A Slack channel for alerts',
    ],
    howToProvision: [
      'Navigate to Service Catalog and click "SRE Onboarding"',
      'Fill in common fields',
      'Enter Service Name',
      'Set Availability SLO target (e.g., 99.9%)',
      'Set Latency SLO target and threshold',
      'Enter Notification Slack Channel',
      'Click "Submit Request"',
    ],
    configOptions: [
      { param: 'service_name', desc: 'Name of the service to monitor. Must match the Kubernetes service name.' },
      { param: 'slo_availability_target', desc: 'Availability target as a percentage (e.g., 99.9).' },
      { param: 'slo_latency_target', desc: 'Percentage of requests within the latency threshold (e.g., 99.0).' },
      { param: 'slo_latency_threshold', desc: 'Latency threshold in seconds (e.g., 0.5 for 500ms).' },
      { param: 'notification_slack_channel', desc: 'Slack channel for alert notifications.' },
    ],
    faqs: [
      { q: 'What metrics are collected?', a: 'Standard RED metrics: Request rate, Error rate, and Duration (latency). Plus Kubernetes pod metrics.' },
      { q: 'Can I add custom dashboards?', a: 'Yes. Grafana is provisioned with your service dashboard. You can add custom panels via the Grafana UI.' },
    ],
  },

  accessGuide: function(r, o, env, region, name, acct, endpoint) {
    return [
      {title:'Access Grafana Dashboard', commands:[
        {label:'Open in browser', code:'# Grafana URL (from your SRE stack):\n'+(o.grafana_url||'https://grafana.'+name+'.internal')+'\n\n# Default login: admin / <from Secrets Manager>'},
        {label:'Get Grafana password', code:'aws secretsmanager get-secret-value \\\n  --secret-id '+name+'-grafana-admin \\\n  --query SecretString --output text \\\n  --region '+region}
      ]},
      {title:'Query Prometheus', commands:[
        {code:'# Prometheus URL:\n'+(o.prometheus_url||'https://prometheus.'+name+'.internal')+'\n\n# Example PromQL queries:\n# CPU usage:    sum(rate(container_cpu_usage_seconds_total[5m])) by (pod)\n# Memory usage: sum(container_memory_working_set_bytes) by (pod)\n# HTTP rate:    sum(rate(http_requests_total[5m])) by (status)'}
      ]},
      {title:'PagerDuty Integration', desc:'Alerts route to your team\'s PagerDuty service.', commands:[
        {code:'# PagerDuty service URL:\nhttps://app.pagerduty.com/services/'+(o.pagerduty_service_id||'<service-id>')}
      ], notes:['Check SLO dashboards in Grafana under the "SLO" folder.','Alert rules are managed in the observability module \u2014 update via PR to the sre-config repo.']}
    ];
  },
},

'argocd-onboarding': {
  name: 'ArgoCD Onboarding',
  icon: '\u{1F504}',
  category: 'Onboarding',
  description: 'GitOps with ApplicationSets and Helm',
  clusterDependent: true,

  fields: [
    {name:'project_name',label:'ArgoCD Project Name',type:'text',required:true,placeholder:'payments'},
    {name:'namespace',label:'Namespace',type:'text',required:true,placeholder:'payments'},
    {name:'source_cluster_key',label:'Target EKS Cluster',type:'text',required:true,desc:'Ticket key of the deployed EKS cluster',placeholder:'INFRA-2005'},
    {name:'cluster_name',label:'Cluster Name',type:'text',desc:'Auto-filled from cluster selection',placeholder:'payments-eks-prod'},
    {name:'services',label:'Services to Onboard',type:'text',required:true,desc:'Comma-separated service names',placeholder:'api,worker,cron'},
    {name:'environments',label:'Target Environments',type:'text',desc:'Comma-separated',placeholder:'dev,staging,prod'},
    {name:'image_registry',label:'Container Image Registry',type:'text',placeholder:'123456789012.dkr.ecr.us-east-1.amazonaws.com'},
  ],

  docs: {
    updated: '2026-04-15',
    overview: 'ArgoCD Onboarding provisions GitOps infrastructure for your team: an ArgoCD project with RBAC, ApplicationSets for multi-environment deployments, and a Helm chart scaffold in the gitops repository.',
    useCases: [
      'Automated Kubernetes deployments from Git',
      'Multi-environment promotion (dev \u2192 staging \u2192 prod)',
      'Drift detection and automatic reconciliation',
    ],
    prerequisites: [
      'An EKS cluster provisioned via Keystone',
      'Application Docker images built and pushed to ECR',
      'Helm chart or Kubernetes manifests in a Git repository',
    ],
    howToProvision: [
      'Navigate to Service Catalog and click "ArgoCD Onboarding"',
      'Fill in common fields',
      'Enter ArgoCD Project Name and target Namespace',
      'Click "Submit Request"',
      'ArgoCD project, ApplicationSets, and Helm scaffold are created in keystone-gitops repo',
    ],
    configOptions: [
      { param: 'project_name', desc: 'ArgoCD project name. Scopes RBAC and resource access.' },
      { param: 'namespace', desc: 'Kubernetes namespace where applications will be deployed.' },
    ],
    faqs: [
      { q: 'How do I deploy after onboarding?', a: 'Push changes to your Helm values in the gitops repo. ArgoCD detects the change and syncs automatically within 3 minutes.' },
    ],
  },

  accessGuide: function(r, o, env, region, name, acct, endpoint) {
    return [
      {title:'Access ArgoCD UI', commands:[
        {label:'Port-forward ArgoCD server', code:'kubectl port-forward svc/argocd-server -n argocd 8443:443'},
        {label:'Open in browser', code:'# Open https://localhost:8443\n# Username: admin\n# Password:'},
        {label:'Get ArgoCD admin password', code:'kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d'}
      ]},
      {title:'ArgoCD CLI', commands:[
        {label:'Install', code:'brew install argocd   # macOS\n# or: curl -sSL -o argocd https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64 && chmod +x argocd && sudo mv argocd /usr/local/bin/'},
        {label:'Login', code:'argocd login localhost:8443 --username admin --password $(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d) --insecure'},
        {label:'List applications', code:'argocd app list'},
        {label:'Sync an application', code:'argocd app sync <app-name>'}
      ]},
      {title:'GitOps Workflow', desc:'Push changes to the configured Git repo and ArgoCD auto-syncs.', commands:[
        {code:'# Your GitOps repo: '+(r.git_repo_url||o.git_repo||'<configured-repo>')+'\n# Branch: '+(r.target_branch||'main')+'\n\ngit clone '+(r.git_repo_url||o.git_repo||'<repo-url>')+'\ncd <repo> && git checkout -b feature/my-change\n# Make changes to manifests / Helm values\ngit push origin feature/my-change\n# Create PR \u2192 merge \u2192 ArgoCD syncs automatically'}
      ], notes:['ArgoCD polls every 3 minutes by default. Use "argocd app sync" for immediate deployment.']}
    ];
  },
},


// ═══════════════════════════════════════════════════════════════════════════
// OPERATIONS
// ═══════════════════════════════════════════════════════════════════════════

'xcr-onboarding': {
  name: 'XCR Onboarding',
  icon: '\u{1F4E6}',
  category: 'Operations',
  description: 'Cross-region container registry replication',

  fields: [
    {name:'summary',label:'Request Summary',type:'text',required:true,placeholder:'Onboard payments cluster to XCR'},
    {name:'business_unit',label:'Business Unit',type:'text',required:true,placeholder:'Financial Services'},
    {name:'client_services',label:'Client Services',type:'text',required:true,placeholder:'payments-api,payments-worker'},
    {name:'component',label:'Component',type:'text',required:true,placeholder:'payments'},
    {name:'primary_contact_email',label:'Primary Contact Email',type:'text',required:true,placeholder:'lead@company.com'},
    {name:'description',label:'Description',type:'text',placeholder:'Onboard payments cluster for cross-region replication'},
    {name:'cloud',label:'Cloud Provider',type:'select',options:['AWS','Azure','GCP']},
    {name:'cluster_type',label:'Cluster Type',type:'select',options:['EKS','ECS','AKS','GKE']},
    {name:'release_type',label:'Release Type',type:'select',options:['stable','canary','blue-green']},
    {name:'size',label:'Cluster Size',type:'select',options:['small','medium','large','xlarge']},
    {name:'connectivity',label:'Connectivity',type:'select',options:['public','private','hybrid']},
    {name:'keycloak_group_name',label:'Keycloak Group Name',type:'text',required:true,desc:'RBAC group for authentication',placeholder:'payments-team'},
  ],

  docs: {
    updated: '2026-04-15',
    overview: 'XCR (Cross-Region Container Registry) Onboarding provisions ECR (Elastic Container Registry) replication rules to automatically replicate container images to multiple AWS regions. Ensures low-latency image pulls for multi-region deployments.',
    useCases: [
      'Multi-region EKS deployments needing local image access',
      'Disaster recovery with images available in secondary regions',
      'Reducing image pull latency for globally distributed teams',
    ],
    prerequisites: [
      'An ECR repository already created (or will be created)',
      'Target regions identified for replication',
    ],
    howToProvision: [
      'Navigate to Service Catalog and click "XCR Onboarding"',
      'Fill in common fields',
      'Enter ECR Repository Name',
      'Specify Target Regions (comma-separated)',
      'Click "Submit Request"',
    ],
    configOptions: [
      { param: 'repository_name', desc: 'Name of the ECR repository to replicate.' },
      { param: 'target_regions', desc: 'Comma-separated list of AWS regions (e.g., eu-west-1, ap-southeast-1).' },
    ],
    faqs: [
      { q: 'Is replication real-time?', a: 'Near real-time. New images are typically available in target regions within 1-2 minutes.' },
    ],
  },

  accessGuide: function(r, o, env, region, name, acct, endpoint) {
    return [
      {title:'Docker Login to ECR', commands:[
        {code:'aws ecr get-login-password --region '+region+' --profile keystone-'+env+' | \\\n  docker login --username AWS --password-stdin '+acct+'.dkr.ecr.'+region+'.amazonaws.com'}
      ]},
      {title:'Push an Image', commands:[
        {label:'Tag your image', code:'docker tag my-app:latest '+acct+'.dkr.ecr.'+region+'.amazonaws.com/'+(r.repository_name||name)+':latest'},
        {label:'Push', code:'docker push '+acct+'.dkr.ecr.'+region+'.amazonaws.com/'+(r.repository_name||name)+':latest'}
      ]},
      {title:'Pull an Image', commands:[
        {code:'docker pull '+acct+'.dkr.ecr.'+region+'.amazonaws.com/'+(r.repository_name||name)+':latest'}
      ]},
      {title:'List Images', commands:[
        {code:'aws ecr describe-images \\\n  --repository-name '+(r.repository_name||name)+' \\\n  --region '+region+' \\\n  --query "imageDetails[*].{Tags:imageTags,Pushed:imagePushedAt,Size:imageSizeInBytes}" \\\n  --output table'}
      ], notes:['CI/CD pipelines should use OIDC roles instead of long-lived credentials for ECR push.']}
    ];
  },
},

'eks-upgrade': {
  name: 'EKS Upgrade',
  icon: '\u2B06\uFE0F',
  category: 'Operations',
  description: 'Managed EKS version upgrade',

  fields: [
    {name:'cluster_name',label:'Cluster Name',type:'text',required:true,placeholder:'my-eks-prod'},
    {name:'target_version',label:'Target Version',type:'select',options:['1.28','1.29','1.30','1.31','1.32']},
  ],

  docs: {
    updated: '2026-04-15',
    overview: 'EKS Upgrade performs a managed Kubernetes version upgrade for an existing EKS cluster. Keystone handles the control plane upgrade, node group rolling update, and add-on compatibility checks with zero-downtime.',
    useCases: [
      'Upgrading Kubernetes to get security patches and new features',
      'Staying within the AWS-supported version window (N-3)',
      'Compliance requirements mandating latest stable versions',
    ],
    prerequisites: [
      'An existing EKS cluster provisioned via Keystone',
      'Target version is exactly one minor version ahead of current',
      'PodDisruptionBudgets configured for critical workloads',
    ],
    howToProvision: [
      'Navigate to Service Catalog and click "EKS Upgrade"',
      'Fill in common fields',
      'Enter the existing Cluster Name',
      'Select Target Version (must be current +1 minor)',
      'Click "Submit Request"',
      'The upgrade runs: control plane first, then node groups rolling update',
    ],
    configOptions: [
      { param: 'cluster_name', desc: 'Name of the existing EKS cluster to upgrade.' },
      { param: 'target_version', desc: 'Target Kubernetes version. Must be current +1 minor (e.g., 1.29 \u2192 1.30).' },
    ],
    faqs: [
      { q: 'How long does an upgrade take?', a: 'Control plane: 15-25 minutes. Node group rolling update: depends on node count, typically 30-60 minutes.' },
      { q: 'Is there downtime?', a: 'Zero downtime for workloads with proper PodDisruptionBudgets. The node group performs a rolling replacement.' },
    ],
  },

  accessGuide: function(r, o, env, region, name, acct, endpoint) {
    return [
      {title:'Verify Upgrade Status', commands:[
        {code:'aws eks describe-cluster \\\n  --name '+(r.cluster_name||name)+' \\\n  --region '+region+' \\\n  --query "cluster.{Version:version,Status:status,Endpoint:endpoint}" \\\n  --output table'}
      ]},
      {title:'Validate Workloads', commands:[
        {label:'Check all pods running', code:'kubectl get pods --all-namespaces | grep -v Running | grep -v Completed'},
        {label:'Check node versions', code:'kubectl get nodes -o wide'},
        {label:'Verify addon versions', code:'aws eks list-addons --cluster-name '+(r.cluster_name||name)+' --region '+region+'\nfor addon in vpc-cni kube-proxy coredns; do\n  aws eks describe-addon --cluster-name '+(r.cluster_name||name)+' --addon-name $addon --region '+region+' --query "addon.{Name:addonName,Version:addonVersion,Status:status}" --output table\ndone'}
      ]},
      {title:'Rollback (if needed)', commands:[
        {code:'# EKS upgrades cannot be rolled back directly.\n# If issues arise, deploy previous workload versions:\nkubectl rollout undo deployment/<deployment-name>'}
      ], notes:['Run integration tests against the upgraded cluster before routing production traffic.']}
    ];
  },
},

}; // end SERVICE_REGISTRY


// ═══════════════════════════════════════════════════════════════════════════
// HELPER: Build KEYSTONE_DOCS from registry (backward-compatible)
// ═══════════════════════════════════════════════════════════════════════════

var KEYSTONE_DOCS = { services: {}, admin: null, teams: [] };

// Auto-populate service docs from registry
Object.keys(SERVICE_REGISTRY).forEach(function(type) {
  var svc = SERVICE_REGISTRY[type];
  if (svc.docs) {
    KEYSTONE_DOCS.services[type] = svc.docs;
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// COST ESTIMATOR — Monthly cost estimates per service (eu-central-1 pricing)
// Shows developers approximate costs before they submit a request
// ═══════════════════════════════════════════════════════════════════════════

var COST_ESTIMATES = {
  'eks-cluster': function(f) {
    var nodeCosts = {'t3.medium':35,'t3.large':70,'m6i.large':85,'m6i.xlarge':170,'m7g.large':78,'m7g.xlarge':156,'r6g.large':115,'r6g.xlarge':230};
    var nodeCount = parseInt(f.desired_capacity || f.min_nodes || 3);
    var nodeType = f.node_instance_type || 'm6i.large';
    var perNode = nodeCosts[nodeType] || 85;
    var cluster = 73; // EKS control plane
    var nat = f.enable_nat_gateway ? 45 : 0;
    return {total: cluster + (perNode * nodeCount) + nat, breakdown: [
      {item:'EKS Control Plane', cost:cluster},
      {item:nodeCount+'x '+nodeType+' nodes', cost:perNode*nodeCount},
      nat > 0 ? {item:'NAT Gateway', cost:nat} : null
    ].filter(Boolean)};
  },
  'rds-database': function(f) {
    var instanceCosts = {'db.t3.micro':18,'db.t3.medium':70,'db.r6g.large':175,'db.r6g.xlarge':350,'db.r7g.large':190,'db.r7g.xlarge':380};
    var inst = f.instance_class || 'db.r6g.large';
    var cost = instanceCosts[inst] || 175;
    var storage = ((parseInt(f.allocated_storage || 100)) * 0.115);
    var multiAz = f.multi_az ? cost : 0;
    return {total: cost + multiAz + storage, breakdown: [
      {item:'Instance ('+inst+')', cost:cost},
      multiAz > 0 ? {item:'Multi-AZ standby', cost:multiAz} : null,
      {item:'Storage ('+Math.round(storage)+'GB gp3)', cost:Math.round(storage)}
    ].filter(Boolean)};
  },
  's3-bucket': function(f) {
    return {total: 3, breakdown: [{item:'S3 Standard (estimated 50GB)', cost:1.15},{item:'Requests (~100k/mo)', cost:0.50},{item:'Data transfer', cost:1.35}]};
  },
  'lambda': function(f) {
    var mem = parseInt(f.memory_size || 256);
    var cost = Math.max(1, Math.round(mem / 128 * 3));
    return {total: cost, breakdown: [{item:'1M invocations/mo ('+mem+'MB)', cost:cost}]};
  },
  'ecs-service': function(f) {
    var cpuCosts = {'256':10,'512':20,'1024':41,'2048':82,'4096':164};
    var cpu = f.cpu || '512';
    var perTask = cpuCosts[cpu] || 20;
    var count = parseInt(f.desired_count || 2);
    var alb = 22;
    return {total: (perTask * count) + alb, breakdown: [
      {item:count+'x Fargate tasks ('+cpu+' CPU)', cost:perTask*count},
      {item:'Application Load Balancer', cost:alb}
    ]};
  },
  'redis': function(f) {
    var nodeCosts = {'cache.t3.micro':15,'cache.t3.medium':55,'cache.r7g.large':175,'cache.r7g.xlarge':350};
    var nodeType = f.node_type || 'cache.t3.medium';
    var nodes = parseInt(f.num_nodes || 2);
    var perNode = nodeCosts[nodeType] || 55;
    return {total: perNode * nodes, breakdown: [{item:nodes+'x '+nodeType, cost:perNode*nodes}]};
  },
  'dynamodb': function(f) {
    var mode = f.billing_mode || 'PAY_PER_REQUEST';
    var cost = mode === 'PAY_PER_REQUEST' ? 5 : 20;
    return {total: cost, breakdown: [{item:mode === 'PAY_PER_REQUEST' ? 'On-demand (estimated light usage)' : 'Provisioned capacity', cost:cost}]};
  },
  'msk': function(f) {
    var brokerCosts = {'kafka.t3.small':28,'kafka.m5.large':115,'kafka.m7g.large':108,'kafka.m5.xlarge':230};
    var brokerType = f.broker_instance_type || 'kafka.m5.large';
    var brokers = parseInt(f.number_of_brokers || 3);
    var perBroker = brokerCosts[brokerType] || 115;
    var storage = (parseInt(f.storage_per_broker_gb || 100) * 0.10 * brokers);
    return {total: (perBroker * brokers) + storage, breakdown: [
      {item:brokers+'x '+brokerType+' brokers', cost:perBroker*brokers},
      {item:'EBS storage', cost:Math.round(storage)}
    ]};
  },
  'documentdb-database': function(f) {
    var instanceCosts = {'db.t3.medium':75,'db.r6g.large':200,'db.r6g.xlarge':400};
    var inst = f.instance_class || 'db.t3.medium';
    var count = parseInt(f.num_instances || 1);
    var perInst = instanceCosts[inst] || 75;
    return {total: perInst * count, breakdown: [{item:count+'x '+inst, cost:perInst*count}]};
  },
  'vpc': function() { return {total: 45, breakdown: [{item:'NAT Gateway', cost:33},{item:'VPN/Endpoints', cost:12}]}; },
  'route53': function() { return {total: 1, breakdown: [{item:'Hosted Zone', cost:0.50},{item:'DNS queries (~1M)', cost:0.50}]}; },
  'aws-account': function() { return {total: 0, breakdown: [{item:'Account creation (no charge)', cost:0}]}; },
  'sre-onboarding': function() { return {total: 65, breakdown: [{item:'Prometheus (AMP)', cost:30},{item:'Grafana (AMG)', cost:25},{item:'Alerting/OTel', cost:10}]}; },
  'argocd-onboarding': function() { return {total: 0, breakdown: [{item:'ArgoCD (runs on existing EKS)', cost:0}]}; },
  'xcr-onboarding': function() { return {total: 0, breakdown: [{item:'Cross-region config only', cost:0}]}; },
  'eks-upgrade': function() { return {total: 0, breakdown: [{item:'Control plane upgrade (no extra cost)', cost:0}]}; },
  'iceberg-table': function() { return {total: 8, breakdown: [{item:'Glue Data Catalog', cost:1},{item:'S3 storage (estimated)', cost:5},{item:'Athena queries', cost:2}]}; },
  'vector-store': function(f) {
    var engine = f.engine || 'pgvector';
    if (engine === 'pgvector') return {total: 175, breakdown: [{item:'RDS PostgreSQL + pgvector', cost:175}]};
    return {total: 120, breakdown: [{item:'OpenSearch Serverless (2 OCU)', cost:120}]};
  },
  'lake-formation': function() { return {total: 0, breakdown: [{item:'Lake Formation (no charge, governance only)', cost:0}]}; },
  'data-access': function() { return {total: 0, breakdown: [{item:'IAM role creation (no charge)', cost:0}]}; },
  'data-classification': function(f) {
    var freq = f.schedule_frequency || 'monthly';
    var costs = {daily:30,weekly:12,monthly:5};
    return {total: costs[freq] || 5, breakdown: [{item:'Macie classification ('+freq+')', cost:costs[freq]||5}]};
  },
  'cross-account-share': function() { return {total: 0, breakdown: [{item:'RAM sharing (no charge)', cost:0}]}; },
};

/**
 * Get estimated monthly cost for a service based on form values.
 * @param {string} type - Service type key
 * @param {object} formValues - Current form field values
 * @returns {{total: number, breakdown: Array<{item: string, cost: number}>}}
 */
function getServiceCostEstimate(type, formValues) {
  var estimator = COST_ESTIMATES[type];
  if (!estimator) return {total: 0, breakdown: [{item: 'Cost estimate not available', cost: 0}]};
  try { return estimator(formValues || {}); }
  catch(e) { return {total: 0, breakdown: [{item: 'Unable to calculate', cost: 0}]}; }
}
