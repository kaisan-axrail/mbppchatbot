"""
Main chatbot stack that orchestrates all components.
"""

from aws_cdk import (
    Stack,
    CfnOutput
)
from constructs import Construct


class ChatbotStack(Stack):
    """Main stack that coordinates all chatbot infrastructure components."""
    
    def __init__(self, scope: Construct, construct_id: str, 
                 database_stack, lambda_stack, api_stack, storage_stack, rest_api_stack=None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.database_stack = database_stack
        self.lambda_stack = lambda_stack
        self.api_stack = api_stack
        self.storage_stack = storage_stack
        self.rest_api_stack = rest_api_stack
        
        # WebSocket API outputs
        CfnOutput(
            self, "WebSocketApiEndpoint",
            value=self.api_stack.websocket_api.api_endpoint,
            description="WebSocket API endpoint URL for client connections",
            export_name="ChatbotWebSocketEndpoint"
        )
        
        CfnOutput(
            self, "WebSocketApiId", 
            value=self.api_stack.websocket_api.api_id,
            description="WebSocket API ID",
            export_name="ChatbotWebSocketApiId"
        )
        
        # DynamoDB table outputs
        CfnOutput(
            self, "SessionsTableName",
            value=self.database_stack.sessions_table.table_name,
            description="Sessions DynamoDB table name",
            export_name="ChatbotSessionsTable"
        )
        
        CfnOutput(
            self, "ConversationsTableName",
            value=self.database_stack.conversations_table.table_name,
            description="Conversations DynamoDB table name",
            export_name="ChatbotConversationsTable"
        )
        
        CfnOutput(
            self, "AnalyticsTableName",
            value=self.database_stack.analytics_table.table_name,
            description="Analytics DynamoDB table name",
            export_name="ChatbotAnalyticsTable"
        )
        
        # Lambda function outputs
        CfnOutput(
            self, "WebSocketHandlerArn",
            value=self.lambda_stack.websocket_handler.function_arn,
            description="WebSocket handler Lambda function ARN",
            export_name="ChatbotWebSocketHandlerArn"
        )
        
        CfnOutput(
            self, "McpServerArn",
            value=self.lambda_stack.mcp_server.function_arn,
            description="MCP server Lambda function ARN",
            export_name="ChatbotMcpServerArn"
        )
        
        CfnOutput(
            self, "SessionCleanupArn",
            value=self.lambda_stack.session_cleanup.function_arn,
            description="Session cleanup Lambda function ARN",
            export_name="ChatbotSessionCleanupArn"
        )
        
        # Secrets Manager outputs
        CfnOutput(
            self, "ApiSecretsArn",
            value=self.lambda_stack.api_secrets.secret_arn,
            description="API secrets ARN in Secrets Manager",
            export_name="ChatbotApiSecretsArn"
        )
        
        CfnOutput(
            self, "McpSecretsArn",
            value=self.lambda_stack.mcp_server_construct.secrets.secret_arn,
            description="MCP server secrets ARN in Secrets Manager",
            export_name="ChatbotMcpSecretsArn"
        )
        
        # Storage stack outputs (only if storage stack is provided)
        if self.storage_stack:
            CfnOutput(
                self, "DocumentsBucketName",
                value=self.storage_stack.documents_bucket.bucket_name,
                description="S3 bucket name for RAG documents",
                export_name="ChatbotDocumentsBucketName"
            )
            
            CfnOutput(
                self, "ProcessedDocumentsBucketName",
                value=self.storage_stack.processed_documents_bucket.bucket_name,
                description="S3 bucket name for processed document chunks",
                export_name="ChatbotProcessedDocumentsBucketName"
            )
            
            CfnOutput(
                self, "DocumentProcessorArn",
                value=self.storage_stack.document_processor.function_arn,
                description="Document processor Lambda function ARN"
            )
            
            CfnOutput(
                self, "DocumentUploadHandlerArn",
                value=self.storage_stack.document_upload_handler.function_arn,
                description="Document upload handler Lambda function ARN"
            )