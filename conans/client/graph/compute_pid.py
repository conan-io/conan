from collections import OrderedDict

from conans.client.graph.graph import PackageType
from conans.errors import conanfile_exception_formatter
from conans.model.info import ConanInfo, RequirementsInfo, RequirementInfo
from conans.util.conan_v2_mode import conan_v2_property


def compute_package_id(node):
    """
    Compute the binary package ID of this node
    :param node: the node to compute the package-ID
    """
    conanfile = node.conanfile
    default_package_id_mode = conanfile.conf["tools.package_id:default_mode"] or "semver_mode"
    default_python_requires_id_mode = "minor_mode"  # self._cache.config.default_python_requires_id_mode

    python_requires = getattr(conanfile, "python_requires", None)
    if python_requires:
        python_requires = python_requires.all_refs()

    data = OrderedDict()
    for require, transitive in node.transitive_deps.items():
        dep_package_id = require.package_id_mode
        dep_node = transitive.node
        if dep_package_id is None:  # Automatically deducing package_id
            if require.include or require.link:  # linked
                if node.package_type is PackageType.SHARED:
                    if dep_node.package_type is PackageType.SHARED:
                        dep_package_id = "minor_mode"
                    else:
                        dep_package_id = "recipe_revision_mode"
                elif node.package_type is PackageType.STATIC:
                    if dep_node.package_type is PackageType.HEADER:
                        dep_package_id = "recipe_revision_mode"
                    else:
                        dep_package_id = "minor_mode"
                elif node.package_type is PackageType.HEADER:
                    dep_package_id = "unrelated_mode"

        req_info = RequirementInfo(dep_node.pref, dep_package_id or default_package_id_mode)
        data[require] = req_info

    reqs_info = RequirementsInfo(data)

    conanfile.info = ConanInfo.create(conanfile.settings.values,
                                      conanfile.options.values,
                                      reqs_info,
                                      python_requires=python_requires,
                                      default_python_requires_id_mode=
                                      default_python_requires_id_mode)

    msvc_incomp = False  # self._cache.new_config["core.package_id"].msvc_visual_incompatible
    if not msvc_incomp:
        msvc_compatible = conanfile.info.msvc_compatible()
        if msvc_compatible:
            conanfile.compatible_packages.append(msvc_compatible)

    # Once we are done, call package_id() to narrow and change possible values
    with conanfile_exception_formatter(str(conanfile), "package_id"):
        with conan_v2_property(conanfile, 'cpp_info',
                               "'self.cpp_info' access in package_id() method is deprecated"):
            conanfile.package_id()

    info = conanfile.info
    node.package_id = info.package_id()
