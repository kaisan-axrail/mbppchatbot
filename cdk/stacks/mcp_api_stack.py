"""
MCP Tools API Stack - REST API Gateway for MCP tools.
"""

from aws_cdk import (
    Stack,
    aws_apigateway as apigw,
    aws_lambda as lambda_,
    aws_iam as iam,
    CustomResource,
    Duration,
    CfnOutput
)
from aws_cdk.custom_resources import Provider
from constructs import Construct


class McpApiStack(Stack):
    """Stack for MCP Tools REST API Gateway."""
    
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        mcp_api_handler: lambda_.IFunction,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Create REST API with SSE support for MCP
        api = apigw.RestApi(
            self,
            "McpToolsApi",
            rest_api_name="MCP Tools API",
            description="REST API for MCP chatbot tools with SSE transport",
            deploy_options=apigw.StageOptions(
                stage_name="prod",
                throttling_rate_limit=100,
                throttling_burst_limit=200
            )
        )
        
        # Create Lambda integration
        api_integration = apigw.LambdaIntegration(mcp_api_handler)
        
        # /mcp endpoint for unified MCP tool requests
        mcp_resource = api.root.add_resource("mcp")
        mcp_resource.add_method("POST", api_integration)  # Unified MCP endpoint
        
        # /mcp/sse endpoint for MCP protocol (SSE transport)
        sse_resource = mcp_resource.add_resource("sse")
        sse_resource.add_method("GET", api_integration)  # SSE connection
        sse_resource.add_method("POST", api_integration)  # MCP messages
        
        # /search_documents endpoint
        search_resource = api.root.add_resource("search_documents")
        search_resource.add_method("POST", api_integration)
        
        # /events resource for CRUD operations
        events_resource = api.root.add_resource("events")
        events_resource.add_method("POST", api_integration)
        events_resource.add_method("GET", api_integration)
        
        # /events/{eventId} for specific event operations
        event_id_resource = events_resource.add_resource("{eventId}")
        event_id_resource.add_method("GET", api_integration)
        event_id_resource.add_method("PUT", api_integration)
        event_id_resource.add_method("DELETE", api_integration)
        
        # Outputs
        CfnOutput(
            self,
            "McpApiEndpoint",
            value=api.url,
            description="MCP Tools API endpoint"
        )
        
        CfnOutput(
            self,
            "McpEndpoint",
            value=f"{api.url}mcp",
            description="Unified MCP endpoint for all tool requests",
            export_name="McpEndpoint"
        )
        
        CfnOutput(
            self,
            "McpSseEndpoint",
            value=f"{api.url}mcp/sse",
            description="MCP SSE endpoint for real MCP protocol"
        )
        
        CfnOutput(
            self,
            "SearchDocumentsEndpoint",
            value=f"{api.url}search_documents",
            description="Search documents endpoint"
        )
        
        CfnOutput(
            self,
            "EventsEndpoint",
            value=f"{api.url}events",
            description="Events CRUD endpoint"
        )
        
        # Lambda to update OpenAPI schema
        schema_updater = lambda_.Function(
            self,
            "SchemaUpdater",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../lambda/schema_updater"),
            timeout=Duration.seconds(30),
            environment={"API_ENDPOINT": api.url}
        )
        
        # Custom resource to trigger schema update
        provider = Provider(
            self,
            "SchemaUpdaterProvider",
            on_event_handler=schema_updater
        )
        
        CustomResource(
            self,
            "SchemaUpdate",
            service_token=provider.service_token,
            properties={"ApiEndpoint": api.url}
        )
        
        # Store for cross-stack reference
        self.api = api
        self.api_endpoint = api.url
