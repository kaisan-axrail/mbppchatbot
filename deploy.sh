#!/bin/bash

# Chatbot WebSocket System Deployment Script
# This script deploys the entire chatbot infrastructure using AWS CDK

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CDK_DIR="cdk"
PYTHON_VERSION="3.11"
REQUIRED_CDK_VERSION="2.100.0"

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

# Function to check Python version
check_python_version() {
    if command_exists python3; then
        PYTHON_VER=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
        if [ "$(printf '%s\n' "$PYTHON_VERSION" "$PYTHON_VER" | sort -V | head -n1)" = "$PYTHON_VERSION" ]; then
            print_success "Python $PYTHON_VER is compatible (required: $PYTHON_VERSION+)"
            return 0
        else
            print_error "Python $PYTHON_VER is not compatible (required: $PYTHON_VERSION+)"
            return 1
        fi
    else
        print_error "Python 3 is not installed"
        return 1
    fi
}

# Function to check AWS CLI
check_aws_cli() {
    if command_exists aws; then
        print_success "AWS CLI is installed"
        
        # Check if AWS credentials are configured
        if aws sts get-caller-identity >/dev/null 2>&1; then
            ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
            REGION=$(aws configure get region)
            print_success "AWS credentials configured for account: $ACCOUNT_ID in region: $REGION"
            return 0
        else
            print_error "AWS credentials are not configured"
            print_status "Please run 'aws configure' to set up your credentials"
            return 1
        fi
    else
        print_error "AWS CLI is not installed"
        print_status "Please install AWS CLI: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
        return 1
    fi
}

# Function to check CDK
check_cdk() {
    if command_exists cdk; then
        CDK_VER=$(cdk --version 2>&1 | cut -d' ' -f1)
        print_success "AWS CDK $CDK_VER is installed"
        return 0
    else
        print_error "AWS CDK is not installed"
        print_status "Please install AWS CDK: npm install -g aws-cdk"
        return 1
    fi
}

