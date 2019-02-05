from nose.plugins.attrib import attr
import os
import platform
import shutil
import tarfile
import textwrap
import unittest
import zipfile

from conans.client.tools import chdir
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, StoppableThreadBottle


@unittest.skipUnless(platform.system() == "Windows", "Only Windows tools")
class WindowsWarningTest(unittest.TestCase):
    """
    Check there are no warnings related to global output and global requester in tools
    """

    def setUp(self):
        conanfile = textwrap.dedent("""
        import os
        import shutil
        
        from conans import ConanFile, tools
        
        class TestConan(ConanFile):
            settings = "os", "build_type", "arch", "compiler"
        
            def build(self):
                tools.vcvars(self.settings)
                tools.vcvars_dict(self.settings)
                tools.vcvars(self.settings)
                tools.build_sln_command(self.settings, "project.sln")
                tools.msvc_build_command(self.settings, "project.sln")
                tools.vswhere()
                tools.vs_comntools("14")
                tools.vs_installation_path("14")
                tools.latest_vs_version_installed()
                tools.run_in_windows_bash(self, "pwd")

                manual_file = os.path.abspath("manual.html")
                with open(manual_file, "w") as fmanual:
                    fmanual.write("content C:/some/PATH/File.txt")
                tools.replace_path_in_file(manual_file, "c:\Some/PATH\File.txt", "C:/file.txt")
        """)
        self.client = TestClient()
        self.client.save({"conanfile.py": conanfile})

    def warning_test(self):
        self.client.run("install .")
        self.client.run("build .")
        self.assertNotIn("Provide the output argument explicitly to function", self.client.out)

    def tearDown(self):
        shutil.rmtree(self.client.current_folder)
        self.client.localdb.connection.close()  # FIXME
        shutil.rmtree(self.client.cache.conan_folder)


@attr("slow")
class DownloadWarningTest(unittest.TestCase):
    """
    Check there are no warnings related to global output and global requester in tools
    """

    def setUp(self):
        from bottle import static_file
        self.http_server = StoppableThreadBottle()
        self.http_server.current_folder = temp_folder()

        with chdir(self.http_server.current_folder):
            zipfile.ZipFile('file.zip', 'w', zipfile.ZIP_DEFLATED).close()
            zip_file = os.path.abspath("file.zip")

        @self.http_server.server.get("/file.zip")
        def get_zip():
            return static_file(os.path.basename(zip_file), os.path.dirname(zip_file))

        with chdir(self.http_server.current_folder):
            tarfile.open("file.tar.gz", "w:gz").close()
            targz_file = os.path.abspath("file.tar.gz")

        @self.http_server.server.get("/file.tar.gz")
        def get_targz():
            return static_file(os.path.basename(targz_file), os.path.dirname(targz_file))

        self.http_server.run_server()

        self.client = TestClient()
        conanfile = textwrap.dedent("""
        import os
        import shutil

        from conans import ConanFile, tools

        class TestConan(ConanFile):
            settings = "os", "build_type", "arch", "compiler"

            def build(self):
                tools.download("http://localhost:{port}/file.zip", "file.zip")
                tools.unzip("file.zip")
                tools.get("http://localhost:{port}/file.tar.gz")  # Uses tools.untargz()
        """)
        self.client.save({"conanfile.py": conanfile.format(port=self.http_server.port)})

    def warning_test(self):
        self.client.run("install .")
        self.client.run("build .")
        self.assertNotIn("Provide the output argument explicitly to function", self.client.out)

    def tearDown(self):
        self.http_server.stop()
        shutil.rmtree(self.http_server.current_folder)
        shutil.rmtree(self.client.current_folder)
        self.client.localdb.connection.close()  # FIXME
        shutil.rmtree(self.client.cache.conan_folder)


class ToolsWarningTest(unittest.TestCase):
    """
    Check there are no warnings related to global output and global requester in tools
    """

    def setUp(self):
        conanfile = textwrap.dedent("""
import os
import shutil

from conans import ConanFile, tools

class TestConan(ConanFile):
    settings = "os", "build_type", "arch", "compiler"

    def build(self):
        tools.cpu_count()
        self.output.info("CONAN_COMPRESSION_LEVEL %s" % tools.get_env("CONAN_COMPRESSION_LEVEL"))
        manual_file = os.path.abspath("manual.html")
        with open(manual_file, "w") as fmanual:
            fmanual.write("this is some content")
        tools.replace_in_file(manual_file, "some content", "something")
        
        tools.md5("this is a string")
        md5 = tools.md5sum(manual_file)
        sha1 = tools.sha1sum(manual_file)
        sha256 = tools.sha256sum(manual_file)
        
        tools.check_md5(manual_file, md5)
        tools.check_with_algorithm_sum("sha1", manual_file, sha1)
        tools.check_sha256(manual_file, sha256)

        with tools.environment_append({"PATH": None}):
            self.output.info("PATH: %s" % tools.get_env("PATH"))
            
        self.output.info("human size: %s" % tools.human_size(1024))
        self.output.info("cross-building: %s" % tools.cross_building(self.settings))
        tools.get_gnu_triplet(self.settings.get_safe("os"), self.settings.get_safe("arch"), 
                              self.settings.get_safe("compiler"))
        tools.get_cased_path(os.path.abspath(os.curdir))
        tools.remove_from_path("fake")
        path = os.path.abspath(os.curdir)
        tools.unix_path(os.path.abspath(os.curdir))
        tools.escape_windows_cmd("cmd fake")
        tools.save("filename.pc", "prefix=/jiowcsjld/fwojclsad")
        tools.replace_prefix_in_pc_file("filename.pc", "my_path")
        tools.unix2dos("filename.pc")
        tools.dos2unix("filename.pc")
        tools.touch("filename.pc")
        tools.mkdir("folder")
        tools.relative_dirs("folder")
        tools.apple_dot_clean("folder")
        tools.rmdir("folder")
        tools.which("cmake")

        if tools.is_apple_os(self.settings.os):
            tools.apple_sdk_name(self.settings)
            tools.apple_deployment_target_env(self.settings.os, "9.0")
            tools.apple_deployment_target_flag(self.settings.os, "9.0")
        tools.to_apple_arch("armv8_32")

        tools.collect_libs(self, "folder")

        with tools.run_environment(self):
            self.output.info("")

        tools.detected_architecture()
        tools.args_to_string(["one", "two"])
        tools.get_cross_building_settings(self.settings)
        """)
        self.client = TestClient()
        self.client.save({"conanfile.py": conanfile})

    def warning_test(self):
        self.client.run("install .")
        self.client.run("build .")
        self.assertNotIn("Provide the output argument explicitly to function", self.client.out)
        self.assertIn("CONAN_COMPRESSION_LEVEL 9", self.client.out)
        self.assertIn("this is something C:/file.txt", self.client.out)
        self.assertIn("PATH: None", self.client.out)
        self.assertIn("human size: 1.0KB", self.client.out)
        self.assertIn("cross-building: False", self.client.out)

    def tearDown(self):
        shutil.rmtree(self.client.current_folder)
        self.client.localdb.connection.close()  # FIXME
        shutil.rmtree(self.client.cache.conan_folder)
