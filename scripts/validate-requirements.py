#!/usr/bin/env python3
"""
Requirements validation script for the chatbot WebSocket system.
This script validates that all required dependencies and configurations are in place.
"""

import os
import sys
import json
import subprocess
import importlib.util
from pathlib import Path
from typing import Dict, List, Tuple, Optional


class RequirementsValidator:
    """Validates system requirements and dependencies."""
    
    def __init__(self):
        """Initialize the validator."""
        self.validation_results = []
        self.project_root = Path(__file__).parent.parent
    
    def log_result(self, test_name: str, success: bool, message: str = ""):
        """Log a validation result."""
        status = "✅" if success else "❌"
        print(f"{status} {test_name}: {message}")
        self.validation_results.append({
            'test': test_name,
            'success': success,
            'message': message
        })
    
    def check_python_version(self) -> bool:
        """Check if Python version meets requirements."""
        print("\n🐍 Checking Python Version...")
        
        required_version = (3, 11)
        current_version = sys.version_info[:2]
        
        if current_version >= required_version:
            self.log_result(
                "Python Version",
                True,
                f"Python {'.'.join(map(str, current_version))} (required: {'.'.join(map(str, required_version))}+)"
            )
            return True
        else:
            self.log_result(
                "Python Version",
                False,
                f"Python {'.'.join(map(str, current_version))} is too old (required: {'.'.join(map(str, required_version))}+)"
            )
            return False
    
    def check_command_availability(self, command: str, required: bool = True) -> bool:
        """Check if a command is available in PATH."""
        try:
            result = subprocess.run(
                [command, '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                version = result.stdout.strip().split('\n')[0]
                self.log_result(
                    f"Command {command}",
                    True,
                    f"Available ({version})"
                )
                return True
            else:
                self.log_result(
                    f"Command {command}",
                    not required,
                    f"Not available or error: {result.stderr.strip()}"
                )
                return False
                
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.log_result(
                f"Command {command}",
                not required,
                "Not found in PATH"
            )
            return False
    
    def check_system_commands(self) -> bool:
        """Check availability of required system commands."""
        print("\n🔧 Checking System Commands...")
        
        required_commands = [
            'aws',
            'cdk',
            'node',
            'npm'
        ]
        
        optional_commands = [
            'wscat',
            'jq'
        ]
        
        all_required_available = True
        
        for command in required_commands:
            if not self.check_command_availability(command, required=True):
                all_required_available = False
        
        for command in optional_commands:
            self.check_command_availability(command, required=False)
        
        return all_required_available
    
    def check_aws_configuration(self) -> bool:
        """Check AWS CLI configuration."""
        print("\n☁️ Checking AWS Configuration...")
        
        try:
            # Check AWS credentials
            result = subprocess.run(
                ['aws', 'sts', 'get-caller-identity'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                identity = json.loads(result.stdout)
                account_id = identity.get('Account', 'Unknown')
                user_arn = identity.get('Arn', 'Unknown')
                
                self.log_result(
                    "AWS Credentials",
                    True,
                    f"Configured for account {account_id}"
                )
                
                # Check AWS region
                region_result = subprocess.run(
                    ['aws', 'configure', 'get', 'region'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if region_result.returncode == 0 and region_result.stdout.strip():
                    region = region_result.stdout.strip()
                    self.log_result(
                        "AWS Region",
                        True,
                        f"Set to {region}"
                    )
                else:
                    self.log_result(
                        "AWS Region",
                        False,
                        "Not configured (set with 'aws configure')"
                    )
                    return False
                
                return True
            else:
                self.log_result(
                    "AWS Credentials",
                    False,
                    f"Not configured: {result.stderr.strip()}"
                )
                return False
                
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            self.log_result(
                "AWS Configuration",
                False,
                f"Error checking configuration: {e}"
            )
            return False
    
    def check_python_dependencies(self) -> bool:
        """Check if required Python packages are installed."""
        print("\n📦 Checking Python Dependencies...")
        
        # Check main requirements
        main_requirements_file = self.project_root / 'requirements.txt'
        cdk_requirements_file = self.project_root / 'cdk' / 'requirements.txt'
        
        all_dependencies_ok = True
        
        if main_requirements_file.exists():
            if not self._check_requirements_file(main_requirements_file, "Main"):
                all_dependencies_ok = False
        else:
            self.log_result(
                "Main Requirements File",
                False,
                f"File not found: {main_requirements_file}"
            )
            all_dependencies_ok = False
        
        if cdk_requirements_file.exists():
            if not self._check_requirements_file(cdk_requirements_file, "CDK"):
                all_dependencies_ok = False
        else:
            self.log_result(
                "CDK Requirements File",
                False,
                f"File not found: {cdk_requirements_file}"
            )
            all_dependencies_ok = False
        
        # Check Lambda function dependencies
        lambda_dir = self.project_root / 'lambda'
        if lambda_dir.exists():
            for function_dir in lambda_dir.iterdir():
                if function_dir.is_dir():
                    req_file = function_dir / 'requirements.txt'
                    if req_file.exists():
                        self._check_requirements_file(
                            req_file, 
                            f"Lambda {function_dir.name}"
                        )
        
        return all_dependencies_ok
    
    def _check_requirements_file(self, requirements_file: Path, context: str) -> bool:
        """Check if packages in a requirements file are installed."""
        try:
            with open(requirements_file, 'r') as f:
                requirements = f.read().strip().split('\n')
            
            missing_packages = []
            
            for requirement in requirements:
                requirement = requirement.strip()
                if not requirement or requirement.startswith('#'):
                    continue
                
                # Extract package name (handle version specifiers)
                package_name = requirement.split('>=')[0].split('==')[0].split('<=')[0].split('>')[0].split('<')[0].split('!=')[0].strip()
                
                # Try to import the package
                try:
                    importlib.import_module(package_name.replace('-', '_'))
                except ImportError:
                    missing_packages.append(package_name)
            
            if missing_packages:
                self.log_result(
                    f"{context} Dependencies",
                    False,
                    f"Missing packages: {', '.join(missing_packages)}"
                )
                return False
            else:
                self.log_result(
                    f"{context} Dependencies",
                    True,
                    f"All packages available ({len(requirements)} checked)"
                )
                return True
                
        except Exception as e:
            self.log_result(
                f"{context} Dependencies",
                False,
                f"Error checking requirements: {e}"
            )
            return False
    
    def check_project_structure(self) -> bool:
        """Check if project structure is correct."""
        print("\n📁 Checking Project Structure...")
        
        required_files = [
            'cdk/app.py',
            'cdk/cdk.json',
            'lambda/websocket_handler/handler.py',
            'lambda/mcp_server/handler.py',
            'lambda/session_cleanup/handler.py',
            'shared/session_manager.py',
            'shared/chatbot_engine.py'
        ]
        
        required_dirs = [
            'cdk/stacks',
            'cdk/constructs',
            'lambda',
            'shared',
            'tests',
            'config/environments'
        ]
        
        all_structure_ok = True
        
        # Check required files
        for file_path in required_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                self.log_result(
                    f"File {file_path}",
                    True,
                    "Present"
                )
            else:
                self.log_result(
                    f"File {file_path}",
                    False,
                    "Missing"
                )
                all_structure_ok = False
        
        # Check required directories
        for dir_path in required_dirs:
            full_path = self.project_root / dir_path
            if full_path.exists() and full_path.is_dir():
                self.log_result(
                    f"Directory {dir_path}",
                    True,
                    "Present"
                )
            else:
                self.log_result(
                    f"Directory {dir_path}",
                    False,
                    "Missing"
                )
                all_structure_ok = False
        
        return all_structure_ok
    
    def check_cdk_configuration(self) -> bool:
        """Check CDK configuration files."""
        print("\n⚙️ Checking CDK Configuration...")
        
        cdk_json_path = self.project_root / 'cdk.json'
        
        if not cdk_json_path.exists():
            self.log_result(
                "CDK Configuration",
                False,
                "cdk.json not found"
            )
            return False
        
        try:
            with open(cdk_json_path, 'r') as f:
                cdk_config = json.load(f)
            
            # Check required configuration
            if 'app' not in cdk_config:
                self.log_result(
                    "CDK App Configuration",
                    False,
                    "Missing 'app' configuration in cdk.json"
                )
                return False
            
            self.log_result(
                "CDK Configuration",
                True,
                f"Valid configuration found"
            )
            
            # Check if CDK can synthesize
            try:
                result = subprocess.run(
                    ['cdk', 'synth', '--quiet'],
                    cwd=self.project_root / 'cdk',
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode == 0:
                    self.log_result(
                        "CDK Synthesis",
                        True,
                        "CDK app can be synthesized"
                    )
                    return True
                else:
                    self.log_result(
                        "CDK Synthesis",
                        False,
                        f"Synthesis failed: {result.stderr.strip()}"
                    )
                    return False
                    
            except subprocess.TimeoutExpired:
                self.log_result(
                    "CDK Synthesis",
                    False,
                    "Synthesis timed out"
                )
                return False
                
        except json.JSONDecodeError as e:
            self.log_result(
                "CDK Configuration",
                False,
                f"Invalid JSON in cdk.json: {e}"
            )
            return False
        except Exception as e:
            self.log_result(
                "CDK Configuration",
                False,
                f"Error reading cdk.json: {e}"
            )
            return False
    
    def check_environment_configs(self) -> bool:
        """Check environment configuration files."""
        print("\n🌍 Checking Environment Configurations...")
        
        config_dir = self.project_root / 'config' / 'environments'
        
        if not config_dir.exists():
            self.log_result(
                "Environment Configs",
                False,
                "Environment configuration directory not found"
            )
            return False
        
        required_configs = ['dev.json', 'prod.json']
        all_configs_ok = True
        
        for config_file in required_configs:
            config_path = config_dir / config_file
            
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                    
                    # Validate required fields
                    required_fields = ['environment', 'region', 'lambdaConfig']
                    missing_fields = [field for field in required_fields if field not in config]
                    
                    if missing_fields:
                        self.log_result(
                            f"Config {config_file}",
                            False,
                            f"Missing fields: {', '.join(missing_fields)}"
                        )
                        all_configs_ok = False
                    else:
                        self.log_result(
                            f"Config {config_file}",
                            True,
                            "Valid configuration"
                        )
                        
                except json.JSONDecodeError as e:
                    self.log_result(
                        f"Config {config_file}",
                        False,
                        f"Invalid JSON: {e}"
                    )
                    all_configs_ok = False
            else:
                self.log_result(
                    f"Config {config_file}",
                    False,
                    "Configuration file not found"
                )
                all_configs_ok = False
        
        return all_configs_ok
    
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
        """Run all validation checks."""
        print("🔍 Starting Requirements Validation")
        print("=" * 50)
        
        # Run all validation checks
        python_ok = self.check_python_version()
        commands_ok = self.check_system_commands()
        aws_ok = self.check_aws_configuration()
        deps_ok = self.check_python_dependencies()
        structure_ok = self.check_project_structure()
        cdk_ok = self.check_cdk_configuration()
        env_ok = self.check_environment_configs()
        
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
            print("\n❌ Requirements validation failed!")
            print("Please resolve the issues above before proceeding with deployment.")
            
            # Provide installation suggestions
            print("\n💡 Installation Suggestions:")
            print("- Install AWS CLI: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html")
            print("- Install CDK: npm install -g aws-cdk")
            print("- Install Python dependencies: pip3 install -r requirements.txt")
            print("- Configure AWS: aws configure")
            
            return False
        else:
            print("\n✅ Requirements validation passed!")
            print("All requirements are met. You can proceed with deployment.")
            return True


def main():
    """Main function to run requirements validation."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate deployment requirements')
    parser.add_argument('--output', help='Output file for validation report (JSON)')
    
    args = parser.parse_args()
    
    validator = RequirementsValidator()
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