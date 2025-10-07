#!/bin/bash

# Deployment script for WebSocket Chatbot in AP-Southeast-1 (Singapore)
# This script deploys the entire infrastructure to your test account

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REGION="ap-southeast-1"
CDK_DIR="cdk"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

print_status "🚀 Starting WebSocket Chatbot Deployment to AP-Southeast-1"
echo "=============================================================="

# Step 1: Validate prerequisites
print_status "Step 1: Validating prerequisites..."

if ! command_exists aws; then
    print_error "AWS CLI not found. Please install AWS CLI first."
    exit 1
fi

if ! command_exists cdk; then
    print_error "CDK CLI not found. Please install CDK CLI first."
    exit 1
fi

if ! command_exists python3; then
    print_error "Python 3 not found. Please install Python 3.11+ first."
    exit 1
fi

print_success "All prerequisites found"

# Step 2: Configure AWS region
print_status "Step 2: Configuring AWS for ap-southeast-1..."

export AWS_REGION=$REGION
export CDK_DEFAULT_REGION=$REGION

# Get account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")
if [ -z "$ACCOUNT_ID" ]; then
    print_error "Unable to get AWS account ID. Please configure AWS credentials."
    print_status "Run: aws configure"
    exit 1
fi

export CDK_DEFAULT_ACCOUNT=$ACCOUNT_ID
print_success "AWS configured for account $ACCOUNT_ID in region $REGION"

# Step 3: Check Bedrock model availability
print_status "Step 3: Checking Bedrock model availability..."

CLAUDE_AVAILABLE=$(aws bedrock list-foundation-models --region $REGION --query 'modelSummaries[?contains(modelId, `claude-3-5-sonnet`)].modelId' --output text 2>/dev/null || echo "")
if [ -z "$CLAUDE_AVAILABLE" ]; then
    print_warning "Claude Sonnet 4.5 may not be available in $REGION"
    print_status "Please check Bedrock model access in AWS Console"
    print_status "URL: https://$REGION.console.aws.amazon.com/bedrock/home?region=$REGION#/modelaccess"
else
    print_success "Claude Sonnet models available in $REGION"
fi

# Step 4: Install dependencies
print_status "Step 4: Installing dependencies..."

# Install CDK dependencies
if [ -f "$CDK_DIR/requirements.txt" ]; then
    print_status "Installing CDK dependencies..."
    cd $CDK_DIR
    pip3 install -r requirements.txt --quiet
    cd ..
    print_success "CDK dependencies installed"
fi

# Install shared dependencies
if [ -f "requirements.txt" ]; then
    print_status "Installing shared dependencies..."
    pip3 install -r requirements.txt --quiet
    print_success "Shared dependencies installed"
fi

# Step 5: Bootstrap CDK (if needed)
print_status "Step 5: Bootstrapping CDK environment..."

cd $CDK_DIR

