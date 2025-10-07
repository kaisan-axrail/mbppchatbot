"""
Unit tests for Strand SDK client configuration and utilities.
"""

import json
import pytest
from unittest.mock import Mock, patch, AsyncMock
from botocore.exceptions import ClientError

from shared.strand_client import (
    StrandClient, 
    StrandClientError, 
    create_strand_client,
    format_messages_for_strand,
    extract_text_from_strand_response
)


class TestStrandClient:
    """Test cases for StrandClient class."""
    
    @patch('shared.strand_client.boto3.client')
    def test_init_with_defaults(self, mock_boto_client):
        """Test StrandClient initialization with default parameters."""
        mock_secrets_client = Mock()
        mock_boto_client.return_value = mock_secrets_client
        
        # Mock successful secret retrieval
        mock_secrets_client.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': 'test-api-key'})
        }
        
        client = StrandClient()
        
        assert client.region == 'us-east-1'
        assert client.api_key_secret_name == 'chatbot/strand-api-key'
        assert client.api_key == 'test-api-key'
        assert client.model_name == 'anthropic.claude-3-5-sonnet-20241022-v2:0'
        assert client.max_tokens == 4096
        assert client.temperature == 0.7
    
    @patch('shared.strand_client.boto3.client')
    def test_init_with_custom_parameters(self, mock_boto_client):
        """Test StrandClient initialization with custom parameters."""
        mock_secrets_client = Mock()
        mock_boto_client.return_value = mock_secrets_client
        
        # Mock successful secret retrieval
        mock_secrets_client.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': 'custom-api-key'})
        }
        
        client = StrandClient(
            region='us-west-2',
            api_key_secret_name='custom/secret'
        )
        
        assert client.region == 'us-west-2'
        assert client.api_key_secret_name == 'custom/secret'
        assert client.api_key == 'custom-api-key'
    
    @patch('shared.strand_client.boto3.client')
    def test_get_api_key_from_secrets_success(self, mock_boto_client):
        """Test successful API key retrieval from Secrets Manager."""
        mock_secrets_client = Mock()
        mock_boto_client.return_value = mock_secrets_client
        
        mock_secrets_client.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': 'test-key-123'})
        }
        
        client = StrandClient()
        assert client.api_key == 'test-key-123'
    
    @patch('shared.strand_client.boto3.client')
    def test_get_api_key_secret_not_found(self, mock_boto_client):
        """Test handling of secret not found error."""
        mock_secrets_client = Mock()
        mock_boto_client.return_value = mock_secrets_client
        
        mock_secrets_client.get_secret_value.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException'}},
            'GetSecretValue'
        )
        
        with pytest.raises(StrandClientError) as exc_info:
            StrandClient()
        
        assert exc_info.value.error_code == "SECRET_NOT_FOUND"
        assert "not found" in str(exc_info.value)
    
    @patch('shared.strand_client.boto3.client')
    def test_get_api_key_invalid_json(self, mock_boto_client):
        """Test handling of invalid JSON in secret."""
        mock_secrets_client = Mock()
        mock_boto_client.return_value = mock_secrets_client
        
        mock_secrets_client.get_secret_value.return_value = {
            'SecretString': 'invalid-json'
        }
        
        with pytest.raises(StrandClientError) as exc_info:
            StrandClient()
        
        assert exc_info.value.error_code == "INVALID_SECRET_FORMAT"
    
    @patch('shared.strand_client.boto3.client')
    def test_get_api_key_missing_key(self, mock_boto_client):
        """Test handling of missing API key in secret."""
        mock_secrets_client = Mock()
        mock_boto_client.return_value = mock_secrets_client
        
        mock_secrets_client.get_secret_value.return_value = {
            'SecretString': json.dumps({'other_key': 'value'})
        }
        
        with pytest.raises(StrandClientError) as exc_info:
            StrandClient()
        
        assert exc_info.value.error_code == "API_KEY_NOT_FOUND"
    
    @patch('shared.strand_client.boto3.client')
    @pytest.mark.asyncio
    async def test_generate_response_success(self, mock_boto_client):
        """Test successful response generation."""
        mock_secrets_client = Mock()
        mock_boto_client.return_value = mock_secrets_client
        
        mock_secrets_client.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': 'test-key'})
        }
        
        client = StrandClient()
        
        # Mock the _call_strand_api method
        expected_response = {
            "id": "msg_123",
            "content": [{"type": "text", "text": "Test response"}],
            "usage": {"input_tokens": 10, "output_tokens": 5}
        }
        
        client._call_strand_api = AsyncMock(return_value=expected_response)
        
        messages = [{"role": "user", "content": "Hello"}]
        response = await client.generate_response(messages)
        
        assert response == expected_response
        client._call_strand_api.assert_called_once()
    
    @patch('shared.strand_client.boto3.client')
    @pytest.mark.asyncio
    async def test_generate_response_with_system_prompt(self, mock_boto_client):
        """Test response generation with system prompt."""
        mock_secrets_client = Mock()
        mock_boto_client.return_value = mock_secrets_client
        
        mock_secrets_client.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': 'test-key'})
        }
        
        client = StrandClient()
        client._call_strand_api = AsyncMock(return_value={})
        
        messages = [{"role": "user", "content": "Hello"}]
        await client.generate_response(
            messages, 
            system_prompt="You are helpful",
            max_tokens=100,
            temperature=0.5
        )
        
        # Verify the call was made with correct parameters
        call_args = client._call_strand_api.call_args[0][0]
        assert call_args["system"] == "You are helpful"
        assert call_args["max_tokens"] == 100
        assert call_args["temperature"] == 0.5
    
    @patch('shared.strand_client.boto3.client')
    def test_validate_configuration(self, mock_boto_client):
        """Test configuration validation."""
        mock_secrets_client = Mock()
        mock_boto_client.return_value = mock_secrets_client
        
        mock_secrets_client.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': 'test-key'})
        }
        
        client = StrandClient()
        config = client.validate_configuration()
        
        assert config["api_key_configured"] is True
        assert config["region"] == 'us-east-1'
        assert config["model_name"] == 'anthropic.claude-3-5-sonnet-20241022-v2:0'
        assert config["max_tokens"] == 4096
        assert config["temperature"] == 0.7


