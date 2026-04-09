import requests
import json
import os

# Define the target API endpoint for Prisma AIRS
url = "https://api.sase.paloaltonetworks.com/ai-red-teaming/mgmt-plane/v1/target"

# Construct the corrected payload
payload_dict = {
    "name": "IT Assistant (REST API)",
    "target_type": "AGENT",
    "connection_type": "CUSTOM",
    "response_mode": "REST",
    "api_endpoint_type": "NETWORK_BROKER",
    "session_supported": True,
    "extra_info": {
        "response_key": "response"
    },
    "connection_params": {
        "api_endpoint": "https://agent.matthewwan.dev:8443/chat/public",
        "request_json": {
            "text": "{INPUT}"
        },
        "response_json": {
            "response": "{RESPONSE}"
        },
        "response_key": "response",
        "request_headers": {
            "Content-Type": "application/json"
        },
        # multi_turn_config is correctly nested here
        "multi_turn_config": {
            "type": "stateful",
            "response_id_field": "conversation_id",
            "request_id_field": "conversation_id"
        }
    },
    "network_broker_channel_uuid": "166a9a38-ee68-4277-9531-7256009818f6",
    "description": "Managed by GitHub Actions CI/CD",
    "target_metadata": {
        "rate_limit_enabled": False,
        "multi_turn": True # Explicitly enabled to match session_supported: True
    },
    "target_background": {
        "industry": "IT",
        "use_case": "IT Support"
    }
}

# Convert dictionary to JSON string
payload = json.dumps(payload_dict)

# Retrieve your bearer token from an environment variable for security
# Make sure to set this in your environment before running: export PRISMA_TOKEN="your_actual_token"
bearer_token = os.getenv("PRISMA_TOKEN", "<FALLBACK_TOKEN_IF_NEEDED>")

# Define the headers
headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'Authorization': f'Bearer {bearer_token}'
}

# Execute the POST request
try:
    response = requests.request("POST", url, headers=headers, data=payload)
    
    # Raise an exception for bad status codes (4xx or 5xx)
    response.raise_for_status()
    
    print("Target registered successfully!")
    print(response.json())

except requests.exceptions.HTTPError as errh:
    print(f"HTTP Error: {errh}")
    print(f"Response Details: {response.text}")
except requests.exceptions.RequestException as err:
    print(f"Connection Error: {err}")
