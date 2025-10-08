"""Sentiment analysis using AWS Comprehend."""
import boto3
import logging

logger = logging.getLogger(__name__)
comprehend = boto3.client('comprehend')

def analyze_sentiment(text: str) -> dict:
    """Analyze sentiment of text using AWS Comprehend."""
    try:
        response = comprehend.detect_sentiment(Text=text[:5000], LanguageCode='en')
        return {
            'sentiment': response['Sentiment'],
            'confidence': max(response['SentimentScore'].values()),
            'scores': response['SentimentScore']
        }
    except Exception as e:
        logger.error(f"Sentiment analysis failed: {str(e)}")
        return {'sentiment': 'NEUTRAL', 'confidence': 0.0, 'scores': {}}
