from dataclasses import dataclass, field
from typing import Iterable, Optional
import os
import subprocess
import yaml 
import re
from snakemake_interface_software_deployment_plugins.settings import (
    SoftwareDeploymentSettingsBase,
)
from snakemake_interface_software_deployment_plugins import (
    EnvBase,
    DeployableEnvBase,
    ArchiveableEnvBase,
    EnvSpecBase,
    SoftwareReport,
)

from snakemake_interface_common.exceptions import WorkflowError  # noqa: F401


"""
    Plugin for using Spack environments.
    Current implementation:
        - Supports only named environments
            - Activated with `spack env activate <envName>`
        - Uses the 'spack.yaml' file to access env information 
            - For hashing 
            - For reporting 
        - CHECK: os.environ.get("SPACK_ROOT") is used to get the spack root directory.
            - Check it is actually accessible.
    TODO:
        - Support yaml file for environment definition.
        - Spack way of working seems similar to Conda in this way.
        - Support for deployment
            - Shouldn't be too hard, but it's better to first make sure everything is working fine.
"""

@dataclass
class SoftwareDeploymentSettings(SoftwareDeploymentSettingsBase):
    pack_parameter: Optional[int] = field(
        default=None,
        metadata={
            "help": "Some help text",
            # Optionally request that setting is also available for specification
            # via an environment variable. The variable will be named automatically as
            # SNAKEMAKE_<storage-plugin-name>_<param-name>, all upper case.
            # This mechanism should only be used for passwords, usernames, and other
            # credentials.
            # For other items, we rather recommend to let people use a profile
            # for setting defaults
            # (https://snakemake.readthedocs.io/en/stable/executing/cli.html#profiles).
            "env_var": False,
            # Optionally specify a function that parses the value given by the user.
            # This is useful to create complex types from the user input.
            "parse_func": ...,
            # If a parse_func is specified, you also have to specify an unparse_func
            # that converts the parsed value back to a string.
            "unparse_func": ...,
            # Optionally specify that setting is required when the executor is in use.
            "required": True,
            # Optionally specify multiple args with "nargs": "+"
        },
    )

@dataclass
class EnvSpec(EnvSpecBase):
    # For now, use only named environments
    envName: Optional[str] = None

    def __post_init__(self):
        if (self.envName is None):
            raise WorkflowError("Exactly one of envName must be set.")

    @classmethod
    def identity_attributes(cls) -> Iterable[str]:
        yield "envName"

    @classmethod
    def source_path_attributes(cls) -> Iterable[str]:
        # Return iterable of attributes of the subclass that represent paths that are
        # supposed to be interpreted as being relative to the defining rule.
        # For example, this would be attributes pointing to conda environment files.
        # Return empty list if no such attributes exist.
        return []




class Env(EnvBase, DeployableEnvBase, ArchiveableEnvBase):
    # For compatibility with future changes, you should not overwrite the __init__
    # method. Instead, use __post_init__ to set additional attributes and initialize
    # futher stuff.

    def run_cmd(self, cmd: str) -> subprocess.CompletedProcess:
        process = subprocess.run(cmd, shell=True, check=True)
        return process.stdout


    def __post_init__(self) -> None:
        # This is optional and can be removed if not needed.
        # Alternatively, you can e.g. prepare anything or set additional attributes.
        self.check()

    def get_spack_env_yaml(self):
        #$SPACK_ROOT/var/spack/environments/myenv/spack.yaml
        SPACK_ROOT = os.environ.get("SPACK_ROOT")
        return f"{SPACK_ROOT}/var/spack/environments/{self.spec.envName}/spack.yaml"

    # The decorator ensures that the decorated method is only called once
    # in case multiple environments of the same kind are created.
    @EnvBase.once
    def check(self) -> None:
        # Check e.g. whether the required software is available (e.g. a container
        # runtime or a module command).
        ...

    def decorate_shellcmd(self, cmd: str) -> str:
        return f"spack env activate {self.spec.envName} && {cmd}"

    def record_hash(self, hash_object) -> None:
        env_yaml = self.get_spack_env_yaml()
        with open(env_yaml, "r") as f:
            hash_object.update(f.read().encode("utf-8"))

    def report_software(self) -> Iterable[SoftwareReport]:
        env_yaml = self.get_spack_env_yaml()
        with open(env_yaml, "r") as f:
            env_data = yaml.safe_load(f)
        pattern = re.compile(r"^([^@^]+)@([\d\.]+)")
        result = []
        
        for spec in env_data.get("spack", {}).get("specs", []):
            match = pattern.match(spec)
            if match:
                name, version = match.groups()
                result.append(
                    SoftwareReport(
                        name=name,
                        version=version
                    )
                )
        
        return result
    # The methods below are optional. Remove them if not needed and adjust the
    # base classes above.

    """async def deploy(self) -> None:
        # Remove method if not deployable!
        # Deploy the environment to self.deployment_path, using self.spec
        # (the EnvSpec object).

        # When issuing shell commands, the environment should use
        # self.run_cmd(cmd: str) -> subprocess.CompletedProcess in order to ensure that
        # it runs within eventual parent environments (e.g. a container or an env
        # module).
        ...

    def is_deployment_path_portable(self) -> bool:
        # Remove method if not deployable!
        # Return True if the deployment is portable, i.e. can be moved to a
        # different location without breaking the environment. Return False otherwise.
        # For example, with conda, environments are not portable in that sense (cannot
        # be moved around, because deployed packages contain hardcoded absolute
        # RPATHs).
        ...

    def remove(self) -> None:
        # Remove method if not deployable!
        # Remove the deployed environment from self.deployment_path and perform
        # any additional cleanup.
        ...

    async def archive(self) -> None:
        # Remove method if not archiveable!
        # Archive the environment to self.archive_path.

        # When issuing shell commands, the environment should use
        # self.run_cmd(cmd: str) -> subprocess.CompletedProcess in order to ensure that
        # it runs within eventual parent environments (e.g. a container or an env
        # module).
        ..."""
