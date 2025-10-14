from __future__ import annotations

import os
from typing import Iterable, Optional

import aws_cdk as cdk
from aws_cdk import Stack
from aws_cdk import aws_iam as iam
from constructs import Construct


class CiAccessStack(Stack):
    """Provision an IAM role for GitHub Actions to push to ECR and deploy ECS services."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        github_org: str | None = self.node.try_get_context("github_org") or os.getenv(
            "GITHUB_ORG"
        )
        github_repo: str | None = self.node.try_get_context("github_repo") or os.getenv(
            "GITHUB_REPO"
        )
        if not github_org or not github_repo:
            raise ValueError(
                "github_org and github_repo context values are required for CiAccessStack"
            )

        repo_names: Iterable[str] = self.node.try_get_context("repo_names") or [
            "prolific-interview-service",
            "prolific-interview-ui",
        ]

        ecs_cluster_names: Iterable[str] = self.node.try_get_context(
            "ecs_cluster_names"
        ) or [
            "prolific-interview-dev",
            "prolific-interview-prod",
        ]
        ecs_service_names: Iterable[str] = self.node.try_get_context(
            "ecs_service_names"
        ) or [
            "interviewer-service",
            "interviewer-ui",
        ]

        existing_provider_arn: Optional[str] = self.node.try_get_context(
            "existing_oidc_provider_arn"
        )
        if existing_provider_arn:
            oidc_provider = iam.OpenIdConnectProvider.from_open_id_connect_provider_arn(
                self, "GitHubOidcProvider", existing_provider_arn
            )
        else:
            oidc_provider = iam.OpenIdConnectProvider(
                self,
                "GitHubOidcProvider",
                url="https://token.actions.githubusercontent.com",
                client_ids=["sts.amazonaws.com"],
            )

        conditions = {
            "StringEquals": {
                "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
            },
            "StringLike": {
                "token.actions.githubusercontent.com:sub": f"repo:{github_org}/{github_repo}:*",
            },
        }

        principal = iam.OpenIdConnectPrincipal(oidc_provider).with_conditions(
            conditions
        )

        role = iam.Role(
            self,
            "GitHubActionsDeployRole",
            role_name="prolific-github-actions-deploy",
            assumed_by=principal,
            description="Allows GitHub Actions to push images to ECR and deploy ECS services",
            max_session_duration=cdk.Duration.hours(1),
        )

        # ECR push/pull permissions limited to configured repositories.
        repo_arns = [
            self.format_arn(service="ecr", resource="repository", resource_name=name)
            for name in repo_names
        ]

        role.add_to_policy(
            iam.PolicyStatement(
                sid="EcrGetAuthToken",
                actions=["ecr:GetAuthorizationToken"],
                resources=["*"],
            )
        )

        role.add_to_policy(
            iam.PolicyStatement(
                sid="EcrPushPull",
                actions=[
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:BatchDeleteImage",
                    "ecr:BatchGetImage",
                    "ecr:CompleteLayerUpload",
                    "ecr:DescribeImages",
                    "ecr:DescribeRepositories",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:InitiateLayerUpload",
                    "ecr:ListImages",
                    "ecr:PutImage",
                    "ecr:UploadLayerPart",
                ],
                resources=repo_arns,
            )
        )

        # ECS deploy permissions.
        cluster_arns = [
            self.format_arn(service="ecs", resource="cluster", resource_name=name)
            for name in ecs_cluster_names
        ]
        service_arns = [
            self.format_arn(
                service="ecs",
                resource="service",
                resource_name=f"{cluster_name}/{service_name}",
            )
            for cluster_name in ecs_cluster_names
            for service_name in ecs_service_names
        ]

        task_definition_arn = self.format_arn(
            service="ecs", resource="task-definition", resource_name="*"
        )

        role.add_to_policy(
            iam.PolicyStatement(
                sid="EcsDeploy",
                actions=[
                    "ecs:DescribeClusters",
                    "ecs:DescribeServices",
                    "ecs:ListTaskDefinitions",
                    "ecs:DescribeTaskDefinition",
                    "ecs:RegisterTaskDefinition",
                    "ecs:UpdateService",
                    "ecs:UpdateServicePrimaryTaskSet",
                    "ecs:DescribeTaskSets",
                    "ecs:DeleteTaskSet",
                ],
                resources=cluster_arns + service_arns + [task_definition_arn],
            )
        )

        role.add_to_policy(
            iam.PolicyStatement(
                sid="EcsRunTask",
                actions=[
                    "ecs:RunTask",
                    "ecs:StartTask",
                    "ecs:StopTask",
                    "ecs:DescribeTasks",
                    "ecs:ListTasks",
                ],
                resources=["*"],
                conditions={
                    "ArnEquals": {
                        "ecs:cluster": cluster_arns,
                    }
                },
            )
        )

        # Allow the workflow to pass the task execution role when registering new task definitions.
        execution_role_arn = self.node.try_get_context("ecs_task_execution_role_arn")
        if execution_role_arn:
            role.add_to_policy(
                iam.PolicyStatement(
                    sid="AllowPassExecutionRole",
                    actions=["iam:PassRole"],
                    resources=[execution_role_arn],
                    conditions={
                        "StringEquals": {
                            "iam:PassedToService": "ecs-tasks.amazonaws.com"
                        }
                    },
                )
            )

        cdk.Tags.of(role).add("Project", "prolific-interview")
        cdk.Tags.of(role).add("Role", "ci-deploy")

        cdk.CfnOutput(self, "GitHubActionsRoleArn", value=role.role_arn)
