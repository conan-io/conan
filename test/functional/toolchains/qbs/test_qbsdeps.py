
import pytest

import textwrap

from conan.test.assets.sources import gen_function_cpp
from conan.test.utils.tools import TestClient
from jinja2 import Template


def gen_qbs_application(**context):
    qbsfile = textwrap.dedent('''
        CppApplication {
            files: [{% for s in files %} "{{s}}", {% endfor %}]
            {% for d in deps %}
            Depends {
                name: "{{d}}"
            }
            {% endfor %}
            qbsModuleProviders: ["conan"]
        }
    ''')

    t = Template(qbsfile)
    return t.render(**context)


@pytest.mark.tool("qbs")
def test_qbsdeps_with_test_requires_header_only():
    client = TestClient()
    with client.chdir("lib"):
        conanfile = textwrap.dedent('''
            from conan import ConanFile
            from conan.tools.files import copy
            import os
            class Recipe(ConanFile):
                exports_sources = ("hello.h")
                version = '0.1.0'
                name = 'hello'
                def package(self):
                    copy(self,
                         "hello.h",
                         src=self.source_folder,
                         dst=os.path.join(self.package_folder, "include"))
        ''')
        header = textwrap.dedent('''
            #pragma once
            inline int hello() { return 0; }
        ''')
        client.save({
            'conanfile.py': conanfile,
            'hello.h': header
        })
        client.run('create .')

    conanfile = textwrap.dedent('''
        from conan import ConanFile
        class Recipe(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "QbsDeps"
            def requirements(self):
                self.requires('hello/0.1.0')
        ''')
    client.save({
        "conanfile.py": conanfile,
        "main.cpp": gen_function_cpp(name="main", includes=["hello"], calls=["hello"]),
        "app.qbs": gen_qbs_application(files=["main.cpp"], deps=["hello"]),
    }, clean_first=True)
    client.run("install .")
    client.run_command("qbs build moduleProviders.conan.installDirectory:.")


@pytest.mark.tool("qbs")
def test_qbsdeps_with_test_requires_lib():
    client = TestClient()
    with client.chdir("lib"):
        client.run("new qbs_lib -d name=hello -d version=1.0")
        client.run("create . -tf=\"\"")

    conanfile = textwrap.dedent('''
        from conan import ConanFile
        class Recipe(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "QbsDeps"
            def requirements(self):
                self.requires('hello/1.0')
        ''')
    client.save({
        "conanfile.py": conanfile,
        "main.cpp": gen_function_cpp(name="main", includes=["hello"], calls=["hello"]),
        "app.qbs": gen_qbs_application(files=["main.cpp"], deps=["hello"]),
    }, clean_first=True)
    client.run("install .")
    client.run_command("qbs build moduleProviders.conan.installDirectory:.")


@pytest.mark.tool("qbs")
def test_qbsdeps_with_qbs_toolchain():
    client = TestClient()
    with client.chdir("lib"):
        client.run("new qbs_lib -d name=hello -d version=1.0")
        client.run("create . -tf=\"\"")

    conanfile = textwrap.dedent('''
        from conan import ConanFile
        from conan.tools.qbs import Qbs

        class Recipe(ConanFile):
            name = "app"
            version = "1.2"
            exports_sources = "*.cpp", "*.h", "*.qbs"
            settings = "os", "compiler", "build_type", "arch"
            generators = "QbsDeps"

            def requirements(self):
                self.requires("hello/1.0")

            def layout(self):
                self.folders.generators = "generators"

            def build(self):
                qbs = Qbs(self)
                qbs.resolve()
                qbs.build()

            def install(self):
                qbs = Qbs(self)
                qbs.install()
        ''')
    client.save({
        "conanfile.py": conanfile,
        "main.cpp": gen_function_cpp(name="main", includes=["hello"], calls=["hello"]),
        "app.qbs": gen_qbs_application(files=["main.cpp"], deps=["hello"]),
    }, clean_first=True)
    client.run("create .")
