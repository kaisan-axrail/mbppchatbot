"""
Knowledge Base stack using GenAI CDK Constructs.
"""

from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_s3 as s3,
    aws_apigateway as apigateway,
    CfnOutput,
    Duration,
    RemovalPolicy
)
from constructs import Construct
from cdklabs.generative_ai_cdk_constructs import bedrock, opensearchserverless


class KnowledgeBaseStack(Stack):
    """Stack for knowledge base with URL ingestion capability using GenAI CDK Constructs."""
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # S3 bucket for knowledge base storage
        self.knowledge_base_bucket = s3.Bucket(
            self, "KnowledgeBaseBucket",
            bucket_name=f"chatbot-knowledge-base-{self.account}-{self.region}",
            versioned=False,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )
        
        # Create OpenSearch Serverless collection first
        vector_collection = opensearchserverless.VectorCollection(
            self, "ChatbotVectorCollection",
            collection_name="chatbot-kb-collection",
            description="Vector collection for chatbot knowledge base"
        )
        
        # Create Knowledge Base using GenAI CDK Constructs
        self.knowledge_base = bedrock.VectorKnowledgeBase(
            self, "ChatbotKnowledgeBase",
            embeddings_model=bedrock.BedrockFoundationModel.TITAN_EMBED_TEXT_V1,
            vector_store=vector_collection,
            instruction="Knowledge base for chatbot with URL ingestion capability"
        )
        
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
                        # S3 access for knowledge base
                        iam.PolicyStatement(
                            actions=[
                                "s3:PutObject",
                                "s3:GetObject",
                                "s3:ListBucket"
                            ],
                            resources=[
                                self.knowledge_base_bucket.bucket_arn,
                                f"{self.knowledge_base_bucket.bucket_arn}/*"
                            ]
                        ),
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
                "KNOWLEDGE_BASE_BUCKET": self.knowledge_base_bucket.bucket_name,
                "KNOWLEDGE_BASE_ID": self.knowledge_base.knowledge_base_id,
                "DATA_SOURCE_ID": "",  # Will be created dynamically per URL
                "BEDROCK_REGION": self.region,
                "EMBEDDING_MODEL": "amazon.titan-embed-text-v1",
                "CHUNK_SIZE": "1000",
                "CHUNK_OVERLAP": "200",
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
        
        # Knowledge base status endpoint: GET /status
        status_resource = self.kb_rest_api.root.add_resource("status")
        status_resource.add_method("GET", url_integration)
        
        # Outputs
        CfnOutput(
            self, "KnowledgeBaseBucketName",
            value=self.knowledge_base_bucket.bucket_name,
            description="Knowledge base S3 bucket name",
            export_name="ChatbotKnowledgeBaseBucket"
        )
        
        CfnOutput(
            self, "KnowledgeBaseId",
            value=self.knowledge_base.knowledge_base_id,
            description="Knowledge Base ID for URL ingestion",
            export_name="ChatbotKnowledgeBaseId"
        )
        
        CfnOutput(
            self, "KnowledgeBaseArn",
            value=self.knowledge_base.knowledge_base_arn,
            description="Knowledge Base ARN",
            export_name="ChatbotKnowledgeBaseArn"
        )
        
        CfnOutput(
            self, "URLIngestionHandlerArn",
            value=self.url_ingestion_handler.function_arn,
            description="URL ingestion Lambda function ARN",
            export_name="ChatbotURLIngestionHandlerArn"
        )
        
        CfnOutput(
            self, "KnowledgeBaseApiUrl",
            value=self.kb_rest_api.url,
            description="Knowledge base REST API URL",
            export_name="ChatbotKnowledgeBaseApiUrl"
        )
        
        CfnOutput(
            self, "IngestUrlEndpoint",
            value=f"{self.kb_rest_api.url}ingest-url",
            description="URL ingestion endpoint",
            export_name="ChatbotIngestUrlEndpoint"
        )