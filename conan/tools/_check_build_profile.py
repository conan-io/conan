
check_msg = "Using the new toolchains and generators without specifying " \
            "a build profile (e.g: -pr:b=default) is discouraged and "\
            "might cause failures and unexpected behavior"


def check_using_build_profile(conanfile):
    """FIXME: Remove this in Conan 2.0 where the two profiles are always applied"""
    if not hasattr(conanfile, "settings_build"):
        conanfile.output.warn(check_msg)
