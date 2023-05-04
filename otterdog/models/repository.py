# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from dataclasses import dataclass, field
from typing import Any

from jsonbender import bend, S, OptionalS, K, Forall

from . import ModelObject, UNSET, ValidationContext, FailureType
from .organization_settings import OrganizationSettings
from .branch_protection_rule import BranchProtectionRule


@dataclass
class Repository(ModelObject):
    name: str = field(metadata={"key": True})
    description: str
    homepage: str
    private: bool
    has_issues: bool
    has_projects: bool
    has_wiki: bool
    default_branch: str
    allow_rebase_merge: bool
    allow_merge_commit: bool
    allow_squash_merge: bool
    allow_auto_merge: bool
    delete_branch_on_merge: bool
    allow_update_branch: bool
    squash_merge_commit_title: str
    squash_merge_commit_message: str
    merge_commit_title: str
    merge_commit_message: str
    archived: bool
    allow_forking: bool
    web_commit_signoff_required: bool
    secret_scanning: str
    secret_scanning_push_protection: str
    dependabot_alerts_enabled: bool
    branch_protection_rules: list[BranchProtectionRule] = field(default_factory=list)

    def validate(self, context: ValidationContext, parent_object: object) -> None:
        org_settings: OrganizationSettings = parent_object.settings

        free_plan = org_settings.plan == "free"

        org_web_commit_signoff_required = org_settings.web_commit_signoff_required is True
        org_members_cannot_fork_private_repositories = org_settings.members_can_fork_private_repositories is False

        is_private = self.private is True
        is_public = self.private is False

        allow_forking = self.allow_forking is True
        disallow_forking = self.allow_forking is False

        if is_public and disallow_forking:
            context.add_failure(FailureType.WARNING,
                                f"public repo[name=\"{self.name}\"] has 'allow_forking' disabled "
                                f"which is not permitted.")

        has_wiki = self.has_wiki is True
        if is_private and has_wiki and free_plan:
            context.add_failure(FailureType.WARNING,
                                f"private repo[name=\"{self.name}\"] has 'has_wiki' enabled which"
                                f"requires at least GitHub Team billing, "
                                f"currently using \"{org_settings.plan}\" plan.")

        if is_private and org_members_cannot_fork_private_repositories and allow_forking:
            context.add_failure(FailureType.ERROR,
                                f"private repo[name=\"{self.name}\"] has 'allow_forking' enabled "
                                f"while the organization disables 'members_can_fork_private_repositories'.")

        repo_web_commit_signoff_not_required = self.web_commit_signoff_required is False
        if repo_web_commit_signoff_not_required and org_web_commit_signoff_required:
            context.add_failure(FailureType.ERROR,
                                f"repo[name=\"{self.name}\"] has 'web_commit_signoff_required' disabled while "
                                f"the organization requires it.")

        for bpr in self.branch_protection_rules:
            bpr.validate(context, self)

    @classmethod
    def from_model(cls, data: dict[str, Any]) -> "Repository":
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}

        mapping.update(
            {
                "branch_protection_rules":
                    OptionalS("branch_protection_rules", default=[]) >>
                    Forall(lambda x: BranchProtectionRule.from_model(x))
            }
        )

        return cls(**bend(mapping, data))

    @classmethod
    def from_provider(cls, data: dict[str, Any]) -> "Repository":
        mapping = {k: S(k) for k in map(lambda x: x.name, cls.all_fields())}

        mapping.update({
            "branch_protection_rules": K([]),
            "secret_scanning":
                OptionalS("security_and_analysis", "secret_scanning", "status", default=UNSET),
            "secret_scanning_push_protection":
                OptionalS("security_and_analysis", "secret_scanning_push_protection", "status", default=UNSET)
        })

        return cls(**bend(mapping, data))