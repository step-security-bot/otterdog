#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import aiofiles.ospath

from otterdog.jsonnet import JsonnetConfig
from otterdog.models.github_organization import GitHubOrganization

from .apply import ApplyOperation


class LocalApplyOperation(ApplyOperation):
    def __init__(
        self,
        suffix: str,
        force_processing: bool,
        no_web_ui: bool,
        update_webhooks: bool,
        update_secrets: bool,
        update_filter: str,
        delete_resources: bool,
        resolve_secrets: bool = True,
        include_resources_with_secrets: bool = True,
    ) -> None:
        super().__init__(
            force_processing=force_processing,
            no_web_ui=no_web_ui,
            update_webhooks=update_webhooks,
            update_secrets=update_secrets,
            update_filter=update_filter,
            delete_resources=delete_resources,
            resolve_secrets=resolve_secrets,
            include_resources_with_secrets=include_resources_with_secrets,
        )

        self._suffix = suffix
        self._other_org: GitHubOrganization | None = None

    @property
    def suffix(self) -> str:
        return self._suffix

    @property
    def other_org(self) -> GitHubOrganization:
        assert self._other_org is not None
        return self._other_org

    def pre_execute(self) -> None:
        self.printer.println("Applying local changes:")
        self.print_legend()

    def verbose_output(self):
        return False

    async def load_current_org(self, github_id: str, jsonnet_config: JsonnetConfig) -> GitHubOrganization:
        other_org_file_name = jsonnet_config.org_config_file + self.suffix

        if not await aiofiles.ospath.exists(other_org_file_name):
            raise RuntimeError(f"configuration file '{other_org_file_name}' does not exist")

        return GitHubOrganization.load_from_file(github_id, other_org_file_name, self.config)
