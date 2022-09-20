"""Pylint plugin for ConanFile"""
import re

import astroid
from astroid import MANAGER
from pylint.checkers import BaseChecker
from pylint.interfaces import IRawChecker


def register(linter):
    """required method to auto register this checker"""
    linter.register_checker(ConanDeprecatedImportsChecker(linter))


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
        "conan_data": str_class,
        "build_requires": build_requires_class,
        "info_build": info_class,
        "info": info_class,
        "copy": file_copier_class,
        "copy_deps": file_importer_class,
        "python_requires": [str_class, python_requires_class],
        "recipe_folder": str_class,
    }

    for f, t in dynamic_fields.items():
        node.locals[f] = [i for i in t]


MANAGER.register_transform(
    astroid.ClassDef, transform_conanfile,
    lambda node: node.qname() == "conans.model.conan_file.ConanFile")


def _python_requires_member():
    return astroid.parse("""
        from conans.client.graph.python_requires import ConanPythonRequire
        python_requires = ConanPythonRequire()
        """)


astroid.register_module_extender(astroid.MANAGER, "conans", _python_requires_member)


class ConanDeprecatedImportsChecker(BaseChecker):
    """
    Check "from conans*" imports which disappears in Conan 2.x. Only "from conan*" is valid
    """

    __implements__ = IRawChecker

    deprecated_imports_pattern = re.compile(r"(from|import)\s+conans[\.|\s].*")
    name = "conan_deprecated_imports"
    msgs = {
        "E9000": (
            "Using deprecated imports from 'conans'. Check migration guide at https://docs.conan.io/en/latest/conan_v2.html",
            "conan1.x-deprecated-imports",
            (
                "Use imports from 'conan' instead of 'conans'"
                " because 'conan' will be the root package for Conan 2.x"
            )
        )
    }
    options = ()

    def process_module(self, node):
        """
        Processing the module's content that is accessible via node.stream() function
        """
        with node.stream() as stream:
            for (index, line) in enumerate(stream):
                if self.deprecated_imports_pattern.match(line.decode('utf-8')):
                    self.add_message("conan1.x-deprecated-imports", line=index + 1)
