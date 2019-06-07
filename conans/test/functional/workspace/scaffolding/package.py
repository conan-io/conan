# coding=utf-8

import os
from collections import namedtuple, defaultdict

from jinja2 import Template

from conans.test.functional.workspace.scaffolding.templates import conanfile_template, \
    cmakelists_template, lib_cpp_template, lib_h_template, main_cpp_template, layout_template
from conans.test.utils.test_files import temp_folder


class _Library:
    Requirement = namedtuple("Requirement", ["name", "target"])

    def __init__(self, name, package):
        self.package = package
        self.name = name
        self.target = name
        self._requires = set()

    def add_link_library(self, other, generator=None):
        assert isinstance(other, _Library), "type(other)={}".format(type(other))
        if other.package == self.package:
            # Generator makes no sense for the same package, it always be the naked target
            self._requires.add(self.Requirement(other.name, other.target))
        else:
            if generator == 'cmake':
                self._requires.add(self.Requirement(other.name, "CONAN_PKG::{}".format(other.package.name)))
            elif generator == 'cmake_find_packages':
                self._requires.add(
                    self.Requirement(other.name, "{pkg}::{pkg}".format(pkg=other.package.name)))
            else:
                raise RuntimeError("Generator '{}' not expected".format(generator))
            self.package._add_requires(other.package, generator=generator)

    def __str__(self):
        return self.name

    @property
    def requires(self):
        return sorted(self._requires, key=lambda u: u.name)


class Package:
    def __init__(self, name, version="0.1", user="ws", channel="testing"):
        self.name = name
        self.version = version
        self.user = user
        self.channel = channel
        self._requires = set()
        self._libraries = []
        self._executables = []
        self.shared = False

        self.generators = defaultdict(set)

        self._directory = None

    @property
    def local_path(self):
        return self._directory

    @property
    def ref(self):
        return "{}/{}@{}/{}".format(self.name, self.version, self.user, self.channel)

    @property
    def requires(self):
        return sorted(self._requires, key=lambda u: u.name)

    @property
    def libraries(self):
        return sorted(self._libraries, key=lambda u: u.name)

    @property
    def executables(self):
        return sorted(self._executables, key=lambda u: u.name)

    @property
    def layout_file(self):
        return os.path.join(self.local_path, 'layout')

    def add_library(self, **data):
        lib = _Library(package=self, **data)
        self._libraries.append(lib)
        return lib

    def add_executable(self, **data):
        exe = _Library(package=self, **data)
        self._executables.append(exe)
        return exe

    def _add_requires(self, requirement, generator):
        assert isinstance(requirement, Package), "type(requirement)={}".format(type(requirement))
        self._requires.add(requirement)
        self.generators[generator].add(requirement)

    @staticmethod
    def _render_template(template_content, output_filename, **context):
        t = Template(template_content)
        output = t.render(**context)
        with open(output_filename, 'w') as f:
            f.write(output)
        return output_filename

    def modify_cpp_message(self, message=None):
        for library in self._libraries:
            library_dir = os.path.join(self._directory, library.name)
            self._render_template(lib_cpp_template,
                                  os.path.join(library_dir, 'lib.cpp'),
                                  package=self, library=library, message=message)

    def render(self, output_folder=None):
        self._directory = output_folder or os.path.join(temp_folder(False), self.name)
        os.makedirs(self._directory)
        self._render_template(conanfile_template,
                              os.path.join(self._directory, 'conanfile.py'),
                              package=self)
        self._render_template(cmakelists_template,
                              os.path.join(self._directory, 'CMakeLists.txt'),
                              package=self)
        self._render_template(layout_template, self.layout_file, package=self)
        for library in self._libraries:
            library_dir = os.path.join(self._directory, library.name)
            os.makedirs(library_dir)
            self._render_template(lib_h_template,
                                  os.path.join(library_dir, 'lib.h'),
                                  package=self, library=library)
            self._render_template(lib_cpp_template,
                                  os.path.join(library_dir, 'lib.cpp'),
                                  package=self, library=library)
        for executable in self._executables:
            executable_dir = os.path.join(self._directory, executable.name)
            os.makedirs(executable_dir, exist_ok=True)
            self._render_template(main_cpp_template,
                                  os.path.join(executable_dir, 'main.cpp'),
                                  package=self, executable=executable)
        return self._directory


if __name__ == "__main__":
    # Clean output folder
    import shutil
    me = os.path.dirname(__file__)
    output_folder = os.path.join(me, "_tmp")
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)
    os.makedirs(output_folder)

    # Package 1
    pkg1 = Package(name="pkg1")
    lib1 = pkg1.add_library(name="lib1")
    lib2 = pkg1.add_library(name="lib2")
    lib2.add_link_library(lib1)
    exe1 = pkg1.add_executable(name="exe1")
    exe1.add_link_library(lib1)
    pkg1.render(os.path.join(output_folder, pkg1.name))

    # Package 2
    pkg2 = Package(name="pkg2")
    pkg2_lib1 = pkg2.add_library(name="pkg2_lib1")
    pkg2_lib1.add_link_library(lib1, generator='cmake')
    pkg2_exe1 = pkg2.add_executable(name="pkg2_exe1")
    pkg2_exe1.add_link_library(pkg2_lib1)
    pkg2.render(os.path.join(output_folder, pkg2.name))

