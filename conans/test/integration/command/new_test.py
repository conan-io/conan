import os
import textwrap
import unittest

from parameterized import parameterized

from conans import __version__ as client_version
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.tools import save
from conans.util.files import load


class NewCommandTest(unittest.TestCase):

    def test_template(self):
        client = TestClient()
        template1 = textwrap.dedent("""
            class {{package_name}}Conan(ConanFile):
                name = "{{name}}"
                version = "{{version}}"
                conan_version = "{{conan_version}}"
        """)
        save(os.path.join(client.cache_folder, "templates/mytemplate.py"), template1)
        client.run("new hello/0.1 --template=mytemplate.py")
        conanfile = client.load("conanfile.py")
        self.assertIn("class HelloConan(ConanFile):", conanfile)
        self.assertIn('name = "hello"', conanfile)
        self.assertIn('version = "0.1"', conanfile)
        self.assertIn('conan_version = "{}"'.format(client_version), conanfile)

    def test_template_custom_definitions(self):
        client = TestClient()
        template1 = textwrap.dedent("""
            class {{package_name}}Conan(ConanFile):
                name = "{{name}}"
                version = "{{version}}"
                conan_version = "{{conan_version}}"
                license = "{{license}}"
                homepage = "{{homepage}}"
        """)
        save(os.path.join(client.cache_folder, "templates/mytemplate.py"), template1)
        client.run("new hello/0.1 --template=mytemplate.py "
                   "-d license=MIT -d homepage=http://example.com")
        conanfile = client.load("conanfile.py")
        self.assertIn("class HelloConan(ConanFile):", conanfile)
        self.assertIn('name = "hello"', conanfile)
        self.assertIn('version = "0.1"', conanfile)
        self.assertIn('conan_version = "{}"'.format(client_version), conanfile)
        self.assertIn('license = "MIT"', conanfile)
        self.assertIn('homepage = "http://example.com"', conanfile)

    def test_template_dir(self):
        client = TestClient()
        template_dir = "templates/command/new/t_dir"
        template_recipe = textwrap.dedent("""
            class {{package_name}}Conan(ConanFile):
                name = "{{name}}"
                version = "{{version}}"
                conan_version = "{{conan_version}}"
        """)
        save(os.path.join(client.cache_folder, template_dir + "/conanfile.py"), template_recipe)

        template_txt = textwrap.dedent("""
            package_name={{package_name}}
            name={{name}}
            version={{version}}
            conan_version={{conan_version}}
        """)
        save(os.path.join(client.cache_folder, template_dir + "/{{name}}/hello.txt"), template_txt)

        client.run("new hello/0.1 --template=t_dir")
        conanfile = client.load("conanfile.py")
        self.assertIn("class HelloConan(ConanFile):", conanfile)
        self.assertIn('name = "hello"', conanfile)
        self.assertIn('version = "0.1"', conanfile)
        self.assertIn('conan_version = "{}"'.format(client_version), conanfile)

        hellotxt = client.load("hello/hello.txt")
        self.assertIn("package_name=Hello", hellotxt)
        self.assertIn("name=hello", hellotxt)
        self.assertIn('version=0.1', hellotxt)
        self.assertIn("conan_version={}".format(client_version), hellotxt)

    def test_template_test_package(self):
        client = TestClient()
        template2 = textwrap.dedent("""
            class {{package_name}}Conan(ConanFile):
                version = "fixed"
        """)
        save(os.path.join(client.cache_folder, "templates", "subfolder", "mytemplate.py"),
             template2)
        client.run("new hello/0.1 -m=subfolder/mytemplate.py")
        conanfile = client.load("conanfile.py")
        self.assertIn("class HelloConan(ConanFile):", conanfile)
        self.assertIn('version = "fixed"', conanfile)

    def test_template_abs_path_test_package(self):
        client = TestClient()
        template2 = textwrap.dedent("""
            class {{package_name}}Conan(ConanFile):
                version = "fixed"
        """)
        tmp = temp_folder()
        full_path = os.path.join(tmp, "templates", "subfolder", "mytemplate.py")
        save(full_path, template2)
        client.run('new hello/0.1 --template="%s"' % full_path)
        conanfile = client.load("conanfile.py")
        self.assertIn("class HelloConan(ConanFile):", conanfile)
        self.assertIn('version = "fixed"', conanfile)

    def test_template_errors(self):
        client = TestClient()
        client.run("new hello/0.1 -m=mytemplate.py", assert_error=True)
        self.assertIn("ERROR: Template doesn't exist", client.out)
        client.run("new hello/0.1 -m=mytemplate", assert_error=True)
        self.assertIn("ERROR: Template doesn't exist", client.out)
        client.run("new hello/0.1 --template=mytemplate.py --bare", assert_error=True)
        self.assertIn("ERROR: 'template' is incompatible", client.out)
        client.run("new hello/0.1 --template", assert_error=True)
        self.assertIn("ERROR: Exiting with code: 2", client.out)

    def test_new(self):
        client = TestClient()
        client.run('new MyPackage/1.3@myuser/testing -t')
        root = client.current_folder
        self.assertTrue(os.path.exists(os.path.join(root, "conanfile.py")))
        content = load(os.path.join(root, "conanfile.py"))
        self.assertIn('name = "MyPackage"', content)
        self.assertIn('version = "1.3"', content)
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/conanfile.py")))
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/CMakeLists.txt")))
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/example.cpp")))
        # assert they are correct at least
        client.run("export . myuser/testing")
        client.run("search")
        self.assertIn("MyPackage/1.3@myuser/testing", client.out)

    def test_new_error(self):
        """ packages with short name
        """
        client = TestClient()
        client.run('new A/1.3@myuser/testing', assert_error=True)
        self.assertIn("ERROR: Value provided for package name, 'A' (type str), is too short. Valid "
                      "names must contain at least 2 characters.", client.out)
        client.run('new A2/1.3@myuser/u', assert_error=True)
        self.assertIn("ERROR: Value provided for channel, 'u' (type str), is too short. Valid "
                      "names must contain at least 2 characters.", client.out)

    @parameterized.expand([("My-Package", "MyPackage"),
                           ("my-package", "MyPackage"),
                           ("my_package", "MyPackage"),
                           ("my.Package", "MyPackage"),
                           ("my+package", "MyPackage")])
    def test_naming(self, package_name, python_class_name):
        """ packages with dash
        """
        client = TestClient()
        client.run('new {}/1.3@myuser/testing -t'.format(package_name))
        root = client.current_folder
        self.assertTrue(os.path.exists(os.path.join(root, "conanfile.py")))
        content = load(os.path.join(root, "conanfile.py"))
        self.assertIn('class {}Conan(ConanFile):'.format(python_class_name), content)
        self.assertIn('name = "{}"'.format(package_name), content)
        self.assertIn('version = "1.3"', content)
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/conanfile.py")))
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/CMakeLists.txt")))
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/example.cpp")))
        # assert they are correct at least
        client.run("export . myuser/testing")
        client.run("search")
        self.assertIn("{}/1.3@myuser/testing".format(package_name), client.out)

    def test_new_header(self):
        client = TestClient()
        client.run('new MyPackage/1.3 -t -i')
        root = client.current_folder
        self.assertTrue(os.path.exists(os.path.join(root, "conanfile.py")))
        content = load(os.path.join(root, "conanfile.py"))
        self.assertIn('name = "MyPackage"', content)
        self.assertIn('version = "1.3"', content)
        self.assertIn('topics = (', content)
        self.assertNotIn('homepage', content)
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/conanfile.py")))
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/CMakeLists.txt")))
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/example.cpp")))
        # assert they are correct at least
        client.run("export . myuser/testing")
        client.run("search")
        self.assertIn("MyPackage/1.3@myuser/testing", client.out)

    def test_new_sources(self):
        client = TestClient()
        client.run('new MyPackage/1.3@myuser/testing -t -s')
        root = client.current_folder
        self.assertTrue(os.path.exists(os.path.join(root, "conanfile.py")))
        content = load(os.path.join(root, "conanfile.py"))
        self.assertIn('name = "MyPackage"', content)
        self.assertIn('version = "1.3"', content)
        self.assertIn('exports_sources', content)
        self.assertIn('topics = (', content)
        self.assertNotIn('homepage', content)
        self.assertNotIn('source()', content)
        # assert they are correct at least
        client.run("export . myuser/testing")
        client.run("search")
        self.assertIn("MyPackage/1.3@myuser/testing", client.out)

    def test_new_purec(self):
        client = TestClient()
        client.run('new MyPackage/1.3@myuser/testing -c -t --source')
        root = client.current_folder
        self.assertTrue(os.path.exists(os.path.join(root, "conanfile.py")))
        content = load(os.path.join(root, "conanfile.py"))
        self.assertIn('name = "MyPackage"', content)
        self.assertIn('version = "1.3"', content)
        self.assertIn('topics = (', content)
        self.assertNotIn('homepage', content)
        # assert they are correct at least
        client.run("export . myuser/testing")
        client.run("search")
        self.assertIn("MyPackage/1.3@myuser/testing", client.out)

    def test_new_without(self):
        client = TestClient()
        client.run('new MyPackage/1.3@myuser/testing')
        root = client.current_folder
        self.assertTrue(os.path.exists(os.path.join(root, "conanfile.py")))
        self.assertFalse(os.path.exists(os.path.join(root, "test_package/conanfile.py")))
        self.assertFalse(os.path.exists(os.path.join(root, "test_package/CMakeLists.txt")))
        self.assertFalse(os.path.exists(os.path.join(root, "test_package/example.cpp")))

    def test_new_ci(self):
        client = TestClient()
        client.run('new MyPackage/1.3@myuser/testing -cis -ciw -cilg -cilc -cio -ciglg -ciglc '
                   '-ciccg -ciccc -cicco -ciu=myurl')
        root = client.current_folder
        build_py = load(os.path.join(root, "build.py"))
        self.assertIn('builder.add_common_builds(shared_option_name="MyPackage:shared")',
                      build_py)
        self.assertNotIn('visual_versions=', build_py)
        self.assertNotIn('gcc_versions=', build_py)
        self.assertNotIn('clang_versions=', build_py)
        self.assertNotIn('apple_clang_versions=', build_py)
        self.assertNotIn('gitlab_gcc_versions=', build_py)
        self.assertNotIn('gitlab_clang_versions=', build_py)
        self.assertNotIn('circleci_gcc_versions=', build_py)
        self.assertNotIn('circleci_clang_versions=', build_py)
        self.assertNotIn('circleci_osx_versions=', build_py)

        appveyor = load(os.path.join(root, "appveyor.yml"))
        self.assertIn("CONAN_UPLOAD: \"myurl\"", appveyor)
        self.assertIn('CONAN_REFERENCE: "MyPackage/1.3"', appveyor)
        self.assertIn('CONAN_USERNAME: "myuser"', appveyor)
        self.assertIn('CONAN_CHANNEL: "testing"', appveyor)
        self.assertIn(r'PYTHON: "C:\\Python37"', appveyor)
        self.assertIn('CONAN_VISUAL_VERSIONS: 12', appveyor)
        self.assertIn('CONAN_VISUAL_VERSIONS: 14', appveyor)
        self.assertIn('CONAN_VISUAL_VERSIONS: 15', appveyor)

        travis = load(os.path.join(root, ".travis.yml"))
        self.assertIn("- CONAN_UPLOAD: \"myurl\"", travis)
        self.assertIn('- CONAN_REFERENCE: "MyPackage/1.3"', travis)
        self.assertIn('- CONAN_USERNAME: "myuser"', travis)
        self.assertIn('- CONAN_CHANNEL: "testing"', travis)
        self.assertIn('env: CONAN_GCC_VERSIONS=5 CONAN_DOCKER_IMAGE=conanio/gcc5',
                      travis)

        gitlab = load(os.path.join(root, ".gitlab-ci.yml"))
        self.assertIn("CONAN_UPLOAD: \"myurl\"", gitlab)
        self.assertIn('CONAN_REFERENCE: "MyPackage/1.3"', gitlab)
        self.assertIn('CONAN_USERNAME: "myuser"', gitlab)
        self.assertIn('CONAN_CHANNEL: "testing"', gitlab)
        self.assertIn('CONAN_GCC_VERSIONS: "5"', gitlab)

        circleci = load(os.path.join(root, ".circleci", "config.yml"))
        self.assertIn("CONAN_UPLOAD: \"myurl\"", circleci)
        self.assertIn('CONAN_REFERENCE: "MyPackage/1.3"', circleci)
        self.assertIn('CONAN_USERNAME: "myuser"', circleci)
        self.assertIn('CONAN_CHANNEL: "testing"', circleci)
        self.assertIn('CONAN_GCC_VERSIONS: "5"', circleci)

    def test_new_ci_partial(self):
        client = TestClient()
        root = client.current_folder
        client.run('new MyPackage/1.3@myuser/testing -cis', assert_error=True)

        client.run('new MyPackage/1.3@myuser/testing -cilg')
        self.assertTrue(os.path.exists(os.path.join(root, "build.py")))
        self.assertTrue(os.path.exists(os.path.join(root, ".travis.yml")))
        self.assertTrue(os.path.exists(os.path.join(root, ".travis/install.sh")))
        self.assertTrue(os.path.exists(os.path.join(root, ".travis/run.sh")))
        self.assertFalse(os.path.exists(os.path.join(root, "appveyor.yml")))
        self.assertFalse(os.path.exists(os.path.join(root, ".gitlab-ci.yml")))
        self.assertFalse(os.path.exists(os.path.join(root, ".circleci/config.yml")))

        client = TestClient()
        root = client.current_folder
        client.run('new MyPackage/1.3@myuser/testing -ciw')
        self.assertTrue(os.path.exists(os.path.join(root, "build.py")))
        self.assertFalse(os.path.exists(os.path.join(root, ".travis.yml")))
        self.assertFalse(os.path.exists(os.path.join(root, ".travis/install.sh")))
        self.assertFalse(os.path.exists(os.path.join(root, ".travis/run.sh")))
        self.assertTrue(os.path.exists(os.path.join(root, "appveyor.yml")))
        self.assertFalse(os.path.exists(os.path.join(root, ".gitlab-ci.yml")))
        self.assertFalse(os.path.exists(os.path.join(root, ".circleci/config.yml")))

        client = TestClient()
        root = client.current_folder
        client.run('new MyPackage/1.3@myuser/testing -cio')
        self.assertTrue(os.path.exists(os.path.join(root, "build.py")))
        self.assertTrue(os.path.exists(os.path.join(root, ".travis.yml")))
        self.assertTrue(os.path.exists(os.path.join(root, ".travis/install.sh")))
        self.assertTrue(os.path.exists(os.path.join(root, ".travis/run.sh")))
        self.assertFalse(os.path.exists(os.path.join(root, "appveyor.yml")))
        self.assertFalse(os.path.exists(os.path.join(root, ".gitlab-ci.yml")))
        self.assertFalse(os.path.exists(os.path.join(root, ".circleci/config.yml")))

        client = TestClient()
        root = client.current_folder
        client.run('new MyPackage/1.3@myuser/testing -gi')
        self.assertTrue(os.path.exists(os.path.join(root, ".gitignore")))

        client = TestClient()
        root = client.current_folder
        client.run('new MyPackage/1.3@myuser/testing -ciglg')
        self.assertTrue(os.path.exists(os.path.join(root, "build.py")))
        self.assertTrue(os.path.exists(os.path.join(root, ".gitlab-ci.yml")))
        self.assertFalse(os.path.exists(os.path.join(root, ".travis.yml")))
        self.assertFalse(os.path.exists(os.path.join(root, ".travis/install.sh")))
        self.assertFalse(os.path.exists(os.path.join(root, ".travis/run.sh")))
        self.assertFalse(os.path.exists(os.path.join(root, "appveyor.yml")))
        self.assertFalse(os.path.exists(os.path.join(root, ".circleci/config.yml")))

        client = TestClient()
        root = client.current_folder
        client.run('new MyPackage/1.3@myuser/testing -ciglc')
        self.assertTrue(os.path.exists(os.path.join(root, "build.py")))
        self.assertTrue(os.path.exists(os.path.join(root, ".gitlab-ci.yml")))
        self.assertFalse(os.path.exists(os.path.join(root, ".travis.yml")))
        self.assertFalse(os.path.exists(os.path.join(root, ".travis/install.sh")))
        self.assertFalse(os.path.exists(os.path.join(root, ".travis/run.sh")))
        self.assertFalse(os.path.exists(os.path.join(root, "appveyor.yml")))
        self.assertFalse(os.path.exists(os.path.join(root, ".circleci/config.yml")))

        client = TestClient()
        root = client.current_folder
        client.run('new MyPackage/1.3@myuser/testing -ciccg')
        self.assertTrue(os.path.exists(os.path.join(root, "build.py")))
        self.assertTrue(os.path.exists(os.path.join(root, ".circleci/config.yml")))
        self.assertTrue(os.path.exists(os.path.join(root, ".circleci/install.sh")))
        self.assertTrue(os.path.exists(os.path.join(root, ".circleci/run.sh")))
        self.assertFalse(os.path.exists(os.path.join(root, ".gitlab-ci.yml")))
        self.assertFalse(os.path.exists(os.path.join(root, ".travis.yml")))
        self.assertFalse(os.path.exists(os.path.join(root, ".travis/install.sh")))
        self.assertFalse(os.path.exists(os.path.join(root, ".travis/run.sh")))
        self.assertFalse(os.path.exists(os.path.join(root, "appveyor.yml")))

        client = TestClient()
        root = client.current_folder
        client.run('new MyPackage/1.3@myuser/testing -ciccc')
        self.assertTrue(os.path.exists(os.path.join(root, "build.py")))
        self.assertTrue(os.path.exists(os.path.join(root, ".circleci/config.yml")))
        self.assertTrue(os.path.exists(os.path.join(root, ".circleci/install.sh")))
        self.assertTrue(os.path.exists(os.path.join(root, ".circleci/run.sh")))
        self.assertFalse(os.path.exists(os.path.join(root, ".gitlab-ci.yml")))
        self.assertFalse(os.path.exists(os.path.join(root, ".travis.yml")))
        self.assertFalse(os.path.exists(os.path.join(root, ".travis/install.sh")))
        self.assertFalse(os.path.exists(os.path.join(root, ".travis/run.sh")))
        self.assertFalse(os.path.exists(os.path.join(root, "appveyor.yml")))

    def test_new_test_package_custom_name(self):
        # https://github.com/conan-io/conan/issues/8164
        client = TestClient()
        client.run("new mypackage/0.1 -t")
        source = client.load("test_package/example.cpp")
        self.assertIn('#include "hello.h"', source)
        self.assertIn("hello();", source)

    def test_new_cmake_lib(self):
        client = TestClient()
        client.run("new pkg/0.1 --template=cmake_lib")
        conanfile = client.load("conanfile.py")
        self.assertIn("CMakeToolchain", conanfile)
        conanfile = client.load("test_package/conanfile.py")
        self.assertIn("CMakeToolchain", conanfile)
        cmake = client.load("test_package/CMakeLists.txt")
        self.assertIn("find_package", cmake)

    def test_new_reference(self):
        client = TestClient()
        # full reference
        client.run("new MyPackage/1.3@myuser/testing --template=cmake_lib")
        conanfile = client.load("conanfile.py")
        self.assertIn('name = "MyPackage"', conanfile)
        self.assertIn('version = "1.3"', conanfile)
        # no username, no channel (with @)
        client.run("new MyPackage/1.3@ --template=cmake_lib")
        conanfile = client.load("conanfile.py")
        self.assertIn('version = "1.3"', conanfile)
        self.assertIn('name = "MyPackage"', conanfile)
        # no username, no channel (without @)
        client.run("new MyPackage/1.3 --template=cmake_lib")
        conanfile = client.load("conanfile.py")
        self.assertIn('name = "MyPackage"', conanfile)
        self.assertIn('version = "1.3"', conanfile)
