"""Pylint plugin for ConanFile"""
import astroid
from astroid import MANAGER


def register(linter):
    """Declare package as plugin

    This function needs to be declared so astroid treats
    current file as a plugin.
    """
    pass


def transform_conanfile(node):
    """Transform definition of ConanFile class so dynamic fields are visible to pylint"""

    str_class = astroid.builtin_lookup("str")
    info_class = MANAGER.ast_from_module_name("conans.model.info").lookup(
        "ConanInfo")
    build_requires_class = MANAGER.ast_from_module_name(
        "conans.client.graph.graph_manager").lookup("_RecipeBuildRequires")
    file_copier_class = MANAGER.ast_from_module_name(
        "conans.client.file_copier").lookup("FileCopier")
    file_importer_class = MANAGER.ast_from_module_name(
        "conans.client.importer").lookup("_FileImporter")
    python_requires_class = MANAGER.ast_from_module_name(
        "conans.client.graph.python_requires").lookup("PyRequires")

    dynamic_fields = {
        "source_folder": str_class,
        "build_folder": str_class,
        "package_folder": str_class,
        "install_folder": str_class,
        "conan_data": str_class,
        "build_requires": build_requires_class,
        "info_build": info_class,
        "info": info_class,
        "copy": file_copier_class,
        "copy_deps": file_importer_class,
        "python_requires": [str_class, python_requires_class],
    }

    for f, t in dynamic_fields.items():
        node.locals[f] = [t]


MANAGER.register_transform(
    astroid.ClassDef, transform_conanfile,
    lambda node: node.qname() == "conans.model.conan_file.ConanFile")


def _python_requires_member():
    return astroid.parse("""
        from conans.client.graph.python_requires import ConanPythonRequire
        python_requires = ConanPythonRequire()
        """)


astroid.register_module_extender(astroid.MANAGER, "conans", _python_requires_member)
