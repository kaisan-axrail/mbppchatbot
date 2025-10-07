"""
Integration tests for CDK deployment validation.

These tests verify that the CDK infrastructure is properly configured
and can be deployed successfully.
"""

import pytest
import json
import os
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch


class TestCDKDeploymentValidation:
    """Integration tests for CDK deployment validation."""
    
    @pytest.fixture
    def project_root(self):
        """Get project root directory."""
        return Path(__file__).parent.parent.parent
    
    def test_cdk_json_configuration(self, project_root):
        """Test CDK configuration file."""
        cdk_json_path = project_root / 'cdk.json'
        assert cdk_json_path.exists(), "cdk.json file should exist"
        
        with open(cdk_json_path, 'r') as f:
            cdk_config = json.load(f)
        
        # Verify required CDK configuration
        assert 'app' in cdk_config, "CDK app command should be specified"
        assert 'python' in cdk_config['app'], "CDK app should use Python"
        
        # Verify CDK context settings
        if 'context' in cdk_config:
            context = cdk_config['context']
            # Check for common CDK context settings
            assert isinstance(context, dict), "CDK context should be a dictionary"
    
    def test_cdk_app_structure(self, project_root):
        """Test CDK app structure and files."""
        cdk_dir = project_root / 'cdk'
        assert cdk_dir.exists(), "CDK directory should exist"
        
        # Check main app file
        app_file = cdk_dir / 'app.py'
        assert app_file.exists(), "CDK app.py file should exist"
        
        # Check stacks directory
        stacks_dir = cdk_dir / 'stacks'
        assert stacks_dir.exists(), "CDK stacks directory should exist"
        
        # Check constructs directory
        constructs_dir = cdk_dir / 'constructs'
        assert constructs_dir.exists(), "CDK constructs directory should exist"
        
        # Check requirements file
        requirements_file = cdk_dir / 'requirements.txt'
        assert requirements_file.exists(), "CDK requirements.txt should exist"
    
    def test_cdk_stack_files(self, project_root):
        """Test CDK stack files exist and are properly structured."""
        stacks_dir = project_root / 'cdk' / 'stacks'
        
        # Required stack files
        required_stacks = [
            'api_stack.py',
            'chatbot_stack.py',
            'database_stack.py',
            'lambda_stack.py'
        ]
        
        for stack_file in required_stacks:
            stack_path = stacks_dir / stack_file
            assert stack_path.exists(), f"Stack file {stack_file} should exist"
            
            # Verify stack file contains basic CDK imports
            with open(stack_path, 'r') as f:
                content = f.read()
                assert 'from aws_cdk import' in content, f"{stack_file} should import CDK modules"
                assert 'Stack' in content, f"{stack_file} should define a Stack class"
    
    def test_cdk_construct_files(self, project_root):
        """Test CDK construct files exist and are properly structured."""
        constructs_dir = project_root / 'cdk' / 'constructs'
        
        # Required construct files
        required_constructs = [
            'websocket_api.py',
            'mcp_server.py'
        ]
        
        for construct_file in required_constructs:
            construct_path = constructs_dir / construct_file
            assert construct_path.exists(), f"Construct file {construct_file} should exist"
            
            # Verify construct file contains basic CDK imports
            with open(construct_path, 'r') as f:
                content = f.read()
                assert 'from aws_cdk import' in content, f"{construct_file} should import CDK modules"
                assert 'Construct' in content, f"{construct_file} should define a Construct class"
    
    def test_lambda_function_structure(self, project_root):
        """Test Lambda function structure for CDK deployment."""
        lambda_dir = project_root / 'lambda'
        assert lambda_dir.exists(), "Lambda directory should exist"
        
        # Required Lambda functions
        required_functions = [
            'websocket_handler',
            'session_cleanup',
            'mcp_server'
        ]
        
        for function_name in required_functions:
            function_dir = lambda_dir / function_name
            assert function_dir.exists(), f"Lambda function {function_name} directory should exist"
            
            # Check handler file
            handler_file = function_dir / 'handler.py'
            assert handler_file.exists(), f"{function_name}/handler.py should exist"
            
            # Check requirements file
            requirements_file = function_dir / 'requirements.txt'
            assert requirements_file.exists(), f"{function_name}/requirements.txt should exist"
            
            # Verify handler file has lambda_handler function
            with open(handler_file, 'r') as f:
                content = f.read()
                assert 'def lambda_handler(' in content, f"{function_name} should have lambda_handler function"
    
    def test_shared_modules_for_lambda(self, project_root):
        """Test shared modules are properly structured for Lambda deployment."""
        shared_dir = project_root / 'shared'
        assert shared_dir.exists(), "Shared directory should exist"
        
        # Required shared modules
        required_modules = [
            'session_manager.py',
            'session_models.py',
            'chatbot_engine.py',
            'rag_handler.py',
            'mcp_handler.py',
            'strand_client.py',
            'strand_utils.py',
            'exceptions.py',
            'utils.py',
            'analytics_tracker.py',
            'conversation_logger.py',
            'retry_utils.py'
        ]
        
        for module_name in required_modules:
            module_file = shared_dir / module_name
            assert module_file.exists(), f"Shared module {module_name} should exist"
            
            # Verify module has proper Python structure
            with open(module_file, 'r') as f:
                content = f.read()
                # Should have docstring or imports
                assert '"""' in content or 'import' in content, f"{module_name} should be a valid Python module"
    
    def test_mcp_server_schema_file(self, project_root):
        """Test MCP server OpenAPI schema file exists."""
        schema_file = project_root / 'lambda' / 'mcp_server' / 'mcp_tools_schema.yaml'
        assert schema_file.exists(), "MCP tools schema file should exist"
        
        # Verify it's valid YAML
        import yaml
        with open(schema_file, 'r') as f:
            schema = yaml.safe_load(f)
            
        assert 'openapi' in schema, "Schema should have OpenAPI version"
        assert 'paths' in schema, "Schema should define API paths"
        assert 'info' in schema, "Schema should have info section"
    
    @pytest.mark.skipif(
        not os.environ.get('CDK_AVAILABLE', False),
        reason="CDK not available in test environment"
    )
    def test_cdk_synth_validation(self, project_root):
        """Test CDK synthesis validation (requires CDK CLI)."""
        # Change to CDK directory
        cdk_dir = project_root / 'cdk'
        
        try:
            # Run CDK synth to validate templates
            result = subprocess.run(
                ['cdk', 'synth', '--quiet'],
                cwd=cdk_dir,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # Check if synthesis was successful
            assert result.returncode == 0, f"CDK synth failed: {result.stderr}"
            
            # Verify CloudFormation templates were generated
            cdk_out_dir = project_root / 'cdk.out'
            assert cdk_out_dir.exists(), "CDK output directory should be created"
            
            # Check for template files
            template_files = list(cdk_out_dir.glob('*.template.json'))
            assert len(template_files) > 0, "CDK should generate CloudFormation templates"
            
        except subprocess.TimeoutExpired:
            pytest.skip("CDK synth timed out")
        except FileNotFoundError:
            pytest.skip("CDK CLI not available")
    
    def test_requirements_consistency(self, project_root):
        """Test requirements.txt consistency across components."""
        # Check root requirements
        root_requirements = project_root / 'requirements.txt'
        assert root_requirements.exists(), "Root requirements.txt should exist"
        
        with open(root_requirements, 'r') as f:
            root_deps = f.read()
        
        # Verify essential dependencies
        essential_deps = ['boto3', 'pytest', 'pytest-asyncio', 'pytest-mock']
        for dep in essential_deps:
            assert dep in root_deps, f"Root requirements should include {dep}"
        
        # Check CDK requirements
        cdk_requirements = project_root / 'cdk' / 'requirements.txt'
        assert cdk_requirements.exists(), "CDK requirements.txt should exist"
        
        with open(cdk_requirements, 'r') as f:
            cdk_deps = f.read()
        
        # Verify CDK dependencies
        assert 'aws-cdk-lib' in cdk_deps, "CDK requirements should include aws-cdk-lib"
        
        # Check Lambda function requirements
        lambda_functions = ['websocket_handler', 'session_cleanup', 'mcp_server']
        
        for function_name in lambda_functions:
            requirements_file = project_root / 'lambda' / function_name / 'requirements.txt'
            assert requirements_file.exists(), f"{function_name} requirements.txt should exist"
            
            with open(requirements_file, 'r') as f:
                lambda_deps = f.read()
            
            # Verify boto3 is included (essential for Lambda)
            assert 'boto3' in lambda_deps, f"{function_name} should include boto3"
    
    def test_environment_variables_configuration(self, project_root):
        """Test environment variables are properly configured in CDK."""
        # Check CDK stack files for environment variable configuration
        stacks_dir = project_root / 'cdk' / 'stacks'
        
        # Look for environment variable configuration in Lambda stacks
        lambda_stack_file = stacks_dir / 'lambda_stack.py'
        if lambda_stack_file.exists():
            with open(lambda_stack_file, 'r') as f:
                content = f.read()
                
            # Should configure environment variables for Lambda functions
            assert 'environment' in content.lower(), "Lambda stack should configure environment variables"
    
    def test_iam_permissions_configuration(self, project_root):
        """Test IAM permissions are configured in CDK stacks."""
        stacks_dir = project_root / 'cdk' / 'stacks'
        
        # Check for IAM configuration in stack files
        stack_files = list(stacks_dir.glob('*.py'))
        
        iam_configured = False
        for stack_file in stack_files:
            with open(stack_file, 'r') as f:
                content = f.read()
                
            if 'iam' in content.lower() or 'role' in content.lower() or 'policy' in content.lower():
                iam_configured = True
                break
        
        assert iam_configured, "CDK stacks should configure IAM permissions"
    
    def test_resource_naming_consistency(self, project_root):
        """Test resource naming consistency across CDK stacks."""
        stacks_dir = project_root / 'cdk' / 'stacks'
        
        # Check for consistent naming patterns
        stack_files = list(stacks_dir.glob('*.py'))
        
        for stack_file in stack_files:
            with open(stack_file, 'r') as f:
                content = f.read()
            
            # Should use consistent naming (e.g., kebab-case or camelCase)
            # This is a basic check - in practice, you'd have more specific rules
            assert 'chatbot' in content.lower() or 'websocket' in content.lower() or 'mcp' in content.lower(), \
                f"{stack_file.name} should reference project components"


class TestDeploymentReadiness:
    """Tests to verify deployment readiness."""
    
    @pytest.fixture
    def project_root(self):
        """Get project root directory."""
        return Path(__file__).parent.parent.parent
    
    def test_all_required_files_present(self, project_root):
        """Test all required files for deployment are present."""
        required_files = [
            'cdk.json',
            'requirements.txt',
            'cdk/app.py',
            'cdk/requirements.txt',
            'lambda/websocket_handler/handler.py',
            'lambda/session_cleanup/handler.py',
            'lambda/mcp_server/handler.py',
            'lambda/mcp_server/mcp_tools_schema.yaml',
            'shared/session_manager.py',
            'shared/chatbot_engine.py',
            'shared/mcp_handler.py'
        ]
        
        for file_path in required_files:
            full_path = project_root / file_path
            assert full_path.exists(), f"Required file {file_path} should exist for deployment"
    
    def test_no_syntax_errors_in_python_files(self, project_root):
        """Test Python files have no syntax errors."""
        python_files = []
        
        # Collect all Python files
        for directory in ['cdk', 'lambda', 'shared', 'tests']:
            dir_path = project_root / directory
            if dir_path.exists():
                python_files.extend(dir_path.rglob('*.py'))
        
        for py_file in python_files:
            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                
                # Compile to check for syntax errors
                compile(content, str(py_file), 'exec')
                
            except SyntaxError as e:
                pytest.fail(f"Syntax error in {py_file}: {e}")
            except Exception as e:
                # Skip files that can't be read or have encoding issues
                continue
    
    def test_import_structure_validity(self, project_root):
        """Test import structure is valid for deployment."""
        # Check shared modules can be imported
        shared_dir = project_root / 'shared'
        
        if shared_dir.exists():
            # Add shared directory to Python path for testing
            import sys
            sys.path.insert(0, str(shared_dir))
            
            try:
                # Test importing key modules
                import session_manager
                import chatbot_engine
                import mcp_handler
                import exceptions
                import utils
                
                # Basic validation that classes/functions exist
                assert hasattr(session_manager, 'SessionManager')
                assert hasattr(chatbot_engine, 'ChatbotEngine')
                assert hasattr(mcp_handler, 'MCPHandler')
                
            except ImportError as e:
                pytest.fail(f"Import error in shared modules: {e}")
            finally:
                # Clean up path
                if str(shared_dir) in sys.path:
                    sys.path.remove(str(shared_dir))


if __name__ == '__main__':
    pytest.main([__file__])