import aws_cdk as cdk
from aws_cdk import (
    App, Stack, Duration, RemovalPolicy,CfnOutput,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_iam as iam,
    aws_secretsmanager as secrets,
)
from constructs import Construct

class HallucinationCheckerStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Cache + results table (auto-delete after 24h)
        self.table = dynamodb.Table(
            self, "ResultsTable",
            partition_key=dynamodb.Attribute(name="cache_key", type=dynamodb.AttributeType.STRING),
            time_to_live_attribute="ttl",
            removal_policy=RemovalPolicy.DESTROY,
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST
        )

        # Logs bucket
        self.log_bucket = s3.Bucket(
            self, "LogsBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

        # Secret for Serper API key
        self.serper_secret = secrets.Secret(self, "SerperSecret",
            secret_name="serper-api-key"
        )

        bedrock_policy = iam.PolicyStatement(
            actions=["bedrock:Converse", "bedrock:InvokeModel"],
            resources=["*"]
        )

        lambda_invoke_policy = iam.PolicyStatement(
            actions=["lambda:InvokeFunction"],
            resources=["*"]
        )

        # Search Lambda
        self.search_lambda = _lambda.Function(
            self, "SearchAgent",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambda_function.handler",
            code=_lambda.Code.from_asset("lambdas/search"),
            timeout=Duration.seconds(15),
            environment={"SERPER_SECRET_NAME": self.serper_secret.secret_name}
        )
        self.serper_secret.grant_read(self.search_lambda)

        # Decision (judge) Lambda
        self.decision_lambda = _lambda.Function(
            self, "DecisionEngine",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambda_function.handler",
            code=_lambda.Code.from_asset("lambdas/decision"),
            timeout=Duration.seconds(30),
            environment={"TABLE_NAME": self.table.table_name}
        )
        self.table.grant_read_write_data(self.decision_lambda)
        self.decision_lambda.add_to_role_policy(bedrock_policy)

        # Orchestrator (main) Lambda
        self.orchestrator_lambda = _lambda.Function(
            self, "Orchestrator",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambda_function.handler",
            code=_lambda.Code.from_asset("lambdas/orchestrator"),
            timeout=Duration.seconds(60),
            memory_size=512,
            environment={
                "SEARCH_LAMBDA_ARN": self.search_lambda.function_arn,
                "DECISION_LAMBDA_ARN": self.decision_lambda.function_arn,
                "TABLE_NAME": self.table.table_name,
                "LOG_BUCKET": self.log_bucket.bucket_name
            }
        )
        self.table.grant_read_write_data(self.orchestrator_lambda)
        self.log_bucket.grant_put(self.orchestrator_lambda)
        self.search_lambda.grant_invoke(self.orchestrator_lambda)
        self.decision_lambda.grant_invoke(self.orchestrator_lambda)
        self.orchestrator_lambda.add_to_role_policy(bedrock_policy)
        self.orchestrator_lambda.add_to_role_policy(lambda_invoke_policy)
        self.api = apigw.RestApi(self, "HallucinationAPI",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,  # allows http://localhost:8000, *
                allow_methods=["OPTIONS", "POST", "GET"],  # preflight + your method
                allow_headers=["Content-Type", "Authorization", "X-Amz-Date", "X-Api-Key"],
                expose_headers=["Content-Type"],
                max_age=Duration.days(1)
            )
        )

        check = self.api.root.add_resource("check")
        check.add_method(
            "POST",
            apigw.LambdaIntegration(self.orchestrator_lambda),
            authorization_type=apigw.AuthorizationType.NONE,  # public - no API key or IAM
            api_key_required=False,
            method_responses=[
                apigw.MethodResponse(status_code="200"),
                apigw.MethodResponse(status_code="400"),
                apigw.MethodResponse(status_code="500"),
            ]
        )

        # Output the endpoint
        cdk.CfnOutput(
            self, "ApiEndpoint",
            value=self.api.url + "check",
            description="Public hallucination check API URL"
        )