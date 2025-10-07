# Chatbot WebSocket System Deployment Guide

This guide provides comprehensive instructions for deploying the chatbot WebSocket system using AWS CDK.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Environment Configuration](#environment-configuration)
- [Deployment Process](#deployment-process)
- [Post-Deployment Configuration](#post-deployment-configuration)
- [Validation and Testing](#validation-and-testing)
- [Troubleshooting](#troubleshooting)
- [Cleanup](#cleanup)

## Prerequisites

### Required Software

1. **Python 3.11+**
   ```bash
   python3 --version  # Should be 3.11 or higher
   ```

2. **AWS CLI v2**
   ```bash
   aws --version
   aws configure  # Configure your AWS credentials
   ```

3. **AWS CDK v2.100.0+**
   ```bash
   npm install -g aws-cdk
   cdk --version
   ```

4. **Node.js 18+** (for CDK)
   ```bash
   node --version
   ```

### AWS Account Setup

1. **IAM Permissions**: Ensure your AWS user/role has the following permissions:
   - CloudFormation full access
   - Lambda full access
   - DynamoDB full access
   - API Gateway full access
   - IAM role creation and management
   - Secrets Manager full access
   - Bedrock model access
   - CloudWatch Logs access

2. **Service Quotas**: Verify you have sufficient quotas for:
   - Lambda functions (at least 10)
   - DynamoDB tables (at least 5)
   - API Gateway APIs (at least 2)

3. **Bedrock Model Access**: Ensure you have access to:
   - `anthropic.claude-3-5-sonnet-20241022-v2:0`
   - `amazon.titan-embed-text-v1`

## Quick Start

For a rapid deployment with default settings:

```bash
# 1. Clone and navigate to the project
cd websocket-chatbot

# 2. Run the deployment script
./deploy.sh
```

The deployment script will:
- Validate prerequisites
- Install dependencies
- Bootstrap CDK (if needed)
- Deploy all stacks
- Validate the deployment

## Environment Configuration

### Development Environment

```bash
# Deploy to development environment
export CDK_ENVIRONMENT=dev
./deploy.sh
```

### Production Environment

```bash
# Deploy to production environment
export CDK_ENVIRONMENT=prod
./deploy.sh
```

### Custom Configuration

Create a custom environment configuration:

```bash
# Create custom config
cp config/environments/dev.json config/environments/custom.json
# Edit custom.json with your settings

# Deploy with custom config
export CDK_ENVIRONMENT=custom
./deploy.sh
```

## Deployment Process

### Step 1: Prepare the Environment

```bash
# Install Python dependencies
pip3 install -r requirements.txt
pip3 install -r cdk/requirements.txt

# Install Lambda dependencies
for dir in lambda/*/; do
    if [ -f "$dir/requirements.txt" ]; then
        pip3 install -r "$dir/requirements.txt" --target "$dir/vendor"
    fi
done
```

### Step 2: CDK Bootstrap

Bootstrap your AWS environment (one-time setup per region):

```bash
cd cdk
cdk bootstrap
```

### Step 3: Deploy Infrastructure

Deploy all stacks in the correct order:

```bash
# Deploy all stacks
cdk deploy --all --require-approval never

# Or deploy individual stacks
cdk deploy ChatbotDatabaseStack
cdk deploy ChatbotLambdaStack
cdk deploy ChatbotApiStack
cdk deploy ChatbotMainStack
```

### Step 4: Verify Deployment

```bash
# List deployed stacks
cdk list

# Get stack outputs
aws cloudformation describe-stacks --stack-name ChatbotMainStack --query 'Stacks[0].Outputs'
```

## Post-Deployment Configuration

### 1. Configure API Keys

Update the secrets in AWS Secrets Manager:

```bash
# Update API keys secret
aws secretsmanager update-secret \
    --secret-id chatbot/api-keys \
    --secret-string '{
        "strand_api_key": "your-strand-api-key",
        "openai_api_key": "your-openai-api-key"
    }'

# Update MCP server secret
aws secretsmanager update-secret \
    --secret-id chatbot/mcp-server \
    --secret-string '{
        "api_key": "your-mcp-api-key",
        "additional_config": "value"
    }'
```

### 2. Test WebSocket Endpoint

Get the WebSocket endpoint URL:

```bash
WEBSOCKET_URL=$(aws cloudformation describe-stacks \
    --stack-name ChatbotMainStack \
    --query 'Stacks[0].Outputs[?OutputKey==`WebSocketApiEndpoint`].OutputValue' \
    --output text)

echo "WebSocket URL: $WEBSOCKET_URL"
```

### 3. Configure Client Applications

Update your client applications to use the deployed WebSocket endpoint:

```javascript
// Example client configuration
const websocketUrl = 'wss://your-api-id.execute-api.region.amazonaws.com/prod';
const ws = new WebSocket(websocketUrl);
```

## Validation and Testing

### Automated Validation

Run the deployment validation script:

```bash
# Basic validation
python3 scripts/validate-deployment.py

# Validation with report output
python3 scripts/validate-deployment.py --output validation-report.json

# Validation for specific region
python3 scripts/validate-deployment.py --region us-west-2
```

### Manual Testing

1. **WebSocket Connection Test**:
   ```bash
   # Install wscat for testing
   npm install -g wscat
   
   # Test connection
   wscat -c wss://your-api-id.execute-api.region.amazonaws.com/prod
   ```

2. **Lambda Function Test**:
   ```bash
   # Test WebSocket handler
   aws lambda invoke \
       --function-name ChatbotLambdaStack-WebSocketHandler \
       --payload '{"requestContext":{"eventType":"CONNECT"}}' \
       response.json
   ```

3. **DynamoDB Access Test**:
   ```bash
   # List tables
   aws dynamodb list-tables
   
   # Describe sessions table
   aws dynamodb describe-table --table-name chatbot-sessions
   ```

### Integration Tests

Run the integration test suite:

```bash
# Run all integration tests
python3 -m pytest tests/integration/ -v

# Run specific test
python3 -m pytest tests/integration/test_cdk_deployment.py -v
```

## Troubleshooting

### Common Issues

#### 1. CDK Bootstrap Issues

**Problem**: `Need to perform AWS CDK bootstrap`

**Solution**:
```bash
cd cdk
cdk bootstrap aws://ACCOUNT-ID/REGION
```

#### 2. Lambda Deployment Failures

**Problem**: Lambda function deployment fails due to package size

**Solution**:
```bash
# Clean up vendor directories
find lambda -name "vendor" -type d -exec rm -rf {} +

# Reinstall with minimal dependencies
pip3 install -r lambda/function_name/requirements.txt \
    --target lambda/function_name/vendor \
    --no-deps --no-cache-dir
```

#### 3. IAM Permission Errors

**Problem**: `User is not authorized to perform: action`

**Solution**: Ensure your AWS user has the required permissions listed in Prerequisites.

#### 4. Bedrock Access Issues

**Problem**: `AccessDeniedException` when calling Bedrock

**Solution**:
1. Request model access in the Bedrock console
2. Verify the model IDs are correct for your region
3. Check IAM permissions for Bedrock

#### 5. WebSocket Connection Failures

**Problem**: WebSocket connections fail or timeout

**Solution**:
1. Check API Gateway logs in CloudWatch
2. Verify Lambda function logs
3. Test with a simple WebSocket client
4. Check security group and network ACL settings

### Debug Mode

Enable debug logging for troubleshooting:

```bash
# Set debug environment variables
export CDK_DEBUG=true
export AWS_SDK_LOAD_CONFIG=1
export AWS_CLI_FILE_ENCODING=UTF-8

# Deploy with verbose output
cdk deploy --all --verbose
```

### Log Analysis

Check CloudWatch logs for issues:

```bash
# WebSocket handler logs
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/ChatbotLambdaStack-WebSocketHandler"

# MCP server logs
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/ChatbotLambdaStack-McpServer"

# Get recent log events
aws logs filter-log-events \
    --log-group-name "/aws/lambda/ChatbotLambdaStack-WebSocketHandler" \
    --start-time $(date -d '1 hour ago' +%s)000
```

## Cleanup

### Complete Cleanup

To remove all deployed resources:

```bash
# Run the destroy script
./destroy.sh

# Or manually destroy stacks
cd cdk
cdk destroy --all --force
```

### Partial Cleanup

To remove specific stacks:

```bash
cd cdk

# Remove main stack (keeps database)
cdk destroy ChatbotMainStack

# Remove specific stack
cdk destroy ChatbotApiStack
```

### Manual Resource Cleanup

If CDK destroy fails, manually clean up resources:

```bash
# List and delete Lambda functions
aws lambda list-functions --query 'Functions[?contains(FunctionName, `Chatbot`)].FunctionName'

# List and delete DynamoDB tables
aws dynamodb list-tables --query 'TableNames[?contains(@, `chatbot`)]'

# List and delete API Gateway APIs
aws apigatewayv2 get-apis --query 'Items[?contains(Name, `chatbot`)].{Name:Name,ApiId:ApiId}'
```

## Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `CDK_ENVIRONMENT` | Environment configuration to use | `dev` |
| `AWS_REGION` | AWS region for deployment | `us-east-1` |
| `AWS_PROFILE` | AWS profile to use | default |
| `CDK_DEBUG` | Enable CDK debug logging | `false` |

## Stack Dependencies

The stacks are deployed in the following order:

1. **ChatbotDatabaseStack**: DynamoDB tables
2. **ChatbotLambdaStack**: Lambda functions and IAM roles
3. **ChatbotApiStack**: API Gateway and WebSocket API
4. **ChatbotMainStack**: Main orchestration and outputs

## Security Considerations

1. **Secrets Management**: All sensitive data is stored in AWS Secrets Manager
2. **IAM Roles**: Each Lambda function has minimal required permissions
3. **Network Security**: API Gateway provides built-in DDoS protection
4. **Encryption**: All data is encrypted at rest and in transit
5. **Access Logging**: All API calls are logged to CloudWatch

## Cost Optimization

1. **DynamoDB**: Uses on-demand billing for cost efficiency
2. **Lambda**: Right-sized memory allocation for each function
3. **API Gateway**: WebSocket API is more cost-effective than REST API
4. **CloudWatch**: Log retention is configured per environment

## Support

For deployment issues:

1. Check the troubleshooting section above
2. Review CloudWatch logs for error details
3. Validate your AWS permissions and quotas
4. Ensure all prerequisites are met
5. Run the validation script for automated checks