# Function to install Python dependencies
install_dependencies() {
    print_status "Installing Python dependencies..."
    
    # Install CDK dependencies
    if [ -f "$CDK_DIR/requirements.txt" ]; then
        print_status "Installing CDK dependencies..."
        pip3 install -r "$CDK_DIR/requirements.txt"
        print_success "CDK dependencies installed"
    fi
    
    # Install Lambda dependencies for each function
    for lambda_dir in lambda/*/; do
        if [ -f "$lambda_dir/requirements.txt" ]; then
            print_status "Installing dependencies for $(basename "$lambda_dir")..."
            pip3 install -r "$lambda_dir/requirements.txt" --target "$lambda_dir/vendor" --quiet
        fi
    done
    
    # Install shared module dependencies
    if [ -f "requirements.txt" ]; then
        print_status "Installing shared dependencies..."
        pip3 install -r requirements.txt
        print_success "Shared dependencies installed"
    fi
}

# Function to validate CDK app
validate_cdk_app() {
    print_status "Validating CDK application..."
    
    cd "$CDK_DIR"
    
    # Synthesize the CDK app to check for errors
    if cdk synth --quiet >/dev/null 2>&1; then
        print_success "CDK application validation passed"
        cd ..
        return 0
    else
        print_error "CDK application validation failed"
        print_status "Running cdk synth for detailed error information..."
        cdk synth
        cd ..
        return 1
    fi
}

# Function to bootstrap CDK (if needed)
bootstrap_cdk() {
    print_status "Checking CDK bootstrap status..."
    
    cd "$CDK_DIR"
    
    # Check if bootstrap is needed
    if cdk bootstrap --show-template >/dev/null 2>&1; then
        print_status "Bootstrapping CDK environment..."
        if cdk bootstrap; then
            print_success "CDK bootstrap completed"
        else
            print_error "CDK bootstrap failed"
            cd ..
            return 1
        fi
    else
        print_success "CDK environment already bootstrapped"
    fi
    
    cd ..
    return 0
}

# Function to deploy CDK stacks
deploy_stacks() {
    print_status "Deploying CDK stacks..."
    
    cd "$CDK_DIR"
    
    # Deploy all stacks
    if cdk deploy --all --require-approval never; then
        print_success "All CDK stacks deployed successfully"
        
        # Get stack outputs
        print_status "Retrieving stack outputs..."
        cdk list --long
        
        cd ..
        return 0
    else
        print_error "CDK deployment failed"
        cd ..
        return 1
    fi
}

# Function to run post-deployment validation
post_deployment_validation() {
    print_status "Running post-deployment validation..."
    
    # Check if Lambda functions are deployed
    print_status "Validating Lambda functions..."
    
    WEBSOCKET_HANDLER=$(aws lambda list-functions --query 'Functions[?contains(FunctionName, `WebSocketHandler`)].FunctionName' --output text)
    MCP_SERVER=$(aws lambda list-functions --query 'Functions[?contains(FunctionName, `McpServer`)].FunctionName' --output text)
    SESSION_CLEANUP=$(aws lambda list-functions --query 'Functions[?contains(FunctionName, `SessionCleanup`)].FunctionName' --output text)
    
    if [ -n "$WEBSOCKET_HANDLER" ]; then
        print_success "WebSocket handler Lambda function deployed: $WEBSOCKET_HANDLER"
    else
        print_warning "WebSocket handler Lambda function not found"
    fi
    
    if [ -n "$MCP_SERVER" ]; then
        print_success "MCP server Lambda function deployed: $MCP_SERVER"
    else
        print_warning "MCP server Lambda function not found"
    fi
    
    if [ -n "$SESSION_CLEANUP" ]; then
        print_success "Session cleanup Lambda function deployed: $SESSION_CLEANUP"
    else
        print_warning "Session cleanup Lambda function not found"
    fi
    
    # Check DynamoDB tables
    print_status "Validating DynamoDB tables..."
    
    SESSIONS_TABLE=$(aws dynamodb list-tables --query 'TableNames[?contains(@, `sessions`)]' --output text)
    CONVERSATIONS_TABLE=$(aws dynamodb list-tables --query 'TableNames[?contains(@, `conversations`)]' --output text)
    ANALYTICS_TABLE=$(aws dynamodb list-tables --query 'TableNames[?contains(@, `analytics`)]' --output text)
    
    if [ -n "$SESSIONS_TABLE" ]; then
        print_success "Sessions table deployed: $SESSIONS_TABLE"
    else
        print_warning "Sessions table not found"
    fi
    
    if [ -n "$CONVERSATIONS_TABLE" ]; then
        print_success "Conversations table deployed: $CONVERSATIONS_TABLE"
    else
        print_warning "Conversations table not found"
    fi
    
    if [ -n "$ANALYTICS_TABLE" ]; then
        print_success "Analytics table deployed: $ANALYTICS_TABLE"
    else
        print_warning "Analytics table not found"
    fi
    
    print_success "Post-deployment validation completed"
}

# Function to display deployment summary
display_summary() {
    print_status "Deployment Summary"
    echo "===================="
    
    cd "$CDK_DIR"
    
    # Get WebSocket API endpoint
    WEBSOCKET_ENDPOINT=$(aws cloudformation describe-stacks --stack-name ChatbotMainStack --query 'Stacks[0].Outputs[?OutputKey==`WebSocketApiEndpoint`].OutputValue' --output text 2>/dev/null || echo "Not available")
    
    echo "WebSocket API Endpoint: $WEBSOCKET_ENDPOINT"
    echo ""
    echo "Next Steps:"
    echo "1. Update your client application to use the WebSocket endpoint above"
    echo "2. Configure API keys in AWS Secrets Manager"
    echo "3. Test the deployment using the provided test scripts"
    echo "4. Monitor CloudWatch logs for any issues"
    
    cd ..
}

# Main deployment function
main() {
    print_status "Starting Chatbot WebSocket System Deployment"
    echo "=============================================="
    
    # Pre-deployment checks
    print_status "Running pre-deployment checks..."
    
    # Run comprehensive requirements validation
    if command_exists python3; then
        print_status "Running comprehensive requirements validation..."
        if python3 scripts/validate-requirements.py; then
            print_success "Requirements validation passed"
        else
            print_error "Requirements validation failed"
            exit 1
        fi
    else
        # Fallback to basic checks
        if ! check_python_version; then
            exit 1
        fi
        
        if ! check_aws_cli; then
            exit 1
        fi
        
        if ! check_cdk; then
            exit 1
        fi
    fi
    
    # Install dependencies
    if ! install_dependencies; then
        print_error "Failed to install dependencies"
        exit 1
    fi
    
    # Validate CDK app
    if ! validate_cdk_app; then
        print_error "CDK application validation failed"
        exit 1
    fi
    
    # Bootstrap CDK if needed
    if ! bootstrap_cdk; then
        print_error "CDK bootstrap failed"
        exit 1
    fi
    
    # Deploy stacks
    if ! deploy_stacks; then
        print_error "CDK deployment failed"
        exit 1
    fi
    
    # Post-deployment validation
    post_deployment_validation
    
    # Display summary
    display_summary
    
    print_success "Deployment completed successfully!"
}

# Handle script arguments
case "${1:-}" in
    --help|-h)
        echo "Chatbot WebSocket System Deployment Script"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --validate     Only validate the CDK application"
        echo "  --bootstrap    Only bootstrap the CDK environment"
        echo ""
        echo "Environment Variables:"
        echo "  AWS_PROFILE    AWS profile to use (optional)"
        echo "  AWS_REGION     AWS region to deploy to (optional)"
        echo ""
        exit 0
        ;;
    --validate)
        print_status "Running validation only..."
        check_python_version && check_aws_cli && check_cdk && validate_cdk_app
        exit $?
        ;;
    --bootstrap)
        print_status "Running bootstrap only..."
        check_python_version && check_aws_cli && check_cdk && bootstrap_cdk
        exit $?
        ;;
    "")
        main
        ;;
    *)
        print_error "Unknown option: $1"
        echo "Use --help for usage information"
        exit 1
        ;;
esac