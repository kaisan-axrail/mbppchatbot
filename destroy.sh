#!/bin/bash

# Chatbot WebSocket System Destroy Script
# This script destroys the entire chatbot infrastructure using AWS CDK

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
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

# Function to confirm destruction
confirm_destruction() {
    print_warning "This will destroy ALL resources created by the chatbot system!"
    print_warning "This action cannot be undone."
    echo ""
    read -p "Are you sure you want to continue? (type 'yes' to confirm): " confirmation
    
    if [ "$confirmation" != "yes" ]; then
        print_status "Destruction cancelled."
        exit 0
    fi
}

# Function to list resources before destruction
list_resources() {
    print_status "Listing resources that will be destroyed..."
    
    cd "$CDK_DIR"
    
    # List all stacks
    print_status "CDK Stacks:"
    cdk list
    
    cd ..
    
    # List Lambda functions
    print_status "Lambda Functions:"
    aws lambda list-functions --query 'Functions[?contains(FunctionName, `Chatbot`) || contains(FunctionName, `WebSocket`) || contains(FunctionName, `Mcp`) || contains(FunctionName, `Session`)].FunctionName' --output table 2>/dev/null || echo "None found"
    
    # List DynamoDB tables
    print_status "DynamoDB Tables:"
    aws dynamodb list-tables --query 'TableNames[?contains(@, `chatbot`) || contains(@, `sessions`) || contains(@, `conversations`) || contains(@, `analytics`)]' --output table 2>/dev/null || echo "None found"
    
    # List API Gateway APIs
    print_status "API Gateway WebSocket APIs:"
    aws apigatewayv2 get-apis --query 'Items[?contains(Name, `chatbot`)].{Name:Name,ApiId:ApiId}' --output table 2>/dev/null || echo "None found"
    
    # List Secrets Manager secrets
    print_status "Secrets Manager Secrets:"
    aws secretsmanager list-secrets --query 'SecretList[?contains(Name, `chatbot`)].{Name:Name,Arn:ARN}' --output table 2>/dev/null || echo "None found"
}

# Function to destroy CDK stacks
destroy_stacks() {
    print_status "Destroying CDK stacks..."
    
    cd "$CDK_DIR"
    
    # Destroy all stacks
    if cdk destroy --all --force; then
        print_success "All CDK stacks destroyed successfully"
        cd ..
        return 0
    else
        print_error "CDK destruction failed"
        cd ..
        return 1
    fi
}

# Function to clean up any remaining resources
cleanup_remaining_resources() {
    print_status "Checking for any remaining resources..."
    
    # Check for remaining Lambda functions
    REMAINING_FUNCTIONS=$(aws lambda list-functions --query 'Functions[?contains(FunctionName, `Chatbot`) || contains(FunctionName, `WebSocket`) || contains(FunctionName, `Mcp`) || contains(FunctionName, `Session`)].FunctionName' --output text 2>/dev/null || echo "")
    
    if [ -n "$REMAINING_FUNCTIONS" ]; then
        print_warning "Found remaining Lambda functions:"
        echo "$REMAINING_FUNCTIONS"
        print_status "These may need to be deleted manually if they were created outside of CDK"
    fi
    
    # Check for remaining DynamoDB tables
    REMAINING_TABLES=$(aws dynamodb list-tables --query 'TableNames[?contains(@, `chatbot`) || contains(@, `sessions`) || contains(@, `conversations`) || contains(@, `analytics`)]' --output text 2>/dev/null || echo "")
    
    if [ -n "$REMAINING_TABLES" ]; then
        print_warning "Found remaining DynamoDB tables:"
        echo "$REMAINING_TABLES"
        print_status "These may need to be deleted manually if they were created outside of CDK"
    fi
    
    # Check for remaining API Gateway APIs
    REMAINING_APIS=$(aws apigatewayv2 get-apis --query 'Items[?contains(Name, `chatbot`)].ApiId' --output text 2>/dev/null || echo "")
    
    if [ -n "$REMAINING_APIS" ]; then
        print_warning "Found remaining API Gateway APIs:"
        echo "$REMAINING_APIS"
        print_status "These may need to be deleted manually if they were created outside of CDK"
    fi
    
    # Check for remaining secrets
    REMAINING_SECRETS=$(aws secretsmanager list-secrets --query 'SecretList[?contains(Name, `chatbot`)].Name' --output text 2>/dev/null || echo "")
    
    if [ -n "$REMAINING_SECRETS" ]; then
        print_warning "Found remaining Secrets Manager secrets:"
        echo "$REMAINING_SECRETS"
        print_status "These may need to be deleted manually if they were created outside of CDK"
    fi
}

# Function to clean up local files
cleanup_local_files() {
    print_status "Cleaning up local deployment artifacts..."
    
    # Remove CDK output directory
    if [ -d "cdk.out" ]; then
        rm -rf cdk.out
        print_success "Removed cdk.out directory"
    fi
    
    # Remove Lambda vendor directories
    find lambda -name "vendor" -type d -exec rm -rf {} + 2>/dev/null || true
    print_success "Removed Lambda vendor directories"
    
    # Remove Python cache files
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    print_success "Removed Python cache files"
}

# Main destruction function
main() {
    print_status "Starting Chatbot WebSocket System Destruction"
    echo "=============================================="
    
    # Pre-destruction checks
    if ! command_exists aws; then
        print_error "AWS CLI is not installed"
        exit 1
    fi
    
    if ! command_exists cdk; then
        print_error "AWS CDK is not installed"
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity >/dev/null 2>&1; then
        print_error "AWS credentials are not configured"
        exit 1
    fi
    
    # List resources that will be destroyed
    list_resources
    
    # Confirm destruction
    confirm_destruction
    
    # Destroy stacks
    if ! destroy_stacks; then
        print_error "Stack destruction failed"
        exit 1
    fi
    
    # Clean up remaining resources
    cleanup_remaining_resources
    
    # Clean up local files
    cleanup_local_files
    
    print_success "Destruction completed successfully!"
    print_status "All chatbot system resources have been removed."
}

# Handle script arguments
case "${1:-}" in
    --help|-h)
        echo "Chatbot WebSocket System Destroy Script"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --list         Only list resources that would be destroyed"
        echo "  --force        Skip confirmation prompt"
        echo ""
        echo "Environment Variables:"
        echo "  AWS_PROFILE    AWS profile to use (optional)"
        echo "  AWS_REGION     AWS region to use (optional)"
        echo ""
        exit 0
        ;;
    --list)
        print_status "Listing resources only..."
        list_resources
        exit 0
        ;;
    --force)
        print_status "Force mode enabled - skipping confirmation"
        # Override confirmation function
        confirm_destruction() { return 0; }
        main
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