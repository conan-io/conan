import logging
import os
import shutil

import patch_ng

from conans.errors import ConanException
from conans.util.files import mkdir

def apply_conandata_requirements(conanfile, keyword, requirements_func):
    """
    Applies requirements or build_requirements stored in 'conanfile.conan_data' (read from 'conandata.yml' file). It will apply
    all the patches under 'requirements' or 'build_requirements' entry that matches the given 'conanfile.version'. If versions are
    not defined in 'conandata.yml' it will apply all the patches directly under 'requirements' or 'build_requirements' keyword.

    Example of 'conandata.yml' without versions defined:

    ```
    requirements:
      "1.0.1":
        - "package_a/1.0"
        - "package_v/1.1"
    ```
    build_requirements:
      "1.0.1":
        - "package_a/1.0"
        - "package_v/1.1"
    """

    if conanfile.conan_data is None:
        raise ConanException("conandata.yml not defined")

    requirements = conanfile.conan_data.get('requirements')
    if requirements is None:
        conanfile.output.info("apply_conandata_requirements(): No patches defined in conandata")
        return

    if isinstance(requirements, dict):
        assert conanfile.version, "Can only be exported if conanfile.version is already defined"
        entries = requirements.get(conanfile.version, [])
    elif isinstance(requirements, list):
        entries = requirements
    else:
        raise ConanException("conandata.yml 'requirements' should be a list or a dict {version: list}")
    for it in entries:
        requirements_func(it)

def conandata_requirements(conanfile):
    apply_conandata_requirements(conanfile, "requirements", conanfile.requires)

def conandata_tool_requirements(conanfile):
    apply_conandata_requirements(conanfile, "tool_requirements", conanfile.tool_requires)
