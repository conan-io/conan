import os
import platform
import pytest
import textwrap

from conan.tools.microsoft.visual import vcvars_command
from conan.test.assets.sources import gen_function_cpp
from ..microsoft.test_msbuild import sln_file, myapp_vcxproj

conanfile_py = textwrap.dedent("""
    from conan import ConanFile, MSBuild, MSBuildToolchain

    class App(ConanFile):
        settings = 'os', 'arch', 'compiler', 'build_type'
        exports_sources = "MyProject.sln", "MyApp/MyApp.vcxproj", "MyApp/MyApp.cpp"
        requires = "hello/0.1"

        def generate(self):
            tc = MSBuildToolchain(self)
            tc.generate()

        def build(self):
            msbuild = MSBuild(self)
            msbuild.build("MyProject.sln")
""")


@pytest.mark.tool("cmake")
@pytest.mark.tool("msbuild")
@pytest.mark.tool("icc")
@pytest.mark.xfail(reason="Intel compiler not installed yet on CI")
@pytest.mark.skipif(platform.system() != "Windows", reason="msbuild requires Windows")
class MSBuildIntelTestCase:
    def test_use_msbuild_toolchain(self):
        self.t.save({'profile': self.profile})
        self.t.run("new hello/0.1 -s")
        self.t.run("create . --name=hello --version=0.1 -pr:h=profile")

        app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

        # Prepare the actual consumer package
        self.t.save({"conanfile.py": conanfile_py,
                     "MyProject.sln": sln_file,
                     "MyApp/MyApp.vcxproj": myapp_vcxproj,
                     "MyApp/MyApp.cpp": app,
                     'profile': self.profile},
                    clean_first=True)

        # Build in the cache
        self.t.run("install . -pr:h=profile -of=conan")

        self.assertIn("conanfile.py: MSBuildToolchain created conan_toolchain_release_x64.props",
                      self.t.out)

        self.t.run("build . -bf=conan")
        self.assertIn("Visual Studio 2017", self.t.out)
        self.assertIn("[vcvarsall.bat] Environment initialized for: 'x64'", self.t.out)

        exe = "x64\\Release\\MyApp.exe"
        self.t.run_command(exe)
        self.assertIn("main __INTEL_COMPILER1910", self.t.out)

        vcvars = vcvars_command(version="15", architecture="x64")
        dumpbind_cmd = '%s && dumpbin /dependents "%s"' % (vcvars, exe)
        self.t.run_command(dumpbind_cmd)
        self.assertIn("KERNEL32.dll", self.t.out)

        # Build locally
        os.unlink(os.path.join(self.t.current_folder, exe))

        cmd = vcvars + ' && msbuild "MyProject.sln" /p:Configuration=Release ' \
                       '/p:Platform=x64 /p:PlatformToolset="Intel C++ Compiler 19.1"'

        self.t.run_command(cmd)
        self.assertIn("Visual Studio 2017", self.t.out)
        self.assertIn("[vcvarsall.bat] Environment initialized for: 'x64'", self.t.out)

        self.t.run_command(exe)
        self.assertIn("main __INTEL_COMPILER1910", self.t.out)

        self.t.run_command(dumpbind_cmd)
        self.assertIn("KERNEL32.dll", self.t.out)
