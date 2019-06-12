# coding=utf-8

import os
import platform
import textwrap
import unittest

from jinja2 import Template
from nose.plugins.attrib import attr

from conans.test.functional.workspace.scaffolding.package import Package
from conans.test.functional.workspace.scaffolding.templates import workspace_yml_template
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient


@attr("slow")
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
           |    +------+   |  +------+      +------+
           +----+ pkgE +---+--+ pkgF |      | pkgH |
                +------+      +------+      +------+
                   ^               ^           ^
                   |               |           |
                   |    +------+   |           |
                   +----+ pkgG +---+-----------+
                        +------+

    """
    maxDiff = None

    original_output = textwrap.dedent("""\
        > pkgG_exe: default
        > pkgG_header: default
        > pkgG: default
        \t> pkgE_header: default
        \t> pkgE: default
        \t\t> pkgB_header: default
        \t\t> pkgB: default
        \t\t\t> pkgA_header: default
        \t\t\t> pkgA: default
        \t\t> pkgC_header: default
        \t\t> pkgC: default
        \t\t\t> pkgA_header: default
        \t\t\t> pkgA: default
        \t\t\t> pkgD_header: default
        \t\t\t> pkgD: default
        \t> pkgF_header: default
        \t> pkgF: default
        \t\t> pkgC_header: default
        \t\t> pkgC: default
        \t\t\t> pkgA_header: default
        \t\t\t> pkgA: default
        \t\t\t> pkgD_header: default
        \t\t\t> pkgD: default
        \t> pkgH_header: default
        \t> pkgH: default""")

    @staticmethod
    def _plain_package(client, pkg, lib_requires=None, add_executable=False,
                       shared=False, version="0.1"):
        """ Create a package with only one library that links and uses libraries declared
            in 'lib_requires'. Optionally it adds an executable to the package (the
            executable will link to the library in the same package)
        """
        pkg = Package(name=pkg, version=version)
        pkg_lib = pkg.add_library(name=pkg.name)  # TODO: Include components (@danimtb)
        if lib_requires:
            for item in lib_requires:
                library = item.libraries[0]  # There is only one lib per package (wait for Dani)
                pkg_lib.add_link_library(library, generator='cmake')
        if add_executable:
            executable = pkg.add_executable(name="{}_{}".format(pkg.name, "exe"))
            executable.add_link_library(pkg_lib)
        pkg.shared = shared
        pkg_folder = pkg.render()
        client.run('create "{}" ws/testing'.format(os.path.join(pkg_folder, 'conanfile.py')))
        return pkg

    def setUp(cls):
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
        cls.libH = cls._plain_package(t, pkg="pkgH")
        cls.libG = cls._plain_package(t, pkg="pkgG", lib_requires=[cls.libE, cls.libF, cls.libH],
                                      add_executable=True)

        executableG = cls.libG.executables[0]
        cls.libG_editable_exe = executableG.path_to_exec()

        cls.editables = [cls.libA, cls.libB, cls.libE, cls.libG]
        cls.affected_by_editables = [cls.libC, cls.libF]
        cls.inmutable = [cls.libD, cls.libH]

    def run_outside_ws(self):
        """ This function runs the full project without taking into account the ws,
            it should only take into account packages in the cache and those in
            editable mode
        """
        t = TestClient(base_folder=self.base_folder)
        t.save({'conanfile.txt': "[requires]\n{}".format(self.libG.ref)})
        t.run('install conanfile.txt -g virtualrunenv')
        executable = self.libG.executables[0]
        if platform.system() != "Windows":
            t.run_command("bash -c 'source activate_run.sh && {}'".format(executable.name))
        else:
            t.run_command("activate_run.bat && {}.exe".format(executable.name))
        self.assertMultiLineEqual(str(t.out).strip(), self.original_output.strip())

    def test_created_projects(self):
        self.run_outside_ws()

    def test_modify_editable(self):
        """ If an editable package is modified, then only the changes into CPP files
            will be reflected because the linking is done in the root project (given
            ABI compatibility).
        """
        t = TestClient(base_folder=self.base_folder)
        ws_yml = Template(workspace_yml_template).render(editables=self.editables)
        t.save({'ws.yml': ws_yml}, clean_first=True)
        t.run("workspace install ws.yml")

        t.run_command('mkdir build')
        t.run_command('cd build && cmake .. -DCMAKE_MODULE_PATH="{}"'.format(t.current_folder))
        t.run_command('cd build && cmake --build .')
        self.assertIn("Built target {}".format(self.libC.name), t.out)
        self.assertIn("Built target {}".format(self.libF.name), t.out)
        t.run_command(self.libG_editable_exe)
        self.assertMultiLineEqual(str(t.out).strip(), self.original_output.strip())

        self.libA.modify_cpp_message("Edited!!!")  # It will change value in cpp and in header file
        t.run_command('cd build && cmake --build .')
        self.assertIn("Built target {}".format(self.libC.name), t.out)
        self.assertIn("Built target {}".format(self.libF.name), t.out)
        t.run_command(self.libG_editable_exe)

        # Check the resulting message with the 'Edited!!!'
        original_output = self.original_output.replace("> pkgA: default",
                                                       "> pkgA: Edited!!!")
        # TODO: FIXME, if pkgC is compiled, then all pkgA_header would have the Edited!!! message.
        original_output = original_output.replace(
            "\t\t> pkgB: default\n\t\t\t> pkgA_header: default",
            "\t\t> pkgB: default\n\t\t\t> pkgA_header: Edited!!!")
        self.assertMultiLineEqual(str(t.out).strip(), original_output)

        # And outside the workspace, everything should behave exactly the same
        self.run_outside_ws()

    def test_editables_shared(self):
        """ All the editable packages are built as shared libs """
        t = TestClient(base_folder=self.base_folder)
        ws_yml = Template(workspace_yml_template).render(editables=self.editables)
        t.save({'ws.yml': ws_yml}, clean_first=True)

        t.run("workspace install ws.yml")
        t.run_command('mkdir build')
        t.run_command('cd build && cmake ..'
                      ' -DCMAKE_MODULE_PATH="{}"'
                      ' -DBUILD_SHARED_LIBS:BOOL=TRUE'
                      ' -DWINDOWS_EXPORT_ALL_SYMBOLS:BOOL=TRUE'
                      ' -DCONAN_CMAKE_POSITION_INDEPENDENT_CODE:BOOL=ON'.format(t.current_folder))
        t.run_command('cd build && cmake --build .')  # TODO: Might need  --clean-first, but better if we control where the ws/build directories are placed.

        # Check that it is building shared libs:
        system = platform.system()
        extension = "dylib" if system == "Darwin" else "so" if system == "Linux" else "dll"
        self.assertIn("pkgA.{}".format(extension), t.out)
        self.assertIn("pkgB.{}".format(extension), t.out)
        self.assertIn("pkgE.{}".format(extension), t.out)
        self.assertIn("pkgG.{}".format(extension), t.out)

        # And it runs!
        t.run_command(self.libG_editable_exe)

        # And libraries are shared!
        original_output = self.original_output
        for it in self.editables:
            original_output = original_output.replace("> {n}: default".format(n=it.name),
                                                      "> {n}: default (shared!)".format(n=it.name))
        self.assertMultiLineEqual(str(t.out).strip(), original_output.strip())

        # Now, if I edit the libA, as it is a shared library, all will get the edition
        self.libA.modify_cpp_message("Edited!!!")  # It will change value in cpp and in header file
        t.run_command('cd build && cmake --build .')
        self.assertIn("Built target {}".format(self.libC.name), t.out)
        self.assertIn("Built target {}".format(self.libF.name), t.out)
        t.run_command(self.libG_editable_exe)

        original_output = original_output.replace("> pkgA: default (shared!)",
                                                  "> pkgA: Edited!!! (shared!)")
        # TODO: FIXME, if pkgC is compiled, then all pkgA_header would have the Edited!!! message.
        original_output = original_output.replace(
            "\t\t> pkgB: default (shared!)\n\t\t\t> pkgA_header: default",
            "\t\t> pkgB: default (shared!)\n\t\t\t> pkgA_header: Edited!!!")
        self.assertMultiLineEqual(str(t.out).strip(), original_output.strip())

        # And outside the workspace, everything should behave exactly the same
        self.run_outside_ws()

    def test_dependents_shared(self):
        """ Packages outside the workspace are shared """
        t = TestClient(base_folder=self.base_folder)
        ws_yml = Template(workspace_yml_template).render(editables=self.editables)
        t.save({'ws.yml': ws_yml}, clean_first=True)

        # Build the shared packages (right now we cannot do it using the workspace command)
        t.run("install {ref} -o {n}:shared=True --build {n}".format(ref=self.libC.ref,
                                                                    n=self.libC.name))
        self.assertIn("{}: Forced build from source".format(self.libC.ref), t.out)

        t.run("install {ref} -o {nC}:shared=True -o {n}:shared=True --build {n}"
              .format(ref=self.libF.ref, n=self.libF.name, nC=self.libC.name))
        self.assertIn("{}: Forced build from source".format(self.libF.ref), t.out)

        t.run("workspace install ws.yml -o pkgF:shared=True -o pkgC:shared=True")
        t.run_command('mkdir build')
        t.run_command('cd build && cmake .. -DCMAKE_MODULE_PATH="{}"'.format(t.current_folder))
        t.run_command('cd build && cmake --build .')

        # And it runs!
        t.run_command(self.libG_editable_exe)
        output_shared = self.original_output.replace("> pkgF: default", "> pkgF: default (shared!)")
        output_shared = output_shared.replace("> pkgC: default", "> pkgC: default (shared!)")
        self.assertMultiLineEqual(str(t.out).strip(), output_shared)

    @unittest.expectedFailure
    def test_several_workspaces(self):
        """ One package is included into two different workspaces with different
            resulting binaries. Those shouldn't mix.
        """
        tmp = TestClient(base_folder=self.base_folder)
        libI = self._plain_package(tmp, pkg="pkgI", lib_requires=[self.libA, self.libD], add_executable=True)
        libI_editable_exe = libI.executables[0].path_to_exec()
        libJ = self._plain_package(tmp, pkg="pkgJ", lib_requires=[self.libA, self.libD], add_executable=True)
        libJ_editable_exe = libJ.executables[0].path_to_exec()

        # Create one workspace
        self.libA.modify_cpp_message("WS-I")
        tI = TestClient(base_folder=self.base_folder)
        ws_yml = Template(workspace_yml_template).render(editables=[self.libA, libI])
        tI.save({'ws.yml': ws_yml}, clean_first=True)
        tI.run("workspace install ws.yml")

        tI.run_command('mkdir build')
        tI.run_command('cd build && cmake ..'
                       ' -DCMAKE_MODULE_PATH="{}"'
                       ' -DBUILD_SHARED_LIBS:BOOL=TRUE'
                       ' -DWINDOWS_EXPORT_ALL_SYMBOLS:BOOL=TRUE'
                       ' -DCONAN_CMAKE_POSITION_INDEPENDENT_CODE:BOOL=ON'.format(tI.current_folder))
        tI.run_command('cd build && cmake --build .')
        tI.run_command(libI_editable_exe)
        pkgI_output = textwrap.dedent("""\
            > pkgI_exe: default
            > pkgI_header: default
            > pkgI: default (shared!)
            \t> pkgA_header: WS-I
            \t> pkgA: WS-I (shared!)
            \t> pkgD_header: default
            \t> pkgD: default
          """)
        self.assertMultiLineEqual(str(tI.out).strip(), pkgI_output.strip())

        # Create the other workspace
        self.libA.modify_cpp_message("WS-J")
        tJ = TestClient(base_folder=self.base_folder)
        ws_yml = Template(workspace_yml_template).render(editables=[self.libA, libJ])
        tJ.save({'ws.yml': ws_yml}, clean_first=True)
        tJ.run("workspace install ws.yml")

        tJ.run_command('mkdir build')
        tJ.run_command('cd build && cmake ..'
                       ' -DCMAKE_MODULE_PATH="{}"'
                       ' -DBUILD_SHARED_LIBS:BOOL=TRUE'
                       ' -DWINDOWS_EXPORT_ALL_SYMBOLS:BOOL=TRUE'
                       ' -DCONAN_CMAKE_POSITION_INDEPENDENT_CODE:BOOL=ON'.format(tJ.current_folder))
        tJ.run_command('cd build && cmake --build .')
        tJ.run_command(libJ_editable_exe)
        pkgJ_output = textwrap.dedent("""\
            > pkgJ_exe: default
            > pkgJ_header: default
            > pkgJ: default (shared!)
            \t> pkgA_header: WS-J
            \t> pkgA: WS-J (shared!)
            \t> pkgD_header: default
            \t> pkgD: default
          """)
        self.assertMultiLineEqual(str(tJ.out).strip(), pkgJ_output.strip())

        # What about the existing WS?
        """ FIXME:
                We are using the same output folder... I demonstrated this behaviour changing
                the sources but it could happen with any option which value is being set
                downstream in the graph.
                
                So I think we should build each workspace into its own folder (by removing the
                NO_OUTPUT_DIRS from the `conan_basic_setup` call), but then it is the WS the
                one that has to compose the layout file.
        """
        tI.run_command(libI_editable_exe)
        self.assertMultiLineEqual(str(tI.out).strip(), pkgI_output.strip())

    def test_version_override(self):
        """ The workspace definition file is able to override dependencies, so we are always
            using the references declared in the workspace file.
        """
        # Create a new version of package A, and recreate B depending on this new one
        t = TestClient(base_folder=self.base_folder)
        newA = self._plain_package(t, pkg=self.libA.name, version="2.0")
        newB = self._plain_package(t, pkg="pkgB", lib_requires=[newA, ])

        t = TestClient(base_folder=self.base_folder)
        editables = [self.libA, newB, self.libE, self.libG]
        ws_yml = Template(workspace_yml_template).render(editables=editables)
        t.save({'ws.yml': ws_yml}, clean_first=True)
        t.run("workspace install ws.yml")

        self.assertIn("WARN: {} requirement {} overridden by your conanfile"
                      " to {}".format(newB.ref, newA.ref, self.libA.ref), t.out)
        self.assertIn("{} from user folder - Editable".format(self.libA.ref), t.out)
