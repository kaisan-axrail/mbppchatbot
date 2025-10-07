# MBPP Workflows - Quick Start Guide

## 🚀 Quick Deploy

### 1. Test Locally (No AWS Required)

```bash
# Run the test suite
python test_mbpp_workflows.py
```

This will test all three workflows without requiring AWS credentials.

### 2. Deploy to AWS

```bash
cd cdk

# Install dependencies
pip install -r requirements.txt

# Bootstrap CDK (first time only)
cdk bootstrap --profile test

# Deploy workflow stack
cdk deploy MBPPWorkflowStack --profile test
```

### 3. Get API Endpoint

```bash
# After deployment, get the endpoint
aws cloudformation describe-stacks \
  --stack-name MBPPWorkflowStack \
  --profile test \
  --query 'Stacks[0].Outputs[?OutputKey==`WorkflowApiEndpoint`].OutputValue' \
  --output text
```

## 📝 Usage Examples

### Example 1: Service Complaint

```bash
curl -X POST https://your-api-endpoint/process \
  -H "Content-Type: application/json" \
  -d '{
    "message": "MBPP website is down",
    "sessionId": "user-123",
    "hasImage": false
  }'
```

**Expected Flow:**
1. Bot: "Would you like to report an incident?"
2. User: "Not an incident (Service Complaint)"
3. Bot: "Could you please describe the issue?"
4. User: "MBPP website down now, cannot access"
5. Bot: "Can you confirm if your internet connection is working?"
6. User: "Yes"
7. Bot: "Ticket logged: 20239/09/25"

### Example 2: Text Incident Report

```bash
curl -X POST https://your-api-endpoint/process \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I want to report a fallen tree blocking the road",
    "sessionId": "user-456",
    "hasImage": false
  }'
```

**Expected Flow:**
1. Bot: "Please share an image, location and describe what happened"
2. User: "Fallen tree at Jalan Terapung"
3. Bot: "Can you confirm you would like to report an incident?"
4. User: "Yes, report an incident"
5. Bot: "Where is this? Share location or type address"
6. User: [Shares GPS location]
7. Bot: "Could you confirm if it's blocking the road?"
8. User: "Yes"
9. Bot: "Ticket logged: 20368/09/25"

### Example 3: Image Incident Report

```bash
curl -X POST https://your-api-endpoint/process \
  -H "Content-Type: application/json" \
  -d '{
    "message": "",
    "sessionId": "user-789",
    "hasImage": true,
    "imageData": "base64_encoded_image_here"
  }'
```

**Expected Flow:**
1. Bot: "Image detected. Can you confirm you would like to report an incident?"
2. User: "Yes, report an incident"
3. Bot: "Please describe what happened and tell us the location"
4. User: "Fallen tree blocking main road at Jalan Batu Feringghi"
5. Bot: "Could you confirm if it's blocking the road?"
6. User: "Yes"
7. Bot: "Ticket logged: 20368/09/25"

### Example 4: RAG Query

```bash
curl -X POST https://your-api-endpoint/process \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are MBPP operating hours?",
    "sessionId": "user-999",
    "hasImage": false
  }'
```

**Expected Response:**
```json
{
  "type": "rag",
  "response": "MBPP operates from 8:00 AM to 5:00 PM, Monday to Friday...",
  "session_id": "user-999"
}
```

## 🔍 Check Workflow Status

```bash
curl -X GET "https://your-api-endpoint/workflow/status?sessionId=user-123"
```

**Response:**
```json
{
  "workflow_id": "uuid-here",
  "workflow_type": "complaint",
  "current_step": 3,
  "status": "in_progress",
  "data": {
    "description": "MBPP website down",
    "verification": "Yes"
  }
}
```

## 🧪 Testing Workflow Detection

