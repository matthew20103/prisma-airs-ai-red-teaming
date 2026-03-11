name: 1. Prisma AIRS - Create Target

on:
  workflow_dispatch:
    inputs:
      target_name:
        description: 'Name of AI Agent'
        required: true
      description:
        description: 'Description'
        required: false
      target_type:
        description: 'Target Type'
        required: true
        type: choice
        options:
          - APPLICATION
          - AGENT
          - MODEL
        default: 'AGENT'
      connection_type:
        description: 'Connection Type'
        required: true
        type: choice
        options:
          - REST
          - STREAMING
        default: 'REST'
      api_endpoint_type:
        description: 'API Endpoint Type'
        required: true
        type: choice
        options:
          - PUBLIC
          - PRIVATE
          - NETWORK_BROKER
        default: 'PUBLIC'
      nb_channel_uuid:
        description: 'NB Channel UUID (Required if using NETWORK_BROKER)'
        required: false
      api_endpoint:
        description: 'URL of the AI Endpoint'
        required: true
      session_supported:
        description: 'Session Supported?'
        required: true
        type: choice
        options:
          - 'false'
          - 'true'
        default: 'false'
      request_headers:
        description: 'Request Headers (JSON)'
        required: false
        default: '{"Content-Type": "application/json"}'
      request_json:
        description: 'Request Payload (JSON containing {INPUT})'
        required: true
        default: '{"prompt": "{INPUT}"}'
      response_json:
        description: 'Response Payload (JSON containing {RESPONSE})'
        required: true
        default: '{"reply": "{RESPONSE}"}'
      multi_turn_config:
        description: 'Multi-Turn Session Configuration (JSON)'
        required: false
      target_rate_limit:
        description: 'Target Rate Limit (Integer)'
        required: false
      target_background:
        description: 'Target Background (JSON)'
        required: false
      additional_context:
        description: 'Additional Context (JSON)'
        required: false

jobs:
  setup-target:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - run: pip install requests
      - name: Create and Profile Target
        env:
          PRISMA_CLIENT_ID: "${{ secrets.PRISMA_CLIENT_ID }}"
          PRISMA_CLIENT_SECRET: "${{ secrets.PRISMA_CLIENT_SECRET }}"
          PRISMA_TSG_ID: "${{ secrets.PRISMA_TSG_ID }}"
          TARGET_NAME: "${{ inputs.target_name }}"
          DESCRIPTION: "${{ inputs.description }}"
          TARGET_TYPE: "${{ inputs.target_type }}"
          CONNECTION_TYPE: "${{ inputs.connection_type }}"
          API_ENDPOINT_TYPE: "${{ inputs.api_endpoint_type }}"
          NB_CHANNEL_UUID: "${{ inputs.nb_channel_uuid }}"
          MODEL_ENDPOINT: "${{ inputs.api_endpoint }}"
          SESSION_SUPPORTED: "${{ inputs.session_supported }}"
          REQUEST_HEADERS: |
            ${{ inputs.request_headers }}
          REQUEST_JSON: |
            ${{ inputs.request_json }}
          RESPONSE_JSON: |
            ${{ inputs.response_json }}
          MULTI_TURN_CONFIG: |
            ${{ inputs.multi_turn_config }}
          TARGET_RATE_LIMIT: "${{ inputs.target_rate_limit }}"
          TARGET_BACKGROUND: |
            ${{ inputs.target_background }}
          ADDITIONAL_CONTEXT: |
            ${{ inputs.additional_context }}
        run: python .github/scripts/create_target.py
