# MBPP Workflow Implementation with Strands Agents + MCP

## Overview

This implementation integrates **Strands Agents SDK** with **MCP (Model Context Protocol)** to handle three distinct MBPP workflows plus normal RAG-based question answering:

1. **Complaint/Service Error Workflow** - For service complaints and system errors
2. **Text-Driven Incident Report Workflow** - For text-based incident reporting
3. **Image-Driven Incident Report Workflow** - For image-based incident reporting
4. **RAG Question Answering** - For general knowledge queries

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interface                          │
│              (WebSocket/HTTP Client)                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  API Gateway                                │
│           (WebSocket + HTTP API)                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              MBPP Agent (Lambda)                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Intent Detection                                     │  │
│  │  - Workflow trigger detection                        │  │
│  │  - RAG query detection                               │  │
│  └──────────────────┬───────────────────────────────────┘  │
│                     │                                       │
│       ┌─────────────┴─────────────┐                        │
│       ▼                           ▼                        │
│  ┌─────────────┐          ┌──────────────┐                │
│  │  Workflow   │          │  RAG Agent   │                │
│  │   Agent     │          │              │                │
│  │             │          │              │                │
│  │ - Complaint │          │ - Vector     │                │
│  │ - Text Inc. │          │   Search     │                │
│  │ - Image Inc.│          │ - Knowledge  │                │
│  └─────────────┘          │   Base       │                │
│                           └──────────────┘                │
└─────────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              External Services                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Bedrock    │  │  OpenSearch  │  │  DynamoDB    │     │
│  │   (Claude)   │  │  (Vectors)   │  │  (Tickets)   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. MBPP Workflow Tool (`mbpp_workflows.py`)

Implements the three workflow types as MCP tools:

```python
from strands_tools.mbpp_workflows import mbpp_workflow

# Detect workflow type
result = mbpp_workflow(
    action="detect",
    message="I want to report a fallen tree",
    has_image=False
)
# Returns: {"workflow_type": "text_incident"}

# Start workflow
result = mbpp_workflow(
    action="start",
    workflow_type="text_incident",
    workflow_id="unique-id"
)
```

**Key Features:**
- Automatic workflow type detection
- Step-by-step workflow management
- Ticket generation with reference numbers
- State persistence across steps

### 2. MBPP Agent (`mbpp_agent.py`)

Main orchestrator that routes requests to appropriate handlers:

```python
from mbpp_agent import MBPPAgent

agent = MBPPAgent()

# Process message
result = agent.process_message(
    message="MBPP website is down",
    session_id="session-123",
    has_image=False
)
```

**Capabilities:**
- Intent detection (workflow vs RAG)
- Session management
- Workflow state tracking
- RAG query processing with vector search

### 3. Workflow Definitions

#### Flow 1: Complaint/Service Error Workflow

```
Step 1: Initial Detection & Triage
  ↓
Step 2: Issue Description
  ↓
Step 3: Verification Check
  ↓
Step 4: Ticket Logging
  ↓
Step 5: Additional Confirmation
  ↓
Step 6: Ticket Confirmation
```

**Example Interaction:**
```
User: "MBPP website is down"
Bot: "Would you like to report an incident?"
User: "Not an incident (Service Complaint)"
Bot: "Could you please describe the issue?"
User: "MBPP website down now, cannot access"
Bot: "Can you confirm if your internet connection is working?"
User: "Yes"
Bot: "Logging the ticket..."
Bot: "Ticket logged: 20239/09/25"
```

#### Flow 2: Text-Driven Incident Report

```
Step 1: Incident Initiation
  ↓
Step 2: User Submits Information
  ↓
Step 3: Incident Confirmation
  ↓
Step 4: Location Collection
  ↓
Step 5: Hazard Verification
  ↓
Step 6: Ticket Processing
  ↓
Step 7: Final Confirmation
```

**Example Interaction:**
```
User: "I want to report an incident"
Bot: "Please share an image, location and describe what happened"
User: "Fallen tree blocking main road at Jalan Terapung"
Bot: "Can you confirm you would like to report an incident?"
User: "Yes, report an incident"
Bot: "Where is this? Share location or type address"
User: [Shares GPS location]
Bot: "Could you confirm if it's blocking the road?"
User: "Yes"
Bot: "Logging the ticket..."
Bot: "Ticket logged: 20368/09/25"
```

#### Flow 3: Image-Driven Incident Report

```
Step 1: Image Upload & Detection
  ↓
Step 2: Incident Confirmation & Description
  ↓
Step 3: User Provides Details
  ↓
Step 4: Hazard Verification
  ↓
Step 5: Ticket Processing
  ↓
Step 6: Final Confirmation
```

**Example Interaction:**
```
User: [Uploads image of fallen tree]
Bot: "Image detected. Can you confirm you would like to report an incident?"
User: "Yes, report an incident"
Bot: "Please describe what happened and tell us the location"
User: "Fallen tree blocking main road at Jalan Batu Feringghi"
Bot: "Could you confirm if it's blocking the road?"
User: "Yes"
Bot: "Logging the ticket..."
Bot: "Ticket logged: 20368/09/25"
```

## RAG Integration

