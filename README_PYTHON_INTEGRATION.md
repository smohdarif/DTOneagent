# Using Dynatrace Tracing Hook with LaunchDarkly in Python

This guide shows you how to integrate Dynatrace OneAgent SDK tracing with LaunchDarkly feature flags in your Python application.

## Prerequisites

1. **Dynatrace OneAgent** must be installed and running on your server
2. **LaunchDarkly SDK Key** - Get this from your LaunchDarkly dashboard
3. **Python 3.7+**

## Installation

### Step 1: Install Required Packages

```bash
# Install LaunchDarkly SDK
pip install launchdarkly-server-sdk

# Install Dynatrace OneAgent SDK
pip install oneagent-sdk

# Install the Dynatrace LaunchDarkly integration hook
pip install git+https://github.com/tarqd/python-server-sdk-dynatrace-one.git
```

Or add to your `requirements.txt`:
```
launchdarkly-server-sdk>=9.0.0
oneagent-sdk>=1.0.0
```

Then install the hook from GitHub:
```bash
pip install git+https://github.com/tarqd/python-server-sdk-dynatrace-one.git
```

## Basic Usage

### 1. Initialize Dynatrace OneAgent SDK

**Important:** This MUST be done before creating the LaunchDarkly client.

```python
import oneagent

# Initialize OneAgent SDK
oneagent.initialize()
```

### 2. Create the Tracing Hook

```python
from lddynatrace.tracing import Hook, HookOptions

# Optional: Configure hook options
hook_options = HookOptions(
    include_value=True,  # Include flag values in traces (default: False)
)

# Create the hook
dt_hook = Hook(options=hook_options)
```

### 3. Initialize LaunchDarkly with the Hook

```python
from ldclient import LDClient, Config
import os

sdk_key = os.getenv('LAUNCHDARKLY_SDK_KEY')

ld_config = Config(
    sdk_key=sdk_key,
    hooks=[dt_hook]  # Add the hook here
)

ld_client = LDClient(config=ld_config)
```

### 4. Use LaunchDarkly Normally

```python
from ldclient import Context

# Create a context (user)
context = Context.builder('user-123')\
    .set('email', 'user@example.com')\
    .build()

# Evaluate flags - tracing happens automatically!
flag_value = ld_client.variation('my-feature-flag', context, False)
```

## What Gets Traced?

Each feature flag evaluation automatically creates a Dynatrace trace span with:

### Before Evaluation (in `before_evaluation`):
- `feature_flag.key` - The flag key being evaluated
- `feature_flag.context.id` - The user/context ID
- `feature_flag.provider.name` - Always "LaunchDarkly"

### After Evaluation (in `after_evaluation`):
- `feature_flag.result.variationIndex` - Which variation was returned
- `feature_flag.result.reason` - Why this value was returned (e.g., "OFF", "TARGET_MATCH", "FALLTHROUGH")
- `feature_flag.result.reason.inExperiment` - Whether this evaluation is part of an experiment
- `feature_flag.result.value` - The actual flag value (if `include_value=True`)

## Configuration Options

### HookOptions

```python
HookOptions(
    include_value=False,  # Set to True to include flag values in traces
)
```

**Note:** `include_variant` is deprecated, use `include_value` instead.

## Example: Flask Application

```python
from flask import Flask
from ldclient import LDClient, Config, Context
from lddynatrace.tracing import Hook
import oneagent
import os

# Initialize Dynatrace
oneagent.initialize()

# Create hook
dt_hook = Hook()

# Initialize LaunchDarkly
ld_client = LDClient(
    config=Config(
        sdk_key=os.getenv('LAUNCHDARKLY_SDK_KEY'),
        hooks=[dt_hook]
    )
)

app = Flask(__name__)

@app.route('/api/users')
def get_users():
    # Create context from request
    user_id = request.headers.get('X-User-ID', 'anonymous')
    context = Context.builder(user_id).build()
    
    # Evaluate flag - automatically traced!
    show_new_ui = ld_client.variation('new-user-interface', context, False)
    
    if show_new_ui:
        return {'ui': 'new'}
    else:
        return {'ui': 'old'}
```

## Example: Django Application

```python
# settings.py
import oneagent
from ldclient import LDClient, Config
from lddynatrace.tracing import Hook
import os

# Initialize Dynatrace
oneagent.initialize()

# Create hook
dt_hook = Hook()

# Initialize LaunchDarkly
LD_CLIENT = LDClient(
    config=Config(
        sdk_key=os.getenv('LAUNCHDARKLY_SDK_KEY'),
        hooks=[dt_hook]
    )
)

# views.py
from django.http import JsonResponse
from ldclient import Context
from django.conf import settings

def my_view(request):
    # Create context from user
    context = Context.builder(str(request.user.id)).build()
    
    # Evaluate flag - automatically traced!
    flag_value = settings.LD_CLIENT.variation('my-flag', context, False)
    
    return JsonResponse({'flag': flag_value})
```

## Viewing Traces in Dynatrace

1. Open Dynatrace
2. Go to **Distributed traces** or **Service flow**
3. Look for service name: **"LaunchDarkly"**
4. Each flag evaluation appears as a custom service call
5. Click on a trace to see:
   - Flag key
   - User/context ID
   - Evaluation result
   - Reason for the result
   - Performance metrics

## Adding Default Value Tracking

As mentioned in the note, you can enhance the hook to track default values. You would need to modify the hook code or create a custom hook that extends the base hook:

```python
from lddynatrace.tracing import Hook
import json

class EnhancedHook(Hook):
    def after_evaluation(self, series_context, data, detail):
        # Call parent implementation
        result = super().after_evaluation(series_context, data, detail)
        
        # Add default value tracking
        if hasattr(detail, 'default_value') and detail.default_value is not None:
            from lddynatrace.tracing import oneagent
            sdk = oneagent.get_sdk()
            sdk.add_custom_request_attribute(
                'feature_flag.result.default',
                json.dumps(detail.default_value)
            )
        
        return result
```

## Troubleshooting

### Traces Not Appearing

1. **Check OneAgent is running:**
   ```python
   import oneagent
   sdk = oneagent.get_sdk()
   print(f"OneAgent initialized: {sdk is not None}")
   ```

2. **Check LaunchDarkly initialization:**
   ```python
   ld_client.wait_for_initialization(timeout=5)
   print(f"LD initialized: {ld_client.is_initialized()}")
   ```

3. **Check hook is registered:**
   ```python
   print(f"Hooks: {ld_client._hooks}")
   ```

### Errors Are Silently Ignored

The hook implementation includes error handling that logs warnings but doesn't break your application. Check your Python warnings/logs for messages like:
```
Warning: Error starting Dynatrace tracer: ...
```

## Cleanup

Always clean up when shutting down:

```python
ld_client.close()
oneagent.shutdown()
```

## Additional Resources

- [LaunchDarkly Python SDK Documentation](https://docs.launchdarkly.com/sdk/server-side/python)
- [Dynatrace OneAgent SDK for Python](https://github.com/Dynatrace/OneAgent-SDK-for-Python)
- [OpenTelemetry Feature Flag Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/feature-flags/)

