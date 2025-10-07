"""
REST API Gateway stack for document operations.
"""

from aws_cdk import (
    Stack,
    aws_apigateway as apigateway,
    aws_lambda as _lambda,
    CfnOutput
)
from constructs import Construct


class RestApiStack(Stack):
    """Stack containing REST API Gateway for document operations."""
    
    def __init__(self, scope: Construct, construct_id: str,
                 document_upload_handler: _lambda.Function,
                 file_delete_handler: _lambda.Function, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Create REST API with CORS
        self.rest_api = apigateway.RestApi(
            self, "ChatbotRestApi",
            rest_api_name="Chatbot Document API",
            description="REST API for document upload and management",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
                allow_headers=["Content-Type", "Authorization", "X-Requested-With"]
            )
        )
        
        # Lambda integration
        upload_integration = apigateway.LambdaIntegration(
            document_upload_handler,
            proxy=True,
            integration_responses=[
                apigateway.IntegrationResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": "'*'"
                    }
                )
            ]
        )
        
        # Upload endpoint: POST /upload
        upload_resource = self.rest_api.root.add_resource("upload")
        upload_resource.add_method(
            "POST", 
            upload_integration,
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True
                    }
                )
            ]
        )
        
        # Documents endpoint: GET /documents
        documents_resource = self.rest_api.root.add_resource("documents")
        documents_resource.add_method(
            "GET", 
            upload_integration,
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True
                    }
                )
            ]
        )
        
        # Delete integration
        delete_integration = apigateway.LambdaIntegration(
            file_delete_handler,
            proxy=True,
            integration_responses=[
                apigateway.IntegrationResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": "'*'"
                    }
                )
            ]
        )
        
        # Delete endpoint: DELETE /delete
        delete_resource = self.rest_api.root.add_resource("delete")
        delete_resource.add_method(
            "DELETE", 
            delete_integration,
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True
                    }
                )
            ]
        )
        
        # Outputs
        CfnOutput(
            self, "RestApiUrl",
            value=self.rest_api.url,
            description="REST API URL for document operations",
            export_name="ChatbotRestApiUrl"
        )
        
        CfnOutput(
            self, "RestApiId",
            value=self.rest_api.rest_api_id,
            description="REST API ID",
            export_name="ChatbotRestApiId"
        )
        
        CfnOutput(
            self, "DocumentsEndpoint",
            value=f"{self.rest_api.url}documents",
            description="Documents list endpoint",
            export_name="ChatbotDocumentsEndpoint"
        )
        
        CfnOutput(
            self, "UploadEndpoint",
            value=f"{self.rest_api.url}upload",
            description="Document upload endpoint",
            export_name="ChatbotUploadEndpoint"
        )
        
        CfnOutput(
            self, "DeleteEndpoint",
            value=f"{self.rest_api.url}delete",
            description="File delete endpoint",
            export_name="ChatbotDeleteEndpoint"
        )