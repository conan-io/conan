import textwrap
import unittest

from conans.test.utils.tools import TestClient


class PythonProfilesTest(unittest.TestCase):

    def test_python_profile_create(self):
        client = TestClient()
        profile_content = textwrap.dedent("""
            import os


            settings = {
                 "os": "Windows",
                 "compiler": "Visual Studio",
                 "compiler.version": "16",
                }
            options = {"shared": "2"}
            env = {"pkg:env_var": "bar"}
            cxxflags = os.environ.get('HOME', "")
            if (cxxflags):
                env['CXXFLAGS'] = cxxflags + "-stdlib=libc++11"
        """)
        profile_content2 = textwrap.dedent("""
            from conans import tools


            settings = {"build_type": "Release"}
            env = {"cpu_count": str(tools.cpu_count())}
        """)
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                options = {"shared": ["1", "2"]}
                def configure(self):
                    self.output.info("BUILD SHARED: %s" % self.options.shared)
            """)
        client.save({"conanfile.py": conanfile, "python_profile.py": profile_content,
                     "pr2.py": profile_content2})
        client.run("create . Pkg/0.1@user/testing -o *:shared=1 -pr python_profile.py -pr pr2.py")
        print(client.out)
        self.assertIn(textwrap.dedent("""
            Configuration:
            [settings]
            build_type=Release
            compiler=Visual Studio
            compiler.runtime=MD
            compiler.version=16
            os=Windows
            [options]
            shared=2
            *:shared=1
            [build_requires]
            [env]
            CXXFLAGS"""), client.out)
        self.assertIn("cpu_count=1", client.out)
