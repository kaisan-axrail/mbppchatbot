"""
Lambda functions stack for chatbot system.
"""

from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_events as events,
    aws_events_targets as targets,
    aws_secretsmanager as secretsmanager,
    aws_s3 as s3,
    Duration,
    BundlingOptions,
    RemovalPolicy
)
from constructs import Construct
from cdk_constructs.mcp_server import McpServerConstruct


class LambdaStack(Stack):
    """Stack containing all Lambda functions for the chatbot system."""
    
    def __init__(self, scope: Construct, construct_id: str,
                 sessions_table, conversations_table, analytics_table, events_table,
                 reports_table=None, workflow_events_table=None, images_bucket=None,
                 processed_bucket=None, knowledge_base_id=None, shared_layer=None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.sessions_table = sessions_table
        self.conversations_table = conversations_table
        self.analytics_table = analytics_table
        self.events_table = events_table
        self.reports_table = reports_table
        self.workflow_events_table = workflow_events_table
        self.images_bucket = images_bucket
        self.processed_bucket = processed_bucket
        
        # Create S3 bucket for session persistence
        self.session_bucket = s3.Bucket(
            self, "SessionBucket",
            bucket_name=f"mbpp-chatbot-sessions-{self.account}",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="DeleteOldSessions",
                    expiration=Duration.days(7),
                    enabled=True
                )
            ]
        )
        
        # Create Secrets Manager secret
        self.api_secrets = secretsmanager.Secret(
            self, "ApiSecrets",
            secret_name="chatbot-api-keys",
            description="API keys for chatbot"
        )
        
        # Create IAM role for WebSocket handler
        websocket_role = iam.Role(
            self, "WebSocketHandlerRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
            inline_policies={
                "DynamoDBAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "dynamodb:GetItem",
                                "dynamodb:PutItem", 
                                "dynamodb:UpdateItem",
                                "dynamodb:DeleteItem",
                                "dynamodb:Query"
                            ],
                            resources=[
                                self.sessions_table.table_arn,
                                self.conversations_table.table_arn,
                                f"arn:aws:dynamodb:{self.region}:{self.account}:table/mbpp-conversation-history",
                                self.analytics_table.table_arn,
                                f"{self.sessions_table.table_arn}/index/*",
                                f"{self.conversations_table.table_arn}/index/*",
                                f"{self.analytics_table.table_arn}/index/*",
                                f"arn:aws:dynamodb:{self.region}:{self.account}:table/mbpp-websocket-connections"
                            ] + (
                                [self.reports_table.table_arn, self.workflow_events_table.table_arn] 
                                if self.reports_table and self.workflow_events_table else []
                            )
                        )
                    ]
                ),
                "ApiGatewayManagement": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "execute-api:ManageConnections"
                            ],
                            resources=["*"]
                        )
                    ]
                ),
                "BedrockAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "bedrock:InvokeModel",
                                "bedrock:InvokeModelWithResponseStream",
                                "bedrock:GetFoundationModel",
                                "bedrock:ListFoundationModels",
                                "bedrock:Retrieve",
                                "bedrock:RetrieveAndGenerate"
                            ],
                            resources=[
                                f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-5-sonnet-20240620-v1:0",
                                f"arn:aws:bedrock:{self.region}::foundation-model/amazon.titan-embed-text-v1",
                                # Add Nova Pro inference profile access
                                f"arn:aws:bedrock:*:*:foundation-model/*",
                                f"arn:aws:bedrock:*:*:inference-profile/*",
                                f"arn:aws:bedrock:{self.region}:{self.account}:inference-profile/*",
                                # Add Knowledge Base access
                                f"arn:aws:bedrock:{self.region}:{self.account}:knowledge-base/*"
                            ]
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
                                self.api_secrets.secret_arn,
                                # Add Strand API key secret access
                                f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:chatbot/strand-api-key*"
                            ]
                        )
                    ]
                ),
                "LambdaInvoke": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["lambda:InvokeFunction"],
                            resources=[f"arn:aws:lambda:{self.region}:{self.account}:function:*"]
                        )
                    ]
                ),
                "S3Access": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
                            resources=[
                                f"{self.session_bucket.bucket_arn}/*"
                            ] + (
                                [f"{self.images_bucket.bucket_arn}/*"] if self.images_bucket else []
                            ) + (
                                [f"{self.processed_bucket.bucket_arn}/*"] if self.processed_bucket else []
                            )
                        ),
                        iam.PolicyStatement(
                            actions=["s3:ListBucket"],
                            resources=[self.session_bucket.bucket_arn] + (
                                [self.images_bucket.bucket_arn] if self.images_bucket else []
                            ) + (
                                [self.processed_bucket.bucket_arn] if self.processed_bucket else []
                            )
                        )
                    ]
                ),
                "ComprehendAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["comprehend:DetectSentiment"],
                            resources=["*"]
                        )
                    ]
                )
            }
        )
        
        # Create MBPP Workflow Layer
        mbpp_workflow_layer = _lambda.LayerVersion(
            self, "MBPPWorkflowLayer",
            code=_lambda.Code.from_asset("../lambda/mbpp_layer"),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_11],
            description="MBPP Workflow Agent with Strands"
        )
        
        # Create WebSocket Layer with shared module and dependencies
        # Layer includes: boto3, pydantic, pydantic-core, shared module
        websocket_layer = _lambda.LayerVersion(
            self, "WebSocketLayer",
            code=_lambda.Code.from_asset(
                "../lambda/websocket_layer",
                bundling=BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_11.bundling_image,
                    command=[
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output/python && "
                        "cp -r python/shared /asset-output/python/"
                    ]
                )
            ),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_11],
            description="WebSocket: boto3, pydantic, shared module"
        )
        
        # Create WebSocket handler Lambda function
        self.websocket_handler = _lambda.Function(
            self, "WebSocketHandler",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler_working.lambda_handler",
            role=websocket_role,
            code=_lambda.Code.from_asset("../lambda/websocket_handler"),
            layers=[websocket_layer, mbpp_workflow_layer],
            environment={
                "SESSIONS_TABLE": self.sessions_table.table_name,
                "CONVERSATIONS_TABLE": self.conversations_table.table_name,
                "CONVERSATION_HISTORY_TABLE": "mbpp-conversation-history",
                "ANALYTICS_TABLE": self.analytics_table.table_name,
                "REPORTS_TABLE": self.reports_table.table_name if self.reports_table else "mbpp-reports",
                "EVENTS_TABLE": self.workflow_events_table.table_name if self.workflow_events_table else "mbpp-events",
                "IMAGES_BUCKET": self.images_bucket.bucket_name if self.images_bucket else f"mbpp-incident-images-{self.account}",
                "SESSION_BUCKET": self.session_bucket.bucket_name,
                "SECRETS_ARN": self.api_secrets.secret_arn,
                "MCP_SERVER_ARN": "",  # Will be updated after MCP server is created
                "BEDROCK_REGION": self.region,
                # Knowledge Base configuration
                "KNOWLEDGE_BASE_ID": knowledge_base_id if knowledge_base_id else "",
                "PROCESSED_BUCKET": self.processed_bucket.bucket_name if self.processed_bucket else "",
                # Inference profile configuration (preferred)
                "BEDROCK_INFERENCE_PROFILE_ARN": "",  # Set this for production deployment
                "BEDROCK_CROSS_REGION_PROFILE": "apac.amazon.nova-pro-v1:0",
                # Fallback model configuration
                "BEDROCK_CLAUDE_MODEL": "anthropic.claude-3-5-sonnet-20240620-v1:0",
                "USE_CROSS_REGION_INFERENCE": "true",
                "BEDROCK_EMBEDDING_MODEL": "amazon.titan-embed-text-v1",
                # Circuit breaker configuration
                "BEDROCK_CIRCUIT_BREAKER_THRESHOLD": "5",
                "BEDROCK_CIRCUIT_BREAKER_TIMEOUT": "30",
                "MCP_SSE_ENDPOINT": "https://4fsaarjly6.execute-api.ap-southeast-1.amazonaws.com/prod/mcp/sse",
                "LOG_LEVEL": "INFO"
            },
            timeout=Duration.seconds(30),
            memory_size=256,
            description="WebSocket handler for chatbot connections and messages"
        )
        
        # Create IAM role for session cleanup handler
        cleanup_role = iam.Role(
            self, "SessionCleanupRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
            inline_policies={
                "DynamoDBAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "dynamodb:Scan",
                                "dynamodb:DeleteItem",
                                "dynamodb:BatchWriteItem"
                            ],
                            resources=[
                                self.sessions_table.table_arn
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
        
        # Create session cleanup Lambda function
        self.session_cleanup = _lambda.Function(
            self, "SessionCleanup",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            role=cleanup_role,
            code=_lambda.Code.from_asset("../lambda/session_cleanup"),
            environment={
                "SESSIONS_TABLE": self.sessions_table.table_name,
                "SESSION_TIMEOUT_MINUTES": "30",
                "DRY_RUN": "false"
            },
            timeout=Duration.minutes(5),
            memory_size=128,
            description="Automated cleanup of inactive and expired sessions"
        )
        
        # Create CRUD Lambda for events table
        crud_role = iam.Role(
            self, "CrudHandlerRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
            inline_policies={
                "DynamoDBAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:Scan"],
                            resources=[self.events_table.table_arn]
                        )
                    ]
                )
            }
        )
        
        self.crud_handler = _lambda.Function(
            self, "CrudHandler",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            role=crud_role,
            code=_lambda.Code.from_asset("../lambda/crud_handler"),
            environment={"EVENTS_TABLE": self.events_table.table_name, "LOG_LEVEL": "INFO"},
            timeout=Duration.seconds(30),
            memory_size=256
        )
        
        # Create MCP server using construct
        self.mcp_server_construct = McpServerConstruct(
            self, "McpServerConstruct",
            sessions_table=self.sessions_table,
            conversations_table=self.conversations_table,
            analytics_table=self.analytics_table,
            events_table=self.events_table,
            processed_bucket=self.processed_bucket,
            knowledge_base_id=knowledge_base_id,
            shared_layer=shared_layer
        )
        self.mcp_server = self.mcp_server_construct.mcp_server
        
        # Add CRUD Lambda ARN to MCP server environment
        self.mcp_server.add_environment("CRUD_LAMBDA_ARN", self.crud_handler.function_arn)
        
        # Grant MCP server permission to invoke CRUD Lambda
        self.crud_handler.grant_invoke(self.mcp_server)
        
        # Create EventBridge rule to run cleanup every hour
        cleanup_rule = events.Rule(
            self, "SessionCleanupSchedule",
            description="Trigger session cleanup Lambda function every hour",
            schedule=events.Schedule.rate(Duration.hours(1))
        )
        
        # Add the Lambda function as a target
        cleanup_rule.add_target(
            targets.LambdaFunction(
                self.session_cleanup,
                retry_attempts=2
            )
        )
        
        # Update WebSocket handler environment with MCP server ARN
        self.websocket_handler.add_environment(
            "MCP_SERVER_ARN", 
            self.mcp_server.function_arn
        )
        
        # MCP API Handler Lambda
        self.mcp_api_handler = _lambda.Function(
            self,
            "McpApiHandler",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("../lambda/mcp_api_handler"),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "MCP_SERVER_ARN": self.mcp_server.function_arn,
                "CRUD_HANDLER_ARN": self.crud_handler.function_arn
            }
        )
        
        # Grant invoke permissions
        self.mcp_server.grant_invoke(self.mcp_api_handler)
        self.crud_handler.grant_invoke(self.mcp_api_handler)