class TestStrandClientUtilities:
    """Test cases for Strand client utility functions."""
    
    def test_format_messages_for_strand_single_message(self):
        """Test formatting single message for Strand API."""
        messages = format_messages_for_strand("Hello world")
        
        expected = [{"role": "user", "content": "Hello world"}]
        assert messages == expected
    
    def test_format_messages_for_strand_with_history(self):
        """Test formatting messages with conversation history."""
        history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"}
        ]
        
        messages = format_messages_for_strand("New question", history)
        
        expected = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
            {"role": "user", "content": "New question"}
        ]
        assert messages == expected
    
    def test_extract_text_from_strand_response_content_array(self):
        """Test extracting text from Strand response with content array."""
        response = {
            "content": [
                {"type": "text", "text": "Hello world"},
                {"type": "other", "data": "ignored"}
            ]
        }
        
        text = extract_text_from_strand_response(response)
        assert text == "Hello world"
    
    def test_extract_text_from_strand_response_direct_text(self):
        """Test extracting text from response with direct text field."""
        response = {"text": "Direct text response"}
        
        text = extract_text_from_strand_response(response)
        assert text == "Direct text response"
    
    def test_extract_text_from_strand_response_empty(self):
        """Test extracting text from empty or invalid response."""
        assert extract_text_from_strand_response({}) == ""
        assert extract_text_from_strand_response({"content": []}) == ""
        assert extract_text_from_strand_response({"content": [{"type": "other"}]}) == ""
    
    @patch('shared.strand_client.StrandClient')
    def test_create_strand_client_factory(self, mock_strand_client):
        """Test factory function for creating Strand client."""
        mock_instance = Mock()
        mock_strand_client.return_value = mock_instance
        
        client = create_strand_client(region='us-west-2', api_key_secret_name='test/secret')
        
        mock_strand_client.assert_called_once_with(
            region='us-west-2',
            api_key_secret_name='test/secret'
        )
        assert client == mock_instance


if __name__ == '__main__':
    pytest.main([__file__])