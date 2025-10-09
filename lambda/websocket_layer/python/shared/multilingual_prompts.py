"""
Prompt-based multilingual and sentiment analysis for MBPP compliance.
Uses LLM capabilities instead of AWS Comprehend for simpler implementation.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class MultilingualPromptService:
    """
    Service for multilingual support using LLM prompts instead of AWS Comprehend.
    Simpler, more cost-effective, and often more accurate approach.
    """
    
    def __init__(self):
        """Initialize multilingual prompt service."""
        self.supported_languages = {
            'English': 'en',
            'Bahasa Malaysia': 'ms', 
            'Mandarin': 'zh',
            'Chinese': 'zh',
            'Tamil': 'ta'
        }
        
        logger.info("Multilingual prompt service initialized")
    
    def get_multilingual_system_prompt(self) -> str:
        """
        Get system prompt that enables multilingual and sentiment-aware responses.
        
        Returns:
            System prompt for multilingual MBPP chatbot
        """
        return """You are ChatMBPP, an intelligent assistant for MBPP (Malaysian Building and Property Portal) services. You have the following capabilities:

LANGUAGE SUPPORT (MBPP Requirement):
- Automatically detect the user's language from their message
- Respond in the SAME language the user used
- Supported languages: English, Bahasa Malaysia, Mandarin (中文), Tamil (தமிழ்)
- If user mixes languages, respond in the primary language used

MALAYSIAN CONTEXT AWARENESS:
- Users are Malaysian, so understand local slang and expressions:
  * "Aduh" / "Adoi" - Expression of frustration, pain, or exasperation (indicates NEGATIVE sentiment)
  * "Walao" / "Wah lau" - Expression of surprise, disbelief, or annoyance (context-dependent sentiment)
  * "Aiyaa" / "Aiyo" - Expression of disappointment, frustration, or mild annoyance (indicates NEGATIVE sentiment)
  * "Alamak" - Expression of shock, surprise, or dismay (indicates NEGATIVE sentiment)
  * "Haiya" - Expression of exasperation or mild frustration (indicates NEGATIVE sentiment)
  * "Wah" - Expression of amazement or surprise (context-dependent, often POSITIVE)
  * "Lah" - Common Malaysian particle, doesn't affect sentiment but indicates local speech
- Be culturally sensitive and respond appropriately to Malaysian communication style
- Recognize code-switching between English, Malay, Chinese, and Tamil within the same message

SENTIMENT AWARENESS (MBPP Requirement):
- Analyze the user's emotional state (positive, negative, neutral, mixed)
- Pay special attention to Malaysian expressions that indicate sentiment:
  * NEGATIVE indicators: "Aduh", "Adoi", "Aiyaa", "Aiyo", "Alamak", "Haiya", "Walao" (when expressing frustration)
  * POSITIVE indicators: "Wah" (when expressing amazement), "Bagus", "Terima kasih", "Thank you lah"
  * NEUTRAL: Factual questions with "lah", "kan", "meh" particles
- Adapt your response tone accordingly:
  * POSITIVE: Be enthusiastic and supportive, match their energy
  * NEGATIVE: Be empathetic, apologetic, and solution-focused. Acknowledge their frustration culturally appropriately
  * NEUTRAL: Be professional and informative, use appropriate Malaysian politeness markers
  * MIXED: Be balanced and understanding, address both positive and negative aspects

RESPONSE FORMAT:
Always structure your response as JSON with this format:
{
  "response": "Your actual response in the user's language",
  "detected_language": "language_code (en/ms/zh/ta)",
  "language_name": "Full language name",
  "detected_sentiment": "POSITIVE/NEGATIVE/NEUTRAL/MIXED",
  "sentiment_confidence": 0.85,
  "requires_attention": false,
  "response_tone": "professional/empathetic/enthusiastic/balanced"
}

EXAMPLES:

