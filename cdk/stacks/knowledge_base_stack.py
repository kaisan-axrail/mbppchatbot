"""
Automated Knowledge Base stack with OpenSearch Serverless collection.
"""

from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_s3 as s3,
    aws_apigateway as apigateway,
    aws_opensearchserverless as opensearch,
    CfnOutput,
    Duration,
    RemovalPolicy
)
from constructs import Construct
from aws_cdk import aws_bedrock as bedrock


class KnowledgeBaseStack(Stack):
    """Stack for knowledge base with URL ingestion capability."""
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Create OpenSearch Serverless collection
        collection_name = "chatbot-kb-collection"
        
        # Security policy for the collection
        security_policy = opensearch.CfnSecurityPolicy(
            self, "KBSecurityPolicy",
            name="chatbot-kb-sec-policy",
            type="encryption",
            policy=f'''{{"Rules":[{{"ResourceType":"collection","Resource":["collection/{collection_name}"]}}],"AWSOwnedKey":true}}'''
        )
        
        # Network policy for the collection
        network_policy = opensearch.CfnSecurityPolicy(
            self, "KBNetworkPolicy",
            name="chatbot-kb-net-policy",
            type="network",
            policy=f'''[{{"Rules":[{{"ResourceType":"collection","Resource":["collection/{collection_name}"]}}],"AllowFromPublic":true}}]'''
        )
        
        # Create the OpenSearch Serverless collection
        self.collection = opensearch.CfnCollection(
            self, "KBCollection",
            name=collection_name,
            type="VECTORSEARCH",
            description="Knowledge Base collection for chatbot RAG"
        )
        
        # Add dependencies
        self.collection.add_dependency(security_policy)
        self.collection.add_dependency(network_policy)
        
        # IAM role for Knowledge Base (create before data access policy)
        self.kb_role = iam.Role(
            self, "KnowledgeBaseRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com")
        )
        
        # Data access policy for Bedrock
        data_access_policy = opensearch.CfnAccessPolicy(
            self, "KBDataAccessPolicy",
            name="chatbot-kb-data-policy",
            type="data",
            policy=f'''[{{"Rules":[{{"ResourceType":"collection","Resource":["collection/{collection_name}"],"Permission":["aoss:CreateCollectionItems","aoss:DeleteCollectionItems","aoss:UpdateCollectionItems","aoss:DescribeCollectionItems"]}},{{"ResourceType":"index","Resource":["index/{collection_name}/*"],"Permission":["aoss:CreateIndex","aoss:DeleteIndex","aoss:UpdateIndex","aoss:DescribeIndex","aoss:ReadDocument","aoss:WriteDocument"]}}],"Principal":["{self.kb_role.role_arn}"]}}]'''
        )
        
        # Add policies to KB role
        self.kb_role.add_to_policy(
            iam.PolicyStatement(
                actions=["aoss:APIAccessAll"],
                resources=[self.collection.attr_arn]
            )
        )
        self.kb_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    f"arn:aws:bedrock:{self.region}::foundation-model/cohere.embed-english-v3"
                ]
            )
        )
        
        # Create Knowledge Base with OpenSearch Serverless
        self.knowledge_base = bedrock.CfnKnowledgeBase(
            self, "ChatbotKnowledgeBase",
            name="chatbot-knowledge-base",
            role_arn=self.kb_role.role_arn,
            knowledge_base_configuration=bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
                type="VECTOR",
                vector_knowledge_base_configuration=bedrock.CfnKnowledgeBase.VectorKnowledgeBaseConfigurationProperty(
                    embedding_model_arn=f"arn:aws:bedrock:{self.region}::foundation-model/cohere.embed-english-v3"
                )
            ),
            storage_configuration=bedrock.CfnKnowledgeBase.StorageConfigurationProperty(
                type="OPENSEARCH_SERVERLESS",
                opensearch_serverless_configuration=bedrock.CfnKnowledgeBase.OpenSearchServerlessConfigurationProperty(
                    collection_arn=self.collection.attr_arn,
                    vector_index_name="bedrock-knowledge-base-default-index",
                    field_mapping=bedrock.CfnKnowledgeBase.OpenSearchServerlessFieldMappingProperty(
                        vector_field="bedrock-knowledge-base-default-vector",
                        text_field="AMAZON_BEDROCK_TEXT_CHUNK",
                        metadata_field="AMAZON_BEDROCK_METADATA"
                    )
                )
            )
        )
        
        # Add dependencies
        self.knowledge_base.add_dependency(data_access_policy)
        
        # IAM role for URL ingestion Lambda
        url_ingestion_role = iam.Role(
            self, "URLIngestionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
            inline_policies={
                "URLIngestionPermissions": iam.PolicyDocument(
                    statements=[

                        iam.PolicyStatement(
                            actions=["bedrock:*", "bedrock-agent:*"],
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
                "KNOWLEDGE_BASE_ID": self.knowledge_base.attr_knowledge_base_id,
                "BEDROCK_REGION": self.region,
                "LOG_LEVEL": "INFO"
            },
            timeout=Duration.minutes(5),
            memory_size=512
        )
        
        # REST API for URL ingestion
        self.kb_rest_api = apigateway.RestApi(
            self, "KnowledgeBaseApi",
            rest_api_name="Knowledge Base API",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["Content-Type", "Authorization"]
            )
        )
        
        # Lambda integration
        url_integration = apigateway.LambdaIntegration(self.url_ingestion_handler, proxy=True)
        
        # URL ingestion endpoint
        ingest_resource = self.kb_rest_api.root.add_resource("ingest-url")
        ingest_resource.add_method("POST", url_integration)
        
        # Status endpoint
        status_resource = self.kb_rest_api.root.add_resource("status")
        status_resource.add_method("GET", url_integration)
        
        # Outputs
        CfnOutput(
            self, "KnowledgeBaseId",
            value=self.knowledge_base.attr_knowledge_base_id,
            description="Knowledge Base ID for RAG system",
            export_name="ChatbotKnowledgeBaseId"
        )
        
        CfnOutput(
            self, "CollectionEndpoint",
            value=self.collection.attr_collection_endpoint,
            description="OpenSearch Serverless collection endpoint"
        )
        
        CfnOutput(
            self, "IngestUrlEndpoint",
            value=f"{self.kb_rest_api.url}ingest-url",
            description="URL ingestion endpoint"
        )
        
        CfnOutput(
            self, "SetupComplete",
            value="Knowledge Base with OpenSearch Serverless collection created automatically",
            description="Automated setup completed successfully"
        )