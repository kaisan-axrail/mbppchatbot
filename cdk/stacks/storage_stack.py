"""
S3 storage stack for RAG document storage and processing.
"""

from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_s3_notifications as s3n,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_events as events,
    aws_events_targets as targets,
    CfnOutput,
    RemovalPolicy,
    Duration,
    BundlingOptions
)
from constructs import Construct


class StorageStack(Stack):
    """Stack containing S3 buckets and document processing infrastructure for RAG."""
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # S3 bucket for storing RAG documents
        self.documents_bucket = s3.Bucket(
            self, "DocumentsBucket",
            bucket_name=f"chatbot-documents-{self.account}-{self.region}",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="DeleteOldVersions",
                    enabled=True,
                    noncurrent_version_expiration=Duration.days(30)
                )
            ],
            cors=[
                s3.CorsRule(
                    allowed_methods=[
                        s3.HttpMethods.GET,
                        s3.HttpMethods.POST,
                        s3.HttpMethods.PUT,
                        s3.HttpMethods.DELETE
                    ],
                    allowed_origins=["*"],
                    allowed_headers=["*"],
                    max_age=3000
                )
            ]
        )
        
        # S3 bucket for processed document chunks and embeddings
        self.processed_documents_bucket = s3.Bucket(
            self, "ProcessedDocumentsBucket", 
            bucket_name=f"chatbot-processed-docs-{self.account}-{self.region}",
            versioned=False,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="TransitionToIA",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(30)
                        ),
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(90)
                        )
                    ]
                )
            ]
        )
        
        # IAM role for document processor Lambda
        document_processor_role = iam.Role(
            self, "DocumentProcessorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
            inline_policies={
                "DocumentProcessorPermissions": iam.PolicyDocument(
                    statements=[
                        # S3 access for reading and writing documents
                        iam.PolicyStatement(
                            actions=[
                                "s3:GetObject",
                                "s3:PutObject",
                                "s3:DeleteObject",
                                "s3:ListBucket"
                            ],
                            resources=[
                                self.documents_bucket.bucket_arn,
                                f"{self.documents_bucket.bucket_arn}/*",
                                self.processed_documents_bucket.bucket_arn,
                                f"{self.processed_documents_bucket.bucket_arn}/*"
                            ]
                        ),
                        # Bedrock access for embeddings
                        iam.PolicyStatement(
                            actions=[
                                "bedrock:InvokeModel",
                                "bedrock:InvokeModelWithResponseStream"
                            ],
                            resources=[
                                f"arn:aws:bedrock:*::foundation-model/cohere.embed-english-v3",
                                f"arn:aws:bedrock:*::foundation-model/cohere.embed-multilingual-v3",
                                f"arn:aws:bedrock:*::foundation-model/cohere.embed-v4:0",
                                f"arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v1",
                                f"arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v2:0"
                            ]
                        ),
                        # CloudWatch metrics
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
        
        # Lambda function for document processing
        self.document_processor = _lambda.Function(
            self, "DocumentProcessor",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            role=document_processor_role,
            code=_lambda.Code.from_asset("../lambda/document_processor"),
            environment={
                "DOCUMENTS_BUCKET": self.documents_bucket.bucket_name,
                "PROCESSED_BUCKET": self.processed_documents_bucket.bucket_name,
                "BEDROCK_REGION": self.region,
                # Bedrock embedding configuration
                "EMBEDDING_MODEL": "amazon.titan-embed-text-v1",
                "BEDROCK_INFERENCE_PROFILE_ARN": "",  # Set for production if needed
                "BEDROCK_CROSS_REGION_PROFILE": "",  # Not typically needed for embeddings
                # Document processing configuration
                "CHUNK_SIZE": "1000",
                "CHUNK_OVERLAP": "200",
                "LOG_LEVEL": "INFO"
            },
            timeout=Duration.minutes(15),
            memory_size=1024,
            description="Process uploaded documents for RAG search"
        )
        
        # S3 event notification to trigger document processing
        self.documents_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(self.document_processor),
            s3.NotificationKeyFilter(
                prefix="uploads/",
                suffix=".pdf"
            )
        )
        
        self.documents_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(self.document_processor),
            s3.NotificationKeyFilter(
                prefix="uploads/",
                suffix=".txt"
            )
        )
        
        self.documents_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(self.document_processor),
            s3.NotificationKeyFilter(
                prefix="uploads/",
                suffix=".docx"
            )
        )
        
        self.documents_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(self.document_processor),
            s3.NotificationKeyFilter(
                prefix="uploads/",
                suffix=".csv"
            )
        )
        
        # IAM role for document upload Lambda
        document_upload_role = iam.Role(
            self, "DocumentUploadRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
            inline_policies={
                "DocumentUploadPermissions": iam.PolicyDocument(
                    statements=[
                        # S3 upload permissions
                        iam.PolicyStatement(
                            actions=[
                                "s3:PutObject",
                                "s3:PutObjectAcl",
                                "s3:GetObject",
                                "s3:ListBucket"
                            ],
                            resources=[
                                self.documents_bucket.bucket_arn,
                                f"{self.documents_bucket.bucket_arn}/*"
                            ]
                        )
                    ]
                )
            }
        )
        
        # Lambda function for handling document uploads
        self.document_upload_handler = _lambda.Function(
            self, "DocumentUploadHandler",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            role=document_upload_role,
            code=_lambda.Code.from_asset("../lambda/document_upload"),
            environment={
                "DOCUMENTS_BUCKET": self.documents_bucket.bucket_name,
                "UPLOAD_PREFIX": "uploads/",
                "MAX_FILE_SIZE": "50000000",  # 50MB
                "ALLOWED_EXTENSIONS": "pdf,txt,docx,md,csv",
                "PRESIGNED_URL_EXPIRY": "3600",  # 1 hour
                "LOG_LEVEL": "INFO"
            },
            timeout=Duration.seconds(30),
            memory_size=256,
            description="Handle document upload requests and generate presigned URLs"
        )
        
        # IAM role for file delete Lambda
        file_delete_role = iam.Role(
            self, "FileDeleteRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
            inline_policies={
                "FileDeletePermissions": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["s3:DeleteObject", "s3:ListBucket"],
                            resources=[
                                self.documents_bucket.bucket_arn,
                                f"{self.documents_bucket.bucket_arn}/*",
                                self.processed_documents_bucket.bucket_arn,
                                f"{self.processed_documents_bucket.bucket_arn}/*"
                            ]
                        )
                    ]
                )
            }
        )
        
        # Lambda function for deleting files
        self.file_delete_handler = _lambda.Function(
            self, "FileDeleteHandler",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            role=file_delete_role,
            code=_lambda.Code.from_asset("../lambda/file_delete"),
            environment={
                "DOCUMENTS_BUCKET": self.documents_bucket.bucket_name,
                "PROCESSED_BUCKET": self.processed_documents_bucket.bucket_name,
                "LOG_LEVEL": "INFO"
            },
            timeout=Duration.seconds(30),
            memory_size=256,
            description="Delete files from S3 storage"
        )
        
        # EventBridge rule for document processing status updates
        document_processing_rule = events.Rule(
            self, "DocumentProcessingRule",
            description="Handle document processing status updates",
            event_pattern=events.EventPattern(
                source=["chatbot.document.processor"],
                detail_type=["Document Processing Status"]
            )
        )
        
        # CloudWatch dashboard for monitoring document processing
        # Note: CloudWatch dashboard creation would go here in a production setup
        
        # Stack outputs
        CfnOutput(
            self, "DocumentsBucketName",
            value=self.documents_bucket.bucket_name,
            description="S3 bucket name for RAG documents",
            export_name="ChatbotDocumentsBucket"
        )
        
        CfnOutput(
            self, "DocumentsBucketArn",
            value=self.documents_bucket.bucket_arn,
            description="S3 bucket ARN for RAG documents",
            export_name="ChatbotDocumentsBucketArn"
        )
        
        CfnOutput(
            self, "ProcessedDocumentsBucketName",
            value=self.processed_documents_bucket.bucket_name,
            description="S3 bucket name for processed document chunks",
            export_name="ChatbotProcessedDocumentsBucket"
        )
        
        CfnOutput(
            self, "DocumentProcessorArn",
            value=self.document_processor.function_arn,
            description="Document processor Lambda function ARN",
            export_name="ChatbotDocumentProcessorArn"
        )
        
        CfnOutput(
            self, "DocumentUploadHandlerArn",
            value=self.document_upload_handler.function_arn,
            description="Document upload handler Lambda function ARN",
            export_name="ChatbotDocumentUploadHandlerArn"
        )
        
        CfnOutput(
            self, "DocumentUploadUrl",
            value=f"https://{self.documents_bucket.bucket_name}.s3.{self.region}.amazonaws.com/uploads/",
            description="Base URL for document uploads",
            export_name="ChatbotDocumentUploadUrl"
        )
        
        CfnOutput(
            self, "FileDeleteHandlerArn",
            value=self.file_delete_handler.function_arn,
            description="File delete handler Lambda function ARN",
            export_name="ChatbotFileDeleteHandlerArn"
        )