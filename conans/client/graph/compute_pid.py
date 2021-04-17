from conans.errors import conanfile_exception_formatter
from conans.model.info import ConanInfo
from conans.util.conan_v2_mode import conan_v2_property


def compute_package_id(node):
    """
    Compute the binary package ID of this node
    :param node: the node to compute the package-ID
    """
    print("COMPUTING ID OF ", node)
    # TODO Conan 2.0. To separate the propagation of the graph (options) of the package-ID
    # A bit risky to be done now
    conanfile = node.conanfile
    neighbors = node.neighbors()

    default_package_id_mode = "semver_mode"  # self._cache.config.default_package_id_mode
    default_python_requires_id_mode = "minor_mode"  # self._cache.config.default_python_requires_id_mode

    python_requires = getattr(conanfile, "python_requires", None)
    if python_requires:
        python_requires = python_requires.all_refs()
    direct_reqs = [r.pref for r in node.conanfile.dependencies.requires]
    indirect_reqs = []
    conanfile.info = ConanInfo.create(conanfile.settings.values,
                                      conanfile.options.values,
                                      direct_reqs,
                                      indirect_reqs,
                                      default_package_id_mode=default_package_id_mode,
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