For non-workflow queries, the system uses RAG (Retrieval Augmented Generation):

```python
# RAG Query Flow
User: "What are MBPP's operating hours?"
  ↓
Agent detects RAG query
  ↓
Search OpenSearch vector database
  ↓
Retrieve relevant documents
  ↓
Build context from search results
  ↓
Generate answer using Claude + context
  ↓
Return answer to user
```

## Deployment

### Prerequisites

```bash
# Install dependencies
pip install -r requirements-strands.txt

# Configure AWS credentials
aws configure --profile test
```

### Deploy with CDK

```bash
cd cdk

# Bootstrap (first time only)
cdk bootstrap --profile test

# Deploy workflow stack
cdk deploy MBPPWorkflowStack --profile test
```

### Environment Variables

```bash
BEDROCK_REGION=us-east-1
OPENSEARCH_INDEX=mbpp-documents
LOG_LEVEL=INFO
```

## API Usage

### Process Message

```bash
POST /process
Content-Type: application/json

{
  "message": "I want to report a fallen tree",
  "sessionId": "session-123",
  "hasImage": false,
  "imageData": null,
  "location": null
}
```

**Response:**
```json
{
  "type": "workflow",
  "workflow_type": "text_incident",
  "workflow_id": "uuid-here",
  "response": "Please share an image, location and describe what happened",
  "session_id": "session-123"
}
```

### Get Workflow Status

```bash
GET /workflow/status?sessionId=session-123
```

**Response:**
```json
{
  "workflow_id": "uuid-here",
  "workflow_type": "text_incident",
  "current_step": 3,
  "status": "in_progress"
}
```

## Testing

### Test Complaint Workflow

```python
import requests

# Start complaint
response = requests.post('https://api-endpoint/process', json={
    "message": "MBPP website is down",
    "sessionId": "test-1",
    "hasImage": False
})

print(response.json())
```

### Test Text Incident Workflow

```python
# Start incident report
response = requests.post('https://api-endpoint/process', json={
    "message": "I want to report a fallen tree",
    "sessionId": "test-2",
    "hasImage": False
})

print(response.json())
```

### Test RAG Query

```python
# Ask general question
response = requests.post('https://api-endpoint/process', json={
    "message": "What are MBPP's operating hours?",
    "sessionId": "test-3",
    "hasImage": False
})

print(response.json())
```

## Workflow State Management

The system maintains workflow state across multiple interactions:

```python
# Session-based state tracking
active_workflows = {
    "session-123": {
        "workflow_id": "uuid",
        "workflow_type": "text_incident",
        "current_step": 3,
        "data": {
            "description": "Fallen tree",
            "location": "Jalan Terapung",
            "hazard_confirmation": "Yes"
        }
    }
}
```

## Error Handling

```python
try:
    result = agent.process_message(message, session_id)
except WorkflowError as e:
    return {"error": "workflow_error", "message": str(e)}
except RAGError as e:
    return {"error": "rag_error", "message": str(e)}
except Exception as e:
    return {"error": "internal_error", "message": str(e)}
```

## Monitoring

### CloudWatch Logs

```bash
# View workflow agent logs
aws logs tail /aws/lambda/MBPPWorkflowAgent --follow --profile test
```

### Metrics

- Workflow completion rate
- Average workflow duration
- RAG query response time
- Error rates by workflow type

## Best Practices

1. **Session Management**: Always use unique session IDs
2. **Workflow Cleanup**: Completed workflows are automatically cleaned up
3. **Error Recovery**: Failed workflows can be restarted from the beginning
4. **Context Preservation**: All workflow data is preserved across steps
5. **RAG Optimization**: Vector search is only performed when needed

## Troubleshooting

### Workflow Not Starting

```bash
# Check if workflow type is detected correctly
result = mbpp_workflow(action="detect", message="your message")
print(result["workflow_type"])
```

### RAG Not Finding Documents

```bash
# Verify OpenSearch index
aws opensearch describe-domain --domain-name mbpp-docs --profile test

# Check if documents are indexed
# Use OpenSearch dashboard to verify
```

### Lambda Timeout

```bash
# Increase timeout in CDK stack
timeout=Duration.seconds(300)  # 5 minutes
```

## Future Enhancements

1. **Multi-language Support**: Add support for Malay and other languages
2. **Image Analysis**: Use Bedrock Vision for automatic incident categorization
3. **Location Services**: Integrate with mapping services for better location handling
4. **Notification System**: Send SMS/email notifications for ticket updates
5. **Analytics Dashboard**: Real-time workflow analytics and reporting

## References

- [Strands Agents Documentation](https://strandsagents.com/latest/documentation/)
- [MCP Protocol](https://modelcontextprotocol.io/)
- [AWS Bedrock](https://aws.amazon.com/bedrock/)
- [OpenSearch Vector Search](https://opensearch.org/docs/latest/search-plugins/knn/)

## Support

For issues or questions:
- Check CloudWatch logs
- Review workflow state in DynamoDB
- Verify Bedrock model access
- Test with simple queries first

---

**Implementation Status**: ✅ Complete
**Last Updated**: 2025-01-03
**Version**: 1.0.0
