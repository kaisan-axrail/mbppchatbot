"""
Unit tests for general question handling functionality in StrandUtils.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from shared.strand_utils import StrandUtils, StrandClientError
from shared.strand_client import StrandClient


class TestGeneralQuestionHandling:
    """Test cases for general question handling functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_strand_client = Mock(spec=StrandClient)
        self.strand_utils = StrandUtils(self.mock_strand_client)
    
    @pytest.mark.asyncio
    async def test_generate_general_response_simple(self):
        """Test generating a simple general response."""
        # Mock the strand client response
        mock_response = {"choices": [{"message": {"content": "This is a helpful response."}}]}
        self.mock_strand_client.generate_response = AsyncMock(return_value=mock_response)
        
        # Mock the format and extract functions
        with patch('shared.strand_utils.format_messages_for_strand') as mock_format, \
             patch('shared.strand_utils.extract_text_from_strand_response') as mock_extract:
            
            mock_format.return_value = [{"role": "user", "content": "Hello"}]
            mock_extract.return_value = "This is a helpful response."
            
            result = await self.strand_utils.generate_general_response("Hello")
            
            assert result == "This is a helpful response."
            mock_format.assert_called_once_with("Hello", None)
            mock_extract.assert_called_once_with(mock_response)
    
    @pytest.mark.asyncio
    async def test_generate_general_response_with_history(self):
        """Test generating a general response with conversation history."""
        conversation_history = [
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "Python is a programming language."}
        ]
        
        # Mock clarification check to return False (clear question)
        self.strand_utils._needs_clarification = AsyncMock(return_value=False)
        
        mock_response = {"choices": [{"message": {"content": "Python is great for beginners."}}]}
        self.mock_strand_client.generate_response = AsyncMock(return_value=mock_response)
        
        with patch('shared.strand_utils.format_messages_for_strand') as mock_format, \
             patch('shared.strand_utils.extract_text_from_strand_response') as mock_extract:
            
            mock_format.return_value = conversation_history + [{"role": "user", "content": "Tell me more"}]
            mock_extract.return_value = "Python is great for beginners."
            
            result = await self.strand_utils.generate_general_response("Tell me more", conversation_history)
            
            assert result == "Python is great for beginners."
            # Should be called once for the main response (clarification is mocked)
            mock_format.assert_called_once_with("Tell me more", conversation_history)
    
    @pytest.mark.asyncio
    async def test_generate_general_response_needs_clarification(self):
        """Test generating a response when clarification is needed."""
        # Mock clarification check to return True
        self.strand_utils._needs_clarification = AsyncMock(return_value=True)
        self.strand_utils._request_clarification = AsyncMock(
            return_value="Could you please be more specific about what you're looking for?"
        )
        
        result = await self.strand_utils.generate_general_response("this")
        
        assert result == "Could you please be more specific about what you're looking for?"
        self.strand_utils._needs_clarification.assert_called_once_with("this", None)
        self.strand_utils._request_clarification.assert_called_once_with("this", None)
    
    @pytest.mark.asyncio
    async def test_generate_general_response_error(self):
        """Test error handling in general response generation."""
        self.mock_strand_client.generate_response = AsyncMock(side_effect=Exception("API error"))
        
        with patch('shared.strand_utils.format_messages_for_strand'), \
             patch('shared.strand_utils.extract_text_from_strand_response'):
            
            with pytest.raises(StrandClientError) as exc_info:
                await self.strand_utils.generate_general_response("Hello")
            
            assert exc_info.value.error_code == "GENERAL_RESPONSE_ERROR"
            assert "Failed to generate general response" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_needs_clarification_unclear_message(self):
        """Test clarification detection for unclear messages."""
        mock_response = {"choices": [{"message": {"content": "yes"}}]}
        self.mock_strand_client.generate_response = AsyncMock(return_value=mock_response)
        
        with patch('shared.strand_utils.format_messages_for_strand') as mock_format, \
             patch('shared.strand_utils.extract_text_from_strand_response') as mock_extract:
            
            mock_format.return_value = [{"role": "user", "content": "this thing"}]
            mock_extract.return_value = "yes"
            
            result = await self.strand_utils._needs_clarification("this thing")
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_needs_clarification_clear_message(self):
        """Test clarification detection for clear messages."""
        mock_response = {"choices": [{"message": {"content": "no"}}]}
        self.mock_strand_client.generate_response = AsyncMock(return_value=mock_response)
        
        with patch('shared.strand_utils.format_messages_for_strand') as mock_format, \
             patch('shared.strand_utils.extract_text_from_strand_response') as mock_extract:
            
            mock_format.return_value = [{"role": "user", "content": "What is the weather like today?"}]
            mock_extract.return_value = "no"
            
            result = await self.strand_utils._needs_clarification("What is the weather like today?")
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_needs_clarification_short_message(self):
        """Test that very short messages don't need clarification."""
        result = await self.strand_utils._needs_clarification("hi")
        
        assert result is False
        # Should not call the API for short messages
        self.mock_strand_client.generate_response.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_needs_clarification_greeting(self):
        """Test that common greetings don't need clarification."""
        greetings = ["hello", "hi", "hey", "thanks", "thank you", "bye", "goodbye"]
        
        for greeting in greetings:
            result = await self.strand_utils._needs_clarification(greeting)
            assert result is False
        
        # Should not call the API for greetings
        self.mock_strand_client.generate_response.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_needs_clarification_error_fallback(self):
        """Test error handling in clarification detection."""
        self.mock_strand_client.generate_response = AsyncMock(side_effect=Exception("API error"))
        
        with patch('shared.strand_utils.format_messages_for_strand'), \
             patch('shared.strand_utils.extract_text_from_strand_response'):
            
            result = await self.strand_utils._needs_clarification("unclear message")
            
            # Should default to False on error
            assert result is False
    
    @pytest.mark.asyncio
    async def test_request_clarification_success(self):
        """Test successful clarification request generation."""
        mock_response = {"choices": [{"message": {"content": "Could you please provide more details?"}}]}
        self.mock_strand_client.generate_response = AsyncMock(return_value=mock_response)
        
        with patch('shared.strand_utils.format_messages_for_strand') as mock_format, \
             patch('shared.strand_utils.extract_text_from_strand_response') as mock_extract:
            
            mock_format.return_value = [{"role": "user", "content": "this"}]
            mock_extract.return_value = "Could you please provide more details?"
            
            result = await self.strand_utils._request_clarification("this")
            
            assert result == "Could you please provide more details?"
            
            # Verify the system prompt includes clarification instructions
            call_args = self.mock_strand_client.generate_response.call_args
            system_prompt = call_args[1]['system_prompt']
            assert "clarification request" in system_prompt.lower()
            assert "polite" in system_prompt.lower()
    
    @pytest.mark.asyncio
    async def test_request_clarification_with_history(self):
        """Test clarification request with conversation history."""
        conversation_history = [
            {"role": "user", "content": "I need help with something"},
            {"role": "assistant", "content": "I'd be happy to help! What do you need assistance with?"}
        ]
        
        mock_response = {"choices": [{"message": {"content": "What specific aspect would you like help with?"}}]}
        self.mock_strand_client.generate_response = AsyncMock(return_value=mock_response)
        
        with patch('shared.strand_utils.format_messages_for_strand') as mock_format, \
             patch('shared.strand_utils.extract_text_from_strand_response') as mock_extract:
            
            mock_format.return_value = conversation_history + [{"role": "user", "content": "that thing"}]
            mock_extract.return_value = "What specific aspect would you like help with?"
            
            result = await self.strand_utils._request_clarification("that thing", conversation_history)
            
            assert result == "What specific aspect would you like help with?"
            mock_format.assert_called_once_with("that thing", conversation_history)
    
    @pytest.mark.asyncio
    async def test_request_clarification_error_fallback(self):
        """Test error handling in clarification request generation."""
        self.mock_strand_client.generate_response = AsyncMock(side_effect=Exception("API error"))
        
        with patch('shared.strand_utils.format_messages_for_strand'), \
             patch('shared.strand_utils.extract_text_from_strand_response'):
            
            result = await self.strand_utils._request_clarification("unclear message")
            
            # Should return fallback message
            assert "I'd be happy to help" in result
            assert "provide a bit more detail" in result
    
    def test_build_general_system_prompt_no_history(self):
        """Test building system prompt without conversation history."""
        result = self.strand_utils._build_general_system_prompt(None)
        
        assert "helpful AI assistant" in result
        assert "AWS Bedrock Claude models" in result
        assert "comprehensive but concise" in result
        # Should not include context-specific instructions
        assert "conversation history" not in result
    
    def test_build_general_system_prompt_with_history(self):
        """Test building system prompt with conversation history."""
        conversation_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        
        result = self.strand_utils._build_general_system_prompt(conversation_history)
        
        assert "helpful AI assistant" in result
        assert "AWS Bedrock Claude models" in result
        assert "conversation history" in result
        assert "follow-up responses" in result
        assert "conversation continuity" in result
    
    def test_build_general_system_prompt_empty_history(self):
        """Test building system prompt with empty conversation history."""
        result = self.strand_utils._build_general_system_prompt([])
        
        # Empty history should be treated as no history
        assert "conversation history" not in result


