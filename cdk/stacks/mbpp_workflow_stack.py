"""
CDK Stack for MBPP Workflow Agent with DynamoDB
"""

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_lambda as lambda_,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as integrations,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_logs as logs,
    CfnOutput
)
from constructs import Construct
import os

class MBPPWorkflowStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # S3 Bucket for images
        from aws_cdk import aws_s3 as s3
        
        images_bucket = s3.Bucket(
            self, "IncidentImagesBucket",
            bucket_name=f"mbpp-incident-images-{self.account}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=Duration.days(90),
                    abort_incomplete_multipart_upload_after=Duration.days(7)
                )
            ]
        )
        
        # DynamoDB Tables
        reports_table = dynamodb.Table(
            self, "ReportsTable",
            partition_key=dynamodb.Attribute(name="ticket_number", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute="ttl"
        )
        
        events_table = dynamodb.Table(
            self, "EventsTable",
            partition_key=dynamodb.Attribute(name="event_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute="ttl"
        )
        
        events_table.add_global_secondary_index(
            index_name="ticket-index",
            partition_key=dynamodb.Attribute(name="ticket_number", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="timestamp", type=dynamodb.AttributeType.STRING)
        )
        
        # Lambda Layer
        strands_layer = lambda_.LayerVersion(
            self, "StrandsAgentsLayer",
            code=lambda_.Code.from_asset("../lambda/mcp_server"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_13],
            description="Strands Agents SDK"
        )
        
        # Lambda Function
        workflow_agent_lambda = lambda_.Function(
            self, "MBPPWorkflowAgent",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="mbpp_agent.lambda_handler",
            code=lambda_.Code.from_asset("../lambda/mcp_server"),
            layers=[strands_layer],
            timeout=Duration.seconds(300),
            memory_size=1024,
            environment={
                "BEDROCK_REGION": os.environ.get("AWS_REGION", "us-east-1"),
                "OPENSEARCH_INDEX": "mbpp-documents",
                "REPORTS_TABLE": reports_table.table_name,
                "EVENTS_TABLE": events_table.table_name,
                "IMAGES_BUCKET": images_bucket.bucket_name,
                "LOG_LEVEL": "INFO"
            },
            log_retention=logs.RetentionDays.ONE_WEEK
        )
        
        # Grant permissions
        workflow_agent_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=["*"]
            )
        )
        
        reports_table.grant_read_write_data(workflow_agent_lambda)
        events_table.grant_read_write_data(workflow_agent_lambda)
        images_bucket.grant_read_write(workflow_agent_lambda)
        
        workflow_agent_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["es:ESHttpGet", "es:ESHttpPost"],
                resources=["*"]
            )
        )
        
        # HTTP API
        http_api = apigwv2.HttpApi(
            self, "MBPPWorkflowApi",
            api_name="mbpp-workflow-api",
            description="MBPP Workflow Agent API",
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_origins=["*"],
                allow_methods=[apigwv2.CorsHttpMethod.POST, apigwv2.CorsHttpMethod.GET],
                allow_headers=["*"]
            )
        )
        
        lambda_integration = integrations.HttpLambdaIntegration(
            "WorkflowAgentIntegration",
            workflow_agent_lambda
        )
        
        http_api.add_routes(
            path="/process",
            methods=[apigwv2.HttpMethod.POST],
            integration=lambda_integration
        )
        
        http_api.add_routes(
            path="/workflow/status",
            methods=[apigwv2.HttpMethod.GET],
            integration=lambda_integration
        )
        
        # Export tables and bucket for use by other stacks
        self.reports_table = reports_table
        self.events_table = events_table
        self.images_bucket = images_bucket
        
        # Outputs
        CfnOutput(self, "WorkflowApiEndpoint", value=http_api.url or "", description="MBPP Workflow API Endpoint")
        CfnOutput(self, "WorkflowAgentLambdaArn", value=workflow_agent_lambda.function_arn, description="Lambda ARN")
        CfnOutput(self, "ReportsTableName", value=reports_table.table_name, description="Reports Table")
        CfnOutput(self, "EventsTableName", value=events_table.table_name, description="Events Table")
        CfnOutput(self, "ImagesBucketName", value=images_bucket.bucket_name, description="Images Bucket")
