# coding=utf-8

import os
import platform
import unittest

from jinja2 import Template
import textwrap

from conans.test.functional.workspace.scaffolding.package import Package
from conans.test.functional.workspace.scaffolding.templates import workspace_yml_template
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient


class WSTests(unittest.TestCase):
    """
        Dependency graph: packages on lower level depends on those in the upper one.

                +------+      +------+
                | pkgA |      | pkgD |
                +--+---+      +---+--+
                   ^              ^
        +------+   |   +------+   |
        | pkgB +---+---+ pkgC +---+
        +--+---+       +---+--+
           ^               ^
           |               |
           |    +------+   |  +------+
           +----+ pkgE +---+--+ pkgF |
                +------+      +------+
                   ^               ^
                   |               |
                   |    +------+   |
                   +----+ pkgG +---+
                        +------+

    """

    original_output = textwrap.dedent("""\
        > pkgG_exe: default
        > pkgG: default
        \t> pkgE: default
        \t\t> pkgB: default
        \t\t\t> pkgA: default
        \t\t> pkgC: default
        \t\t\t> pkgA: default
        \t\t\t> pkgD: default
        \t> pkgF: default
        \t\t> pkgC: default
        \t\t\t> pkgA: default
        \t\t\t> pkgD: default""")

    @staticmethod
    def _plain_package(client, pkg, lib_requires=None, add_executable=False):
        """ Create a package with only one library that links and uses libraries declared
            in 'lib_requires'. Optionally it adds an executable to the package (the
            executable will link to the library in the same package)
        """
        pkg = Package(name=pkg)
        pkg_lib = pkg.add_library(name=pkg.name)  # TODO: Include components (@danimtb)
        if lib_requires:
            for item in lib_requires:
                library = item.libraries[0]  # There is only one lib per package (wait for Dani)
                pkg_lib.add_link_library(library, generator='cmake')
        if add_executable:
            exec = pkg.add_executable(name="{}_{}".format(pkg.name, "exe"))
            exec.add_link_library(pkg_lib)
        pkg_folder = pkg.render()
        client.run('create "{}" ws/testing'.format(os.path.join(pkg_folder, 'conanfile.py')))
        return pkg

    @classmethod
    def setUpClass(cls):
        super(WSTests, cls).setUpClass()
        folder = temp_folder(path_with_spaces=False)
        cls.base_folder = temp_folder(path_with_spaces=False)

        t = TestClient(current_folder=folder, base_folder=cls.base_folder)
        cls.libA = cls._plain_package(t, pkg="pkgA")
        cls.libD = cls._plain_package(t, pkg="pkgD")
        cls.libB = cls._plain_package(t, pkg="pkgB", lib_requires=[cls.libA, ])
        cls.libC = cls._plain_package(t, pkg="pkgC", lib_requires=[cls.libA, cls.libD])
        cls.libE = cls._plain_package(t, pkg="pkgE", lib_requires=[cls.libB, cls.libC])
        cls.libF = cls._plain_package(t, pkg="pkgF", lib_requires=[cls.libC])
        cls.libG = cls._plain_package(t, pkg="pkgG", lib_requires=[cls.libE, cls.libF], add_executable=True)

        cls.editables = [cls.libA, cls.libB, cls.libE, cls.libG]
        cls.affected_by_editables = [cls.libC, cls.libF]
        cls.inmutable = [cls.libD, ]

    def _reset_cache(self):
        """ In order to return the cache to the original state, it is only needed to revert
            the packages affected by the workspace whose binaries are in the cache
            # TODO: These should be fixed in the future, the cache cannot be poisoned by workspaces
        """
        for it in self.affected_by_editables:
            it.modify_cpp_message("default")

    def run_outside_ws(self):
        """ This function runs the full project without taking into account the ws,
            it should only take into account packages in the cache and those in
            editable mode
        """
        t = TestClient(base_folder=self.base_folder)
        t.save({'conanfile.txt': "[requires]\n{}".format(self.libG.ref)})
        t.run('install conanfile.txt -g virtualrunenv')
        exec = self.libG.executables[0]
        if platform.system() != "Windows":
            t.run_command("bash -c 'source activate_run.sh && {}'".format(exec.name))
        else:
            t.run_command("activate_run.bat && {}.exe".format(exec.name))
        self.assertMultiLineEqual(str(t.out).strip(), self.original_output.strip())

    def test_created_projects(self):
        self.run_outside_ws()

    def test_workspace(self):
        t = TestClient(base_folder=self.base_folder)
        ws_yml = Template(workspace_yml_template).render(editables=self.editables)
        t.save({'ws.yml': ws_yml}, clean_first=True)
        t.run("workspace install ws.yml")

        t.run_command('mkdir build')
        t.run_command('cd build && cmake .. -DCMAKE_MODULE_PATH="{}"'.format(t.current_folder))
        t.run_command('cd build && cmake --build .')
        t.run_command('cd build && ./bin/pkgG_exe')
        self.assertMultiLineEqual(str(t.out).strip(), self.original_output.strip())

        self.libA.modify_cpp_message("Edited!!!")
        t.run_command('cd build && cmake --build .')
        t.run_command('cd build && ./bin/pkgG_exe')
        print(t.out)

        self.fail("test_workspace")
