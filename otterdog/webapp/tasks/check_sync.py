#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
from io import StringIO
from typing import Union, cast

from pydantic import ValidationError
from quart import current_app, render_template

from otterdog.models import LivePatch
from otterdog.operations.diff_operation import DiffStatus
from otterdog.operations.plan import PlanOperation
from otterdog.providers.github import RestApi
from otterdog.utils import IndentingPrinter, LogLevel
from otterdog.webapp.db.models import TaskModel
from otterdog.webapp.tasks import Task
from otterdog.webapp.tasks.validate_pull_request import get_admin_team
from otterdog.webapp.utils import (
    escape_for_github,
    fetch_config_from_github,
    get_otterdog_config,
)
from otterdog.webapp.webhook.github_models import PullRequest, Repository


@dataclasses.dataclass(repr=False)
class CheckConfigurationInSyncTask(Task[bool]):
    """Checks whether the base ref is in sync with live settings."""

    installation_id: int
    org_id: str
    repository: Repository
    pull_request_or_number: PullRequest | int

    def create_task_model(self):
        return TaskModel(
            type=type(self).__name__,
            org_id=self.org_id,
            repo_name=self.repository.name,
            pull_request=self.pull_request.number,
        )

    async def _pre_execute(self) -> None:
        rest_api = await self.get_rest_api(self.installation_id)

        if isinstance(self.pull_request_or_number, int):
            response = await rest_api.pull_request.get_pull_request(
                self.org_id, self.repository.name, str(self.pull_request_or_number)
            )
            try:
                self.pull_request = PullRequest.model_validate(response)
            except ValidationError as ex:
                self.logger.exception("failed to load pull request event data", exc_info=ex)
                return
        else:
            self.pull_request = cast(PullRequest, self.pull_request_or_number)

        self.logger.info(
            "checking if base ref is in sync for pull request #%d of repo '%s'",
            self.pull_request.number,
            self.repository.full_name,
        )

        await self._create_pending_status(rest_api)

    async def _post_execute(self, result_or_exception: Union[bool, Exception]) -> None:
        rest_api = await self.get_rest_api(self.installation_id)

        if isinstance(result_or_exception, Exception):
            await self._create_failure_status(rest_api)
        else:
            await self._update_final_status(rest_api, result_or_exception)

    async def _execute(self) -> bool:
        pull_request_number = str(self.pull_request.number)
        otterdog_config = await get_otterdog_config()
        rest_api = await self.get_rest_api(self.installation_id)

        async with self.get_organization_config(otterdog_config, rest_api, self.installation_id) as org_config:
            # get BASE config
            base_file = org_config.jsonnet_config.org_config_file
            await fetch_config_from_github(
                rest_api,
                self.org_id,
                self.org_id,
                otterdog_config.default_config_repo,
                base_file,
                self.pull_request.base.ref,
            )

            output = StringIO()
            printer = IndentingPrinter(output, log_level=LogLevel.ERROR)
            operation = PlanOperation(True, False, False, "")

            config_in_sync = True

            def sync_callback(org_id: str, diff_status: DiffStatus, patches: list[LivePatch]):
                nonlocal config_in_sync
                config_in_sync = diff_status.total_changes(True) == 0

            operation.set_callback(sync_callback)
            operation.init(otterdog_config, printer)

            await operation.execute(org_config)

            sync_output = output.getvalue()
            self.logger.info("sync plan:\n" + sync_output)

            if config_in_sync is False:
                comment = await render_template(
                    "comment/out_of_sync_comment.txt",
                    result=escape_for_github(sync_output),
                    admin_team=f"{self.org_id}/{get_admin_team()}",
                )
            else:
                comment = await render_template("comment/in_sync_comment.txt")

            await rest_api.issue.create_comment(
                self.org_id, otterdog_config.default_config_repo, pull_request_number, comment
            )

            return config_in_sync

    async def _create_pending_status(self, rest_api: RestApi):
        await rest_api.commit.create_commit_status(
            self.org_id,
            self.repository.name,
            self.pull_request.head.sha,
            "pending",
            _get_webhook_sync_context(),
            "checking if configuration is in-sync using otterdog",
        )

    async def _create_failure_status(self, rest_api: RestApi):
        await rest_api.commit.create_commit_status(
            self.org_id,
            self.repository.name,
            self.pull_request.head.sha,
            "failure",
            _get_webhook_sync_context(),
            "otterdog sync check failed, please contact an admin",
        )

    async def _update_final_status(self, rest_api: RestApi, config_in_sync: bool) -> None:
        if config_in_sync is True:
            desc = "otterdog sync check completed successfully"
            status = "success"
        else:
            desc = "otterdog sync check failed, check comment history"
            status = "error"

        await rest_api.commit.create_commit_status(
            self.org_id,
            self.repository.name,
            self.pull_request.head.sha,
            status,
            _get_webhook_sync_context(),
            desc,
        )

    def __repr__(self) -> str:
        pull_request_number = (
            self.pull_request_or_number
            if isinstance(self.pull_request_or_number, int)
            else self.pull_request_or_number.number
        )
        return f"CheckConfigurationInSyncTask(repo={self.repository.full_name}, pull_request={pull_request_number})"


def _get_webhook_sync_context() -> str:
    return current_app.config["GITHUB_WEBHOOK_SYNC_CONTEXT"]
