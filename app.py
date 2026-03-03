#!/usr/bin/env python3
import os

import aws_cdk as cdk

from hallucination_checker.stack import HallucinationCheckerStack

app = cdk.App()

stack = HallucinationCheckerStack(
    app,
    "HallucinationChecker",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),
        region=os.getenv("CDK_DEFAULT_REGION")
    )
)

app.synth()