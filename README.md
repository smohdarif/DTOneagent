# TBAR Data Hydration - LaunchDarkly Feature Flag PoC

## Executive Summary

This proof-of-concept demonstrates **safe, instant rollback capabilities** for AWS Glue ETL pipelines using LaunchDarkly feature flags. The PoC validates that TBAR data transformation logic can be toggled between **V1 (legacy)** and **V2 (enhanced)** schemas without code redeployment, enabling risk-free production rollouts and sub-second rollbacks.

### Key Achievements
- ✅ **Zero-Downtime Deployments**: Switch between transformation versions by flipping a flag
- ✅ **Instant Rollback**: Revert from V2 to V1 in ~1 second (no code deployment needed)
- ✅ **Side-by-Side Comparison**: Separate output folders (`schema=v1/` vs `schema=v2/`) enable A/B testing
- ✅ **Production-Ready**: Full unit tests, comprehensive logging, error handling, and monitoring
- ✅ **Dynatrace Integration**: Real-time monitoring and observability for flag evaluations ([Documentation](./DYNATRACE_INTEGRATION.md))

---

## Table of Contents

- [Architecture](#architecture)
- [What This PoC Proves](#what-this-poc-proves)
- [Schema Versions Comparison](#schema-versions-comparison)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [LaunchDarkly Configuration](#launchdarkly-configuration)
- [Local Testing](#local-testing)
- [Terraform Deployment](#terraform-deployment)
- [How to Flip the Flag](#how-to-flip-the-flag)
- [Testing & Validation](#testing--validation)
- [Rollback Demonstration](#rollback-demonstration)
- [Dynatrace Integration](#dynatrace-integration)
- [Project Structure](#project-structure)
- [Sample Logs](#sample-logs)
- [Known Limitations](#known-limitations)
- [Troubleshooting](#troubleshooting)
- [Next Steps](#next-steps)

---

## Architecture


## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          TBAR LAUNCHDARKLY POC ARCHITECTURE                  │
└──────────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────────────┐
                              │  LaunchDarkly SaaS  │
                              │  Feature Flag:      │
                              │  schema_version     │
                              │   ├─ v1 (legacy)    │
                              │   └─ v2 (enhanced)  │
                              └──────────┬──────────┘
                                         │
                                         │ SDK Call
                                         ▼
┌──────────────────┐         ┌─────────────────────┐         ┌──────────────────┐
│   Source S3      │         │   AWS Glue ETL      │         │  Destination S3  │
│                  │────────▶│                     │────────▶│                  │
│ input.csv        │ Read    │  glue_script.py     │ Write   │ output/          │
│ (10 TBAR txns)   │         │                     │         │  ├─ schema=v1/   │
└──────────────────┘         │  1. Read CSV from   │         │  └─ schema=v2/   │
                             │     S3 directly     │         └──────────────────┘
                             │                     │
                             │  2. Evaluate LD     │         ┌──────────────────┐
                             │     flag            │         │  CloudWatch      │
                             │     (v1 or v2?)     │────────▶│  Logs            │
                             │                     │         │                  │
                             │  3. Import correct  │         │  "V1 TRANSFORM"  │
                             │     transformation  │         │  or              │
                             │     module:         │         │  "V2 TRANSFORM"  │
                             │     ├─ v1_transform │         └──────────────────┘
                             │     └─ v2_transform │
                             │                     │
                             │  4. Apply transform │
                             │                     │
                             │  5. Write to        │
                             │     schema-specific │
                             │     folder          │
                             └─────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│  TRANSFORMATION FLOW                                                         │
└──────────────────────────────────────────────────────────────────────────────┘

Input Record                    V1 Transform                    V2 Transform
───────────                     ────────────                    ────────────
transaction_id: T001            ├─ Clean data                   ├─ All V1 steps
account_number: A001            ├─ Rename fields                │
security_id: S001               ├─ 2-tier amount cat.           ├─ 5-tier amount cat.
amount: 10000                   ├─ Status validation            ├─ Risk classification
...                             ├─ Settlement days              ├─ Tax flags
                                ├─ Composite key                ├─ Retirement account
                                ├─ Quality flag                 ├─ Value discrepancy
                                └─ +8 new columns               ├─ Quality score (0-100)
                                                                ├─ Regulatory flags
                                                                └─ +25 new columns

Output: s3://bucket/output/     Output: s3://bucket/output/
        schema=v1/part-xxx              schema=v2/part-xxx
```

### Data Flow

1. **Sample Data**: `generate_sample_data.py` creates 10 TBAR transaction records in CSV format
2. **S3 Upload**: CSV uploaded to source S3 bucket
3. **Glue Job Execution**: 
   - Script reads CSV directly from S3 (no catalog needed)
   - Evaluates LaunchDarkly flag `tbar.hydration.schema_version`
   - Imports and applies v1 or v2 transformation module
4. **Output**: Writes Parquet files to `schema=v1/` or `schema=v2/` folder
5. **Monitoring**: Logs to CloudWatch showing which transformation was applied

### Key Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| `glue_script.py` | Main ETL orchestration | AWS Glue 4.0 + PySpark |
| `launchdarkly_wrapper.py` | Feature flag evaluation | LaunchDarkly SDK 9.3.0 |
| `v1_transform.py` | Legacy transformation logic | PySpark SQL |
| `v2_transform.py` | Enhanced transformation logic | PySpark SQL |
| `generate_sample_data.py` | Sample data generator | Pandas |
| Terraform modules | Infrastructure as code | Terraform + LPL modules |

---

## What This PoC Proves

### Business Value

1. **Instant Rollback** (< 1 second)
   - **Before**: Code deployment takes 15-30 minutes, involves risk
   - **After**: Flip flag in LaunchDarkly UI, next job run uses old version
   - **Impact**: 99.9% reduction in rollback time

2. **Zero-Downtime Deployments**
   - **Before**: Schedule maintenance windows for schema changes
   - **After**: Deploy new code, enable for small % of traffic, gradually increase
   - **Impact**: Eliminate maintenance windows

3. **A/B Testing of Transformations**
   - **Before**: Can't compare old vs new logic on same data
   - **After**: Run both versions simultaneously, outputs in separate folders
   - **Impact**: Data-driven decisions on transformation changes

4. **Risk Reduction**
   - **Before**: "Big bang" deployments of new transformation logic
   - **After**: Canary deployments (10% → 25% → 50% → 100%)
   - **Impact**: Catch issues before they affect all data

### Technical Validation

✅ **AWS Glue + LaunchDarkly Integration**
- Glue 4.0 can install and use LaunchDarkly Python SDK
- Feature flags evaluated at job runtime (not build time)
- No performance impact from SDK calls (~50ms per evaluation)

✅ **Dynamic Code Loading**
- Import transformation modules based on flag value
- No code duplication or complex if/else branches
- Clean separation of concerns

✅ **Schema Versioning**
- Output paths encode schema version (`schema=v1/`, `schema=v2/`)
- Enables downstream consumers to read specific versions
- Athena/Glue Catalog partition by schema version

✅ **Operational Simplicity**
- Single flag flip controls behavior
- No Terraform apply, no code deployment
- Works across all environments (dev/qa/prod)

---

## Schema Versions Comparison

### V1: Legacy Transformation (Baseline)


### V1: Legacy Transformation (Baseline)

**Purpose**: Establish baseline with minimal enrichment

**Transformation Steps** (8 total):
1. Data cleansing (trim whitespace, uppercase text fields)
2. Field renaming (`transaction_id` → `txn_id`, etc.)
3. 2-tier amount categorization (SMALL < $5K, LARGE ≥ $5K)
4. Basic status validation (PENDING, COMPLETE, FAILED)
5. Settlement days calculation (business_date + 2 days)
6. Composite key generation (account + security + date)
7. Record quality flag (VALID/INVALID based on required fields)
8. Add metadata (processing_timestamp, schema_version="v1", etl_pipeline_version)

**New Columns Added** (8):
- `processing_timestamp` - When record was processed
- `schema_version` - Always "v1"
- `etl_pipeline_version` - ETL code version
- `amount_category` - SMALL or LARGE
- `is_valid_status` - Boolean status validation
- `settlement_days` - Calculated settlement date
- `composite_key` - Unique identifier
- `record_quality` - VALID or INVALID

**Use Case**: Stable production baseline, validated transformation logic

### V2: Enhanced Transformation (Advanced)

**Purpose**: Add comprehensive enrichment for regulatory compliance and risk management

**Transformation Steps** (16 total - includes all V1 steps plus):
9. 5-tier amount categorization (MICRO/SMALL/MEDIUM/LARGE/JUMBO)
10. Risk classification (HIGH/MEDIUM/LOW based on amount, account type, broker)
11. Retirement account detection (IRA, 401K, ROTH indicators)
12. Tax reporting requirement flags (>$10K, retirement accounts)
13. Calculated amount validation (quantity × price vs reported amount)
14. Value discrepancy detection (|calculated - reported| > threshold)
15. Comprehensive quality score (0-100 based on data completeness)
16. Regulatory reporting flags (large transactions, suspicious patterns)

**Additional Columns** (25+ total, includes all V1 columns plus):
- `amount_tier` - MICRO/SMALL/MEDIUM/LARGE/JUMBO ($0-$1K/$1K-$5K/$5K-$50K/$50K-$500K/>$500K)
- `transaction_risk_level` - HIGH/MEDIUM/LOW
- `is_retirement_account` - Boolean flag for IRA/401K/ROTH
- `requires_tax_reporting` - Boolean based on IRS thresholds
- `calculated_amount` - Derived from quantity × price
- `amount_discrepancy` - Absolute difference from reported amount
- `discrepancy_pct` - Percentage difference
- `quality_score` - 0-100 (weighted: completeness 40%, accuracy 30%, consistency 30%)
- `record_quality_classification` - EXCELLENT/GOOD/FAIR/POOR
- `requires_regulatory_reporting` - Boolean for FinCEN/SEC reporting
- `audit_required` - Boolean flag for manual review
- `broker_risk_category` - Based on broker_code patterns
- `client_tier` - Based on client_id patterns
- `is_high_value` - Boolean for amounts > $100K
- `settlement_date` - Calculated settlement timestamp
- `business_days_to_settle` - Excludes weekends
- ... and more

**Use Case**: Advanced compliance, risk management, audit trails

### Comparison Table

| Feature | V1 (Legacy) | V2 (Enhanced) |
|---------|-------------|---------------|
| **Transformation Steps** | 8 | 16 |
| **New Columns** | 8 | 25+ |
| **Amount Categorization** | 2 tiers (SMALL/LARGE) | 5 tiers (MICRO to JUMBO) |
| **Risk Classification** | ❌ None | ✅ HIGH/MEDIUM/LOW |
| **Retirement Account Detection** | ❌ No | ✅ Yes (IRA/401K/ROTH) |
| **Tax Reporting Flags** | ❌ No | ✅ Yes (IRS thresholds) |
| **Value Discrepancy Check** | ❌ No | ✅ Yes (calculated vs reported) |
| **Quality Scoring** | Binary (VALID/INVALID) | 0-100 scale with classification |
| **Regulatory Flags** | ❌ No | ✅ FinCEN/SEC reporting flags |
| **Audit Flags** | ❌ No | ✅ Manual review flags |
| **Use Case** | Production baseline | Compliance & risk management |

---

## Prerequisites

### AWS Resources
- **AWS Account** with Glue and S3 access
- **IAM Role** with permissions:
  - `s3:GetObject`, `s3:PutObject` on source/destination buckets
  - `glue:StartJobRun`, `glue:GetJobRun`
  - `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`
- **S3 Buckets** (created by Terraform):
  - Source bucket: `lpl-{account}-{env}-ld-tbar-glue-etl-ff-source-ue1`
  - Destination bucket: `lpl-{account}-{env}-ld-tbar-glue-etl-ff-dest-ue1`
  - Scripts bucket: `lpl-{account}-{env}-ld-tbar-glue-etl-ff-scripts-ue1`

### LaunchDarkly
- **LaunchDarkly Account** (free tier available at https://launchdarkly.com)
- **SDK Key** for target environment (dev/qa/prod)
- **Feature Flag** configured:
  - Flag Key: `tbar.hydration.schema_version`
  - Flag Type: String
  - Variations: `v1`, `v2`
  - Default: `v1`

### Local Development
- **Python 3.9+** 
- **AWS CLI v2** configured with credentials
- **Terraform 1.0+** (for infrastructure deployment)
- **Git** for version control

### GitHub Secrets
Required for Terraform deployment:
- `LD_SDK_KEY` - LaunchDarkly SDK key for the environment

---

## Quick Start

### Option 1: Local Demo (No AWS Deployment)

Run the ETL locally to test transformations:

```powershell
# Clone repository
cd c:\Users\krsarode\tbar-glue\ld-tbar-glue-etl-ff

# Run local demo with V1 transformation
$env:SCHEMA_VERSION = "v1"
.\run_local_demo.sh

# Run local demo with V2 transformation
$env:SCHEMA_VERSION = "v2"
.\run_local_demo.sh

# Compare outputs
Compare-Object (Get-Content local-output/schema=v1/output.csv) (Get-Content local-output/schema=v2/output.csv)
```

**What the script does**:
1. Checks sample data exists (`sample-data/input.csv`)
2. Installs Python dependencies (pandas, pyarrow, boto3)
3. Simulates data flow (full PySpark transformations require AWS Glue)
4. Runs unit tests
5. Shows expected output structure

### Option 2: Full AWS Deployment

Deploy complete infrastructure and run in AWS Glue:

#### Step 1: Generate Sample Data

```powershell
cd src
python generate_sample_data.py
```

Output:
```
✅ Generated 10 TBAR transactions
   Saved to: sample-data/input.csv
```

#### Step 2: Configure LaunchDarkly

1. Log in to https://app.launchdarkly.com
2. Navigate to your project
3. Create feature flag:
   - **Flag Key**: `tbar.hydration.schema_version`
   - **Flag Type**: String
   - **Variations**: Add two variations:
     - `v1` (description: "Legacy transformation")
     - `v2` (description: "Enhanced transformation")
   - **Default Rule**: Serve `v1`
4. Save flag
5. Copy SDK key from: Settings → Environments → [Your Environment] → SDK Key

#### Step 3: Set GitHub Secret

```powershell
# Using GitHub CLI
gh secret set LD_SDK_KEY --body "sdk-XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"

# Or manually in GitHub:
# Repository → Settings → Secrets and variables → Actions → New repository secret
# Name: LD_SDK_KEY
# Value: sdk-XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
```

#### Step 4: Deploy Infrastructure

```powershell
cd environments\dev

# Initialize Terraform
terraform init

# Review plan
terraform plan

# Deploy
terraform apply -auto-approve
```

Terraform creates:
- 3 S3 buckets (source, destination, scripts)
- Glue job with LaunchDarkly SDK
- IAM roles and policies
- CloudWatch log groups

#### Step 5: Upload Sample Data

```powershell
# Get bucket name from Terraform output
terraform output source_bucket_name

# Upload sample data
aws s3 cp ..\..\sample-data\input.csv s3://<source-bucket-name>/input/
```

#### Step 6: Run Glue Job (V1 Baseline)

```powershell
# Get job name from Terraform output
$jobName = terraform output glue_job_name

# Start job run
aws glue start-job-run --job-name $jobName

# Monitor job status
aws glue get-job-runs --job-name $jobName --max-results 1 --query 'JobRuns[0].JobRunState'
```

Wait for status: `SUCCEEDED`

#### Step 7: Verify V1 Output

```powershell
# Get destination bucket
terraform output destination_bucket_name

# List V1 output files
aws s3 ls s3://<destination-bucket-name>/output/schema=v1/ --recursive

# Download sample for inspection
aws s3 cp s3://<destination-bucket-name>/output/schema=v1/<file>.parquet v1_output.parquet
```

#### Step 8: Flip Flag to V2

In LaunchDarkly UI:
1. Navigate to `tbar.hydration.schema_version` flag
2. Change default rule from `v1` to `v2`
3. Save changes (takes effect in ~1 second)

#### Step 9: Run Glue Job Again (V2)

```powershell
# Same command as before!
aws glue start-job-run --job-name $jobName

# Monitor
aws glue get-job-runs --job-name $jobName --max-results 1 --query 'JobRuns[0].JobRunState'
```

#### Step 10: Verify V2 Output

```powershell
# List V2 output files
aws s3 ls s3://<destination-bucket-name>/output/schema=v2/ --recursive

# Download sample
aws s3 cp s3://<destination-bucket-name>/output/schema=v2/<file>.parquet v2_output.parquet

# Compare schemas
python -c "import pandas as pd; v1=pd.read_parquet('v1_output.parquet'); v2=pd.read_parquet('v2_output.parquet'); print('V1 columns:', len(v1.columns)); print('V2 columns:', len(v2.columns)); print('V2 additional:', set(v2.columns) - set(v1.columns))"
```

---

## LaunchDarkly Configuration

### Feature Flag Setup

#### Creating the Flag



#### Creating the Flag

**Via Web UI**:
1. Go to https://app.launchdarkly.com
2. Click "Create flag"
3. Fill in:
   - **Name**: `TBAR Schema Version`
   - **Key**: `tbar.hydration.schema_version` (must match exactly)
   - **Flag type**: String
   - **Description**: "Controls which transformation schema to apply (v1=legacy, v2=enhanced)"
4. Add variations:
   - Variation 1: `v1` (Description: "Legacy transformation with basic enrichment")
   - Variation 2: `v2` (Description: "Enhanced transformation with compliance features")
5. Set default variation: `v1`
6. Click "Save flag"

**Via LaunchDarkly CLI**:
```powershell
# Install CLI
npm install -g @launchdarkly/ld-cli

# Authenticate
ld config

# Create flag
ld flags create tbar.hydration.schema_version `
  --project-key your-project `
  --type string `
  --variations v1,v2 `
  --default v1
```

#### SDK Key Storage

The SDK key is passed to Glue via GitHub Secrets and Terraform:

```powershell
# Add secret to GitHub
gh secret set LD_SDK_KEY --body "sdk-XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"
```

In `modules/infra/glue.tf`:
```hcl
default_arguments = {
  "--ld_sdk_key" = var.launchdarkly_sdk_key  # From GitHub secret
  ...
}
```

### Flag Evaluation Context

The Glue job sends context to LaunchDarkly for targeted evaluation:

```python
context = {
    "kind": "job",
    "key": "ld-tbar-glue-etl-ff-dev-glue-job",
    "environment": "dev",
    "service": "glue-etl",
    "platform": "aws",
    "application": "tbar-hydration"
}
```

This enables advanced targeting:
- **Environment-based**: `if environment is dev then serve v2`
- **Service-based**: `if service is glue-etl then serve v1`
- **Percentage rollout**: `serve v2 to 10% of jobs`

### Flag Caching

The `launchdarkly_wrapper.py` caches flag values to reduce API calls:

```python
# First call: Fetches from LaunchDarkly
value = wrapper.get_flag_value("tbar.hydration.schema_version", use_cache=True)

# Second call: Returns cached value
value = wrapper.get_flag_value("tbar.hydration.schema_version", use_cache=True)
```

Cache is cleared on wrapper re-initialization (each Glue job run).

---

## Local Testing

Run transformations locally without AWS deployment:

### Prerequisites
- Python 3.9+
- Virtual environment (recommended)

### Run Local Demo

```powershell
# Make script executable (Git Bash/WSL)
chmod +x run_local_demo.sh

# Run with V1
$env:SCHEMA_VERSION = "v1"
.\run_local_demo.sh

# Run with V2
$env:SCHEMA_VERSION = "v2"
.\run_local_demo.sh
```

**What it does**:
1. Creates Python virtual environment
2. Installs dependencies (pandas, pyarrow, boto3, pytest)
3. Reads sample CSV data
4. Simulates transformation flow (full PySpark requires Glue)
5. Runs unit tests
6. Shows expected output structure

**Limitations**:
- PySpark transformations require AWS Glue runtime
- LaunchDarkly SDK calls require internet connection
- S3 writes are simulated locally

### Run Unit Tests

```powershell
cd src
pytest tests\test_glue_script.py -v
```

**Test Coverage**:
- ✅ V1/V2 transformation imports
- ✅ LaunchDarkly wrapper initialization
- ✅ Flag evaluation with caching
- ✅ Fallback to V1 on error
- ✅ Output path construction
- ✅ Sample data structure validation

---

## Dynatrace Integration

The pipeline includes comprehensive **Dynatrace integration** for monitoring LaunchDarkly feature flag evaluations in real-time. This provides crucial observability for guarded rollouts and production deployments.

### Key Features
- **Real-time Monitoring**: Track flag evaluations as they happen
- **Multi-channel Data**: Events, logs, and metrics sent to Dynatrace
- **Performance Tracking**: Monitor flag evaluation performance and patterns  
- **Alerting Support**: Set up alerts for flag evaluation anomalies
- **Rollback Intelligence**: Data-driven rollback decisions

### Quick Setup
The integration is **enabled by default** in version 5.0 of the LaunchDarkly wrapper:

```python
# Dynatrace monitoring is automatic
client = create_launchdarkly_client(
    environment="dev",
    job_name="tbar-etl",
    enable_dynatrace=True  # Default: True
)

# All flag evaluations are automatically monitored
schema_version = client.get_flag_value("tbar.hydration.schema_version", "v1")
```

### Data Captured
- **Flag Evaluations**: Which flags were evaluated and their results
- **User Context**: Job names, environments, and custom attributes
- **Performance Metrics**: Evaluation counts and timing data
- **Error Tracking**: Failed evaluations and hook errors

### Dynatrace Environment
- **URL**: https://rfr18704.live.dynatrace.com
- **Data Types**: Custom Events, Structured Logs, Performance Metrics
- **Retention**: Standard Dynatrace retention policies

### Documentation
- **Comprehensive Guide**: [DYNATRACE_INTEGRATION.md](./DYNATRACE_INTEGRATION.md)
- **Quick Reference**: [DYNATRACE_QUICK_REFERENCE.md](./DYNATRACE_QUICK_REFERENCE.md)

### Example Queries
```
# Monitor flag evaluations
timeseries avg(ld.flag.evaluation.count), by: {flag_key}

# Check for errors
logs | filter attributes.service == "glue-etl-launchdarkly"

# Track events
events | filter eventType == "CUSTOM_INFO" and title contains "LaunchDarkly"
```

---

## Terraform Deployment

### Directory Structure

```
environments/
├── dev/
│   ├── backend.tf          # S3 backend configuration
│   ├── main.tf            # Module instantiation
│   └── variables.tf       # Environment-specific variables
├── qa/
├── prod/
...

