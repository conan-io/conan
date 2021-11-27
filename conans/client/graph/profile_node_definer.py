import fnmatch

from conans.client import settings_preprocessor
from conans.client.graph.graph import CONTEXT_HOST, CONTEXT_BUILD
from conans.errors import ConanException


def _initialize_conanfile(conanfile, profile, ref):
    # Prepare the settings for the loaded conanfile
    # Mixing the global settings with the specified for that name if exist
    tmp_settings = profile.processed_settings.copy()
    package_settings_values = profile.package_settings_values
    if conanfile.user is not None:
        ref_str = "%s/%s@%s/%s" % (conanfile.name, conanfile.version,
                                   conanfile.user, conanfile.channel)
    else:
        ref_str = "%s/%s" % (conanfile.name, conanfile.version)
    if package_settings_values:
        # First, try to get a match directly by name (without needing *)
        # TODO: Conan 2.0: We probably want to remove this, and leave a pure fnmatch
        pkg_settings = package_settings_values.get(conanfile.name)

        if conanfile.develop and "&" in package_settings_values:
            # "&" overrides the "name" scoped settings.
            pkg_settings = package_settings_values.get("&")

        if pkg_settings is None:  # If there is not exact match by package name, do fnmatch
            for pattern, settings in package_settings_values.items():
                if fnmatch.fnmatchcase(ref_str, pattern):
                    pkg_settings = settings
                    # TODO: Conan 2.0 won't stop at first match
                    break
        if pkg_settings:
            tmp_settings.update_values(pkg_settings)
            # if the global settings are composed with per-package settings, need to preprocess
            settings_preprocessor.preprocess(tmp_settings)

    try:
        tmp_settings.constrained(conanfile.settings)
    except Exception as e:
        raise ConanException("The recipe %s is constraining settings. %s" % (
            conanfile.display_name, str(e)))
    conanfile.settings = tmp_settings
    conanfile._conan_buildenv = profile.buildenv
    conanfile.conf = profile.conf.get_conanfile_conf(ref_str)
    if profile.dev_reference and profile.dev_reference == ref:
        conanfile.develop = True


def initialize_conanfile_profile(conanfile, profile_build, profile_host, base_context,
                                 build_require, ref=None):
    # NOTE: Need the context, as conanfile.context NOT defined yet
    # graph_builder _create_new_node
    # If there is a context_switch, it is because it is a BR-build
    # Assign the profiles depending on the context
    #
    # settings_build=profile_build ALWAYS
    # host -(r)-> host => settings_host=profile_host, settings_target=None
    # host -(br)-> build => settings_host=profile_build, settings_target=profile_host
    # build(gcc) -(r)-> build(openssl/zlib) => settings_host=profile_build, settings_target=None
    # build(gcc) -(br)-> build(gcc) => settings_host=profile_build, settings_target=profile_build
    # profile host
    profile = profile_build if build_require or base_context == CONTEXT_BUILD else profile_host
    _initialize_conanfile(conanfile, profile, ref)
    # profile build
    conanfile.settings_build = profile_build.processed_settings.copy()
    # profile target
    conanfile.settings_target = None
    if base_context == CONTEXT_HOST:
        if build_require:
            conanfile.settings_target = profile_host.processed_settings.copy()
    else:
        if not build_require:
            conanfile.settings_target = profile_build.processed_settings.copy()


def txt_definer(conanfile, profile_host):
    tmp_settings = profile_host.processed_settings.copy()
    package_settings_values = profile_host.package_settings_values
    if "&" in package_settings_values:
        pkg_settings = package_settings_values.get("&")
        if pkg_settings:
            tmp_settings.update_values(pkg_settings)
    tmp_settings._unconstrained = True  # TODO: Remove unconstrained, probably not necesary anymore
    conanfile.settings = tmp_settings
    conanfile._conan_buildenv = profile_host.buildenv
    conanfile.conf = profile_host.conf.get_conanfile_conf(None)


def virtual_definer(conanfile, profile_host):
    tmp_settings = profile_host.processed_settings.copy()
    conanfile.settings = tmp_settings
    conanfile._conan_buildenv = profile_host.buildenv
    conanfile.conf = profile_host.conf.get_conanfile_conf(None)
