"""
WebSocket API construct for chatbot system.
"""

from aws_cdk import (
    aws_apigatewayv2 as apigwv2,
    aws_lambda as _lambda,
    aws_iam as iam,
    CfnOutput
)
from aws_cdk.aws_apigatewayv2_integrations import WebSocketLambdaIntegration
from constructs import Construct


class WebSocketApiConstruct(Construct):
    """Construct for creating WebSocket API with proper configuration."""
    
    def __init__(self, scope: Construct, construct_id: str, 
                 websocket_handler: _lambda.Function, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.websocket_handler = websocket_handler
        
        # Create WebSocket API
        self.websocket_api = apigwv2.WebSocketApi(
            self, "ChatbotWebSocketApi",
            api_name="chatbot-websocket-api",
            description="WebSocket API for real-time chatbot communication",
            route_selection_expression="$request.body.action",
            connect_route_options=apigwv2.WebSocketRouteOptions(
                integration=WebSocketLambdaIntegration(
                    "ConnectIntegration",
                    self.websocket_handler
                )
            ),
            disconnect_route_options=apigwv2.WebSocketRouteOptions(
                integration=WebSocketLambdaIntegration(
                    "DisconnectIntegration", 
                    self.websocket_handler
                )
            ),
            default_route_options=apigwv2.WebSocketRouteOptions(
                integration=WebSocketLambdaIntegration(
                    "DefaultIntegration",
                    self.websocket_handler
                )
            )
        )
        
        # Add additional routes for conversation management
        self.websocket_api.add_route(
            "conversation-update",
            integration=WebSocketLambdaIntegration(
                "ConversationUpdateIntegration",
                self.websocket_handler
            )
        )
        
        # Create WebSocket stage
        self.websocket_stage = apigwv2.WebSocketStage(
            self, "ChatbotWebSocketStage",
            web_socket_api=self.websocket_api,
            stage_name="prod",
            auto_deploy=True
        )
        
        # CDK automatically grants API Gateway permission to invoke Lambda
        
        # Output WebSocket API endpoint
        CfnOutput(
            self, "WebSocketApiEndpoint",
            value=self.websocket_api.api_endpoint,
            description="WebSocket API endpoint URL"
        )
        
        CfnOutput(
            self, "WebSocketApiId",
            value=self.websocket_api.api_id,
            description="WebSocket API ID"
        )