# Check if already bootstrapped
BOOTSTRAP_STACK=$(aws cloudformation describe-stacks --stack-name CDKToolkit --region $REGION --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$BOOTSTRAP_STACK" = "NOT_FOUND" ]; then
    print_status "Bootstrapping CDK for the first time..."
    cdk bootstrap aws://$ACCOUNT_ID/$REGION
    print_success "CDK bootstrap completed"
else
    print_success "CDK already bootstrapped (Status: $BOOTSTRAP_STACK)"
fi

# Step 6: Synthesize CDK app
print_status "Step 6: Synthesizing CDK application..."

if cdk synth --quiet > /dev/null 2>&1; then
    print_success "CDK synthesis successful"
else
    print_error "CDK synthesis failed"
    print_status "Running synthesis with verbose output..."
    cdk synth
    exit 1
fi

# Step 7: Deploy infrastructure
print_status "Step 7: Deploying infrastructure stacks..."

print_status "This will deploy the following stacks:"
print_status "  - ChatbotDatabaseStack (DynamoDB tables)"
print_status "  - ChatbotLambdaStack (Lambda functions)"
print_status "  - ChatbotApiStack (WebSocket API)"
print_status "  - ChatbotMainStack (Main orchestration)"

read -p "Continue with deployment? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_status "Deployment cancelled"
    exit 0
fi

print_status "Deploying all stacks..."
if cdk deploy --all --require-approval never; then
    print_success "All stacks deployed successfully!"
else
    print_error "Deployment failed"
    exit 1
fi

cd ..

# Step 8: Get deployment outputs
print_status "Step 8: Retrieving deployment information..."

WEBSOCKET_URL=$(aws cloudformation describe-stacks --stack-name ChatbotMainStack --region $REGION --query 'Stacks[0].Outputs[?OutputKey==`WebSocketApiEndpoint`].OutputValue' --output text 2>/dev/null || echo "Not available")
WEBSOCKET_API_ID=$(aws cloudformation describe-stacks --stack-name ChatbotMainStack --region $REGION --query 'Stacks[0].Outputs[?OutputKey==`WebSocketApiId`].OutputValue' --output text 2>/dev/null || echo "Not available")

print_success "Deployment completed successfully!"
echo ""
echo "📊 DEPLOYMENT SUMMARY"
echo "====================="
echo "Region: $REGION"
echo "Account: $ACCOUNT_ID"
echo "WebSocket URL: $WEBSOCKET_URL"
echo "API ID: $WEBSOCKET_API_ID"
echo ""

# Step 9: Configure secrets (optional)
print_status "Step 9: Configuring secrets..."
print_warning "You need to configure API keys in AWS Secrets Manager:"
echo ""
echo "1. Strand API Key:"
echo "   aws secretsmanager put-secret-value \\"
echo "     --secret-id chatbot/api-keys \\"
echo "     --secret-string '{\"strand_api_key\":\"YOUR_ACTUAL_KEY\"}' \\"
echo "     --region $REGION"
echo ""
echo "2. MCP Server Secret (auto-generated during deployment)"
echo ""

# Step 10: Basic health check
print_status "Step 10: Running basic health checks..."

# Check Lambda functions
LAMBDA_FUNCTIONS=$(aws lambda list-functions --region $REGION --query 'Functions[?contains(FunctionName, `Chatbot`)].FunctionName' --output text)
if [ -n "$LAMBDA_FUNCTIONS" ]; then
    print_success "Lambda functions deployed: $(echo $LAMBDA_FUNCTIONS | wc -w) functions"
else
    print_warning "No Lambda functions found with 'Chatbot' in name"
fi

# Check DynamoDB tables
DYNAMODB_TABLES=$(aws dynamodb list-tables --region $REGION --query 'TableNames[?contains(@, `chatbot`)]' --output text)
if [ -n "$DYNAMODB_TABLES" ]; then
    print_success "DynamoDB tables created: $(echo $DYNAMODB_TABLES | wc -w) tables"
else
    print_warning "No DynamoDB tables found with 'chatbot' in name"
fi

print_success "🎉 Deployment to AP-Southeast-1 completed successfully!"
echo ""
echo "🔗 NEXT STEPS:"
echo "1. Configure your Strand API key in Secrets Manager"
echo "2. Test the WebSocket connection using the URL above"
echo "3. Monitor CloudWatch logs for any issues"
echo "4. Use the destroy script when done testing"
echo ""
echo "📊 MONITORING:"
echo "CloudWatch Logs: https://$REGION.console.aws.amazon.com/cloudwatch/home?region=$REGION#logsV2:log-groups"
echo "DynamoDB Tables: https://$REGION.console.aws.amazon.com/dynamodbv2/home?region=$REGION#tables"
echo "Lambda Functions: https://$REGION.console.aws.amazon.com/lambda/home?region=$REGION#/functions"
echo ""
echo "💰 ESTIMATED MONTHLY COST: $30-100 USD (based on usage)"