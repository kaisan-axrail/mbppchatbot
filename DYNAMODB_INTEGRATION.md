# DynamoDB Integration for MBPP Workflows

## ✅ Changes Applied

### 1. **Reports Table** (`mbpp-reports`)
Stores all incident and complaint tickets.

**Schema:**
```
Partition Key: ticket_number (String)
Attributes:
- subject
- details
- location
- feedback
- category
- sub_category
- blocked_road
- created_at
- status
- ttl (90 days auto-delete)
```

### 2. **Events Table** (`mbpp-events`)
Tracks all workflow events for audit trail.

**Schema:**
```
Partition Key: event_id (String)
GSI: ticket-index (ticket_number + timestamp)
Attributes:
- ticket_number
- event_type (complaint_created, incident_created)
- timestamp
- data (JSON)
- ttl (90 days auto-delete)
```

## 📝 Updated Files

### `mbpp_workflows.py`
```python
# Now saves to DynamoDB
def _save_report(self, ticket: Dict[str, Any]) -> bool:
    self.reports_table.put_item(Item={...})

def _create_event(self, event_type: str, ticket_number: str, data: Dict) -> bool:
    self.events_table.put_item(Item={...})
```

### `mbpp_workflow_stack.py`
```python
# Creates DynamoDB tables
reports_table = dynamodb.Table(...)
events_table = dynamodb.Table(...)

# Grants permissions
reports_table.grant_read_write_data(lambda_function)
events_table.grant_read_write_data(lambda_function)
```

## 🚀 Deployment

```bash
cd cdk
cdk deploy MBPPWorkflowStack --profile test
```

## 📊 Query Examples

### Get Report by Ticket Number
```python
import boto3

dynamodb = boto3.resource('dynamodb')
reports_table = dynamodb.Table('mbpp-reports')

response = reports_table.get_item(
    Key={'ticket_number': '20239/2025/01/03'}
)
report = response['Item']
```

### Get Events for Ticket
```python
events_table = dynamodb.Table('mbpp-events')

response = events_table.query(
    IndexName='ticket-index',
    KeyConditionExpression='ticket_number = :ticket',
    ExpressionAttributeValues={':ticket': '20239/2025/01/03'}
)
events = response['Items']
```

### List All Open Reports
```python
response = reports_table.scan(
    FilterExpression='#status = :status',
    ExpressionAttributeNames={'#status': 'status'},
    ExpressionAttributeValues={':status': 'open'}
)
reports = response['Items']
```

## ✅ Benefits

1. **Persistent Storage** - Reports survive Lambda restarts
2. **Audit Trail** - All events tracked
3. **Auto-Cleanup** - TTL removes old data after 90 days
4. **Scalable** - Pay-per-request billing
5. **Queryable** - GSI for efficient queries

## 🔍 Monitoring

### CloudWatch Metrics
- `ConsumedReadCapacityUnits`
- `ConsumedWriteCapacityUnits`
- `UserErrors`
- `SystemErrors`

### View Table Data
```bash
# List reports
aws dynamodb scan --table-name mbpp-reports --profile test

# Get specific report
aws dynamodb get-item \
  --table-name mbpp-reports \
  --key '{"ticket_number": {"S": "20239/2025/01/03"}}' \
  --profile test
```

---

**Status**: ✅ Complete and deployed
