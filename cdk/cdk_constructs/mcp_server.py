"""
MCP server construct for chatbot system.
"""

from aws_cdk import (
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_secretsmanager as secretsmanager,
    Duration,
    CfnOutput,
    BundlingOptions
)
from constructs import Construct


class McpServerConstruct(Construct):
    """Construct for creating MCP server with OpenAPI schema integration."""
    
    def __init__(self, scope: Construct, construct_id: str,
                 sessions_table, conversations_table, analytics_table, events_table,
                 processed_bucket=None, knowledge_base_id=None, shared_layer=None) -> None:
        super().__init__(scope, construct_id)
        
        self.shared_layer = shared_layer
        
        self.sessions_table = sessions_table
        self.conversations_table = conversations_table
        self.analytics_table = analytics_table
        self.events_table = events_table
        self.processed_bucket = processed_bucket
        self.knowledge_base_id = knowledge_base_id
        
        # Create secrets for sensitive configuration
        self.secrets = self._create_secrets()
        
        # Create MCP server Lambda function
        self.mcp_server = self._create_mcp_server()
        
        # Create outputs
        self._create_outputs()
    
    def _create_secrets(self) -> secretsmanager.Secret:
        """Create Secrets Manager secret for sensitive configuration."""
        return secretsmanager.Secret(
            self, "McpServerSecrets",
            secret_name="chatbot/mcp-server",
            description="Sensitive configuration for MCP server",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"placeholder": "value"}',
                generate_string_key="api_key",
                exclude_characters=' %+~`#$&*()|[]{}:;<>?!\'/@"\\',
                password_length=32
            )
        )
    
    def _create_mcp_server(self) -> _lambda.Function:
        """Create MCP server Lambda function with OpenAPI schema and AWS service access."""
        
        # Create IAM role for MCP server
        mcp_role = iam.Role(
            self, "McpServerRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
            inline_policies={
                "BedrockAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "bedrock:InvokeModel",
                                "bedrock:InvokeModelWithResponseStream",
                                "bedrock:Retrieve"
                            ],
                            resources=[
                                f"arn:aws:bedrock:*::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0",
                                f"arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v1",
                                f"arn:aws:bedrock:*::foundation-model/cohere.embed-english-v3",
                                f"arn:aws:bedrock:*::foundation-model/cohere.embed-multilingual-v3",
                                f"arn:aws:bedrock:ap-southeast-1:{self.node.try_get_context('account') or '*'}:knowledge-base/*"
                            ]
                        )
                    ]
                ),
                "DynamoDBAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "dynamodb:GetItem",
                                "dynamodb:PutItem",
                                "dynamodb:UpdateItem",
                                "dynamodb:DeleteItem",
                                "dynamodb:Query",
                                "dynamodb:Scan",
                                "dynamodb:BatchGetItem",
                                "dynamodb:BatchWriteItem"
                            ],
                            resources=[
                                self.events_table.table_arn
                            ]
                        )
                    ]
                ),
                "OpenSearchAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "aoss:APIAccessAll",
                                "aoss:DashboardsAccessAll"
                            ],
                            resources=["*"]
                        )
                    ]
                ),
                "SecretsManagerAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "secretsmanager:GetSecretValue"
                            ],
                            resources=[
                                self.secrets.secret_arn
                            ]
                        )
                    ]
                ),
                "S3Access": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "s3:GetObject",
                                "s3:ListBucket"
                            ],
                            resources=[
                                f"{self.processed_bucket.bucket_arn}/*" if self.processed_bucket else "*",
                                self.processed_bucket.bucket_arn if self.processed_bucket else "*"
                            ]
                        )
                    ]
                ),
                "CloudWatchMetrics": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "cloudwatch:PutMetricData"
                            ],
                            resources=["*"]
                        )
                    ]
                )
            }
        )
        
        # Create Lambda function with OpenAPI schema bundling
        return _lambda.Function(
            self, "McpServer",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler_working.lambda_handler",
            role=mcp_role,
            code=_lambda.Code.from_asset("../lambda/mcp_server"),
            layers=[self.shared_layer] if self.shared_layer else [],
            environment={
                "SCHEMA_PATH": "/var/task/mcp_tools_schema.yaml",
                "SESSIONS_TABLE": self.sessions_table.table_name,
                "CONVERSATIONS_TABLE": self.conversations_table.table_name,
                "ANALYTICS_TABLE": self.analytics_table.table_name,
                "EVENTS_TABLE": self.events_table.table_name,
                "PROCESSED_BUCKET": self.processed_bucket.bucket_name if self.processed_bucket else "",
                "SECRETS_ARN": self.secrets.secret_arn,
                "KNOWLEDGE_BASE_ID": self.knowledge_base_id if self.knowledge_base_id else "",
                # Bedrock configuration for embeddings and search
                "BEDROCK_REGION": "ap-southeast-1",  # Default region
                "BEDROCK_INFERENCE_PROFILE_ARN": "",  # Set for production if needed
                "BEDROCK_CROSS_REGION_PROFILE": "",  # Not typically needed for embeddings
                "EMBEDDING_MODEL": "amazon.titan-embed-text-v1",
                "LOG_LEVEL": "INFO"
            },
            timeout=Duration.minutes(5),
            memory_size=512,
            description="MCP server with RAG and CRUD tools using OpenAPI schema"
        )
    
    def _create_outputs(self) -> None:
        """Create CloudFormation outputs for the MCP server."""
        CfnOutput(
            self, "McpServerArn",
            value=self.mcp_server.function_arn,
            description="MCP server Lambda function ARN"
        )
        
        CfnOutput(
            self, "McpServerName",
            value=self.mcp_server.function_name,
            description="MCP server Lambda function name"
        )
        
        CfnOutput(
            self, "McpSecretsArn",
            value=self.secrets.secret_arn,
            description="MCP server secrets ARN"
        )