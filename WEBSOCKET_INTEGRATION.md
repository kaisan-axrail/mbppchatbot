# WebSocket Integration with MBPP Workflows

## ✅ Integration Complete

The MBPP Workflow system is now integrated into the existing WebSocket handler. The frontend chat interface will automatically use workflows when users trigger them.

## 🔄 How It Works

```
User sends message via WebSocket
         ↓
WebSocket Handler receives message
         ↓
MBPP Agent checks if it's a workflow trigger
         ↓
    ┌────┴────┐
    ▼         ▼
Workflow   Nova Pro
 Agent      Engine
    │         │
    └────┬────┘
         ↓
Response sent back via WebSocket
         ↓
Frontend displays response
```

## 📝 Changes Made

### 1. **WebSocket Handler** (`handler_working.py`)
```python
# Now checks for workflow triggers first
mbpp_agent = MBPPAgent()
result = mbpp_agent.process_message(
    message=user_message,
    session_id=session_id,
    has_image=False
)

# If workflow, return workflow response
if result.get('type') in ['workflow', 'workflow_complete']:
    return workflow_response

# Otherwise use Nova Pro
```

### 2. **Lambda Stack** (`lambda_stack.py`)
```python
# Added MBPP Workflow Layer
mbpp_workflow_layer = _lambda.LayerVersion(
    code=_lambda.Code.from_asset("../lambda/mcp_server"),
    description="MBPP Workflow Agent with Strands"
)

# Added to WebSocket handler
layers=[shared_layer, mbpp_workflow_layer]

# Added environment variables
"REPORTS_TABLE": "mbpp-reports",
"EVENTS_TABLE": "mbpp-events"
```

## 🎯 User Experience

### Complaint Workflow
```
User: "MBPP website is down"
Bot: "Would you like to report an incident?"
User: "Not an incident (Service Complaint)"
Bot: "Could you please describe the issue?"
...
Bot: "Ticket logged: 20239/2025/01/03"
```

### Incident Workflow
```
User: "I want to report a fallen tree"
Bot: "Please share image, location and describe what happened"
...
Bot: "Ticket logged: 20368/2025/01/03"
```

### Normal Questions (RAG)
```
User: "What are MBPP's operating hours?"
Bot: "MBPP operates from 8:00 AM to 5:00 PM..."
```

## 🚀 Deployment

```bash
cd cdk

# Deploy updated Lambda stack
cdk deploy ChatbotLambdaStack --profile test

# Deploy MBPP Workflow stack (if not already deployed)
cdk deploy MBPPWorkflowStack --profile test
```

## ✅ No Frontend Changes Needed

The frontend (`aeon.web.chat`) **does not need any changes**. It will:
- Continue using the same WebSocket endpoint
- Automatically receive workflow responses
- Display them as normal chat messages

## 📊 Response Format

### Workflow Response
```json
{
  "type": "assistant_message",
  "content": "Would you like to report an incident?",
  "sessionId": "session-123",
  "timestamp": "2025-01-03T10:30:00.000Z",
  "provider": "mbpp-workflow",
  "workflowType": "complaint",
  "workflowId": "uuid-here"
}
```

### Nova Pro Response
```json
{
  "type": "assistant_message",
  "content": "MBPP operates from 8:00 AM to 5:00 PM...",
  "sessionId": "session-123",
  "timestamp": "2025-01-03T10:30:00.000Z",
  "provider": "nova-pro",
  "queryType": "rag"
}
```

## 🔍 Testing

### Test Workflow Trigger
```javascript
// In browser console or test script
const ws = new WebSocket('wss://ynw017q5lc.execute-api.ap-southeast-1.amazonaws.com/prod');

ws.onopen = () => {
  ws.send(JSON.stringify({
    message: "MBPP website is down",
    sessionId: "test-123",
    timestamp: new Date().toISOString()
  }));
};

ws.onmessage = (event) => {
  console.log('Response:', JSON.parse(event.data));
};
```

### Expected Response
```json
{
  "type": "assistant_message",
  "content": "Would you like to report an incident?",
  "provider": "mbpp-workflow",
  "workflowType": "complaint"
}
```

## 📈 Monitoring

### CloudWatch Logs
```bash
# View WebSocket handler logs
aws logs tail /aws/lambda/ChatbotLambdaStack-WebSocketHandler --follow

# Filter for workflow messages
aws logs filter-log-events \
  --log-group-name /aws/lambda/ChatbotLambdaStack-WebSocketHandler \
  --filter-pattern "mbpp-workflow"
```

### Metrics to Watch
- Workflow trigger rate
- Workflow completion rate
- Response time (workflow vs RAG)
- Error rates

## ✅ Benefits

1. **Seamless Integration** - No frontend changes needed
2. **Automatic Detection** - Workflows triggered automatically
3. **Session Persistence** - Workflows tracked per session
4. **Fallback to RAG** - Non-workflow queries use Nova Pro
5. **DynamoDB Storage** - All reports persisted

---

**Status**: ✅ Complete - Ready to deploy
**Frontend**: ✅ No changes needed
**Backend**: ✅ Integrated with WebSocket handler
