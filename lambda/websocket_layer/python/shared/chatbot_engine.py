"""
ChatbotEngine for processing different types of queries and routing them appropriately.
"""

import logging
import os
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

from shared.strand_client import StrandClient
from shared.strand_utils import StrandUtils, QueryType
from shared.session_manager import SessionManager
from shared.session_models import SessionStatus
from shared.utils import get_current_timestamp, generate_message_id
from shared.exceptions import (
    ChatbotEngineError,
    StrandClientError,
    QueryProcessingError,
    TimeoutError,
    RateLimitError,
    get_user_friendly_message
)
from shared.error_handler import error_handler, with_bedrock_degradation, isolate_analytics_errors

# Configure logging
logger = logging.getLogger(__name__)


class ChatbotResponse:
    """Response object from ChatbotEngine."""
    
    def __init__(
        self,
        content: str,
        query_type: QueryType,
        sources: List[str] = None,
        tools_used: List[str] = None,
        response_time: float = None,
        message_id: str = None
    ):
        self.content = content
        self.query_type = query_type
        self.sources = sources or []
        self.tools_used = tools_used or []
        self.response_time = response_time
        self.message_id = message_id or generate_message_id()
        self.timestamp = get_current_timestamp()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary format."""
        return {
            'message_id': self.message_id,
            'content': self.content,
            'query_type': self.query_type.value,
            'sources': self.sources,
            'tools_used': self.tools_used,
            'response_time': self.response_time,
            'timestamp': self.timestamp
        }


class ChatbotEngine:
    """
    Main chatbot engine for processing messages and routing to appropriate handlers.
    """
    
    def __init__(
        self,
        strand_client: StrandClient = None,
        session_manager: SessionManager = None,
        region: str = None
    ):
        """
        Initialize ChatbotEngine.
        
        Args:
            strand_client: Configured StrandClient instance
            session_manager: SessionManager instance
            region: AWS region for DynamoDB
        """
        self.region = region or 'us-east-1'
        
        # Initialize clients
        if strand_client is None:
            from shared.strand_client import create_strand_client
            self.strand_client = create_strand_client(region=self.region)
        else:
            self.strand_client = strand_client
        
        self.strand_utils = StrandUtils(self.strand_client)
        
        if session_manager is None:
            sessions_table_name = self._get_table_name('sessions')
            self.session_manager = SessionManager(
                table_name=sessions_table_name,
                region_name=self.region
            )
        else:
            self.session_manager = session_manager
        
        # Initialize DynamoDB for conversation logging
        self.dynamodb = boto3.resource('dynamodb', region_name=self.region)
        self.conversations_table_name = self._get_table_name('conversations')
        self.analytics_table_name = self._get_table_name('analytics')
        
        # Conversation context cache (in production, this would be Redis or similar)
        self._conversation_cache: Dict[str, List[Dict[str, str]]] = {}
        
        logger.info("ChatbotEngine initialized successfully")
    
    async def process_message(
        self, 
        session_id: str, 
        message: str, 
        user_context: Dict[str, Any] = None
    ) -> ChatbotResponse:
        """
        Process a user message and generate appropriate response.
        
        Args:
            session_id: Session identifier
            message: User's message
            user_context: Additional user context
            
        Returns:
            ChatbotResponse object
            
        Raises:
            ChatbotEngineError: If message processing fails
        """
        start_time = datetime.now()
        
        try:
            # Validate session
            session = await self.session_manager.get_session(session_id)
            if not session or session.status != SessionStatus.ACTIVE:
                raise ChatbotEngineError(
                    f"Invalid or inactive session: {session_id}",
                    "INVALID_SESSION"
                )
            
            # Update session activity
            await self.session_manager.update_activity(session_id)
            
            # Determine query type
            query_type = await self.determine_query_type(message)
            
            # Get conversation history
            conversation_history = self._get_conversation_history(session_id)
            
            # Route to appropriate handler
            response_content = ""
            sources = []
            tools_used = []
            
            if query_type == QueryType.RAG:
                response_content, sources = await self._handle_rag_query(
                    message, conversation_history
                )
            elif query_type == QueryType.GENERAL:
                response_content = await self._handle_general_query(
                    message, conversation_history
                )
            elif query_type == QueryType.MCP_TOOL:
                response_content, tools_used = await self._handle_mcp_query(
                    message, conversation_history
                )
            
            # Calculate response time
            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds() * 1000  # milliseconds
            
            # Create response object
            response = ChatbotResponse(
                content=response_content,
                query_type=query_type,
                sources=sources,
                tools_used=tools_used,
                response_time=response_time
            )
            
            # Log conversation
            self._log_conversation(session_id, message, response, user_context)
            
            # Update conversation context
            self._update_conversation_context(session_id, message, response_content)
            
            logger.info(f"Processed message for session {session_id}, type: {query_type.value}")
            return response
            
        except ChatbotEngineError:
            raise
        except Exception as e:
            logger.error(f"Failed to process message: {str(e)}")
            raise ChatbotEngineError(
                f"Failed to process message: {str(e)}",
                "MESSAGE_PROCESSING_ERROR"
            )
    
    async def determine_query_type(self, message: str) -> QueryType:
        """
        Determine the type of query using Strand SDK.
        
        Args:
            message: User's message
            
        Returns:
            QueryType enum value
        """
        try:
            query_type = await self.strand_utils.determine_query_type(message)
            logger.debug(f"Determined query type: {query_type.value} for message: {message[:50]}...")
            return query_type
            
        except Exception as e:
            logger.error(f"Failed to determine query type: {str(e)}")
            # Default to general on error
            return QueryType.GENERAL
    
    async def _handle_rag_query(
        self, 
        message: str, 
        conversation_history: List[Dict[str, str]]
    ) -> Tuple[str, List[str]]:
        """
        Handle RAG (Retrieval-Augmented Generation) queries.
        
        Args:
            message: User's message
            conversation_history: Previous conversation messages
            
        Returns:
            Tuple of (response_content, sources)
        """
        try:
            # Call the MCP server to search documents
            from shared.mcp_handler import create_mcp_handler
            
            mcp_handler = create_mcp_handler(
                mcp_server_lambda_arn=os.environ.get('MCP_SERVER_ARN'),
                region=self.region
            )
            
            # Search for relevant documents
            search_result = await mcp_handler.execute_tool(
                tool_name='search_documents',
                parameters={
                    'query': message,
                    'limit': 5,
                    'threshold': 0.7
                }
            )
            
            # Extract documents from search result
            documents = []
            if search_result.get('success') and search_result.get('results'):
                documents = search_result['results']
                logger.info(f"Found {len(documents)} relevant documents")
            else:
                logger.warning(f"No documents found for query: {message[:50]}...")
            
            # Generate response using Strand SDK with retrieved context
            response_content, sources = await self.strand_utils.generate_rag_response(
                message, documents, conversation_history
            )
            
            logger.info(f"Generated RAG response with {len(sources)} sources")
            return response_content, sources
            
        except Exception as e:
            logger.error(f"Failed to handle RAG query: {str(e)}")
            # Fallback to general response
            response_content = await self.strand_utils.generate_general_response(
                message, conversation_history
            )
            return response_content, []
    
    async def _handle_general_query(
        self, 
        message: str, 
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """
        Handle general queries with enhanced error handling and graceful degradation.
        
        Args:
            message: User's message
            conversation_history: Previous conversation messages
            
        Returns:
            Response content
        """
        try:
            # Enhanced conversation context management
            enhanced_history = self._enhance_conversation_context(conversation_history)
            
            response_content = await self.strand_utils.generate_general_response(
                message, enhanced_history
            )
            
            logger.info(f"Generated general response for message: {message[:50]}...")
            return response_content
            
        except Exception as e:
            # Use error handler for comprehensive error management
            context = {
                'query_type': 'general',
                'message_preview': message[:100],
                'history_length': len(conversation_history)
            }
            
            # Handle Bedrock-related errors with graceful degradation
            if 'bedrock' in str(e).lower() or isinstance(e, StrandClientError):
                error_result = error_handler.handle_bedrock_error(e, context, fallback_enabled=True)
                if 'fallback_response' in error_result:
                    # Extract text from fallback response
                    fallback_content = error_result['fallback_response'].get('content', [])
                    if fallback_content and fallback_content[0].get('type') == 'text':
                        return fallback_content[0].get('text', '')
                
                return error_result.get('user_message', self._get_error_fallback_message(str(e)))
            else:
                # Log other errors with context
                error_handler.log_error_with_context(e, context)
                return self._get_error_fallback_message(str(e))
    
    def _enhance_conversation_context(
        self, 
        conversation_history: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        Enhance conversation context by filtering and organizing messages.
        
        Args:
            conversation_history: Raw conversation history
            
        Returns:
            Enhanced conversation history
        """
        if not conversation_history:
            return []
        
        # Filter out system messages and keep only user/assistant exchanges
        filtered_history = []
        for message in conversation_history:
            if message.get('role') in ['user', 'assistant']:
                # Ensure content is not empty
                content = message.get('content', '').strip()
                if content:
                    filtered_history.append({
                        'role': message['role'],
                        'content': content
                    })
        
        # Keep only the most recent exchanges (last 10 messages = 5 exchanges)
        if len(filtered_history) > 10:
            filtered_history = filtered_history[-10:]
        
        return filtered_history
    
    def _get_error_fallback_message(self, error_details: str) -> str:
        """
        Generate an appropriate error fallback message based on the error.
        
        Args:
            error_details: Details about the error that occurred
            
        Returns:
            User-friendly error message
        """
        # Use centralized error message logic
        try:
            # Create a mock exception to use the centralized error message logic
            mock_error = Exception(error_details)
            return get_user_friendly_message(mock_error)
        except Exception:
            # Fallback to default message if error processing fails
            return "I apologize, but I encountered an unexpected error. Please try asking your question again."
    
    async def _handle_mcp_query(
        self, 
        message: str, 
        conversation_history: List[Dict[str, str]]
    ) -> Tuple[str, List[str]]:
        """
        Handle MCP tool queries using real MCP protocol with Strands Agent.
        
        Args:
            message: User's message
            conversation_history: Previous conversation messages
            
        Returns:
            Tuple of (response_content, tools_used)
        """
        try:
            from shared.mcp_client_real import create_real_mcp_handler
            
            mcp_lambda_arn = os.environ.get('MCP_SERVER_ARN')
            if not mcp_lambda_arn:
                logger.warning("MCP_SERVER_ARN not configured")
                response_content = await self.strand_utils.generate_general_response(
                    message, conversation_history
                )
                return response_content, []
            
            mcp_handler = create_real_mcp_handler(mcp_lambda_arn)
            response_content = await mcp_handler.process_with_agent(message, conversation_history)
            tools_used = ['mcp_tools']
            
            logger.info(f"Generated MCP response using Strands Agent")
            return response_content, tools_used
            
        except Exception as e:
            logger.error(f"Failed to handle MCP query: {str(e)}")
            response_content = await self.strand_utils.generate_general_response(
                message, conversation_history
            )
            return response_content, []
    
    def _filter_events(self, events: List[Dict], search_term: str) -> List[Dict]:
        """Filter events by name, location, or description."""
        if not search_term:
            return events
        search_lower = search_term.lower()
        return [e for e in events if 
                search_lower in e.get('name', '').lower() or
                search_lower in e.get('eventName', '').lower() or
                search_lower in e.get('location', '').lower() or
                search_lower in e.get('description', '').lower()]
    
    def _get_conversation_history(
        self, 
        session_id: str, 
        limit: int = 10
    ) -> List[Dict[str, str]]:
        """
        Get conversation history for a session.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of conversation messages
        """
        # Check cache first
        if session_id in self._conversation_cache:
            history = self._conversation_cache[session_id]
            return history[-limit*2:] if len(history) > limit*2 else history
        
        # In a production system, this would query DynamoDB
        # For now, return empty history
        return []
    
    def _update_conversation_context(
        self, 
        session_id: str, 
        user_message: str, 
        assistant_response: str
    ) -> None:
        """
        Update conversation context cache.
        
        Args:
            session_id: Session identifier
            user_message: User's message
            assistant_response: Assistant's response
        """
        if session_id not in self._conversation_cache:
            self._conversation_cache[session_id] = []
        
        # Add user message
        self._conversation_cache[session_id].append({
            'role': 'user',
            'content': user_message
        })
        
        # Add assistant response
        self._conversation_cache[session_id].append({
            'role': 'assistant',
            'content': assistant_response
        })
        
        # Keep only last 20 messages (10 exchanges)
        if len(self._conversation_cache[session_id]) > 20:
            self._conversation_cache[session_id] = self._conversation_cache[session_id][-20:]
    
    @isolate_analytics_errors
    def _log_conversation(
        self, 
        session_id: str, 
        user_message: str, 
        response: ChatbotResponse, 
        user_context: Dict[str, Any] = None
    ) -> None:
        """
        Log conversation to DynamoDB with error isolation and sentiment analysis.
        
        Args:
            session_id: Session identifier
            user_message: User's message
            response: ChatbotResponse object
            user_context: Additional user context
        """
        from shared.sentiment_analyzer import analyze_sentiment
        
        conversations_table = self.dynamodb.Table(self.conversations_table_name)
        history_table = self.dynamodb.Table(os.environ.get('CONVERSATION_HISTORY_TABLE', 'chatbot-conversation-history'))
        
        # Analyze sentiment
        user_sentiment = analyze_sentiment(user_message)
        response_sentiment = analyze_sentiment(response.content)
        
        timestamp = get_current_timestamp()
        
        # Log user message to conversations table
        user_record = {
            'sessionId': session_id,
            'messageId': generate_message_id(),
            'timestamp': timestamp,
            'message_type': 'user',
            'content': user_message,
            'sentiment': user_sentiment['sentiment'],
            'sentiment_confidence': user_sentiment['confidence'],
            'user_context': user_context or {}
        }
        
        # Log assistant response to conversations table
        assistant_record = {
            'sessionId': session_id,
            'messageId': response.message_id,
            'timestamp': response.timestamp,
            'message_type': 'assistant',
            'content': response.content,
            'sentiment': response_sentiment['sentiment'],
            'sentiment_confidence': response_sentiment['confidence'],
            'query_type': response.query_type.value,
            'sources': response.sources,
            'tools_used': response.tools_used,
            'response_time': response.response_time
        }
        
        # Write to conversations table
        conversations_table.put_item(Item=user_record)
        conversations_table.put_item(Item=assistant_record)
        
        # Write to conversation history table
        history_table.put_item(Item=user_record)
        history_table.put_item(Item=assistant_record)
        
        # Log analytics with isolation
        self._log_analytics_isolated(session_id, response.query_type, response.tools_used)
        
        logger.debug(f"Logged conversation for session {session_id}")
    
    @isolate_analytics_errors
    def _log_analytics_isolated(
        self,
        session_id: str,
        query_type: 'QueryType',
        tools_used: List[str]
    ) -> None:
        """
        Log analytics data with error isolation.
        
        Args:
            session_id: Session identifier
            query_type: Type of query processed
            tools_used: List of tools used
        """
        analytics_table = self.dynamodb.Table(self.analytics_table_name)
        
        # Log query type analytics
        query_record = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'event_id': f"{session_id}_{generate_message_id()}",
            'event_type': 'query',
            'session_id': session_id,
            'details': {
                'query_type': query_type.value,
                'tools_used': tools_used
            },
            'timestamp': get_current_timestamp()
        }
        
        analytics_table.put_item(Item=query_record)
        
        # Log tool usage analytics
        for tool in tools_used:
            tool_record = {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'event_id': f"{session_id}_{tool}_{generate_message_id()}",
                'event_type': 'tool_usage',
                'session_id': session_id,
                'details': {
                    'tool_name': tool,
                    'query_type': query_type.value
                },
                'timestamp': get_current_timestamp()
            }
            
            analytics_table.put_item(Item=tool_record)
        
        logger.debug(f"Logged analytics for session {session_id}")
    

    
    def _get_table_name(self, table_type: str) -> str:
        """
        Get DynamoDB table name from environment or default.
        
        Args:
            table_type: Type of table (conversations, analytics)
            
        Returns:
            Table name
        """
        import os
        
        table_mapping = {
            'conversations': os.environ.get('CONVERSATIONS_TABLE', 'chatbot-conversations'),
            'analytics': os.environ.get('ANALYTICS_TABLE', 'chatbot-analytics'),
            'sessions': os.environ.get('SESSIONS_TABLE', 'chatbot-sessions')
        }
        
        return table_mapping.get(table_type, f'chatbot-{table_type}')
    
    def get_engine_status(self) -> Dict[str, Any]:
        """
        Get current engine status and configuration.
        
        Returns:
            Status dictionary
        """
        return {
            'region': self.region,
            'strand_client_configured': bool(self.strand_client.api_key),
            'conversations_table': self.conversations_table_name,
            'analytics_table': self.analytics_table_name,
            'cached_sessions': len(self._conversation_cache),
            'timestamp': get_current_timestamp()
        }


def create_chatbot_engine(
    strand_client: StrandClient = None,
    session_manager: SessionManager = None,
    region: str = None
) -> ChatbotEngine:
    """
    Factory function to create a configured ChatbotEngine.
    
    Args:
        strand_client: Optional pre-configured StrandClient
        session_manager: Optional pre-configured SessionManager
        region: AWS region
        
    Returns:
        ChatbotEngine instance
    """
    return ChatbotEngine(
        strand_client=strand_client,
        session_manager=session_manager,
        region=region
    )