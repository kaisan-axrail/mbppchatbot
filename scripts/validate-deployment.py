#!/usr/bin/env python3
"""
Deployment validation script for the chatbot WebSocket system.
This script validates that all components are properly deployed and functional.
"""

import json
import sys
import time
import boto3
import requests
import websocket
from typing import Dict, List, Optional, Tuple
from botocore.exceptions import ClientError, NoCredentialsError


class DeploymentValidator:
    """Validates the deployment of the chatbot WebSocket system."""
    
    def __init__(self, region: str = 'us-east-1'):
        """Initialize the validator with AWS clients."""
        self.region = region
        try:
            self.lambda_client = boto3.client('lambda', region_name=region)
            self.dynamodb_client = boto3.client('dynamodb', region_name=region)
            self.apigateway_client = boto3.client('apigatewayv2', region_name=region)
            self.secrets_client = boto3.client('secretsmanager', region_name=region)
            self.cloudformation_client = boto3.client('cloudformation', region_name=region)
        except NoCredentialsError:
            print("❌ AWS credentials not configured")
            sys.exit(1)
        
        self.validation_results = []
    
    def log_result(self, test_name: str, success: bool, message: str = ""):
        """Log a validation result."""
        status = "✅" if success else "❌"
        print(f"{status} {test_name}: {message}")
        self.validation_results.append({
            'test': test_name,
            'success': success,
            'message': message
        })
    
    def validate_lambda_functions(self) -> bool:
        """Validate that all Lambda functions are deployed and configured correctly."""
        print("\n🔍 Validating Lambda Functions...")
        
        expected_functions = [
            'WebSocketHandler',
            'McpServer', 
            'SessionCleanup'
        ]
        
        all_valid = True
        
        try:
            response = self.lambda_client.list_functions()
            deployed_functions = [f['FunctionName'] for f in response['Functions']]
            
            for expected in expected_functions:
                matching_functions = [f for f in deployed_functions if expected in f]
                
                if matching_functions:
                    function_name = matching_functions[0]
                    
                    # Get function configuration
                    try:
                        config = self.lambda_client.get_function_configuration(
                            FunctionName=function_name
                        )
                        
                        # Check if function is active
                        if config['State'] == 'Active':
                            self.log_result(
                                f"Lambda {expected}",
                                True,
                                f"Active ({function_name})"
                            )
                        else:
                            self.log_result(
                                f"Lambda {expected}",
                                False,
                                f"Not active: {config['State']}"
                            )
                            all_valid = False
                            
                    except ClientError as e:
                        self.log_result(
                            f"Lambda {expected}",
                            False,
                            f"Configuration error: {e}"
                        )
                        all_valid = False
                else:
                    self.log_result(
                        f"Lambda {expected}",
                        False,
                        "Function not found"
                    )
                    all_valid = False
                    
        except ClientError as e:
            self.log_result("Lambda Functions", False, f"AWS error: {e}")
            return False
            
        return all_valid
    
    def validate_dynamodb_tables(self) -> bool:
        """Validate that all DynamoDB tables are created and active."""
        print("\n🔍 Validating DynamoDB Tables...")
        
        expected_tables = [
            'chatbot-sessions',
            'chatbot-conversations', 
            'chatbot-analytics'
        ]
        
        all_valid = True
        
        try:
            response = self.dynamodb_client.list_tables()
            deployed_tables = response['TableNames']
            
            for expected in expected_tables:
                matching_tables = [t for t in deployed_tables if expected in t]
                
                if matching_tables:
                    table_name = matching_tables[0]
                    
                    # Get table status
                    try:
                        table_info = self.dynamodb_client.describe_table(
                            TableName=table_name
                        )
                        
                        status = table_info['Table']['TableStatus']
                        if status == 'ACTIVE':
                            self.log_result(
                                f"DynamoDB {expected}",
                                True,
                                f"Active ({table_name})"
                            )
                        else:
                            self.log_result(
                                f"DynamoDB {expected}",
                                False,
                                f"Status: {status}"
                            )
                            all_valid = False
                            
                    except ClientError as e:
                        self.log_result(
                            f"DynamoDB {expected}",
                            False,
                            f"Describe error: {e}"
                        )
                        all_valid = False
                else:
                    self.log_result(
                        f"DynamoDB {expected}",
                        False,
                        "Table not found"
                    )
                    all_valid = False
                    
        except ClientError as e:
            self.log_result("DynamoDB Tables", False, f"AWS error: {e}")
            return False
            
        return all_valid
    
    def validate_api_gateway(self) -> Tuple[bool, Optional[str]]:
        """Validate that the WebSocket API is deployed and accessible."""
        print("\n🔍 Validating API Gateway...")
        
        try:
            response = self.apigateway_client.get_apis()
            apis = response['Items']
            
            chatbot_apis = [api for api in apis if 'chatbot' in api.get('Name', '').lower()]
            
            if not chatbot_apis:
                self.log_result("API Gateway", False, "WebSocket API not found")
                return False, None
            
            api = chatbot_apis[0]
            api_id = api['ApiId']
            api_endpoint = api.get('ApiEndpoint', '')
            
            # Get API stages
            try:
                stages_response = self.apigateway_client.get_stages(ApiId=api_id)
                stages = stages_response['Items']
                
                if stages:
                    stage = stages[0]
                    stage_name = stage['StageName']
                    websocket_url = f"{api_endpoint}/{stage_name}"
                    
                    self.log_result(
                        "API Gateway WebSocket",
                        True,
                        f"Available at {websocket_url}"
                    )
                    return True, websocket_url
                else:
                    self.log_result("API Gateway", False, "No stages found")
                    return False, None
                    
            except ClientError as e:
                self.log_result("API Gateway", False, f"Stages error: {e}")
                return False, None
                
        except ClientError as e:
            self.log_result("API Gateway", False, f"AWS error: {e}")
            return False, None
    
    def validate_secrets_manager(self) -> bool:
        """Validate that secrets are created in Secrets Manager."""
        print("\n🔍 Validating Secrets Manager...")
        
        expected_secrets = [
            'chatbot/api-keys',
            'chatbot/mcp-server'
        ]
        
        all_valid = True
        
        try:
            response = self.secrets_client.list_secrets()
            deployed_secrets = [s['Name'] for s in response['SecretList']]
            
            for expected in expected_secrets:
                matching_secrets = [s for s in deployed_secrets if expected in s]
                
                if matching_secrets:
                    secret_name = matching_secrets[0]
                    self.log_result(
                        f"Secret {expected}",
                        True,
                        f"Available ({secret_name})"
                    )
                else:
                    self.log_result(
                        f"Secret {expected}",
                        False,
                        "Secret not found"
                    )
                    all_valid = False
                    
        except ClientError as e:
            self.log_result("Secrets Manager", False, f"AWS error: {e}")
            return False
            
        return all_valid
    
    def validate_cloudformation_stacks(self) -> bool:
        """Validate that CloudFormation stacks are deployed successfully."""
        print("\n🔍 Validating CloudFormation Stacks...")
        
        expected_stacks = [
            'ChatbotDatabaseStack',
            'ChatbotLambdaStack',
            'ChatbotApiStack',
            'ChatbotMainStack'
        ]
        
        all_valid = True
        
        try:
            response = self.cloudformation_client.list_stacks(
                StackStatusFilter=[
                    'CREATE_COMPLETE',
                    'UPDATE_COMPLETE',
                    'CREATE_FAILED',
                    'UPDATE_FAILED'
                ]
            )
            
            deployed_stacks = {s['StackName']: s['StackStatus'] for s in response['StackSummaries']}
            
            for expected in expected_stacks:
                matching_stacks = {k: v for k, v in deployed_stacks.items() if expected in k}
                
                if matching_stacks:
                    stack_name, status = list(matching_stacks.items())[0]
                    
                    if status in ['CREATE_COMPLETE', 'UPDATE_COMPLETE']:
                        self.log_result(
                            f"Stack {expected}",
                            True,
                            f"{status} ({stack_name})"
                        )
                    else:
                        self.log_result(
                            f"Stack {expected}",
                            False,
                            f"{status} ({stack_name})"
                        )
                        all_valid = False
                else:
                    self.log_result(
                        f"Stack {expected}",
                        False,
                        "Stack not found"
                    )
                    all_valid = False
                    
        except ClientError as e:
            self.log_result("CloudFormation Stacks", False, f"AWS error: {e}")
            return False
            
        return all_valid
    
    def test_websocket_connection(self, websocket_url: str) -> bool:
        """Test WebSocket connection to the API."""
        print("\n🔍 Testing WebSocket Connection...")
        
        try:
            # Simple connection test
            ws = websocket.create_connection(websocket_url, timeout=10)
            
            # Send a test message
            test_message = {
                "action": "test",
                "message": "deployment validation"
            }
            ws.send(json.dumps(test_message))
            
            # Wait for response (with timeout)
            ws.settimeout(5)
            try:
                response = ws.recv()
                ws.close()
                
                self.log_result(
                    "WebSocket Connection",
                    True,
                    "Connection successful"
                )
                return True
                
            except websocket.WebSocketTimeoutException:
                ws.close()
                self.log_result(
                    "WebSocket Connection",
                    True,
                    "Connection established (no response expected)"
                )
                return True
                
        except Exception as e:
            self.log_result(
                "WebSocket Connection",
                False,
                f"Connection failed: {e}"
            )
            return False
    
    def generate_report(self) -> Dict:
        """Generate a comprehensive validation report."""
        total_tests = len(self.validation_results)
        passed_tests = sum(1 for r in self.validation_results if r['success'])
        failed_tests = total_tests - passed_tests
        
        return {
            'summary': {
                'total_tests': total_tests,
                'passed': passed_tests,
                'failed': failed_tests,
                'success_rate': f"{(passed_tests/total_tests)*100:.1f}%" if total_tests > 0 else "0%"
            },
            'results': self.validation_results,
            'overall_status': 'PASS' if failed_tests == 0 else 'FAIL'
        }
    
    def run_all_validations(self) -> bool:
        """Run all validation tests."""
        print("🚀 Starting Deployment Validation")
        print("=" * 50)
        
        # Run all validation tests
        lambda_valid = self.validate_lambda_functions()
        dynamodb_valid = self.validate_dynamodb_tables()
        api_valid, websocket_url = self.validate_api_gateway()
        secrets_valid = self.validate_secrets_manager()
        stacks_valid = self.validate_cloudformation_stacks()
        
        # Test WebSocket connection if API is valid
        websocket_valid = True
        if api_valid and websocket_url:
            websocket_valid = self.test_websocket_connection(websocket_url)
        
        # Generate and display report
        report = self.generate_report()
        
        print("\n📊 Validation Summary")
        print("=" * 50)
        print(f"Total Tests: {report['summary']['total_tests']}")
        print(f"Passed: {report['summary']['passed']}")
        print(f"Failed: {report['summary']['failed']}")
        print(f"Success Rate: {report['summary']['success_rate']}")
        print(f"Overall Status: {report['overall_status']}")
        
        if report['overall_status'] == 'FAIL':
            print("\n❌ Deployment validation failed!")
            print("Please check the failed tests above and resolve any issues.")
            return False
        else:
            print("\n✅ Deployment validation passed!")
            print("All components are properly deployed and functional.")
            return True


def main():
    """Main function to run deployment validation."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate chatbot deployment')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--output', help='Output file for validation report (JSON)')
    
    args = parser.parse_args()
    
    validator = DeploymentValidator(region=args.region)
    success = validator.run_all_validations()
    
    # Save report if output file specified
    if args.output:
        report = validator.generate_report()
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n📄 Validation report saved to {args.output}")
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()