from collections import OrderedDict

from conans.errors import conanfile_exception_formatter, ConanInvalidConfiguration, \
    conanfile_remove_attr
from conans.model.info import ConanInfo, RequirementsInfo, RequirementInfo, PythonRequiresInfo


def compute_package_id(node, new_config):
    """
    Compute the binary package ID of this node
    """
    conanfile = node.conanfile

    unknown_mode = new_config.get("core.package_id:default_unknown_mode", default="semver_mode")
    non_embed_mode = new_config.get("core.package_id:default_non_embed_mode", default="minor_mode")
    # recipe_revision_mode already takes into account the package_id
    embed_mode = new_config.get("core.package_id:default_embed_mode", default="full_mode")
    python_mode = new_config.get("core.package_id:default_python_mode", default="minor_mode")
    build_mode = new_config.get("core.package_id:default_build_mode", default=None)

    python_requires = getattr(conanfile, "python_requires", None)
    if python_requires:
        python_requires = python_requires.all_refs()

    data = OrderedDict()
    build_data = OrderedDict()
    for require, transitive in node.transitive_deps.items():
        dep_node = transitive.node
        require.deduce_package_id_mode(conanfile.package_type, dep_node,
                                       non_embed_mode, embed_mode, build_mode, unknown_mode)
        if require.package_id_mode is not None:
            req_info = RequirementInfo(dep_node.pref.ref, dep_node.pref.package_id,
                                       require.package_id_mode)
            if require.build:
                build_data[require] = req_info
            else:
                data[require] = req_info

    reqs_info = RequirementsInfo(data)
    build_requires_info = RequirementsInfo(build_data)
    python_requires = PythonRequiresInfo(python_requires, python_mode)

    conanfile.info = ConanInfo(settings=conanfile.settings.copy_conaninfo_settings(),
                               options=conanfile.options.copy_conaninfo_options(),
                               reqs_info=reqs_info,
                               build_requires_info=build_requires_info,
                               python_requires=python_requires,
                               conf=conanfile.conf.copy_conaninfo_conf())
    conanfile.original_info = conanfile.info.clone()

    if hasattr(conanfile, "validate_build"):
        with conanfile_exception_formatter(conanfile, "validate_build"):
            try:
                conanfile.validate_build()
            except ConanInvalidConfiguration as e:
                # This 'cant_build' will be ignored if we don't have to build the node.
                node.cant_build = str(e)

    run_validate_package_id(conanfile)

    info = conanfile.info
    node.package_id = info.package_id()


def run_validate_package_id(conanfile):
    # IMPORTANT: This validation code must run before calling info.package_id(), to mark "invalid"
    if hasattr(conanfile, "validate"):
        with conanfile_exception_formatter(conanfile, "validate"):
            with conanfile_remove_attr(conanfile, ['cpp_info'], "validate"):
                try:
                    conanfile.validate()
                except ConanInvalidConfiguration as e:
                    conanfile.info.invalid = str(e)

    # Once we are done, call package_id() to narrow and change possible values
    if hasattr(conanfile, "package_id"):
        with conanfile_exception_formatter(conanfile, "package_id"):
            with conanfile_remove_attr(conanfile, ['cpp_info', 'settings', 'options'], "package_id"):
                conanfile.package_id()

    conanfile.info.validate()
