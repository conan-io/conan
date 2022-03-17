from collections import OrderedDict

from conans.client.graph.graph import BINARY_INVALID, BINARY_ERROR
from conans.errors import conanfile_exception_formatter, ConanInvalidConfiguration, \
    ConanErrorConfiguration, ConanException
from conans.model.info import ConanInfo, RequirementsInfo, RequirementInfo
from conans.model.pkg_type import PackageType
from conans.util.conan_v2_mode import conan_v2_property


def _get_mode(node, require, dep_node, lib_mode, bin_mode, build_mode, unknown_mode):
    # If defined by the ``require(package_id_mode=xxx)`` trait, that is higher priority
    # The "conf" values are defaults, no hard overrides
    if require.package_id_mode:
        return require.package_id_mode

    if require.build:
        if build_mode and require.direct:
            return build_mode
        return None  # At the moment no defaults

    pkg_type = node.conanfile.package_type
    dep_pkg_type = dep_node.conanfile.package_type
    if require.headers or require.libs:  # only if linked
        if pkg_type in (PackageType.SHARED, PackageType.APP):
            if dep_pkg_type is PackageType.SHARED:
                return lib_mode
            else:
                return bin_mode
        elif pkg_type is PackageType.STATIC:
            if dep_pkg_type is PackageType.HEADER:
                return bin_mode
            else:
                return lib_mode
        # HEADER-ONLY is automatically cleared in compute_package_id()

    return unknown_mode


def compute_package_id(node, new_config):
    """
    Compute the binary package ID of this node
    """
    conanfile = node.conanfile

    unknown_mode = new_config.get("core.package_id:default_unknown_mode", default="semver_mode")
    lib_mode = new_config.get("core.package_id:default_lib_mode", default="minor_mode")
    # TODO: Change it to "full_mode" including package_id
    bin_mode = new_config.get("core.package_id:default_bin_mode", default="recipe_revision_mode")
    python_mode = new_config.get("core.package_id:default_python_mode", default="minor_mode")
    build_mode = new_config.get("core.package_id:default_build_mode", default=None)

    python_requires = getattr(conanfile, "python_requires", None)
    if python_requires:
        python_requires = python_requires.all_refs()

    data = OrderedDict()
    build_data = OrderedDict()
    for require, transitive in node.transitive_deps.items():
        dep_node = transitive.node
        dep_package_id_mode = _get_mode(node, require, dep_node, lib_mode, bin_mode, build_mode,
                                        unknown_mode)
        if dep_package_id_mode is not None:
            req_info = RequirementInfo(dep_node.pref, dep_package_id_mode)
            if require.build:
                build_data[require] = req_info
            else:
                data[require] = req_info

    reqs_info = RequirementsInfo(data)
    build_requires_info = RequirementsInfo(build_data)

    conanfile.info = ConanInfo.create(conanfile.settings.values,
                                      conanfile.options,
                                      reqs_info,
                                      build_requires_info,
                                      python_requires=python_requires,
                                      default_python_requires_id_mode=python_mode)

    msvc_incomp = False  # self._cache.new_config["core.package_id:msvc_visual_incompatible"]
    if not msvc_incomp:
        msvc_compatible = conanfile.info.msvc_compatible()
        if msvc_compatible:
            conanfile.compatible_packages.append(msvc_compatible)

    # Once we are done, call package_id() to narrow and change possible values
    with conanfile_exception_formatter(conanfile, "package_id"):
        with conan_v2_property(conanfile, 'cpp_info',
                               "'self.cpp_info' access in package_id() method is deprecated"):
            conanfile.package_id()

    # IMPORTANT: This validation code must run before calling info.package_id(), to mark "invalid"
    if hasattr(conanfile, "validate") and callable(conanfile.validate):
        with conanfile_exception_formatter(conanfile, "validate"):
            try:
                conanfile.validate()
            except ConanInvalidConfiguration as e:
                conanfile.info.invalid = BINARY_INVALID, str(e)
            except ConanErrorConfiguration as e:
                conanfile.info.invalid = BINARY_ERROR, str(e)

    try:
        # TODO: What if something is not defined, but still the binary exists and the option is for
        # consumers only?
        conanfile.settings.validate()  # All has to be ok!
        conanfile.options.validate()
    except ConanException as e:
        conanfile.info.invalid = BINARY_INVALID, str(e)

    info = conanfile.info
    node.package_id = info.package_id()
