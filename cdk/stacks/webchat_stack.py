"""
Web Chat Frontend Stack - S3 + CloudFront deployment
"""

from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_s3_deployment as s3deploy,
    aws_iam as iam,
    RemovalPolicy,
    CfnOutput,
    Duration
)
from constructs import Construct


class WebChatStack(Stack):
    """Stack for deploying web chat frontend to S3 + CloudFront"""
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Create S3 bucket for web chat
        self.webchat_bucket = s3.Bucket(
            self, "WebChatBucket",
            bucket_name=f"mbpp-webchat-{self.account}",
            website_index_document="index.html",
            website_error_document="index.html",
            public_read_access=True,
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=False,
                block_public_policy=False,
                ignore_public_acls=False,
                restrict_public_buckets=False
            ),
            removal_policy=RemovalPolicy.RETAIN,
            auto_delete_objects=False,
            cors=[
                s3.CorsRule(
                    allowed_methods=[s3.HttpMethods.GET, s3.HttpMethods.HEAD],
                    allowed_origins=["*"],
                    allowed_headers=["*"],
                    max_age=3000
                )
            ]
        )
        
        # CloudFront Origin Access Identity
        oai = cloudfront.OriginAccessIdentity(
            self, "WebChatOAI",
            comment="OAI for MBPP Web Chat"
        )
        
        # Grant CloudFront access to S3 bucket
        self.webchat_bucket.grant_read(oai)
        
        # CloudFront distribution
        self.distribution = cloudfront.Distribution(
            self, "WebChatDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(
                    self.webchat_bucket,
                    origin_access_identity=oai
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD,
                cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                compress=True
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(5)
                ),
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(5)
                )
            ],
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
            comment="MBPP Web Chat Distribution"
        )
        
        # Deploy web chat files to S3
        s3deploy.BucketDeployment(
            self, "DeployWebChat",
            sources=[s3deploy.Source.asset("../aeon-usersidechatbot/aeon.web.chat/dist")],
            destination_bucket=self.webchat_bucket,
            distribution=self.distribution,
            distribution_paths=["/*"],
            memory_limit=512,
            prune=True
        )
        
        # Outputs
        CfnOutput(
            self, "WebChatBucketName",
            value=self.webchat_bucket.bucket_name,
            description="S3 bucket name for web chat",
            export_name="WebChatBucketName"
        )
        
        CfnOutput(
            self, "WebChatUrl",
            value=f"https://{self.distribution.distribution_domain_name}",
            description="CloudFront URL for web chat",
            export_name="WebChatUrl"
        )
        
        CfnOutput(
            self, "DistributionId",
            value=self.distribution.distribution_id,
            description="CloudFront distribution ID",
            export_name="WebChatDistributionId"
        )
