"""
API Gateway and WebSocket API stack for chatbot system.
"""

from aws_cdk import (
    Stack,
    aws_apigateway as apigateway,
    CfnOutput
)
from constructs import Construct
from cdk_constructs.websocket_api import WebSocketApiConstruct


class ApiStack(Stack):
    """Stack containing API Gateway and WebSocket API for the chatbot system."""
    
    def __init__(self, scope: Construct, construct_id: str,
                 websocket_handler, document_upload_handler=None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.websocket_handler = websocket_handler
        self.document_upload_handler = document_upload_handler
        
        # Create WebSocket API using construct
        self.websocket_api_construct = WebSocketApiConstruct(
            self, "WebSocketApiConstruct",
            websocket_handler=self.websocket_handler
        )
        
        # Expose WebSocket API for other stacks
        self.websocket_api = self.websocket_api_construct.websocket_api
        self.websocket_stage = self.websocket_api_construct.websocket_stage
        
        # Create REST API for document operations if handler provided
        if self.document_upload_handler:
            self.rest_api = apigateway.RestApi(
                self, "DocumentRestApi",
                rest_api_name="Chatbot Document API",
                description="REST API for document upload and management",
                default_cors_preflight_options=apigateway.CorsOptions(
                    allow_origins=apigateway.Cors.ALL_ORIGINS,
                    allow_methods=apigateway.Cors.ALL_METHODS,
                    allow_headers=["Content-Type", "Authorization"]
                )
            )
            
            # Document upload endpoint
            upload_integration = apigateway.LambdaIntegration(
                self.document_upload_handler,
                proxy=True
            )
            
            upload_resource = self.rest_api.root.add_resource("upload")
            upload_resource.add_method("POST", upload_integration)
            
            # Document list endpoint
            documents_resource = self.rest_api.root.add_resource("documents")
            documents_resource.add_method("GET", upload_integration)
            
            # Output REST API URL
            CfnOutput(
                self, "RestApiUrl",
                value=self.rest_api.url,
                description="REST API URL for document operations",
                export_name="ChatbotRestApiUrl"
            )