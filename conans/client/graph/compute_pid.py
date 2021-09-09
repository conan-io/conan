from collections import OrderedDict

from conans.client.graph.graph import BINARY_INVALID, BINARY_ERROR, BINARY_UNKNOWN
from conans.model.pkg_type import PackageType
from conans.errors import conanfile_exception_formatter, ConanInvalidConfiguration, \
    ConanErrorConfiguration, ConanException
from conans.model.info import ConanInfo, RequirementsInfo, RequirementInfo, PACKAGE_ID_INVALID, \
    PACKAGE_ID_UNKNOWN
from conans.util.conan_v2_mode import conan_v2_property


def compute_package_id(node, new_config):
    """
    Compute the binary package ID of this node
    """
    conanfile = node.conanfile
    default_package_id_mode = new_config["core.package_id:default_mode"] or "semver_mode"
    default_python_requires_id_mode = new_config["core.package_id:python_default_mode"] or "minor_mode"

    python_requires = getattr(conanfile, "python_requires", None)
    if python_requires:
        python_requires = python_requires.all_refs()

    data = OrderedDict()
    build_data = OrderedDict()
    for require, transitive in node.transitive_deps.items():
        dep_package_id = require.package_id_mode
        dep_node = transitive.node
        dep_conanfile = dep_node.conanfile
        if require.build:
            if dep_package_id:
                req_info = RequirementInfo(dep_node.pref, dep_package_id, dep_node.binary)
                build_data[require] = req_info
        else:
            if dep_package_id is None:  # Automatically deducing package_id
                if require.headers or require.libs:  # linked
                    if conanfile.package_type is PackageType.SHARED:
                        if dep_conanfile.package_type is PackageType.SHARED:
                            dep_package_id = "minor_mode"
                        else:
                            dep_package_id = "recipe_revision_mode"
                    elif conanfile.package_type is PackageType.STATIC:
                        if dep_conanfile.package_type is PackageType.HEADER:
                            dep_package_id = "recipe_revision_mode"
                        else:
                            dep_package_id = "minor_mode"
                    elif conanfile.package_type is PackageType.HEADER:
                        dep_package_id = "unrelated_mode"
            req_info = RequirementInfo(dep_node.pref, dep_package_id or default_package_id_mode,
                                       dep_node.binary)
            data[require] = req_info

    reqs_info = RequirementsInfo(data)
    build_requires_info = RequirementsInfo(build_data)

    conanfile.info = ConanInfo.create(conanfile.settings.values,
                                      conanfile.options.values,
                                      reqs_info,
                                      build_requires_info,
                                      python_requires=python_requires,
                                      default_python_requires_id_mode=
                                      default_python_requires_id_mode)

    msvc_incomp = False  # self._cache.new_config["core.package_id:msvc_visual_incompatible"]
    if not msvc_incomp:
        msvc_compatible = conanfile.info.msvc_compatible()
        if msvc_compatible:
            conanfile.compatible_packages.append(msvc_compatible)

    # Once we are done, call package_id() to narrow and change possible values
    with conanfile_exception_formatter(str(conanfile), "package_id"):
        with conan_v2_property(conanfile, 'cpp_info',
                               "'self.cpp_info' access in package_id() method is deprecated"):
            conanfile.package_id()

    # IMPORTANT: This validation code must run before calling info.package_id(), to mark "invalid"
    if hasattr(conanfile, "validate") and callable(conanfile.validate):
        with conanfile_exception_formatter(str(conanfile), "validate"):
            try:
                conanfile.validate()
            except ConanInvalidConfiguration as e:
                node.binary = BINARY_INVALID
                node.binary_error = str(e)
            except ConanErrorConfiguration as e:
                node.binary = BINARY_ERROR
                node.binary_error = str(e)

    try:
        # TODO: Maybe we want to validate the "info" values?
        conanfile.settings.validate()  # All has to be ok!
        conanfile.options.validate()
    except ConanException as e:
        node.binary = BINARY_INVALID
        node.binary_error = str(e)

    pid = conanfile.info.package_id()
    node.package_id = pid
    binary_error = conanfile.info.req_binary_error()
    if binary_error == BINARY_INVALID:
        node.binary = BINARY_INVALID
        node.binary_error = "The package has invalid transitive dependencies"
    elif binary_error == BINARY_UNKNOWN:
        node.binary = BINARY_UNKNOWN
        node.binary_error = "The package_id cannot be computed until all dependencies are known"
