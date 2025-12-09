"""
Example: Using Dynatrace OneAgent SDK with LaunchDarkly in Python

This example shows how to integrate the Dynatrace tracing hook with LaunchDarkly
to automatically trace feature flag evaluations in Dynatrace.
"""

import os
import oneagent
from ldclient import LDClient, Config
from ldclient.config import Config
from lddynatrace.tracing import Hook, HookOptions

# Step 1: Initialize Dynatrace OneAgent SDK
# This MUST be done before creating the LaunchDarkly client
# 
# IMPORTANT: oneagent.initialize() does NOT connect directly to Dynatrace server!
# Instead, it connects to the Dynatrace OneAgent process running locally on your host.
# The OneAgent (installed separately) is pre-configured with the Dynatrace endpoint.
# 
# Data Flow:
#   1. Your code → OneAgent SDK (via oneagent.initialize())
#   2. OneAgent SDK → Local OneAgent process (via IPC)
#   3. OneAgent → Dynatrace server (pre-configured endpoint)
#   4. Dynatrace server → Dynatrace UI
#
# The endpoint is configured in OneAgent, NOT in your Python code!
oneagent.initialize()


# Step 2: Create the Dynatrace tracing hook
# Configure options if needed
hook_options = HookOptions(
    include_value=True,  # Set to True to include flag values in traces
)

dt_hook = Hook(options=hook_options)


# Step 3: Initialize LaunchDarkly client with the hook
# Replace 'YOUR_SDK_KEY' with your actual LaunchDarkly SDK key
sdk_key = os.getenv('LAUNCHDARKLY_SDK_KEY', 'YOUR_SDK_KEY')

ld_config = Config(
    sdk_key=sdk_key,
    # Add the hook to the LaunchDarkly configuration
    hooks=[dt_hook]
)

ld_client = LDClient(config=ld_config)


# Step 4: Use LaunchDarkly as normal - tracing happens automatically!
def example_usage():
    """Example function showing how to use LaunchDarkly with automatic tracing."""
    
    from ldclient import Context
    
    # Create a user context
    context = Context.builder('user-123')\
        .set('email', 'user@example.com')\
        .set('name', 'John Doe')\
        .build()
    
    # Evaluate a feature flag
    # The Dynatrace hook will automatically:
    # - Create a trace span before evaluation
    # - Add flag metadata (key, context ID, provider)
    # - Add result metadata (variation index, reason, value)
    # - End the span after evaluation
    flag_value = ld_client.variation('test-lpl', context, False)
    
    print(f"Flag value: {flag_value}")
    
    # All flag evaluations are now automatically traced in Dynatrace!
    # You can see them in Dynatrace under:
    # - Service: "LaunchDarkly"
    # - Custom attributes: feature_flag.key, feature_flag.context.id, etc.


def example_with_multiple_flags():
    """Example showing multiple flag evaluations."""
    
    from ldclient import Context
    
    context = Context.builder('user-456')\
        .set('email', 'another@example.com')\
        .build()
    
    # Each flag evaluation gets its own trace span
    flag1 = ld_client.variation('feature-new-ui', context, False)
    flag2 = ld_client.variation('feature-payment', context, True)
    flag3 = ld_client.string_variation('feature-theme', context, 'light')
    
    print(f"UI Feature: {flag1}")
    print(f"Payment Feature: {flag2}")
    print(f"Theme: {flag3}")


def example_with_error_handling():
    """Example showing that tracing works even with errors."""
    
    from ldclient import Context
    
    context = Context.builder('user-789').build()
    
    try:
        # Even if the flag evaluation fails, the trace will be created
        flag_value = ld_client.variation('some-flag', context, False)
    except Exception as e:
        # The trace will still be recorded with error information
        print(f"Error evaluating flag: {e}")


# Step 5: Cleanup when shutting down
def cleanup():
    """Clean up resources."""
    ld_client.close()
    oneagent.shutdown()


if __name__ == '__main__':
    # Wait for LaunchDarkly to initialize
    ld_client.wait_for_initialization(timeout=5)
    
    # Run examples
    example_usage()
    example_with_multiple_flags()
    example_with_error_handling()
    
    # Cleanup
    cleanup()

