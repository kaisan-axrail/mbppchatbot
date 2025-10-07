"""
Simplified Knowledge Base stack that creates the minimum viable setup.
"""

from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_apigateway as apigateway,
    CfnOutput,
    Duration,
    CfnResource
)
from constructs import Construct


class SimpleKnowledgeBaseStack(Stack):
    """Simplified Knowledge Base stack."""
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Create Knowledge Base using CloudFormation custom resource
        # This will be created manually first, then referenced here
        
        # For now, we'll create the Lambda and API without the KB
        # The KB ID will be set via environment variable after manual creation
        
        # IAM role for URL ingestion Lambda
        url_ingestion_role = iam.Role(
            self, "URLIngestionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
            inline_policies={
                "URLIngestionPermissions": iam.PolicyDocument(
                    statements=[
                        # Bedrock Agent access for knowledge base
                        iam.PolicyStatement(
                            actions=[
                                "bedrock:*",
                                "bedrock-agent:*"
                            ],
                            resources=["*"]
                        )
                    ]
                )
            }
        )
        
        # Lambda function for URL ingestion
        self.url_ingestion_handler = _lambda.Function(
            self, "URLIngestionHandler",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            role=url_ingestion_role,
            code=_lambda.Code.from_asset("../lambda/url_ingestion"),
            environment={
                "KNOWLEDGE_BASE_ID": "",  # Set manually after KB creation
                "DATA_SOURCE_ID": "",     # Will be created dynamically
                "BEDROCK_REGION": self.region,
                "LOG_LEVEL": "INFO"
            },
            timeout=Duration.minutes(5),
            memory_size=512,
            description="Process URLs for knowledge base ingestion"
        )
        
        # REST API for URL ingestion
        self.kb_rest_api = apigateway.RestApi(
            self, "KnowledgeBaseApi",
            rest_api_name="Knowledge Base API",
            description="API for knowledge base URL ingestion",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["Content-Type", "Authorization"]
            )
        )
        
        # Lambda integration
        url_integration = apigateway.LambdaIntegration(
            self.url_ingestion_handler,
            proxy=True
        )
        
        # URL ingestion endpoint: POST /ingest-url
        ingest_resource = self.kb_rest_api.root.add_resource("ingest-url")
        ingest_resource.add_method("POST", url_integration)
        
        # Outputs
        CfnOutput(
            self, "URLIngestionHandlerArn",
            value=self.url_ingestion_handler.function_arn,
            description="URL ingestion Lambda function ARN"
        )
        
        CfnOutput(
            self, "IngestUrlEndpoint",
            value=f"{self.kb_rest_api.url}ingest-url",
            description="URL ingestion endpoint"
        )
        
        CfnOutput(
            self, "SetupInstructions",
            value="1. Create Knowledge Base manually in AWS Console 2. Update Lambda env var KNOWLEDGE_BASE_ID",
            description="Manual setup steps required"
        )