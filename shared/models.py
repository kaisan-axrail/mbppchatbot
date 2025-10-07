"""
Shared data models for the chatbot system.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from enum import Enum


class QueryType(Enum):
    """Enumeration of supported query types."""
    RAG = 'rag'
    GENERAL = 'general'
    MCP_TOOL = 'mcp_tool'


@dataclass
class Session:
    """Session data model."""
    sessionId: str
    createdAt: str
    lastActivity: str
    isActive: bool
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class SessionRecord:
    """DynamoDB session record model."""
    sessionId: str
    createdAt: str
    lastActivity: str
    isActive: bool
    clientInfo: Optional[Dict[str, str]] = None
    ttl: Optional[int] = None


@dataclass
class ConversationRecord:
    """DynamoDB conversation record model."""
    sessionId: str
    messageId: str
    timestamp: str
    messageType: str  # 'user' | 'assistant'
    content: str
    queryType: Optional[QueryType] = None
    sources: Optional[List[str]] = None
    toolsUsed: Optional[List[str]] = None
    responseTime: Optional[int] = None


@dataclass
class AnalyticsRecord:
    """DynamoDB analytics record model."""
    date: str
    eventId: str
    eventType: str  # 'query' | 'tool_usage' | 'session_created' | 'session_closed'
    sessionId: str
    details: Dict[str, Any]
    timestamp: str


@dataclass
class WebSocketMessage:
    """WebSocket message model."""
    sessionId: str
    messageId: str
    content: str
    timestamp: str
    messageType: str  # 'user' | 'system'


@dataclass
class WebSocketResponse:
    """WebSocket response model."""
    sessionId: str
    messageId: str
    content: str
    timestamp: str
    sources: Optional[List[str]] = None
    toolsUsed: Optional[List[str]] = None


@dataclass
class ChatbotResponse:
    """Chatbot response model."""
    content: str
    queryType: QueryType
    sources: Optional[List[str]] = None
    toolsUsed: Optional[List[str]] = None


@dataclass
class DocumentChunk:
    """Document chunk model for RAG operations."""
    id: str
    content: str
    source: str
    score: float