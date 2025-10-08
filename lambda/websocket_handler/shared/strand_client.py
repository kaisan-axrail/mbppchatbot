"""
Strands Agents client for Claude interactions using proper Strands SDK.
"""

import json
import logging
import os
from typing import Dict, Any, Optional, List
import boto3
from botocore.exceptions import ClientError

# Import Strands SDK
try:
    from strands_agents import StrandsClient as ActualStrandsClient
    from strands_agents_tools import ToolRegistry
    STRANDS_AVAILABLE = True
except ImportError:
    STRANDS_AVAILABLE = False
    ActualStrandsClient = None
    ToolRegistry = None
from shared.exceptions import (
    StrandClientError,
    SecretNotFoundError,
    AuthenticationError,
    NetworkError,
    BedrockError
)
from shared.retry_utils import (
    retry_with_backoff,
    STRAND_RETRY_CONFIG,
    with_graceful_degradation
)
from shared.error_handler import error_handler, with_bedrock_degradation

# Configure logging
logger = logging.getLogger(__name__)


class StrandClient:
    """
    Strands Agents client for Claude interactions using proper Strands SDK.
    """
    
    def __init__(self, region: str = None, api_key_secret_name: str = None):
        """
        Initialize Strands client with fallback to AWS Bedrock.
        
        Args:
            region: AWS region for Bedrock fallback
            api_key_secret_name: Secret name for Strands API key
        """
        self.region = region or os.environ.get('AWS_REGION', 'ap-southeast-1')
        self.api_key_secret_name = api_key_secret_name or 'chatbot/api-keys'
        
        # Initialize Strands client if available
        if STRANDS_AVAILABLE:
            try:
                self.strands_client = self._initialize_strands_client()
                self.use_strands = True
                logger.info("Initialized Strands Agents client successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Strands client: {e}, falling back to Bedrock")
                self.use_strands = False
                self.strands_client = None
        else:
            logger.warning("Strands SDK not available, using Bedrock fallback")
            self.use_strands = False
            self.strands_client = None
        
        # Initialize AWS Bedrock client as fallback
        self.bedrock_client = boto3.client('bedrock-runtime', region_name=self.region)
        
        # Inference profile configuration (preferred)
        self.inference_profile_arn = os.environ.get('BEDROCK_INFERENCE_PROFILE_ARN')
        self.cross_region_profile = os.environ.get('BEDROCK_CROSS_REGION_PROFILE', 'us.anthropic.claude-3-5-sonnet-20241022-v2:0')
        
        # Fallback model configuration
        self.model_id = os.environ.get('BEDROCK_CLAUDE_MODEL', 'anthropic.claude-sonnet-4-20250514-v1:0')
        self.max_tokens = int(os.environ.get('BEDROCK_MAX_TOKENS', '4096'))
        self.temperature = float(os.environ.get('BEDROCK_TEMPERATURE', '0.7'))
        
        # Circuit breaker configuration
        self.circuit_breaker_threshold = int(os.environ.get('BEDROCK_CIRCUIT_BREAKER_THRESHOLD', '5'))
        self.circuit_breaker_timeout = int(os.environ.get('BEDROCK_CIRCUIT_BREAKER_TIMEOUT', '30'))
        
        # Determine which model identifier to use
        self.active_model_id = self._get_active_model_id()
        
        if self.use_strands:
            logger.info(f"Initialized Strands client for region {self.region}")
        else:
            logger.info(f"Initialized Bedrock fallback client for region {self.region} with model {self.active_model_id}")
    
    def _initialize_strands_client(self) -> ActualStrandsClient:
        """
        Initialize the actual Strands client.
        
        Returns:
            Configured Strands client
        """
        # Get API key from Secrets Manager
        api_key = self._get_strands_api_key()
        
        # Initialize Strands client
        strands_client = ActualStrandsClient(
            api_key=api_key,
            region=self.region
        )
        
        return strands_client
    
    def _get_strands_api_key(self) -> str:
        """
        Get Strands API key from AWS Secrets Manager.
        
        Returns:
            Strands API key
        """
        try:
            secrets_client = boto3.client('secretsmanager', region_name=self.region)
            response = secrets_client.get_secret_value(SecretId=self.api_key_secret_name)
            
            secret_data = json.loads(response['SecretString'])
            api_key = secret_data.get('strands_api_key')
            
            if not api_key:
                raise SecretNotFoundError(f"strands_api_key not found in secret {self.api_key_secret_name}")
            
            return api_key
            
        except Exception as e:
            logger.error(f"Failed to get Strands API key: {e}")
            raise AuthenticationError(f"Cannot retrieve Strands API key: {e}")
        
    def _get_active_model_id(self) -> str:
        """
        Determine the active model ID based on available configuration.
        
        Returns:
            Model ID or inference profile to use
        """
        if self.inference_profile_arn:
            logger.info(f"Using inference profile ARN: {self.inference_profile_arn}")
            return self.inference_profile_arn
        elif self.cross_region_profile:
            logger.info(f"Using cross-region inference profile: {self.cross_region_profile}")
            return self.cross_region_profile
        else:
            logger.warning(f"No inference profile configured, falling back to direct model: {self.model_id}")
            return self.model_id
    
    @retry_with_backoff(
        config=STRAND_RETRY_CONFIG,
        service_name="strands"
    )
    async def generate_response(
        self, 
        messages: List[Dict[str, str]], 
        max_tokens: int = None,
        temperature: float = None,
        system_prompt: str = None
    ) -> Dict[str, Any]:
        """
        Generate response using Strands Agents with Bedrock fallback.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            system_prompt: System prompt for the conversation
            
        Returns:
            Response dictionary with generated content
            
        Raises:
            StrandClientError: If generation fails
        """
        # Try Strands first if available
        if self.use_strands and self.strands_client:
            try:
                return await self._generate_with_strands(messages, max_tokens, temperature, system_prompt)
            except Exception as e:
                logger.warning(f"Strands generation failed: {e}, falling back to Bedrock")
                # Fall through to Bedrock fallback
        
        # Fallback to Bedrock
        return await self._generate_with_fallback(messages, max_tokens, temperature, system_prompt)
    
    async def _generate_with_strands(
        self,
        messages: List[Dict[str, str]], 
        max_tokens: int = None,
        temperature: float = None,
        system_prompt: str = None
    ) -> Dict[str, Any]:
        """
        Generate response using Strands Agents SDK.
        
        Args:
            messages: List of message dictionaries
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            system_prompt: System prompt
            
        Returns:
            Response dictionary
        """
        try:
            # Use provided values or defaults
            max_tokens = max_tokens or self.max_tokens
            temperature = temperature or self.temperature
            
            # Call Strands API
            response = await self.strands_client.generate(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                system_prompt=system_prompt
            )
            
            logger.info("Successfully generated response using Strands Agents")
            
            # Convert Strands response to standard format
            return {
                "content": [{"type": "text", "text": response.get('content', '')}],
                "usage": response.get('usage', {}),
                "model": "strands-claude",
                "provider": "strands"
            }
            
        except Exception as e:
            logger.error(f"Strands generation error: {e}")
            raise StrandClientError(f"Strands generation failed: {e}", "STRANDS_GENERATION_ERROR")
    
    async def _generate_with_fallback(
        self,
        messages: List[Dict[str, str]], 
        max_tokens: int = None,
        temperature: float = None,
        system_prompt: str = None
    ) -> Dict[str, Any]:
        """
        Generate response with enhanced fallback mechanism and error handling.
        """
        # Use provided values or defaults
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature or self.temperature
        
        # Format messages for Claude
        # Check if using Nova Pro model for message formatting
        is_nova_model = "nova" in self.model_id.lower() or "nova" in (self.inference_profile_arn or "").lower() or "nova" in (self.cross_region_profile or "").lower()
        
        claude_messages = []
        for msg in messages:
            if is_nova_model:
                # Nova Pro message format
                claude_messages.append({
                    "role": msg.get("role", "user"),
                    "content": [{"text": msg.get("content", "")}]
                })
            else:
                # Claude message format
                claude_messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
        
        # Check if using Nova Pro model and adjust API format
        is_nova_model = "nova" in self.model_id.lower() or "nova" in (self.inference_profile_arn or "").lower() or "nova" in (self.cross_region_profile or "").lower()
        
        if is_nova_model:
            # Nova Pro API format
            body = {
                "messages": claude_messages,
                "inferenceConfig": {
                    "maxTokens": max_tokens,
                    "temperature": temperature
                }
            }
            # Add system prompt if provided
            if system_prompt:
                body["system"] = [{"text": system_prompt}]
        else:
            # Claude API format
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": claude_messages
            }
            # Add system prompt if provided
            if system_prompt:
                body["system"] = system_prompt
        
        # Context for error handling
        context = {
            'model_attempts': [],
            'message_count': len(claude_messages),
            'max_tokens': max_tokens,
            'temperature': temperature
        }
        
        # Try inference profile ARN first
        if self.inference_profile_arn:
            try:
                context['model_attempts'].append('inference_profile_arn')
                result = await self._invoke_model(self.inference_profile_arn, body)
                logger.info(f"Successfully used inference profile ARN: {self.inference_profile_arn}")
                return result
            except ClientError as e:
                context['inference_profile_error'] = str(e)
                if e.response['Error']['Code'] == 'ValidationException':
                    logger.warning(f"Inference profile ARN failed with ValidationException: {e}")
                else:
                    # Handle non-validation errors with error handler
                    bedrock_error = BedrockError(f"Inference profile error: {str(e)}", "INFERENCE_PROFILE_ERROR")
                    error_result = error_handler.handle_bedrock_error(bedrock_error, context)
                    if not error_result['success'] and 'fallback_response' in error_result:
                        return error_result['fallback_response']
                    raise bedrock_error
        
        # Try cross-region inference profile
        if self.cross_region_profile:
            try:
                context['model_attempts'].append('cross_region_profile')
                result = await self._invoke_model(self.cross_region_profile, body)
                logger.info(f"Successfully used cross-region profile: {self.cross_region_profile}")
                return result
            except ClientError as e:
                context['cross_region_error'] = str(e)
                if e.response['Error']['Code'] == 'ValidationException':
                    logger.warning(f"Cross-region profile failed with ValidationException: {e}")
                else:
                    # Handle non-validation errors with error handler
                    bedrock_error = BedrockError(f"Cross-region profile error: {str(e)}", "CROSS_REGION_ERROR")
                    error_result = error_handler.handle_bedrock_error(bedrock_error, context)
                    if not error_result['success'] and 'fallback_response' in error_result:
                        return error_result['fallback_response']
                    raise bedrock_error
        
        # Final fallback to direct model access
        try:
            context['model_attempts'].append('direct_model')
            result = await self._invoke_model(self.model_id, body)
            logger.info(f"Successfully used direct model access: {self.model_id}")
            return result
        except Exception as e:
            context['direct_model_error'] = str(e)
            
            # Create comprehensive error for all failed attempts
            bedrock_error = BedrockError(
                f"All Bedrock access methods failed. Attempts: {context['model_attempts']}. Last error: {str(e)}",
                "BEDROCK_ACCESS_FAILED"
            )
            
            # Use error handler for graceful degradation
            error_result = error_handler.handle_bedrock_error(bedrock_error, context, fallback_enabled=True)
            
            if 'fallback_response' in error_result:
                logger.warning("Returning fallback response due to Bedrock service unavailability")
                return error_result['fallback_response']
            else:
                raise bedrock_error
    
    async def _invoke_model(self, model_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invoke Bedrock model with enhanced error handling and logging.
        
        Args:
            model_id: Model ID or inference profile ARN
            body: Request body for the model
            
        Returns:
            Response dictionary with generated content
        """
        try:
            # Call Bedrock with detailed logging
            logger.debug(f"Invoking Bedrock model: {model_id}")
            
            response = self.bedrock_client.invoke_model(
                modelId=model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json"
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            
            # Debug: Log the response structure to understand Nova Pro format
            logger.info(f"Bedrock response structure: {json.dumps(response_body, indent=2)}")
            
            # Extract content from response - handle both Claude and Nova Pro formats
            content = ""
            if 'content' in response_body and response_body['content']:
                # Claude format: content[0].text
                if isinstance(response_body['content'], list) and response_body['content']:
                    content = response_body['content'][0].get('text', '')
                # Nova Pro format: content.text
                elif isinstance(response_body['content'], dict):
                    content = response_body['content'].get('text', '')
            # Nova Pro alternative format: output.message.content[0].text
            elif 'output' in response_body and 'message' in response_body['output']:
                message = response_body['output']['message']
                if 'content' in message and message['content']:
                    content = message['content'][0].get('text', '')
            
            logger.info(
                f"Successfully generated response using model: {model_id}",
                extra={
                    'model_id': model_id,
                    'content_length': len(content),
                    'input_tokens': response_body.get("usage", {}).get("input_tokens", 0),
                    'output_tokens': response_body.get("usage", {}).get("output_tokens", 0)
                }
            )
            
            return {
                "content": [{"type": "text", "text": content}],
                "usage": response_body.get("usage", {}),
                "model": model_id
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            # Log detailed error information for debugging
            logger.error(
                f"Bedrock ClientError for model {model_id}",
                extra={
                    'model_id': model_id,
                    'error_code': error_code,
                    'error_message': error_message,
                    'actionable_info': self._get_client_error_actionable_info(error_code)
                }
            )
            
            # Re-raise with enhanced error information
            raise BedrockError(f"{error_code}: {error_message}", error_code)
            
        except Exception as e:
            # Log unexpected errors with full context
            logger.error(
                f"Unexpected error invoking model {model_id}: {str(e)}",
                extra={
                    'model_id': model_id,
                    'error_type': type(e).__name__,
                    'error_message': str(e)
                }
            )
            raise BedrockError(f"Model invocation failed: {str(e)}", "MODEL_INVOCATION_ERROR")
    
    def _get_client_error_actionable_info(self, error_code: str) -> Dict[str, str]:
        """
        Get actionable information for Bedrock ClientError codes.
        
        Args:
            error_code: AWS error code
            
        Returns:
            Dictionary with actionable debugging information
        """
        actionable_info = {
            'ValidationException': {
                'issue': 'Model ID or inference profile not supported',
                'action': 'Verify inference profile ARN or switch to supported model',
                'priority': 'high'
            },
            'AccessDeniedException': {
                'issue': 'Insufficient permissions for Bedrock model access',
                'action': 'Check IAM roles and Bedrock model access policies',
                'priority': 'critical'
            },
            'ThrottlingException': {
                'issue': 'Request rate limit exceeded',
                'action': 'Implement exponential backoff or request quota increase',
                'priority': 'medium'
            },
            'ServiceUnavailableException': {
                'issue': 'Bedrock service temporarily unavailable',
                'action': 'Check AWS service status and retry with backoff',
                'priority': 'high'
            },
            'InternalServerException': {
                'issue': 'Internal AWS service error',
                'action': 'Check AWS service status and contact support if persistent',
                'priority': 'high'
            }
        }
        
        return actionable_info.get(error_code, {
            'issue': f'Unknown Bedrock error: {error_code}',
            'action': 'Check AWS documentation and service status',
            'priority': 'medium'
        })
    
    def validate_configuration(self) -> Dict[str, Any]:
        """
        Validate Bedrock client configuration and access.
        
        Returns:
            Configuration validation results
        """
        validation_result = {
            "region": self.region,
            "model_id": self.model_id,
            "active_model_id": self.active_model_id,
            "inference_profile_arn": self.inference_profile_arn,
            "cross_region_profile": self.cross_region_profile,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "circuit_breaker_threshold": self.circuit_breaker_threshold,
            "circuit_breaker_timeout": self.circuit_breaker_timeout,
            "status": "unknown",
            "access_tests": {}
        }
        
        # Test Bedrock access with different configurations
        try:
            # Test basic client connectivity by checking if we can make a simple call
            # We'll use the model access test as the connectivity test
            validation_result["access_tests"]["client_connectivity"] = "success"
            
            # Test inference profile access if configured
            if self.inference_profile_arn:
                validation_result["access_tests"]["inference_profile_arn"] = self._test_model_access(self.inference_profile_arn)
            
            if self.cross_region_profile:
                validation_result["access_tests"]["cross_region_profile"] = self._test_model_access(self.cross_region_profile)
            
            # Test direct model access
            validation_result["access_tests"]["direct_model"] = self._test_model_access(self.model_id)
            
            # Determine overall status
            if any(test == "success" for test in validation_result["access_tests"].values()):
                validation_result["status"] = "configured"
            else:
                validation_result["status"] = "access_failed"
                
        except Exception as e:
            validation_result["status"] = "client_error"
            validation_result["error"] = str(e)
            logger.error(f"Bedrock client validation failed: {str(e)}")
        
        return validation_result
    
    def _test_model_access(self, model_id: str) -> str:
        """
        Test access to a specific model or inference profile.
        
        Args:
            model_id: Model ID or inference profile to test
            
        Returns:
            Test result status
        """
        try:
            # Simple test message - adjust format based on model type
            is_nova_model = "nova" in model_id.lower()
            
            if is_nova_model:
                # Nova Pro API format
                test_body = {
                    "messages": [{"role": "user", "content": [{"text": "Hello"}]}],
                    "inferenceConfig": {
                        "maxTokens": 10,
                        "temperature": 0.1
                    }
                }
            else:
                # Claude API format
                test_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 10,
                    "temperature": 0.1,
                    "messages": [{"role": "user", "content": "Hello"}]
                }
            
            response = self.bedrock_client.invoke_model(
                modelId=model_id,
                body=json.dumps(test_body),
                contentType="application/json",
                accept="application/json"
            )
            
            # If we get here, the call succeeded
            logger.info(f"Model access test successful for: {model_id}")
            return "success"
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.warning(f"Model access test failed for {model_id}: {error_code}")
            return f"failed_{error_code.lower()}"
        except Exception as e:
            # Handle credential and other errors gracefully
            error_str = str(e).lower()
            if 'credential' in error_str or 'token' in error_str:
                logger.warning(f"Model access test - credential issue for {model_id}")
                return "failed_credentials"
            elif 'region' in error_str:
                logger.warning(f"Model access test - region issue for {model_id}")
                return "failed_region"
            else:
                logger.warning(f"Model access test error for {model_id}: {str(e)}")
                return "failed_unknown"
    
    def create_fallback_response(self, error_context: str = None) -> Dict[str, Any]:
        """
        Create a fallback response when Bedrock is unavailable.
        
        Args:
            error_context: Context about the error that triggered fallback
            
        Returns:
            Fallback response dictionary
        """
        fallback_message = (
            "I apologize, but I'm currently experiencing technical difficulties connecting to the AI service. "
            "Please try again in a few moments. If the issue persists, please contact support."
        )
        
        if error_context:
            logger.warning(f"Creating fallback response due to: {error_context}")
        
        return {
            "content": [{"type": "text", "text": fallback_message}],
            "usage": {"input_tokens": 0, "output_tokens": len(fallback_message.split())},
            "model": "fallback",
            "is_fallback": True
        }


def create_strand_client(region: str = None, api_key_secret_name: str = None) -> StrandClient:
    """
    Factory function to create a configured Bedrock client.
    
    Args:
        region: AWS region
        api_key_secret_name: Not used (kept for compatibility)
        
    Returns:
        Configured StrandClient (actually Bedrock client)
    """
    return StrandClient(region=region, api_key_secret_name=api_key_secret_name)


def format_messages_for_strand(
    user_message: str, 
    conversation_history: List[Dict[str, str]] = None
) -> List[Dict[str, str]]:
    """
    Format messages for Claude API.
    
    Args:
        user_message: Current user message
        conversation_history: Previous conversation messages
        
    Returns:
        Formatted message list
    """
    messages = []
    
    # Add conversation history
    if conversation_history:
        messages.extend(conversation_history)
    
    # Add current user message
    messages.append({
        "role": "user",
        "content": user_message
    })
    
    return messages


def extract_text_from_strand_response(response: Dict[str, Any]) -> str:
    """
    Extract text content from Bedrock response.
    
    Args:
        response: Response from Bedrock API
        
    Returns:
        Extracted text content
    """
    try:
        # Claude format: content[0].text
        if 'content' in response and response['content']:
            if isinstance(response['content'], list):
                for content_item in response['content']:
                    if content_item.get('type') == 'text':
                        return content_item.get('text', '')
            # Nova Pro format: content.text
            elif isinstance(response['content'], dict):
                return response['content'].get('text', '')
        
        # Nova Pro alternative format: output.message.content[0].text
        if 'output' in response and 'message' in response['output']:
            message = response['output']['message']
            if 'content' in message and message['content']:
                return message['content'][0].get('text', '')
        
        return ""
        
    except Exception as e:
        logger.error(f"Failed to extract text from Bedrock response: {str(e)}")
        return ""