class TestGeneralQuestionIntegration:
    """Integration tests for general question handling."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_strand_client = Mock(spec=StrandClient)
        self.strand_utils = StrandUtils(self.mock_strand_client)
    
    @pytest.mark.asyncio
    async def test_full_general_response_flow_clear_question(self):
        """Test the full flow for a clear general question."""
        # Mock clarification check to return False (clear question)
        self.strand_utils._needs_clarification = AsyncMock(return_value=False)
        
        # Mock the main response generation
        mock_response = {"choices": [{"message": {"content": "Here's a helpful answer to your question."}}]}
        self.mock_strand_client.generate_response = AsyncMock(return_value=mock_response)
        
        with patch('shared.strand_utils.format_messages_for_strand') as mock_format, \
             patch('shared.strand_utils.extract_text_from_strand_response') as mock_extract:
            
            mock_format.return_value = [{"role": "user", "content": "What is machine learning?"}]
            mock_extract.return_value = "Here's a helpful answer to your question."
            
            result = await self.strand_utils.generate_general_response("What is machine learning?")
            
            assert result == "Here's a helpful answer to your question."
            
            # Verify the system prompt was built correctly
            call_args = self.mock_strand_client.generate_response.call_args
            system_prompt = call_args[1]['system_prompt']
            assert "helpful AI assistant" in system_prompt
            assert "AWS Bedrock Claude models" in system_prompt
    
    @pytest.mark.asyncio
    async def test_full_general_response_flow_unclear_question(self):
        """Test the full flow for an unclear question requiring clarification."""
        # Mock clarification check to return True (unclear question)
        self.strand_utils._needs_clarification = AsyncMock(return_value=True)
        self.strand_utils._request_clarification = AsyncMock(
            return_value="I'd be happy to help! Could you please be more specific about what you're looking for?"
        )
        
        result = await self.strand_utils.generate_general_response("this thing")
        
        assert result == "I'd be happy to help! Could you please be more specific about what you're looking for?"
        
        # Should not call the main response generation
        self.mock_strand_client.generate_response.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_full_general_response_flow_with_context(self):
        """Test the full flow with conversation context."""
        conversation_history = [
            {"role": "user", "content": "I'm learning about AI"},
            {"role": "assistant", "content": "That's great! AI is a fascinating field."}
        ]
        
        # Mock clarification check to return False
        self.strand_utils._needs_clarification = AsyncMock(return_value=False)
        
        # Mock the main response generation
        mock_response = {"choices": [{"message": {"content": "Machine learning is a subset of AI that focuses on algorithms."}}]}
        self.mock_strand_client.generate_response = AsyncMock(return_value=mock_response)
        
        with patch('shared.strand_utils.format_messages_for_strand') as mock_format, \
             patch('shared.strand_utils.extract_text_from_strand_response') as mock_extract:
            
            mock_format.return_value = conversation_history + [{"role": "user", "content": "What about machine learning?"}]
            mock_extract.return_value = "Machine learning is a subset of AI that focuses on algorithms."
            
            result = await self.strand_utils.generate_general_response("What about machine learning?", conversation_history)
            
            assert result == "Machine learning is a subset of AI that focuses on algorithms."
            
            # Verify context was included in system prompt
            call_args = self.mock_strand_client.generate_response.call_args
            system_prompt = call_args[1]['system_prompt']
            assert "conversation history" in system_prompt
            assert "follow-up responses" in system_prompt


if __name__ == '__main__':
    pytest.main([__file__])