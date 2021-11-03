from conans.client.tools import no_op
from conans.errors import conanfile_exception_formatter
from conans.model.pkg_type import PackageType
from conans.model.requires import BuildRequirements, TestRequirements


def run_configure_method(conanfile, down_options, profile_options, ref):
    """ Run all the config-related functions for the given conanfile object """

    # Avoid extra time manipulating the sys.path for python
    with no_op():  # TODO: Remove this in a later refactor
        with conanfile_exception_formatter(str(conanfile), "config_options"):
            conanfile.config_options()

        # Assign only the current package options values, but none of the dependencies
        conanfile.options.apply_downstream(down_options, profile_options, ref)

        with conanfile_exception_formatter(str(conanfile), "configure"):
            conanfile.configure()

        self_options, up_options = conanfile.options.get_upstream_options(down_options, ref)
        # self_options are the minimum to reproduce state, as defined from downstream (not profile)
        conanfile.self_options = self_options
        # up_options are the minimal options that should be propagated to dependencies
        conanfile.up_options = up_options

        PackageType.compute_package_type(conanfile)

        if hasattr(conanfile, "requirements"):
            with conanfile_exception_formatter(str(conanfile), "requirements"):
                conanfile.requirements()

        # TODO: Maybe this could be integrated in one single requirements() method
        if hasattr(conanfile, "build_requirements"):
            with conanfile_exception_formatter(str(conanfile), "build_requirements"):
                conanfile.build_requires = BuildRequirements(conanfile.requires)
                conanfile.test_requires = TestRequirements(conanfile.requires)
                conanfile.build_requirements()
