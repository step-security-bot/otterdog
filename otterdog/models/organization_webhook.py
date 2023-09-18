# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from __future__ import annotations

import dataclasses

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import ModelObject, LivePatch, LivePatchType
from otterdog.models.webhook import Webhook
from otterdog.providers.github import GitHubProvider
from otterdog.utils import IndentingPrinter, write_patch_object_as_json


@dataclasses.dataclass
class OrganizationWebhook(Webhook):
    """
    Represents a Webhook defined on organization level.
    """

    @property
    def model_object_name(self) -> str:
        return "org_webhook"

    def to_jsonnet(
        self,
        printer: IndentingPrinter,
        jsonnet_config: JsonnetConfig,
        extend: bool,
        default_object: ModelObject,
    ) -> None:
        patch = self.get_patch_to(default_object)
        patch.pop("url")
        printer.print(f"orgs.{jsonnet_config.create_org_webhook}('{self.url}')")
        write_patch_object_as_json(patch, printer)

    @classmethod
    def apply_live_patch(cls, patch: LivePatch, org_id: str, provider: GitHubProvider) -> None:
        match patch.patch_type:
            case LivePatchType.ADD:
                assert isinstance(patch.expected_object, OrganizationWebhook)
                provider.add_org_webhook(org_id, patch.expected_object.to_provider_data(org_id, provider))

            case LivePatchType.REMOVE:
                assert isinstance(patch.current_object, OrganizationWebhook)
                provider.delete_org_webhook(org_id, patch.current_object.id, patch.current_object.url)

            case LivePatchType.CHANGE:
                assert isinstance(patch.expected_object, OrganizationWebhook)
                assert isinstance(patch.current_object, OrganizationWebhook)
                provider.update_org_webhook(
                    org_id, patch.current_object.id, patch.expected_object.to_provider_data(org_id, provider)
                )
