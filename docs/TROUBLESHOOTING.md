# Troubleshooting Guide

This guide helps diagnose and resolve common issues with the chatbot WebSocket system deployment and operation.

## Table of Contents

- [Deployment Issues](#deployment-issues)
- [Runtime Issues](#runtime-issues)
- [Performance Issues](#performance-issues)
- [Monitoring and Debugging](#monitoring-and-debugging)
- [Common Error Messages](#common-error-messages)
- [Recovery Procedures](#recovery-procedures)

## Deployment Issues

### CDK Bootstrap Problems

#### Issue: "Need to perform AWS CDK bootstrap"
```
Error: Need to perform AWS CDK bootstrap in this environment
```

**Diagnosis**:
```bash
# Check bootstrap status
cdk doctor
aws cloudformation describe-stacks --stack-name CDKToolkit
```

**Solution**:
```bash
# Bootstrap the environment
cd cdk
cdk bootstrap

# For specific account/region
cdk bootstrap aws://123456789012/us-east-1
```

#### Issue: Bootstrap stack update fails
```
Error: CDKToolkit stack update failed
```

**Solution**:
```bash
# Force update the bootstrap stack
cdk bootstrap --force

# Or delete and recreate
aws cloudformation delete-stack --stack-name CDKToolkit
# Wait for deletion, then bootstrap again
cdk bootstrap
```

### Lambda Deployment Issues

#### Issue: Package size too large
```
Error: Unzipped size must be smaller than 262144000 bytes
```

**Diagnosis**:
```bash
# Check package sizes
find lambda -name "*.zip" -exec ls -lh {} \;
du -sh lambda/*/
```

**Solution**:
```bash
# Clean up vendor directories
find lambda -name "vendor" -type d -exec rm -rf {} +

# Reinstall with minimal dependencies
for dir in lambda/*/; do
    if [ -f "$dir/requirements.txt" ]; then
        pip3 install -r "$dir/requirements.txt" \
            --target "$dir/vendor" \
            --no-deps --no-cache-dir \
            --platform linux_x86_64 \
            --only-binary=all
    fi
done

# Remove unnecessary files
find lambda -name "*.pyc" -delete
find lambda -name "__pycache__" -type d -exec rm -rf {} +
find lambda -name "*.dist-info" -type d -exec rm -rf {} +
```

#### Issue: Lambda function timeout during deployment
```
Error: The function couldn't be updated because it's in the process of being updated
```

**Solution**:
```bash
# Wait and retry
sleep 30
cdk deploy --all

# Or update function configuration directly
aws lambda update-function-configuration \
    --function-name YourFunctionName \
    --timeout 300
```

### IAM Permission Issues

#### Issue: Insufficient permissions for CDK operations
```
Error: User: arn:aws:iam::123456789012:user/username is not authorized to perform: action
```

**Diagnosis**:
```bash
# Check current user permissions
aws sts get-caller-identity
aws iam get-user
aws iam list-attached-user-policies --user-name username
```

**Solution**: Attach the following managed policies to your user:
- `AWSCloudFormationFullAccess`
- `AWSLambda_FullAccess`
- `AmazonDynamoDBFullAccess`
- `AmazonAPIGatewayAdministrator`
- `IAMFullAccess`
- `SecretsManagerReadWrite`

Or create a custom policy with minimal required permissions.

### DynamoDB Issues

#### Issue: Table already exists
```
Error: Table already exists: chatbot-sessions
```

**Solution**:
```bash
# Check existing tables
aws dynamodb list-tables

# Delete conflicting table (if safe)
aws dynamodb delete-table --table-name chatbot-sessions

# Or use different table names in configuration
```

#### Issue: DynamoDB capacity exceeded
```
Error: ProvisionedThroughputExceededException
```

**Solution**:
```bash
# Switch to on-demand billing
aws dynamodb modify-table \
    --table-name chatbot-sessions \
    --billing-mode PAY_PER_REQUEST

# Or increase provisioned capacity
aws dynamodb modify-table \
    --table-name chatbot-sessions \
    --provisioned-throughput ReadCapacityUnits=10,WriteCapacityUnits=10
```

## Runtime Issues

### WebSocket Connection Problems

#### Issue: WebSocket connection fails
```
Error: WebSocket connection failed: Error during WebSocket handshake
```

**Diagnosis**:
```bash
# Test WebSocket endpoint
wscat -c wss://your-api-id.execute-api.region.amazonaws.com/prod

# Check API Gateway logs
aws logs filter-log-events \
    --log-group-name "API-Gateway-Execution-Logs_your-api-id/prod" \
    --start-time $(date -d '1 hour ago' +%s)000
```

**Solution**:
1. Verify API Gateway deployment
2. Check Lambda function permissions
3. Validate WebSocket routes configuration
4. Test with different WebSocket client

#### Issue: WebSocket messages not processed
```
Error: Message sent but no response received
```

**Diagnosis**:
```bash
# Check Lambda function logs
aws logs filter-log-events \
    --log-group-name "/aws/lambda/ChatbotLambdaStack-WebSocketHandler" \
    --start-time $(date -d '1 hour ago' +%s)000

# Check function metrics
aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Invocations \
    --dimensions Name=FunctionName,Value=ChatbotLambdaStack-WebSocketHandler \
    --start-time $(date -d '1 hour ago' --iso-8601) \
    --end-time $(date --iso-8601) \
    --period 300 \
    --statistics Sum
```

**Solution**:
1. Check Lambda function error logs
2. Verify message format and routing
3. Test Lambda function directly
4. Check DynamoDB permissions and capacity

### Bedrock Integration Issues

#### Issue: Bedrock model access denied
```
Error: AccessDeniedException: You don't have access to the model
```

**Diagnosis**:
```bash
# Check available models
aws bedrock list-foundation-models --region us-east-1

# Test model access
aws bedrock invoke-model \
    --model-id anthropic.claude-3-5-sonnet-20241022-v2:0 \
    --body '{"messages":[{"role":"user","content":"test"}],"max_tokens":10}' \
    --content-type application/json \
    --accept application/json \
    response.json
```

**Solution**:
1. Request model access in Bedrock console
2. Verify model ID is correct for your region
3. Check IAM permissions for Bedrock
4. Wait for model access approval (can take time)

#### Issue: Bedrock rate limiting
```
Error: ThrottlingException: Rate exceeded
```

**Solution**:
```bash
# Implement exponential backoff in Lambda function
# Check current usage and limits
aws service-quotas get-service-quota \
    --service-code bedrock \
    --quota-code L-12345678
```

### MCP Server Issues

#### Issue: MCP tools not responding
```
Error: MCP tool execution failed
```

**Diagnosis**:
```bash
# Check MCP server logs
aws logs filter-log-events \
    --log-group-name "/aws/lambda/ChatbotLambdaStack-McpServer" \
    --start-time $(date -d '1 hour ago' +%s)000

# Test MCP server directly
aws lambda invoke \
    --function-name ChatbotLambdaStack-McpServer \
    --payload '{"action":"list_tools"}' \
    response.json
```

**Solution**:
1. Verify OpenAPI schema is included in deployment
2. Check MCP server configuration
3. Validate tool permissions and access
4. Test individual MCP tools

## Performance Issues

### High Latency

#### Issue: WebSocket messages have high latency
**Diagnosis**:
```bash
# Check Lambda cold starts
aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Duration \
    --dimensions Name=FunctionName,Value=ChatbotLambdaStack-WebSocketHandler \
    --start-time $(date -d '1 hour ago' --iso-8601) \
    --end-time $(date --iso-8601) \
    --period 300 \
    --statistics Average,Maximum

# Check DynamoDB performance
aws cloudwatch get-metric-statistics \
    --namespace AWS/DynamoDB \
    --metric-name SuccessfulRequestLatency \
    --dimensions Name=TableName,Value=chatbot-sessions \
    --start-time $(date -d '1 hour ago' --iso-8601) \
    --end-time $(date --iso-8601) \
    --period 300 \
    --statistics Average
```

**Solution**:
1. Increase Lambda memory allocation
2. Implement connection pooling
3. Use DynamoDB DAX for caching
4. Optimize database queries

### Memory Issues

#### Issue: Lambda function out of memory
```
Error: Runtime.OutOfMemory: Lambda function ran out of memory
```

**Solution**:
```bash
# Increase memory allocation
aws lambda update-function-configuration \
    --function-name ChatbotLambdaStack-WebSocketHandler \
    --memory-size 512

# Monitor memory usage
aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name MemoryUtilization \
    --dimensions Name=FunctionName,Value=ChatbotLambdaStack-WebSocketHandler \
    --start-time $(date -d '1 hour ago' --iso-8601) \
    --end-time $(date --iso-8601) \
    --period 300 \
    --statistics Maximum
```

## Monitoring and Debugging

### Enable Debug Logging

```bash
# Update Lambda environment variables
aws lambda update-function-configuration \
    --function-name ChatbotLambdaStack-WebSocketHandler \
    --environment Variables='{
        "LOG_LEVEL":"DEBUG",
        "SESSIONS_TABLE":"chatbot-sessions",
        "CONVERSATIONS_TABLE":"chatbot-conversations",
        "ANALYTICS_TABLE":"chatbot-analytics"
    }'
```

### CloudWatch Dashboards

Create a monitoring dashboard:

```bash
# Create dashboard configuration
cat > dashboard.json << 'EOF'
{
    "widgets": [
        {
            "type": "metric",
            "properties": {
                "metrics": [
                    ["AWS/Lambda", "Invocations", "FunctionName", "ChatbotLambdaStack-WebSocketHandler"],
                    [".", "Errors", ".", "."],
                    [".", "Duration", ".", "."]
                ],
                "period": 300,
                "stat": "Sum",
                "region": "us-east-1",
                "title": "Lambda Metrics"
            }
        }
    ]
}
EOF

# Create dashboard
aws cloudwatch put-dashboard \
    --dashboard-name "ChatbotSystem" \
    --dashboard-body file://dashboard.json
```

### Log Analysis

```bash
# Search for errors in logs
aws logs filter-log-events \
    --log-group-name "/aws/lambda/ChatbotLambdaStack-WebSocketHandler" \
    --filter-pattern "ERROR" \
    --start-time $(date -d '24 hours ago' +%s)000

# Search for specific patterns
aws logs filter-log-events \
    --log-group-name "/aws/lambda/ChatbotLambdaStack-WebSocketHandler" \
    --filter-pattern "[timestamp, request_id, level=ERROR, ...]" \
    --start-time $(date -d '1 hour ago' +%s)000
```

## Common Error Messages

### "ResourceNotFoundException"
**Cause**: Resource (table, function, etc.) doesn't exist
**Solution**: Verify resource names and deployment status

### "ValidationException"
**Cause**: Invalid parameters or configuration
**Solution**: Check parameter formats and constraints

### "ThrottlingException"
**Cause**: Rate limits exceeded
**Solution**: Implement retry logic with exponential backoff

### "TimeoutException"
**Cause**: Operation timed out
**Solution**: Increase timeout values or optimize performance

### "AccessDeniedException"
**Cause**: Insufficient permissions
**Solution**: Review and update IAM policies

## Recovery Procedures

### Rollback Deployment

```bash
# Rollback to previous version
cd cdk
cdk deploy --rollback

# Or deploy specific version
git checkout previous-tag
cdk deploy --all
```

### Restore from Backup

```bash
# Restore DynamoDB table from backup
aws dynamodb restore-table-from-backup \
    --target-table-name chatbot-sessions-restored \
    --backup-arn arn:aws:dynamodb:region:account:table/chatbot-sessions/backup/backup-id

# Update Lambda environment to use restored table
aws lambda update-function-configuration \
    --function-name ChatbotLambdaStack-WebSocketHandler \
    --environment Variables='{"SESSIONS_TABLE":"chatbot-sessions-restored"}'
```

### Emergency Shutdown

```bash
# Disable API Gateway
aws apigatewayv2 update-stage \
    --api-id your-api-id \
    --stage-name prod \
    --throttle-settings BurstLimit=0,RateLimit=0

# Disable Lambda functions
aws lambda put-function-concurrency \
    --function-name ChatbotLambdaStack-WebSocketHandler \
    --reserved-concurrent-executions 0
```

### Health Check Script

```bash
#!/bin/bash
# health-check.sh - Quick system health check

echo "🏥 Chatbot System Health Check"
echo "=============================="

# Check Lambda functions
echo "📋 Lambda Functions:"
aws lambda list-functions --query 'Functions[?contains(FunctionName, `Chatbot`)].{Name:FunctionName,State:State}' --output table

# Check DynamoDB tables
echo "📊 DynamoDB Tables:"
aws dynamodb list-tables --query 'TableNames[?contains(@, `chatbot`)]' --output table

# Check API Gateway
echo "🌐 API Gateway:"
aws apigatewayv2 get-apis --query 'Items[?contains(Name, `chatbot`)].{Name:Name,State:ApiEndpoint}' --output table

# Check recent errors
echo "❌ Recent Errors (last hour):"
aws logs filter-log-events \
    --log-group-name "/aws/lambda/ChatbotLambdaStack-WebSocketHandler" \
    --filter-pattern "ERROR" \
    --start-time $(date -d '1 hour ago' +%s)000 \
    --query 'events[].message' \
    --output text | head -5

echo "✅ Health check complete"
```

Make the script executable and run it:
```bash
chmod +x health-check.sh
./health-check.sh
```