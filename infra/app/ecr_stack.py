from __future__ import annotations

from typing import Iterable

import aws_cdk as cdk
from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_iam as iam
from constructs import Construct

DEFAULT_REPOS = [
    "prolific-interview-service",
    "prolific-interview-ui",
]


class EcrStack(Stack):
    """Provision opinionated ECR repositories for the interviewer project."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        repo_names: Iterable[str] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        names = list(
            repo_names or self.node.try_get_context("repo_names") or DEFAULT_REPOS
        )
        description = (
            self.node.try_get_context("description")
            or "Container images for the Prolific AI interviewer stack"
        )
        grant_cross_account = self.node.try_get_context("cross_account_ids") or []

        for repo_name in names:
            logical_id = repo_name.replace("-", "").replace("_", "").title()
            repo = ecr.Repository(
                self,
                logical_id,
                repository_name=repo_name,
                image_scan_on_push=True,
                image_tag_mutability=ecr.TagMutability.IMMUTABLE,
                encryption=ecr.RepositoryEncryption.AES256,
                removal_policy=RemovalPolicy.RETAIN,
                lifecycle_rules=[
                    ecr.LifecycleRule(
                        description="Keep last 20 images; expire untagged after 7 days",
                        max_image_count=20,
                        tag_status=ecr.TagStatus.ANY,
                    ),
                    ecr.LifecycleRule(
                        description="Remove untagged images quickly",
                        tag_status=ecr.TagStatus.UNTAGGED,
                        max_image_age=Duration.days(7),
                    ),
                ],
            )

            repo.apply_removal_policy(RemovalPolicy.RETAIN)
            cdk.Tags.of(repo).add("Project", "prolific-interview")
            cdk.Tags.of(repo).add("Role", "container-repo")

            if grant_cross_account:
                for account_id in grant_cross_account:
                    repo.grant_pull_push(iam.AccountPrincipal(account_id))

            cdk.CfnOutput(
                self,
                f"{logical_id}Uri",
                value=repo.repository_uri,
                description=f"ECR repo for {repo_name}",
            )
