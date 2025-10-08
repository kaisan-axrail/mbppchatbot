"""
Simple CDK Pipeline for automated deployment
"""

from aws_cdk import (
    Stack,
    Stage,
    aws_codebuild as codebuild,
    aws_iam,
    CfnOutput
)
from constructs import Construct
import aws_cdk.pipelines as pipelines
from .database_stack import DatabaseStack
from .storage_stack import StorageStack
from .lambda_stack import LambdaStack
from .api_stack import ApiStack
from .mbpp_workflow_stack import MBPPWorkflowStack


class PipelineStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, 
                 codestar_connection_arn: str,
                 github_repo: str, 
                 github_branch: str = "main", 
                 **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        pipeline = pipelines.CodePipeline(
            self, "Pipeline",
            pipeline_name="mbpp-chatbot-pipeline",
            synth=pipelines.ShellStep(
                "Synth",
                input=pipelines.CodePipelineSource.connection(
                    repo_string=github_repo,
                    branch=github_branch,
                    connection_arn=codestar_connection_arn
                ),
                commands=[
                    "cd cdk",
                    "pip install -r requirements.txt",
                    "npx cdk synth"
                ],
                primary_output_directory="cdk/cdk.out"
            ),
            self_mutation=True
        )
        
        deploy_stage = pipeline.add_stage(ApplicationStage(self, "MBPP"))
        
        # Post-deployment step temporarily disabled - Lambda layer structure needs fixing
        # deploy_stage.add_post(
        #     pipelines.CodeBuildStep(
        #         "SaveWebSocketUrl",
        #         commands=[
        #             "WS_URL=$(aws cloudformation describe-stacks --stack-name MBPP-Api --query 'Stacks[0].Outputs[?OutputKey==`WebSocketApiEndpoint`].OutputValue' --output text)",
        #             "if [ -z \"$WS_URL\" ]; then echo 'Error: WebSocket URL not found'; exit 1; fi",
        #             "aws ssm put-parameter --name /mbpp/websocket-url --value \"$WS_URL\" --type String --overwrite",
        #             "echo WebSocket URL saved to Parameter Store: $WS_URL"
        #         ],
        #         build_environment=codebuild.BuildEnvironment(
        #             build_image=codebuild.LinuxBuildImage.STANDARD_7_0
        #         ),
        #         role_policy_statements=[
        #             aws_iam.PolicyStatement(
        #                 actions=["cloudformation:DescribeStacks"],
        #                 resources=[f"arn:aws:cloudformation:*:{self.account}:stack/MBPP-*/*"]
        #             ),
        #             aws_iam.PolicyStatement(
        #                 actions=["ssm:PutParameter"],
        #                 resources=[f"arn:aws:ssm:*:{self.account}:parameter/mbpp/*"]
        #             )
        #         ]
        #     )
        # )


class ApplicationStage(Stage):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        
        database_stack = DatabaseStack(self, "Database")
        storage_stack = StorageStack(self, "Storage")
        
        lambda_stack = LambdaStack(
            self, "Lambda",
            sessions_table=database_stack.sessions_table,
            conversations_table=database_stack.conversations_table,
            analytics_table=database_stack.analytics_table,
            events_table=database_stack.events_table
        )
        
        api_stack = ApiStack(
            self, "Api",
            websocket_handler=lambda_stack.websocket_handler
        )
        
        mbpp_stack = MBPPWorkflowStack(self, "Workflow")
