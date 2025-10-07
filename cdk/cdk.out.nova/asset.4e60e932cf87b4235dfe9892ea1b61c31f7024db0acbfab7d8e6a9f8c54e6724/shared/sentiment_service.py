"""
Sentiment analysis service for MBPP compliance.
Uses prompt-based approach instead of AWS Comprehend for simpler implementation.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from shared.multilingual_prompts import MultilingualPromptService

# Configure logging
logger = logging.getLogger(__name__)


class SentimentAnalysisError(Exception):
    """Exception for sentiment analysis errors."""
    pass


class SentimentService:
    """
    Service for sentiment analysis of user interactions.
    Implements MBPP requirements using prompt-based sentiment detection.
    """
    
    def __init__(self):
        """Initialize sentiment service with prompt-based analysis."""
        self.multilingual_service = MultilingualPromptService()
        
        # Sentiment categories mapping
        self.sentiment_categories = {
            'POSITIVE': {
                'label': 'Positive',
                'description': 'User expresses satisfaction, happiness, or positive sentiment',
                'priority': 'low'
            },
            'NEGATIVE': {
                'label': 'Negative', 
                'description': 'User expresses dissatisfaction, frustration, or negative sentiment',
                'priority': 'high'
            },
            'NEUTRAL': {
                'label': 'Neutral',
                'description': 'User expresses neutral or factual sentiment',
                'priority': 'low'
            },
            'MIXED': {
                'label': 'Mixed',
                'description': 'User expresses both positive and negative sentiments',
                'priority': 'medium'
            }
        }
        
        logger.info("Sentiment service initialized with prompt-based analysis")
    
    def extract_sentiment_from_response(self, response_data: Dict[str, Any], session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract sentiment analysis from multilingual prompt response.
        
        Args:
            response_data: Response data from multilingual prompt service
            session_id: Optional session ID for tracking
            
        Returns:
            Dictionary containing sentiment analysis results
        """
        try:
            sentiment = response_data.get('detected_sentiment', 'NEUTRAL')
            confidence = response_data.get('sentiment_confidence', 0.5)
            requires_attention = response_data.get('requires_attention', False)
            language_code = response_data.get('detected_language', 'en')
            
            # Get category info
            category_info = self.sentiment_categories.get(sentiment, self.sentiment_categories['NEUTRAL'])
            
            # Create sentiment scores based on detected sentiment
            sentiment_scores = self._create_sentiment_scores(sentiment, confidence)
            
            result = {
                'sentiment': sentiment,
                'sentiment_label': category_info['label'],
                'confidence': confidence,
                'sentiment_scores': sentiment_scores,
                'priority': category_info['priority'],
                'requires_attention': requires_attention,
                'language_code': language_code,
                'analysis_timestamp': datetime.now(timezone.utc).isoformat(),
                'session_id': session_id,
                'text_length': len(response_data.get('response', '')),
                'description': category_info['description'],
                'analysis_method': 'prompt_based'
            }
            
            logger.info(f"Sentiment analysis completed: {sentiment} (confidence: {confidence:.2f})")
            return result
            
        except Exception as e:
            logger.error(f"Sentiment analysis error: {str(e)}")
            return self._get_neutral_sentiment_result(session_id, f"extraction_error: {str(e)}")
    
    def _create_sentiment_scores(self, sentiment: str, confidence: float) -> Dict[str, float]:
        """Create sentiment scores based on detected sentiment and confidence."""
        scores = {
            'positive': 0.0,
            'negative': 0.0,
            'neutral': 0.0,
            'mixed': 0.0
        }
        
        if sentiment == 'POSITIVE':
            scores['positive'] = confidence
            scores['neutral'] = 1.0 - confidence
        elif sentiment == 'NEGATIVE':
            scores['negative'] = confidence
            scores['neutral'] = 1.0 - confidence
        elif sentiment == 'MIXED':
            scores['mixed'] = confidence
            scores['positive'] = (1.0 - confidence) * 0.3
            scores['negative'] = (1.0 - confidence) * 0.3
            scores['neutral'] = (1.0 - confidence) * 0.4
        else:  # NEUTRAL
            scores['neutral'] = confidence
            scores['positive'] = (1.0 - confidence) * 0.5
            scores['negative'] = (1.0 - confidence) * 0.5
        
        return scores
    
    def is_negative_sentiment_requiring_attention(self, response_data: Dict[str, Any]) -> bool:
        """
        Check if sentiment requires escalation based on prompt analysis.
        
        Args:
            response_data: Parsed multilingual prompt response data
            
        Returns:
            True if escalation is needed
        """
        return self.multilingual_service.is_negative_sentiment_requiring_attention(response_data)
    
    def get_sentiment_analysis_prompt(self, text: str) -> str:
        """
        Get the proper LLM prompt for sentiment analysis.
        This is the CORRECT way to do sentiment analysis.
        
        Args:
            text: User input text
            
        Returns:
            Complete prompt for LLM sentiment analysis
        """
        return self.multilingual_service.create_language_aware_prompt(text)
    
    async def analyze_sentiment_with_llm(
        self, 
        text: str, 
        llm_response: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        RECOMMENDED: Analyze sentiment from LLM response that used multilingual prompt.
        This is the proper way to do sentiment analysis with the new system.
        
        Args:
            text: Original user input text
            llm_response: Raw LLM response string (JSON format)
            session_id: Optional session ID for tracking
            
        Returns:
            Dictionary containing sentiment analysis results
        """
        try:
            # Extract structured data from LLM response
            response_data = self.multilingual_service.extract_response_data(llm_response)
            
            # Extract sentiment analysis from the response
            return self.extract_sentiment_from_response(response_data, session_id)
            
        except Exception as e:
            logger.error(f"LLM sentiment analysis error: {str(e)}")
            # Fallback to pattern-based analysis
            return await self.analyze_sentiment(text, session_id=session_id)
    
    async def analyze_sentiment(
        self, 
        text: str, 
        language_code: str = 'en',
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze sentiment using LLM prompt-based approach.
        This method should ideally be called after getting LLM response,
        but provides compatibility for existing code.
        
        Args:
            text: User input text to analyze
            language_code: Language code for analysis (en, ms, zh, ta)
            session_id: Optional session ID for tracking
            
        Returns:
            Dictionary containing sentiment analysis results
        """
        try:
            if not text or not text.strip():
                return self._get_neutral_sentiment_result(session_id, "empty_text")
            
            # TODO: This should ideally call an LLM with the multilingual prompt
            # For now, using pattern-based detection as fallback
            # In production, this would be:
            # 1. prompt = self.multilingual_service.create_language_aware_prompt(text)
            # 2. llm_response = call_llm(prompt)  # Your LLM integration
            # 3. response_data = self.multilingual_service.extract_response_data(llm_response)
            # 4. return self.extract_sentiment_from_response(response_data, session_id)
            
            logger.warning("Using pattern-based sentiment fallback. Consider using LLM-based analysis for better accuracy.")
            
            # Fallback to pattern-based detection
            sentiment = self._detect_sentiment_simple(text)
            confidence = 0.6  # Lower confidence for pattern-based
            
            category_info = self.sentiment_categories.get(sentiment, self.sentiment_categories['NEUTRAL'])
            
            # Determine if this requires attention
            requires_attention = sentiment == 'NEGATIVE' and confidence > 0.5
            
            # Create sentiment scores
            sentiment_scores = self._create_sentiment_scores(sentiment, confidence)
            
            result = {
                'sentiment': sentiment,
                'sentiment_label': category_info['label'],
                'confidence': confidence,
                'sentiment_scores': sentiment_scores,
                'priority': category_info['priority'],
                'requires_attention': requires_attention,
                'language_code': language_code,
                'analysis_timestamp': datetime.now(timezone.utc).isoformat(),
                'session_id': session_id,
                'text_length': len(text),
                'description': category_info['description'],
                'analysis_method': 'pattern_based_fallback',
                'recommendation': 'Use LLM-based analysis for better accuracy'
            }
            
            logger.info(f"Sentiment analysis completed: {sentiment} (confidence: {confidence:.2f}) - Using fallback method")
            return result
            
        except Exception as e:
            logger.error(f"Sentiment analysis error: {str(e)}")
            return self._get_neutral_sentiment_result(session_id, f"analysis_error: {str(e)}")
    
    def _detect_sentiment_simple(self, text: str) -> str:
        """
        Simple pattern-based sentiment detection.
        
        Args:
            text: Text to analyze
            
        Returns:
            Sentiment category (POSITIVE, NEGATIVE, NEUTRAL, MIXED)
        """
        text_lower = text.lower().strip()
        
        # Negative indicators (multiple languages)
        negative_words = [
            # English
            'bad', 'terrible', 'awful', 'hate', 'angry', 'frustrated', 'disappointed', 
            'problem', 'issue', 'error', 'wrong', 'fail', 'broken', 'worst',
            # Bahasa Malaysia
            'buruk', 'teruk', 'marah', 'kecewa', 'masalah', 'salah', 'rosak',
            # Chinese (simplified patterns)
            '坏', '糟糕', '生气', '失望', '问题', '错误', '坏了',
            # Tamil (simplified patterns)
            'கெட்ட', 'மோசமான', 'கோபம', 'ஏமாற்றம', 'பிரச்சனை'
        ]
        
        # Positive indicators (multiple languages)
        positive_words = [
            # English
            'good', 'great', 'excellent', 'amazing', 'wonderful', 'perfect', 'love',
            'happy', 'satisfied', 'pleased', 'thank', 'awesome', 'fantastic',
            # Bahasa Malaysia
            'bagus', 'hebat', 'sempurna', 'suka', 'gembira', 'puas', 'terima kasih',
            # Chinese (simplified patterns)
            '好', '很好', '完美', '喜欢', '高兴', '满意', '谢谢',
            # Tamil (simplified patterns)
            'நல்ல', 'சிறந்த', 'மகிழ்ச்சி', 'திருப்தி', 'நன்றி'
        ]
        
        negative_count = sum(1 for word in negative_words if word in text_lower)
        positive_count = sum(1 for word in positive_words if word in text_lower)
        
        if negative_count > positive_count and negative_count > 0:
            return 'NEGATIVE'
        elif positive_count > negative_count and positive_count > 0:
            return 'POSITIVE'
        elif negative_count > 0 and positive_count > 0:
            return 'MIXED'
        else:
            return 'NEUTRAL'
    
    def _get_neutral_sentiment_result(
        self, 
        session_id: Optional[str] = None, 
        reason: str = "default"
    ) -> Dict[str, Any]:
        """Get neutral sentiment result when analysis fails or text is empty."""
        return {
            'sentiment': 'NEUTRAL',
            'sentiment_label': 'Neutral',
            'confidence': 1.0,
            'sentiment_scores': {
                'positive': 0.0,
                'negative': 0.0,
                'neutral': 1.0,
                'mixed': 0.0
            },
            'priority': 'low',
            'requires_attention': False,
            'language_code': 'en',
            'analysis_timestamp': datetime.now(timezone.utc).isoformat(),
            'session_id': session_id,
            'text_length': 0,
            'description': 'Neutral or factual sentiment',
            'fallback_reason': reason
        }
    
    def get_sentiment_summary(self, sentiment_results: list) -> Dict[str, Any]:
        """
        Generate summary statistics from multiple sentiment analyses.
        
        Args:
            sentiment_results: List of sentiment analysis results
            
        Returns:
            Summary statistics dictionary
        """
        if not sentiment_results:
            return {
                'total_interactions': 0,
                'sentiment_distribution': {},
                'average_confidence': 0.0,
                'attention_required_count': 0
            }
        
        total = len(sentiment_results)
        sentiment_counts = {}
        total_confidence = 0.0
        attention_count = 0
        
        for result in sentiment_results:
            sentiment = result.get('sentiment', 'NEUTRAL')
            sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
            total_confidence += result.get('confidence', 0.0)
            
            if result.get('requires_attention', False):
                attention_count += 1
        
        # Calculate percentages
        sentiment_distribution = {
            sentiment: {
                'count': count,
                'percentage': (count / total) * 100
            }
            for sentiment, count in sentiment_counts.items()
        }
        
        return {
            'total_interactions': total,
            'sentiment_distribution': sentiment_distribution,
            'average_confidence': total_confidence / total if total > 0 else 0.0,
            'attention_required_count': attention_count,
            'attention_percentage': (attention_count / total) * 100 if total > 0 else 0.0,
            'summary_timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    def should_escalate(self, sentiment_result: Dict[str, Any]) -> bool:
        """
        Determine if a sentiment result should trigger escalation.
        
        Args:
            sentiment_result: Sentiment analysis result
            
        Returns:
            True if escalation is recommended
        """
        return (
            sentiment_result.get('sentiment') == 'NEGATIVE' and
            sentiment_result.get('confidence', 0.0) > 0.8
        ) or (
            sentiment_result.get('sentiment') == 'MIXED' and
            sentiment_result.get('sentiment_scores', {}).get('negative', 0.0) > 0.7
        )
    
    def get_response_tone_guidance(self, sentiment_result: Dict[str, Any]) -> Dict[str, str]:
        """
        Get guidance for response tone based on detected sentiment.
        
        Args:
            sentiment_result: Sentiment analysis result
            
        Returns:
            Response tone guidance dictionary
        """
        sentiment = sentiment_result.get('sentiment', 'NEUTRAL')
        
        guidance = {
            'POSITIVE': {
                'tone': 'enthusiastic',
                'approach': 'Match the positive energy while remaining professional',
                'keywords': ['great', 'excellent', 'wonderful', 'pleased']
            },
            'NEGATIVE': {
                'tone': 'empathetic',
                'approach': 'Acknowledge concerns, show understanding, offer solutions',
                'keywords': ['understand', 'apologize', 'help', 'resolve']
            },
            'NEUTRAL': {
                'tone': 'professional',
                'approach': 'Provide clear, factual information in a helpful manner',
                'keywords': ['information', 'assist', 'provide', 'help']
            },
            'MIXED': {
                'tone': 'balanced',
                'approach': 'Address concerns while building on positive aspects',
                'keywords': ['understand', 'appreciate', 'improve', 'support']
            }
        }
        
        return guidance.get(sentiment, guidance['NEUTRAL'])


# Factory function for easy import
def create_sentiment_service() -> SentimentService:
    """Create and return a configured SentimentService instance."""
    return SentimentService()