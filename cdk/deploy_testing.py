#!/usr/bin/env python3
"""
Deploy MBPP Testing Stack standalone
"""

import aws_cdk as cdk
from stacks.testing_stack import MBPPTestingStack

app = cdk.App()

# Get WebSocket handler ARN
websocket_handler_arn = "arn:aws:lambda:ap-southeast-1:836581769622:function:MBPP-Lambda-WebSocketHandler47C0AA1A-Pt6SFsWEsl2r"

MBPPTestingStack(
    app, "MBPPTestingStack",
    websocket_handler_arn=websocket_handler_arn,
    env=cdk.Environment(
        account="836581769622",
        region="ap-southeast-1"
    )
)

app.synth()
