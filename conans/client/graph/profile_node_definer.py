from conans.client.graph.graph import CONTEXT_HOST, CONTEXT_BUILD
from conans.errors import ConanException
from conans.model.recipe_ref import ref_matches


def initialize_conanfile_profile(conanfile, profile_build, profile_host, base_context,
                                 is_build_require, ref=None):
    """ this function fills conanfile information with the profile informaiton
    It is called for:
        - computing the root_node
           - GraphManager.load_consumer_conanfile, for "conan source" command
           - GraphManager._load_root_consumer for "conan install <path to conanfile>
           - GraphManager._load_root_test_package for "conan create ." with test_package folder
        - computing each graph node:
            GraphBuilder->create_new_node
    """
    # NOTE: Need the context, as conanfile.context NOT defined yet

    # settings_build=profile_build ALWAYS
    # host -(r)-> host => settings_host=profile_host, settings_target=None
    # host -(br)-> build => settings_host=profile_build, settings_target=profile_host
    # build(gcc) -(r)-> build(openssl/zlib) => settings_host=profile_build, settings_target=None
    # build(gcc) -(br)-> build(gcc) => settings_host=profile_build, settings_target=profile_build
    # profile host
    profile = profile_build if is_build_require or base_context == CONTEXT_BUILD else profile_host
    _initialize_conanfile(conanfile, profile, ref)
    # profile build
    conanfile.settings_build = profile_build.processed_settings.copy()
    # profile target
    conanfile.settings_target = None
    if base_context == CONTEXT_HOST:
        if is_build_require:
            conanfile.settings_target = profile_host.processed_settings.copy()
    else:
        if not is_build_require:
            conanfile.settings_target = profile_build.processed_settings.copy()


def _initialize_conanfile(conanfile, profile, ref):
    # Prepare the settings for the loaded conanfile
    # Mixing the global settings with the specified for that name if exist
    tmp_settings = profile.processed_settings.copy()
    package_settings_values = profile.package_settings_values

    if package_settings_values:
        pkg_settings = []

        for pattern, settings in package_settings_values.items():
            if ref_matches(ref, pattern, conanfile._conan_is_consumer):
                pkg_settings.extend(settings)

        if pkg_settings:
            tmp_settings.update_values(pkg_settings)
            # if the global settings are composed with per-package settings, need to preprocess

    try:
        tmp_settings.constrained(conanfile.settings)
    except Exception as e:
        raise ConanException("The recipe %s is constraining settings. %s" % (
            conanfile.display_name, str(e)))
    conanfile.settings = tmp_settings
    conanfile._conan_buildenv = profile.buildenv
    conanfile._conan_runenv = profile.runenv
    conanfile.conf = profile.conf.get_conanfile_conf(ref, conanfile._conan_is_consumer)  # Maybe this can be done lazy too


def consumer_definer(conanfile, profile_host):
    """ conanfile.txt does not declare settings, but it assumes it uses all the profile settings
    These settings are very necessary for helpers like generators to produce the right output
    """
    tmp_settings = profile_host.processed_settings.copy()
    package_settings_values = profile_host.package_settings_values

    for pattern, settings in package_settings_values.items():
        if ref_matches(ref=None, pattern=pattern, is_consumer=True):
            tmp_settings.update_values(settings)

    conanfile.settings = tmp_settings
    conanfile._conan_buildenv = profile_host.buildenv
    conanfile._conan_runenv = profile_host.runenv
    conanfile.conf = profile_host.conf.get_conanfile_conf(None, is_consumer=True)
