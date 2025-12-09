# How Data Flows from Your Code to Dynatrace

## Architecture Overview

The Dynatrace OneAgent SDK does **NOT** connect directly to Dynatrace. Instead, it uses a **local agent** (OneAgent) installed on your server.

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Your Python Application                  │
│                                                             │
│  1. oneagent.initialize()                                   │
│     ↓                                                        │
│  2. Hook creates trace spans via OneAgent SDK               │
│     ↓                                                        │
│  3. SDK sends data to → OneAgent (local process)            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              Dynatrace OneAgent (Local Process)             │
│                                                             │
│  - Runs as a background service on your host               │
│  - Pre-configured with Dynatrace endpoint                   │
│  - Collects trace data from SDK                             │
│  - Buffers and batches data                                 │
│  - Sends to Dynatrace server                                │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              Dynatrace Server (Cloud/Managed)                │
│                                                             │
│  Endpoint: https://[your-environment].live.dynatrace.com   │
│  or: https://[your-server]/e/[tenant-id]/api/v2/...        │
│                                                             │
│  - Receives trace data                                       │
│  - Processes and stores                                      │
│  - Makes available in Dynatrace UI                          │
└─────────────────────────────────────────────────────────────┘
```

## Key Points

### 1. **No Endpoint in Your Application Code**

When you call `oneagent.initialize()`, the SDK:
- **Automatically detects** if OneAgent is running on the host
- **Connects to OneAgent** via local inter-process communication (IPC)
- **Does NOT** connect directly to Dynatrace server

### 2. **OneAgent is Pre-Configured**

The Dynatrace OneAgent installed on your server is configured with:
- **Dynatrace endpoint URL** (set during OneAgent installation)
- **Authentication token** (embedded in OneAgent)
- **Connection settings** (SSL, proxy, etc.)

### 3. **Where Endpoint is Configured**

The endpoint is configured in **OneAgent**, not in your Python code:

#### During OneAgent Installation:
```bash
# OneAgent installer configures the endpoint
./oneagentctl.sh install \
  --set-host-group=production \
  --set-server=https://your-environment.live.dynatrace.com
```

#### Or via Environment Variables (if using OneAgent SDK without full OneAgent):
```bash
# These are read by OneAgent, not your Python code
export DT_TENANT=your-tenant-id
export DT_TENANT_TOKEN=your-token
export DT_CONNECTION_POINT=https://your-environment.live.dynatrace.com
```

## Code Flow Example

```python
# Step 1: Initialize SDK (connects to local OneAgent)
import oneagent
oneagent.initialize()  # ← Connects to OneAgent via IPC, NOT to Dynatrace server

# Step 2: Create hook
from lddynatrace.tracing import Hook
dt_hook = Hook()

# Step 3: Use LaunchDarkly
from ldclient import LDClient, Config
ld_client = LDClient(config=Config(sdk_key='...', hooks=[dt_hook]))

# Step 4: Evaluate flag
flag_value = ld_client.variation('test-lpl', context, False)
# ↓
# Hook.before_evaluation() creates trace span
# ↓
# SDK sends span data to OneAgent (local)
# ↓
# OneAgent buffers and sends to Dynatrace server
# ↓
# Data appears in Dynatrace UI
```

## How to Verify Connection

### 1. Check if OneAgent is Running
```bash
# On Linux/Mac
ps aux | grep oneagent

# Check OneAgent status
/opt/dynatrace/oneagent/agent/bin/oneagentctl.sh status
```

### 2. Check OneAgent Configuration
```bash
# View OneAgent configuration
cat /opt/dynatrace/oneagent/agent/conf/oneagent.conf

# Look for:
# - server (Dynatrace endpoint)
# - tenant (tenant ID)
# - tenanttoken (authentication token)
```

### 3. Check SDK Connection to OneAgent
```python
import oneagent

sdk = oneagent.get_sdk()
if sdk is None:
    print("OneAgent SDK not initialized - OneAgent may not be running")
else:
    print("OneAgent SDK connected successfully")
```

## Important Notes

### ✅ **What You DON'T Need:**
- ❌ No endpoint URL in your Python code
- ❌ No API token in your Python code
- ❌ No direct HTTP calls to Dynatrace
- ❌ No network configuration in your application

### ✅ **What You DO Need:**
- ✅ Dynatrace OneAgent installed and running on your host
- ✅ OneAgent configured with Dynatrace endpoint (done during installation)
- ✅ `oneagent.initialize()` in your code (connects to local OneAgent)

## If OneAgent is NOT Installed

If OneAgent is not installed, the SDK will:
- Still initialize successfully (`oneagent.initialize()` returns True)
- But tracing calls will **gracefully no-op** (do nothing)
- No errors will be thrown
- No data will be sent to Dynatrace

This is why the hook code has try/except blocks - it handles the case where OneAgent might not be available.

## Alternative: Direct API Integration (Not Recommended)

If you want to send data directly to Dynatrace API (bypassing OneAgent), you would need:

```python
# NOT how the OneAgent SDK works - this is for reference only
import requests

DYNATRACE_ENDPOINT = "https://your-environment.live.dynatrace.com/api/v2/metrics/ingest"
DYNATRACE_TOKEN = "your-api-token"

headers = {
    "Authorization": f"Api-Token {DYNATRACE_TOKEN}",
    "Content-Type": "text/plain"
}

# Send metrics directly (not recommended - use OneAgent instead)
requests.post(DYNATRACE_ENDPOINT, headers=headers, data=metric_data)
```

**However, the OneAgent SDK does NOT work this way.** It always goes through OneAgent.

## Summary

1. **Your Code** → Calls OneAgent SDK (`oneagent.initialize()`, `trace_custom_service()`)
2. **OneAgent SDK** → Sends data to **local OneAgent process** (via IPC)
3. **OneAgent** → Buffers, batches, and sends to **Dynatrace server** (pre-configured endpoint)
4. **Dynatrace Server** → Processes and displays in UI

The endpoint is configured in **OneAgent**, not in your Python application code.