```python
from strands_tools.mbpp_workflows import mbpp_workflow

# Test 1: Complaint detection
result = mbpp_workflow(
    action="detect",
    message="MBPP website is down",
    has_image=False
)
print(result)  # {"workflow_type": "complaint"}

# Test 2: Text incident detection
result = mbpp_workflow(
    action="detect",
    message="I want to report a fallen tree",
    has_image=False
)
print(result)  # {"workflow_type": "text_incident"}

# Test 3: Image incident detection
result = mbpp_workflow(
    action="detect",
    message="",
    has_image=True
)
print(result)  # {"workflow_type": "image_incident"}

# Test 4: RAG query detection
result = mbpp_workflow(
    action="detect",
    message="What are MBPP's operating hours?",
    has_image=False
)
print(result)  # {"workflow_type": "general"}
```

## 📊 Workflow Types Summary

| Workflow Type | Trigger | Steps | Output |
|--------------|---------|-------|--------|
| **Complaint** | Service/system error keywords | 6 steps | Service complaint ticket |
| **Text Incident** | Incident keywords without image | 7 steps | Incident report ticket |
| **Image Incident** | Image upload with incident keywords | 6 steps | Incident report ticket |
| **RAG Query** | General questions | 1 step | Knowledge-based answer |

## 🔧 Configuration

### Environment Variables

```bash
# Required
export BEDROCK_REGION=us-east-1
export OPENSEARCH_INDEX=mbpp-documents

# Optional
export LOG_LEVEL=INFO
export WORKFLOW_TIMEOUT=300
```

### CDK Context

```json
{
  "bedrock_region": "us-east-1",
  "opensearch_domain": "mbpp-docs",
  "lambda_timeout": 300,
  "lambda_memory": 1024
}
```

## 🐛 Troubleshooting

### Issue: Workflow not detected

**Solution:**
```python
# Check detection logic
result = mbpp_workflow(action="detect", message="your message")
print(f"Detected: {result['workflow_type']}")
```

### Issue: Lambda timeout

**Solution:**
```python
# Increase timeout in CDK stack
timeout=Duration.seconds(300)  # 5 minutes
```

### Issue: RAG not finding documents

**Solution:**
```bash
# Verify OpenSearch index exists
aws opensearch describe-domain --domain-name mbpp-docs

# Check if documents are indexed
# Use OpenSearch dashboard
```

## 📈 Monitoring

### CloudWatch Logs

```bash
# View logs
aws logs tail /aws/lambda/MBPPWorkflowAgent --follow

# Filter by workflow type
aws logs filter-log-events \
  --log-group-name /aws/lambda/MBPPWorkflowAgent \
  --filter-pattern "workflow_type=complaint"
```

### Metrics

```bash
# Get workflow completion rate
aws cloudwatch get-metric-statistics \
  --namespace MBPP/Workflows \
  --metric-name CompletionRate \
  --start-time 2025-01-01T00:00:00Z \
  --end-time 2025-01-03T00:00:00Z \
  --period 3600 \
  --statistics Average
```

## 🎯 Next Steps

1. ✅ Test workflows locally
2. ✅ Deploy to AWS
3. ✅ Test with real API
4. 🔄 Integrate with WebSocket
5. 🔄 Add OpenSearch RAG
6. 🔄 Implement notifications
7. 🔄 Add analytics dashboard

## 📚 Additional Resources

- [Full Implementation Guide](./MBPP_WORKFLOW_IMPLEMENTATION.md)
- [Strands Agents Docs](https://strandsagents.com/latest/documentation/)
- [MCP Protocol](https://modelcontextprotocol.io/)
- [AWS Bedrock](https://aws.amazon.com/bedrock/)

## 💡 Tips

1. **Session Management**: Always use unique session IDs for each user
2. **Error Handling**: Workflows can be restarted if they fail
3. **Context Preservation**: All data is preserved across workflow steps
4. **RAG Optimization**: Vector search only runs when needed
5. **Testing**: Use the test script before deploying to production

---

**Ready to go!** 🚀

Run `python test_mbpp_workflows.py` to get started!
