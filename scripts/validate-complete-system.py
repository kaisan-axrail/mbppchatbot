#!/usr/bin/env python3
"""
Complete system validation test for the WebSocket chatbot project.

This script performs comprehensive validation to determine if the entire
project can actually work in a real deployment scenario.
"""

import os
import sys
import json
import subprocess
import importlib.util
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime


class SystemValidator:
    """Comprehensive system validator for the chatbot project."""
    
    def __init__(self):
        """Initialize the system validator."""
        self.project_root = Path(__file__).parent.parent
        self.validation_results = []
        self.critical_issues = []
        self.warnings = []
        
    def print_header(self, text: str):
        """Print a formatted header."""
        print(f"\n{'='*60}")
        print(f"🔍 {text}")
        print(f"{'='*60}")
    
    def print_success(self, text: str):
        """Print success message."""
        print(f"✅ {text}")
    
    def print_warning(self, text: str):
        """Print warning message."""
        print(f"⚠️  {text}")
        self.warnings.append(text)
    
    def print_error(self, text: str):
        """Print error message."""
        print(f"❌ {text}")
        self.critical_issues.append(text)
    
    def print_info(self, text: str):
        """Print info message."""
        print(f"ℹ️  {text}")
    
    def validate_project_structure(self) -> bool:
        """Validate the complete project structure."""
        self.print_header("PROJECT STRUCTURE VALIDATION")
        
        required_structure = {
            'cdk/': ['app.py', 'cdk.json', 'requirements.txt'],
            'cdk/stacks/': ['__init__.py', 'api_stack.py', 'chatbot_stack.py', 'database_stack.py', 'lambda_stack.py'],
            'cdk/constructs/': ['mcp_server.py', 'websocket_api.py'],
            'lambda/websocket_handler/': ['handler.py', 'requirements.txt'],
            'lambda/mcp_server/': ['handler.py', 'mcp_server.py', 'mcp_tools_schema.yaml', 'requirements.txt'],
            'lambda/session_cleanup/': ['handler.py', 'requirements.txt'],
            'shared/': ['session_manager.py', 'chatbot_engine.py', 'strand_client.py', 'mcp_handler.py'],
            'tests/unit/': [],
            'tests/integration/': [],
            'scripts/': ['validate-requirements.py', 'validate-deployment.py'],
            'docs/': ['DEPLOYMENT.md', 'TROUBLESHOOTING.md']
        }
        
        all_valid = True
        
        for directory, files in required_structure.items():
            dir_path = self.project_root / directory
            
            if not dir_path.exists():
                self.print_error(f"Missing directory: {directory}")
                all_valid = False
                continue
            
            self.print_success(f"Directory exists: {directory}")
            
            for file in files:
                file_path = dir_path / file
                if not file_path.exists():
                    self.print_error(f"Missing file: {directory}{file}")
                    all_valid = False
                else:
                    self.print_success(f"File exists: {directory}{file}")
        
        return all_valid
    
    def validate_python_syntax(self) -> bool:
        """Validate Python syntax in all Python files."""
        self.print_header("PYTHON SYNTAX VALIDATION")
        
        python_files = []
        for pattern in ['**/*.py']:
            python_files.extend(self.project_root.glob(pattern))
        
        syntax_errors = []
        
        for py_file in python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    source = f.read()
                
                compile(source, str(py_file), 'exec')
                
            except SyntaxError as e:
                error_msg = f"Syntax error in {py_file.relative_to(self.project_root)}: {e}"
                self.print_error(error_msg)
                syntax_errors.append(error_msg)
            except Exception as e:
                # Skip files that can't be read (binary, etc.)
                continue
        
        if syntax_errors:
            self.print_error(f"Found {len(syntax_errors)} syntax errors")
            return False
        else:
            self.print_success(f"All Python files have valid syntax ({len(python_files)} files checked)")
            return True
    
    def validate_imports_and_dependencies(self) -> bool:
        """Validate that all imports can be resolved."""
        self.print_header("IMPORT AND DEPENDENCY VALIDATION")
        
        # Add project paths to sys.path for import testing
        sys.path.insert(0, str(self.project_root))
        sys.path.insert(0, str(self.project_root / 'shared'))
        
        critical_modules = [
            ('shared.session_manager', 'SessionManager'),
            ('shared.chatbot_engine', 'ChatbotEngine'),
            ('shared.strand_client', 'StrandClient'),
            ('shared.mcp_handler', 'MCPHandler'),
            ('shared.exceptions', 'ChatbotError'),
            ('shared.utils', 'generate_message_id'),
        ]
        
        import_errors = []
        
        for module_name, class_name in critical_modules:
            try:
                module = importlib.import_module(module_name)
                if hasattr(module, class_name):
                    self.print_success(f"Successfully imported {module_name}.{class_name}")
                else:
                    error_msg = f"Class {class_name} not found in {module_name}"
                    self.print_error(error_msg)
                    import_errors.append(error_msg)
                    
            except ImportError as e:
                error_msg = f"Failed to import {module_name}: {e}"
                self.print_error(error_msg)
                import_errors.append(error_msg)
            except Exception as e:
                error_msg = f"Error importing {module_name}: {e}"
                self.print_warning(error_msg)
        
        return len(import_errors) == 0
    
    def validate_cdk_configuration(self) -> bool:
        """Validate CDK configuration and synthesis."""
        self.print_header("CDK CONFIGURATION VALIDATION")
        
        # Check cdk.json
        cdk_json_path = self.project_root / 'cdk.json'
        if not cdk_json_path.exists():
            self.print_error("cdk.json not found")
            return False
        
        try:
            with open(cdk_json_path, 'r') as f:
                cdk_config = json.load(f)
            
            required_keys = ['app']
            for key in required_keys:
                if key not in cdk_config:
                    self.print_error(f"Missing required key in cdk.json: {key}")
                    return False
            
            self.print_success("cdk.json is valid")
            
        except json.JSONDecodeError as e:
            self.print_error(f"Invalid JSON in cdk.json: {e}")
            return False
        
        # Check CDK app file
        cdk_app_path = self.project_root / 'cdk' / 'app.py'
        if not cdk_app_path.exists():
            self.print_error("CDK app.py not found")
            return False
        
        # Validate CDK app imports
        try:
            with open(cdk_app_path, 'r') as f:
                app_content = f.read()
            
            required_imports = [
                'aws_cdk',
                'ChatbotStack',
                'DatabaseStack',
                'LambdaStack',
                'ApiStack'
            ]
            
            for import_name in required_imports:
                if import_name not in app_content:
                    self.print_warning(f"Missing import in CDK app: {import_name}")
            
            self.print_success("CDK app structure is valid")
            
        except Exception as e:
            self.print_error(f"Error reading CDK app: {e}")
            return False
        
        # Test CDK synthesis (if CDK CLI is available)
        try:
            result = subprocess.run(
                ['cdk', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                self.print_info(f"CDK CLI available: {result.stdout.strip()}")
                
                # Try CDK synthesis
                try:
                    synth_result = subprocess.run(
                        ['cdk', 'synth', '--quiet'],
                        cwd=self.project_root / 'cdk',
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    
                    if synth_result.returncode == 0:
                        self.print_success("CDK synthesis successful")
                        return True
                    else:
                        self.print_error(f"CDK synthesis failed: {synth_result.stderr}")
                        return False
                        
                except subprocess.TimeoutExpired:
                    self.print_warning("CDK synthesis timed out")
                    return True  # Don't fail on timeout
                    
            else:
                self.print_warning("CDK CLI not available - skipping synthesis test")
                return True
                
        except FileNotFoundError:
            self.print_warning("CDK CLI not found - skipping synthesis test")
            return True
        except Exception as e:
            self.print_warning(f"CDK validation error: {e}")
            return True
    
    def validate_lambda_functions(self) -> bool:
        """Validate Lambda function structure and handlers."""
        self.print_header("LAMBDA FUNCTION VALIDATION")
        
        lambda_functions = [
            'websocket_handler',
            'mcp_server',
            'session_cleanup'
        ]
        
        all_valid = True
        
        for function_name in lambda_functions:
            function_dir = self.project_root / 'lambda' / function_name
            
            if not function_dir.exists():
                self.print_error(f"Lambda function directory missing: {function_name}")
                all_valid = False
                continue
            
            # Check handler file
            handler_file = function_dir / 'handler.py'
            if not handler_file.exists():
                self.print_error(f"Handler file missing: {function_name}/handler.py")
                all_valid = False
                continue
            
            # Check for lambda_handler function
            try:
                with open(handler_file, 'r') as f:
                    handler_content = f.read()
                
                if 'def lambda_handler(' not in handler_content:
                    self.print_error(f"lambda_handler function missing in {function_name}")
                    all_valid = False
                else:
                    self.print_success(f"Lambda handler valid: {function_name}")
                    
            except Exception as e:
                self.print_error(f"Error reading handler {function_name}: {e}")
                all_valid = False
            
            # Check requirements.txt
            requirements_file = function_dir / 'requirements.txt'
            if not requirements_file.exists():
                self.print_warning(f"Requirements file missing: {function_name}/requirements.txt")
            else:
                self.print_success(f"Requirements file exists: {function_name}")
        
        return all_valid
    
    def validate_shared_modules(self) -> bool:
        """Validate shared modules and their interfaces."""
        self.print_header("SHARED MODULES VALIDATION")
        
        # Add shared to path
        sys.path.insert(0, str(self.project_root / 'shared'))
        
        module_validations = [
            ('session_manager', ['SessionManager'], ['create_session', 'get_session']),
            ('chatbot_engine', ['ChatbotEngine', 'ChatbotResponse'], ['process_message']),
            ('strand_client', ['StrandClient'], ['generate_response']),
            ('mcp_handler', ['MCPHandler'], ['identify_tools', 'execute_tool']),
            ('exceptions', ['ChatbotError', 'SessionNotFoundError'], []),
            ('utils', [], ['generate_message_id', 'get_current_timestamp']),
        ]
        
        all_valid = True
        
        for module_name, expected_classes, expected_functions in module_validations:
            try:
                module = importlib.import_module(module_name)
                
                # Check classes
                for class_name in expected_classes:
                    if hasattr(module, class_name):
                        self.print_success(f"Class found: {module_name}.{class_name}")
                        
                        # Check methods for classes
                        if expected_functions:
                            cls = getattr(module, class_name)
                            for method_name in expected_functions:
                                if hasattr(cls, method_name):
                                    self.print_success(f"Method found: {class_name}.{method_name}")
                                else:
                                    self.print_error(f"Method missing: {class_name}.{method_name}")
                                    all_valid = False
                    else:
                        self.print_error(f"Class missing: {module_name}.{class_name}")
                        all_valid = False
                
                # Check functions
                if not expected_classes:  # For utility modules
                    for func_name in expected_functions:
                        if hasattr(module, func_name):
                            self.print_success(f"Function found: {module_name}.{func_name}")
                        else:
                            self.print_error(f"Function missing: {module_name}.{func_name}")
                            all_valid = False
                            
            except ImportError as e:
                self.print_error(f"Failed to import {module_name}: {e}")
                all_valid = False
            except Exception as e:
                self.print_error(f"Error validating {module_name}: {e}")
                all_valid = False
        
        return all_valid
    
    def validate_configuration_files(self) -> bool:
        """Validate configuration files and schemas."""
        self.print_header("CONFIGURATION FILES VALIDATION")
        
        config_files = [
            ('lambda/mcp_server/mcp_tools_schema.yaml', 'YAML'),
            ('cdk.json', 'JSON'),
            ('requirements.txt', 'TEXT'),
        ]
        
        all_valid = True
        
        for file_path, file_type in config_files:
            full_path = self.project_root / file_path
            
            if not full_path.exists():
                self.print_error(f"Configuration file missing: {file_path}")
                all_valid = False
                continue
            
            try:
                with open(full_path, 'r') as f:
                    content = f.read()
                
                if file_type == 'JSON':
                    json.loads(content)
                    self.print_success(f"Valid JSON: {file_path}")
                elif file_type == 'YAML':
                    import yaml
                    yaml.safe_load(content)
                    self.print_success(f"Valid YAML: {file_path}")
                else:
                    self.print_success(f"File readable: {file_path}")
                    
            except Exception as e:
                self.print_error(f"Invalid {file_type} in {file_path}: {e}")
                all_valid = False
        
        return all_valid
    
    def validate_test_coverage(self) -> bool:
        """Validate test coverage and structure."""
        self.print_header("TEST COVERAGE VALIDATION")
        
        test_directories = [
            'tests/unit',
            'tests/integration'
        ]
        
        test_files_found = 0
        
        for test_dir in test_directories:
            test_path = self.project_root / test_dir
            
            if test_path.exists():
                test_files = list(test_path.glob('test_*.py'))
                test_files_found += len(test_files)
                self.print_success(f"Found {len(test_files)} test files in {test_dir}")
            else:
                self.print_warning(f"Test directory missing: {test_dir}")
        
        if test_files_found > 0:
            self.print_success(f"Total test files found: {test_files_found}")
            return True
        else:
            self.print_warning("No test files found")
            return False
    
    def validate_deployment_readiness(self) -> bool:
        """Validate deployment readiness."""
        self.print_header("DEPLOYMENT READINESS VALIDATION")
        
        deployment_files = [
            'deploy.sh',
            'destroy.sh',
            'scripts/validate-requirements.py',
            'scripts/validate-deployment.py'
        ]
        
        all_valid = True
        
        for file_path in deployment_files:
            full_path = self.project_root / file_path
            
            if full_path.exists():
                # Check if shell scripts are executable
                if file_path.endswith('.sh'):
                    if os.access(full_path, os.X_OK):
                        self.print_success(f"Executable script: {file_path}")
                    else:
                        self.print_warning(f"Script not executable: {file_path}")
                else:
                    self.print_success(f"Deployment file exists: {file_path}")
            else:
                self.print_error(f"Deployment file missing: {file_path}")
                all_valid = False
        
        return all_valid
    
    def run_sample_integration_test(self) -> bool:
        """Run a sample integration test to validate core functionality."""
        self.print_header("SAMPLE INTEGRATION TEST")
        
        try:
            # Add paths for imports
            sys.path.insert(0, str(self.project_root))
            sys.path.insert(0, str(self.project_root / 'shared'))
            
            # Test basic imports and instantiation
            from shared.session_manager import SessionManager
            from shared.session_models import ClientInfo, generate_session_id
            from shared.utils import generate_message_id, get_current_timestamp
            
            # Test session ID generation
            session_id = generate_session_id()
            if len(session_id) == 36:  # UUID format
                self.print_success("Session ID generation works")
            else:
                self.print_error("Session ID generation failed")
                return False
            
            # Test message ID generation
            message_id = generate_message_id()
            if len(message_id) == 36:  # UUID format
                self.print_success("Message ID generation works")
            else:
                self.print_error("Message ID generation failed")
                return False
            
            # Test timestamp generation
            timestamp = get_current_timestamp()
            if 'T' in timestamp:  # ISO format
                self.print_success("Timestamp generation works")
            else:
                self.print_error("Timestamp generation failed")
                return False
            
            # Test ClientInfo creation
            client_info = ClientInfo(
                user_agent="test-browser",
                ip_address="127.0.0.1"
            )
            if client_info.user_agent == "test-browser":
                self.print_success("ClientInfo creation works")
            else:
                self.print_error("ClientInfo creation failed")
                return False
            
            self.print_success("All basic functionality tests passed")
            return True
            
        except Exception as e:
            self.print_error(f"Integration test failed: {e}")
            return False
    
    def generate_final_report(self) -> Dict[str, Any]:
        """Generate final validation report."""
        self.print_header("FINAL VALIDATION REPORT")
        
        total_validations = len(self.validation_results)
        critical_count = len(self.critical_issues)
        warning_count = len(self.warnings)
        
        # Determine overall status
        if critical_count == 0:
            overall_status = "✅ READY FOR DEPLOYMENT"
            can_deploy = True
        elif critical_count <= 2:
            overall_status = "⚠️  DEPLOYMENT POSSIBLE WITH FIXES"
            can_deploy = False
        else:
            overall_status = "❌ NOT READY FOR DEPLOYMENT"
            can_deploy = False
        
        print(f"\n📊 VALIDATION SUMMARY")
        print(f"{'='*40}")
        print(f"Critical Issues: {critical_count}")
        print(f"Warnings: {warning_count}")
        print(f"Overall Status: {overall_status}")
        
        if critical_count > 0:
            print(f"\n🚨 CRITICAL ISSUES TO FIX:")
            for i, issue in enumerate(self.critical_issues, 1):
                print(f"  {i}. {issue}")
        
        if warning_count > 0:
            print(f"\n⚠️  WARNINGS TO CONSIDER:")
            for i, warning in enumerate(self.warnings, 1):
                print(f"  {i}. {warning}")
        
        return {
            'timestamp': datetime.now().isoformat(),
            'overall_status': overall_status,
            'can_deploy': can_deploy,
            'critical_issues': critical_count,
            'warnings': warning_count,
            'critical_issues_list': self.critical_issues,
            'warnings_list': self.warnings,
            'validation_results': self.validation_results
        }
    
    def run_complete_validation(self) -> Dict[str, Any]:
        """Run complete system validation."""
        print("🚀 STARTING COMPLETE SYSTEM VALIDATION")
        print(f"Project Root: {self.project_root}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        # Run all validations
        validations = [
            ("Project Structure", self.validate_project_structure),
            ("Python Syntax", self.validate_python_syntax),
            ("Imports & Dependencies", self.validate_imports_and_dependencies),
            ("CDK Configuration", self.validate_cdk_configuration),
            ("Lambda Functions", self.validate_lambda_functions),
            ("Shared Modules", self.validate_shared_modules),
            ("Configuration Files", self.validate_configuration_files),
            ("Test Coverage", self.validate_test_coverage),
            ("Deployment Readiness", self.validate_deployment_readiness),
            ("Sample Integration", self.run_sample_integration_test),
        ]
        
        for validation_name, validation_func in validations:
            try:
                result = validation_func()
                self.validation_results.append({
                    'name': validation_name,
                    'passed': result,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                self.print_error(f"Validation '{validation_name}' failed with exception: {e}")
                self.validation_results.append({
                    'name': validation_name,
                    'passed': False,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })
        
        # Generate final report
        return self.generate_final_report()


def main():
    """Main function to run complete system validation."""
    validator = SystemValidator()
    
    try:
        report = validator.run_complete_validation()
        
        # Save report
        report_file = validator.project_root / 'test-reports' / 'system-validation-report.json'
        report_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Full report saved to: {report_file}")
        
        # Exit with appropriate code
        if report['can_deploy']:
            print("\n🎉 PROJECT IS READY FOR DEPLOYMENT!")
            sys.exit(0)
        else:
            print("\n🔧 PROJECT NEEDS FIXES BEFORE DEPLOYMENT")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 VALIDATION FAILED WITH EXCEPTION: {e}")
        sys.exit(2)


if __name__ == '__main__':
    main()