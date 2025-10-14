from __future__ import annotations

import os

import aws_cdk as cdk
from ci_access_stack import CiAccessStack
from ecr_stack import EcrStack


def build_app() -> cdk.App:
    app = cdk.App()

    account = os.getenv("CDK_DEFAULT_ACCOUNT")
    region = os.getenv("CDK_DEFAULT_REGION")

    EcrStack(
        app,
        "ProlificInterviewerEcrStack",
        env=cdk.Environment(account=account, region=region),
    )

    CiAccessStack(
        app,
        "ProlificInterviewerCiAccessStack",
        env=cdk.Environment(account=account, region=region),
    )

    return app


if __name__ == "__main__":
    build_app().synth()
