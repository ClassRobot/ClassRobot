from __future__ import annotations

from src.platform.helper import Param, Helper

from ..spec import CommandSpec


def command_spec_to_helper(spec: CommandSpec) -> Helper:
    """Render a command spec into the existing Helper view model."""

    return Helper(
        command=spec.name,
        aliases=set(spec.aliases),
        description=spec.description,
        ai_description=spec.ai_description or None,
        tags=set(spec.tags),
        roles=set(spec.roles),
        exclude_roles=set(spec.exclude_roles),
        scopes=set(spec.scopes),
        params=[
            Param(
                name=param.name,
                description=param.description or None,
                mode=param.mode,
            )
            for param in spec.params
        ],
        example=list(spec.examples),
    )