User: "Hello, I need help with my property registration."
Response: {
  "response": "Hello! I'd be happy to help you with your property registration. What specific information do you need?",
  "detected_language": "en",
  "language_name": "English", 
  "detected_sentiment": "NEUTRAL",
  "sentiment_confidence": 0.9,
  "requires_attention": false,
  "response_tone": "professional"
}

User: "Saya sangat kecewa dengan perkhidmatan ini!"
Response: {
  "response": "Saya memahami kekecewaan anda dan saya minta maaf atas masalah yang anda hadapi. Saya akan membantu menyelesaikan isu ini dengan segera. Boleh anda beritahu saya masalah yang tepat?",
  "detected_language": "ms",
  "language_name": "Bahasa Malaysia",
  "detected_sentiment": "NEGATIVE", 
  "sentiment_confidence": 0.95,
  "requires_attention": true,
  "response_tone": "empathetic"
}

User: "我想查询我的房产信息"
Response: {
  "response": "您好！我很乐意帮助您查询房产信息。请告诉我您需要查询哪些具体信息？",
  "detected_language": "zh",
  "language_name": "Mandarin",
  "detected_sentiment": "NEUTRAL",
  "sentiment_confidence": 0.88,
  "requires_attention": false,
  "response_tone": "professional"
}

User: "Aduh, this system so slow lah! Very frustrating!"
Response: {
  "response": "Adoi, I really understand your frustration with the slow system! I'm very sorry about this inconvenience. Let me help you resolve this issue quickly. What specific task were you trying to complete?",
  "detected_language": "en",
  "language_name": "English",
  "detected_sentiment": "NEGATIVE",
  "sentiment_confidence": 0.95,
  "requires_attention": true,
  "response_tone": "empathetic"
}

User: "Wah, this new feature very good leh!"
Response: {
  "response": "Wah, thank you so much for the positive feedback! I'm really happy to hear you're enjoying the new feature. Is there anything else I can help you explore?",
  "detected_language": "en", 
  "language_name": "English",
  "detected_sentiment": "POSITIVE",
  "sentiment_confidence": 0.92,
  "requires_attention": false,
  "response_tone": "enthusiastic"
}

IMPORTANT GUIDELINES:
1. Always respond in the user's detected language
2. Be culturally appropriate for each language
3. Maintain professional MBPP service standards
4. Provide accurate sentiment analysis
5. Flag negative sentiment for escalation
6. Keep responses helpful and solution-oriented"""
    
    def get_rag_multilingual_prompt(self, context_documents: list) -> str:
        """
        Get RAG prompt that handles multilingual document search and response.
        Uses the universal multilingual system as foundation.
        
        Args:
            context_documents: List of relevant document chunks
            
        Returns:
            RAG system prompt with full multilingual and sentiment support
        """
        documents_text = "\n\n".join([
            f"Document {i+1}: {doc.get('content', '')}"
            for i, doc in enumerate(context_documents)
        ])
        
        rag_instructions = f"""CONTEXT DOCUMENTS:
{documents_text}

