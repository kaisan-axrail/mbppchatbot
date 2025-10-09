#!/usr/bin/env python3
"""
CDK app with proper Strands Agents and MCP integration.
"""

import os
import sys

# Add the CDK directory to the Python path
cdk_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cdk_dir)

import aws_cdk as cdk
from stacks.database_stack import DatabaseStack
from stacks.lambda_stack import LambdaStack
from stacks.api_stack import ApiStack
from stacks.rest_api_stack import RestApiStack
from stacks.mcp_api_stack import McpApiStack
from stacks.shared_layer_stack import SharedLayerStack
from stacks.chatbot_stack import ChatbotStack
from stacks.mbpp_workflow_stack import MBPPWorkflowStack
from stacks.pipeline_stack import PipelineStack
from stacks.webchat_stack import WebChatStack

app = cdk.App()

# Uncomment to enable CI/CD pipeline
PipelineStack(app, "PipelineStack",
    codestar_connection_arn="arn:aws:codestar-connections:ap-southeast-1:836581769622:connection/534fd2dc-e758-4dcd-959d-32af796a20c6",
    github_repo="kaisan-axrail/mbppchatbot",
    github_branch="main"
)

# Old Chatbot stacks commented out - now managed by PipelineStack
# The PipelineStack will create MBPP-* stacks automatically

# # Create shared layer first
# shared_layer_stack = SharedLayerStack(app, "ChatbotSharedLayerStack")

# # Create stacks with proper dependencies
# database_stack = DatabaseStack(app, "ChatbotDatabaseStack")

# # Enable storage stack for full RAG functionality
# from stacks.storage_stack import StorageStack
# storage_stack = StorageStack(app, "ChatbotStorageStack")

# lambda_stack = LambdaStack(app, "ChatbotLambdaStack", 
#                           sessions_table=database_stack.sessions_table,
#                           conversations_table=database_stack.conversations_table,
#                           analytics_table=database_stack.analytics_table,
#                           events_table=database_stack.events_table,
#                           processed_bucket=storage_stack.processed_documents_bucket,
#                           knowledge_base_id="",
#                           shared_layer=shared_layer_stack.shared_layer)

# api_stack = ApiStack(app, "ChatbotApiStack",
#                     websocket_handler=lambda_stack.websocket_handler)

# # Create REST API stack for document operations
# rest_api_stack = RestApiStack(app, "ChatbotRestApiStack",
#                              document_upload_handler=storage_stack.document_upload_handler,
#                              file_delete_handler=storage_stack.file_delete_handler)

# # Create MCP API stack for MCP tools
# mcp_api_stack = McpApiStack(app, "ChatbotMcpApiStack",
#                            mcp_api_handler=lambda_stack.mcp_api_handler)

# # Create main stack to hold outputs
# chatbot_stack = ChatbotStack(app, "ChatbotMainStack",
#                            database_stack=database_stack,
#                            lambda_stack=lambda_stack,
#                            api_stack=api_stack,
#                            storage_stack=storage_stack,
#                            rest_api_stack=rest_api_stack)

# # Add MCP SSE endpoint as output (manual configuration needed)
# cdk.CfnOutput(
#     mcp_api_stack, "McpSseEndpointForWebSocket",
#     value=f"{mcp_api_stack.api_endpoint}mcp/sse",
#     description="Set this as MCP_SSE_ENDPOINT in WebSocket handler",
#     export_name="McpSseEndpoint"
# )

# # Create MBPP Workflow Stack (creates reports and events tables)
# mbpp_workflow_stack = MBPPWorkflowStack(app, "MBPPWorkflowStack")

# # Grant WebSocket handler access to MBPP tables
# if hasattr(lambda_stack, 'websocket_handler'):
#     lambda_stack.websocket_handler.add_to_role_policy(
#         cdk.aws_iam.PolicyStatement(
#             actions=["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query", "dynamodb:Scan"],
#             resources=[
#                 f"arn:aws:dynamodb:{app.region}:{app.account}:table/mbpp-reports",
#                 f"arn:aws:dynamodb:{app.region}:{app.account}:table/mbpp-events",
#                 f"arn:aws:dynamodb:{app.region}:{app.account}:table/mbpp-events/index/*"
#             ]
#         )
#     )

# # Deploy Web Chat Frontend (S3 + CloudFront)
# # Uncomment to deploy web chat
# webchat_stack = WebChatStack(app, "MBPPWebChatStack")

# Deploy Web Chat separately (not in pipeline)
WebChatStack(app, "MBPPWebChatStack")

app.synth()