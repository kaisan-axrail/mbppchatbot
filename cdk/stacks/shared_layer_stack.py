"""Shared Lambda layer for common code."""
from aws_cdk import Stack
from aws_cdk.aws_lambda import LayerVersion, Runtime, Code
from constructs import Construct

class SharedLayerStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        
        # Create Lambda layer with shared code
        self.shared_layer = LayerVersion(
            self, "SharedLayer",
            code=Code.from_asset("../shared"),
            compatible_runtimes=[Runtime.PYTHON_3_11],
            description="Shared code for chatbot Lambda functions"
        )