RAG DOCUMENT SEARCH:
1. Search the provided documents for relevant information
2. Base your answer on the document content when possible
3. If documents don't contain the answer, say so in the user's language
4. Cite which documents you used for your answer
5. Translate document information to the user's language if needed"""
        
        additional_fields = {
            '"sources_used"': '["document_1", "document_2"] (which documents you referenced)',
            '"confidence_in_answer"': '0.9 (how confident you are based on documents)'
        }
        
        return self.create_specialized_prompt(rag_instructions, additional_fields)
    

    
    def create_specialized_prompt(self, base_instructions: str, additional_fields: dict = None) -> str:
        """
        Create a specialized prompt that inherits all multilingual and sentiment capabilities.
        
        Args:
            base_instructions: Specific instructions for this prompt type
            additional_fields: Extra JSON fields to include in response format
            
        Returns:
            Complete prompt with multilingual foundation + specialized instructions
        """
        # Start with the master multilingual prompt
        base_prompt = self.get_multilingual_system_prompt()
        
        # Add specialized instructions
        specialized_section = f"""

SPECIALIZED INSTRUCTIONS:
{base_instructions}"""
        
        # Add additional response fields if specified
        if additional_fields:
            fields_text = "\n".join([f'- "{key}": {value}' for key, value in additional_fields.items()])
            specialized_section += f"""

ADDITIONAL RESPONSE FIELDS:
Add these fields to your JSON response:
{fields_text}"""
        
        return base_prompt + specialized_section
    
    def extract_response_data(self, llm_response: str) -> Dict[str, Any]:
        """
        Extract structured data from LLM JSON response.
        
        Args:
            llm_response: Raw LLM response string
            
        Returns:
            Parsed response data dictionary
        """
        try:
            # Try to parse as JSON
            import json
            
            # Clean up response if it has markdown formatting
            cleaned_response = llm_response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response.replace('```json', '').replace('```', '').strip()
            elif cleaned_response.startswith('```'):
                cleaned_response = cleaned_response.replace('```', '').strip()
            
            response_data = json.loads(cleaned_response)
            
            # Validate required fields
            required_fields = ['response', 'detected_language', 'detected_sentiment']
            for field in required_fields:
                if field not in response_data:
                    logger.warning(f"Missing required field: {field}")
                    response_data[field] = self._get_default_value(field)
            
            # Add timestamp
            response_data['analysis_timestamp'] = datetime.now(timezone.utc).isoformat()
            
            return response_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {str(e)}")
            # Fallback: treat entire response as text
            return {
                'response': llm_response,
                'detected_language': 'en',
                'language_name': 'English',
                'detected_sentiment': 'NEUTRAL',
                'sentiment_confidence': 0.5,
                'requires_attention': False,
                'response_tone': 'professional',
                'analysis_timestamp': datetime.now(timezone.utc).isoformat(),
                'parsing_error': str(e)
            }
        except Exception as e:
            logger.error(f"Error extracting response data: {str(e)}")
            return self._get_fallback_response(llm_response, str(e))
    
    def _get_default_value(self, field: str) -> Any:
        """Get default value for missing fields."""
        defaults = {
            'response': 'I apologize, but I encountered an issue processing your request.',
            'detected_language': 'en',
            'language_name': 'English',
            'detected_sentiment': 'NEUTRAL',
            'sentiment_confidence': 0.5,
            'requires_attention': False,
            'response_tone': 'professional'
        }
        return defaults.get(field, '')
    
    def _get_fallback_response(self, original_response: str, error: str) -> Dict[str, Any]:
        """Get fallback response when parsing fails."""
        return {
            'response': original_response,
            'detected_language': 'en',
            'language_name': 'English', 
            'detected_sentiment': 'NEUTRAL',
            'sentiment_confidence': 0.5,
            'requires_attention': False,
            'response_tone': 'professional',
            'analysis_timestamp': datetime.now(timezone.utc).isoformat(),
            'fallback_reason': 'parsing_error',
            'error': error
        }
    
    def create_language_aware_prompt(self, user_message: str, context: str = "") -> str:
        """
        Create a language-aware prompt for the LLM.
        
        Args:
            user_message: User's message
            context: Optional context (RAG documents, conversation history)
            
        Returns:
            Complete prompt for multilingual response
        """
        base_prompt = self.get_multilingual_system_prompt()
        
        if context:
            base_prompt += f"\n\nCONTEXT INFORMATION:\n{context}"
        
        base_prompt += f"\n\nUSER MESSAGE: {user_message}"
        base_prompt += "\n\nProvide your response in JSON format as specified above."
        
        return base_prompt
    
    def ensure_multilingual_capabilities(self, any_prompt: str) -> str:
        """
        Ensure any prompt has multilingual and sentiment capabilities.
        This is the universal method that adds Malaysian slang awareness to ANY prompt.
        
        Args:
            any_prompt: Any existing prompt from any tool/service
            
        Returns:
            Enhanced prompt with full multilingual and sentiment support
        """
        # Extract the core multilingual capabilities from the master prompt
        master_prompt = self.get_multilingual_system_prompt()
        
        # Find the core capabilities sections
        language_section = master_prompt[master_prompt.find("LANGUAGE SUPPORT"):master_prompt.find("MALAYSIAN CONTEXT")]
        malaysian_section = master_prompt[master_prompt.find("MALAYSIAN CONTEXT"):master_prompt.find("SENTIMENT AWARENESS")]
        sentiment_section = master_prompt[master_prompt.find("SENTIMENT AWARENESS"):master_prompt.find("RESPONSE FORMAT")]
        response_format = master_prompt[master_prompt.find("RESPONSE FORMAT"):master_prompt.find("EXAMPLES")]
        
        # Combine with the existing prompt
        enhanced_prompt = f"""{any_prompt}

{language_section.strip()}

{malaysian_section.strip()}

{sentiment_section.strip()}

{response_format.strip()}

IMPORTANT: Always detect language and sentiment regardless of the task type. Respond in user's language with appropriate cultural sensitivity."""
        
        return enhanced_prompt
    
    def is_negative_sentiment_requiring_attention(self, response_data: Dict[str, Any]) -> bool:
        """
        Check if sentiment requires escalation based on LLM analysis.
        
        Args:
            response_data: Parsed LLM response data
            
        Returns:
            True if escalation is needed
        """
        sentiment = response_data.get('detected_sentiment', 'NEUTRAL')
        confidence = response_data.get('sentiment_confidence', 0.0)
        requires_attention = response_data.get('requires_attention', False)
        
        return (
            sentiment == 'NEGATIVE' and confidence > 0.7
        ) or (
            sentiment == 'MIXED' and confidence > 0.8
        ) or requires_attention
    
    def get_system_messages(self, language_code: str) -> Dict[str, str]:
        """
        Get system messages in the specified language.
        
        Args:
            language_code: Language code
            
        Returns:
            Dictionary of system messages in the specified language
        """
        messages = {
            'en': {
                'welcome': "Hello! I'm your MBPP assistant. How can I help you today?",
                'error': "I apologize, but I encountered an error. Please try again.",
                'no_results': "I couldn't find relevant information for your query. Could you please rephrase your question?",
                'processing': "I'm processing your request. Please wait a moment...",
                'goodbye': "Thank you for using MBPP services. Have a great day!"
            },
            'ms': {
                'welcome': "Halo! Saya adalah pembantu MBPP anda. Bagaimana saya boleh membantu anda hari ini?",
                'error': "Maaf, saya menghadapi masalah. Sila cuba lagi.",
                'no_results': "Saya tidak dapat mencari maklumat yang berkaitan untuk pertanyaan anda. Bolehkah anda menyatakan semula soalan anda?",
                'processing': "Saya sedang memproses permintaan anda. Sila tunggu sebentar...",
                'goodbye': "Terima kasih kerana menggunakan perkhidmatan MBPP. Semoga hari anda menyenangkan!"
            },
            'zh': {
                'welcome': "您好！我是您的MBPP助手。今天我可以为您做些什么？",
                'error': "抱歉，我遇到了错误。请重试。",
                'no_results': "我无法找到与您查询相关的信息。您能重新表述您的问题吗？",
                'processing': "我正在处理您的请求。请稍等...",
                'goodbye': "感谢您使用MBPP服务。祝您有美好的一天！"
            },
            'ta': {
                'welcome': "வணக்கம்! நான் உங்கள் MBPP உதவியாளர். இன்று நான் உங்களுக்கு எப்படி உதவ முடியும்?",
                'error': "மன்னிக்கவும், நான் ஒரு பிழையை எதிர்கொண்டேன். தயவுசெய்து மீண்டும் முயற்சிக்கவும்.",
                'no_results': "உங்கள் கேள்விக்கு தொடர்புடைய தகவல்களை என்னால் கண்டுபிடிக்க முடியவில்லை. தயவுசெய்து உங்கள் கேள்வியை மீண்டும் கூற முடியுமா?",
                'processing': "நான் உங்கள் கோரிக்கையை செயல்படுத்துகிறேன். தயவுசெய்து சிறிது காத்திருக்கவும்...",
                'goodbye': "MBPP சேவைகளைப் பயன்படுத்தியதற்கு நன்றி. நல்ல நாள் இருக்கட்டும்!"
            }
        }
        
        return messages.get(language_code, messages['en'])
    
    def detect_language_simple(self, text: str) -> str:
        """
        Simple language detection based on text patterns.
        Used as fallback when full multilingual response is not available.
        
        Args:
            text: User input text to analyze
            
        Returns:
            Language code (en, ms, zh, ta)
        """
        if not text or not text.strip():
            return 'en'
        
        text_lower = text.lower().strip()
        
        # Simple pattern-based detection
        # Bahasa Malaysia indicators
        ms_indicators = ['saya', 'anda', 'dengan', 'untuk', 'adalah', 'boleh', 'tidak', 'ada', 'ini', 'itu']
        if any(word in text_lower for word in ms_indicators):
            return 'ms'
        
        # Chinese characters detection
        if any('\u4e00' <= char <= '\u9fff' for char in text):
            return 'zh'
        
        # Tamil characters detection  
        if any('\u0b80' <= char <= '\u0bff' for char in text):
            return 'ta'
        
        # Default to English
        return 'en'
    
    async def detect_language(self, text: str) -> Dict[str, Any]:
        """
        Compatibility method for existing code that expects separate language detection.
        Uses simple pattern-based detection as fallback.
        
        Args:
            text: User input text to analyze
            
        Returns:
            Dictionary containing language detection results
        """
        try:
            if not text or not text.strip():
                return self._get_default_language_result()
            
            # Use simple pattern-based detection
            detected_code = self.detect_language_simple(text)
            
            supported_languages = {
                'en': {'name': 'English', 'native_name': 'English'},
                'ms': {'name': 'Bahasa Malaysia', 'native_name': 'Bahasa Malaysia'},
                'zh': {'name': 'Mandarin', 'native_name': '中文'},
                'ta': {'name': 'Tamil', 'native_name': 'தமிழ்'}
            }
            
            language_info = supported_languages[detected_code]
            
            return {
                'language_code': detected_code,
                'language_name': language_info['name'],
                'native_name': language_info['native_name'],
                'confidence': 0.8,  # Reasonable confidence for pattern-based detection
                'is_supported': True,
                'detection_timestamp': datetime.now(timezone.utc).isoformat(),
                'detection_method': 'pattern_based_fallback'
            }
                
        except Exception as e:
            logger.error(f"Language detection error: {str(e)}")
            return self._get_default_language_result(error=str(e))
    
    def _get_default_language_result(self, error: Optional[str] = None) -> Dict[str, Any]:
        """Get default language result when detection fails or text is empty."""
        result = {
            'language_code': 'en',
            'language_name': 'English',
            'native_name': 'English',
            'confidence': 1.0,
            'is_supported': True,
            'detection_timestamp': datetime.now(timezone.utc).isoformat(),
            'fallback_reason': 'default',
            'detection_method': 'fallback'
        }
        
        if error:
            result['error'] = error
            result['fallback_reason'] = 'error'
            
        return result
    
    def get_multilingual_prompt(self, user_message: str, context: str = "") -> str:
        """
        Compatibility method - same as create_language_aware_prompt.
        
        Args:
            user_message: User's message
            context: Optional context
            
        Returns:
            Complete multilingual prompt
        """
        return self.create_language_aware_prompt(user_message, context)


# Factory functions
def create_multilingual_prompt_service() -> MultilingualPromptService:
    """Create and return a configured MultilingualPromptService instance."""
    return MultilingualPromptService()

# Compatibility function for existing code
def create_language_service() -> MultilingualPromptService:
    """
    Compatibility function that returns MultilingualPromptService.
    This allows existing code to continue working without changes.
    """
    return MultilingualPromptService()