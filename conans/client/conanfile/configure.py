from conans.errors import conanfile_exception_formatter
from conans.model.pkg_type import PackageType
from conans.model.requires import BuildRequirements, TestRequirements, ToolRequirements
from conans.client.conanfile.implementations import auto_shared_fpic_config_options, \
    auto_shared_fpic_configure, auto_language


def run_configure_method(conanfile, down_options, profile_options, ref):
    """ Run all the config-related functions for the given conanfile object """

    initial_requires_count = len(conanfile.requires)

    if hasattr(conanfile, "config_options"):
        with conanfile_exception_formatter(conanfile, "config_options"):
            conanfile.config_options()
    elif "auto_shared_fpic" in conanfile.implements:
        auto_shared_fpic_config_options(conanfile)

    auto_language(conanfile)  # default implementation removes `compiler.cstd`

    # Assign only the current package options values, but none of the dependencies
    is_consumer = conanfile._conan_is_consumer
    conanfile.options.apply_downstream(down_options, profile_options, ref, is_consumer)

    if hasattr(conanfile, "configure"):
        with conanfile_exception_formatter(conanfile, "configure"):
            conanfile.configure()
    elif "auto_shared_fpic" in conanfile.implements:
        auto_shared_fpic_configure(conanfile)

    if initial_requires_count != len(conanfile.requires):
        conanfile.output.warning("Requirements should only be added in the requirements()/build_requirements() methods, not configure()/config_options(), which might raise errors in the future.", warn_tag="deprecated")

    result = conanfile.options.get_upstream_options(down_options, ref, is_consumer)
    self_options, up_options, private_up_options = result
    # self_options are the minimum to reproduce state, as defined from downstream (not profile)
    conanfile.self_options = self_options
    # up_options are the minimal options that should be propagated to dependencies
    conanfile.up_options = up_options
    conanfile.private_up_options = private_up_options

    PackageType.compute_package_type(conanfile)

    conanfile.build_requires = BuildRequirements(conanfile.requires)
    conanfile.test_requires = TestRequirements(conanfile.requires)
    conanfile.tool_requires = ToolRequirements(conanfile.requires)

    if hasattr(conanfile, "requirements"):
        with conanfile_exception_formatter(conanfile, "requirements"):
            conanfile.requirements()

    if hasattr(conanfile, "build_requirements"):
        with conanfile_exception_formatter(conanfile, "build_requirements"):
            conanfile.build_requirements()
