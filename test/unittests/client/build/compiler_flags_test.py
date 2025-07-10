import pytest

from conan.tools.build.flags import architecture_flag, build_type_flags, threads_flags
from conan.test.utils.mocks import MockSettings, ConanFileMock


class TestCompilerFlags:

    @pytest.mark.parametrize("compiler,arch,the_os,flag", [("gcc", "x86", None, "-m32"),
                           ("clang", "x86", None, "-m32"),
                           ("sun-cc", "x86", None, "-m32"),
                           ("gcc", "x86_64", None, "-m64"),
                           ("clang", "x86_64", None, "-m64"),
                           ("sun-cc", "x86_64", None, "-m64"),
                           ("sun-cc", "sparc", None, "-m32"),
                           ("sun-cc", "sparcv9", None, "-m64"),
                           ("gcc", "armv7", None, ""),
                           ("clang", "armv7", None, ""),
                           ("sun-cc", "armv7", None, ""),
                           ("gcc", "s390", None, "-m31"),
                           ("clang", "s390", None, "-m31"),
                           ("sun-cc", "s390", None, "-m31"),
                           ("gcc", "s390x", None, "-m64"),
                           ("clang", "s390x", None, "-m64"),
                           ("sun-cc", "s390x", None, "-m64"),
                           ("msvc", "x86", None, ""),
                           ("msvc", "x86_64", None, ""),
                           ("gcc", "ppc32", "AIX", "-maix32"),
                           ("gcc", "ppc64", "AIX", "-maix64"),
                           ])
    def test_arch_flag(self, compiler, arch, the_os, flag):
        settings = MockSettings({"compiler": compiler,
                                 "arch": arch,
                                 "os": the_os})
        conanfile = ConanFileMock()
        conanfile.settings = settings
        assert architecture_flag(conanfile) == flag


    @pytest.mark.parametrize("compiler,threads,flag", [("clang", None, []),
                           ("emcc", None, []),
                           ("emcc", "posix", ["-pthread"]),
                           ("emcc", "wasm_workers", ["-sWASM_WORKERS=1"]),
                           ])
    def test_threads_flag(self, compiler, threads, flag):
        settings = MockSettings({"compiler": compiler,
                                 "compiler.threads": threads})
        conanfile = ConanFileMock()
        conanfile.settings = settings
        assert threads_flags(conanfile) == flag

    @pytest.mark.parametrize("compiler,arch,the_os,flag", [("clang", "x86", "Windows", ""),
                           ("clang", "x86_64", "Windows", "")
                           ])
    def test_arch_flag_clangcl(self,  compiler, arch, the_os, flag):
        settings = MockSettings({"compiler": compiler,
                                 "arch": arch,
                                 "os": the_os})
        conanfile = ConanFileMock()
        conanfile.conf.define("tools.build:compiler_executables", {"c": "clang-cl"})
        conanfile.settings = settings
        assert architecture_flag(conanfile) == flag

    def test_catalyst(self):
        settings = MockSettings({"compiler": "apple-clang",
                                 "arch": "x86_64",
                                 "os": "Macos",
                                 "os.subsystem": "catalyst",
                                 "os.subsystem.ios_version": "13.1"})
        conanfile = ConanFileMock()
        conanfile.settings = settings
        assert architecture_flag(conanfile) == "--target=x86_64-apple-ios13.1-macabi"

        settings = MockSettings({"compiler": "apple-clang",
                                 "arch": "armv8",
                                 "os": "Macos",
                                 "os.subsystem": "catalyst",
                                 "os.subsystem.ios_version": "13.1"})
        conanfile = ConanFileMock()
        conanfile.settings = settings
        assert architecture_flag(conanfile) == "--target=arm64-apple-ios13.1-macabi"

    @pytest.mark.parametrize("os_,arch,flag", [("Linux", "x86", "-m32"),
                           ("Linux", "x86_64", "-m64"),
                           ("Windows", "x86", "/Qm32"),
                           ("Windows", "x86_64", "/Qm64"),
                           ])
    def test_arch_flag_intel(self, os_, arch, flag):
        settings = MockSettings({"compiler": "intel-cc",
                                 "os": os_,
                                 "arch": arch})
        conanfile = ConanFileMock()
        conanfile.settings = settings
        assert architecture_flag(conanfile) == flag

    @pytest.mark.parametrize("arch,flag", [("e2k-v2", "-march=elbrus-v2"),
                           ("e2k-v3", "-march=elbrus-v3"),
                           ("e2k-v4", "-march=elbrus-v4"),
                           ("e2k-v5", "-march=elbrus-v5"),
                           ("e2k-v6", "-march=elbrus-v6"),
                           ("e2k-v7", "-march=elbrus-v7"),
                           ])
    def test_arch_flag_mcst_lcc(self, arch, flag):
        conanfile = ConanFileMock()
        settings = MockSettings({"compiler": "mcst-lcc",
                                 "arch": arch})
        conanfile.settings = settings
        assert architecture_flag(conanfile) == flag

    @pytest.mark.parametrize("compiler,build_type,vs_toolset,flags", [("msvc", "Debug", None, "-Zi -Ob0 -Od"),
                           ("msvc", "Release", None, "-O2 -Ob2"),
                           ("msvc", "RelWithDebInfo", None, "-Zi -O2 -Ob1"),
                           ("msvc", "MinSizeRel", None, "-O1 -Ob1"),
                           ("msvc", "Debug", "v140_clang_c2", "-gline-tables-only -fno-inline -O0"),
                           ("msvc", "Release", "v140_clang_c2", "-O2"),
                           ("msvc", "RelWithDebInfo", "v140_clang_c2", "-gline-tables-only -O2 -fno-inline"),
                           ("msvc", "MinSizeRel", "v140_clang_c2", ""),
                           ("gcc", "Debug", None, "-g"),
                           ("gcc", "Release", None, "-O3"),
                           ("gcc", "RelWithDebInfo", None, "-O2 -g"),
                           ("gcc", "MinSizeRel", None, "-Os"),
                           ("clang", "Debug", None, "-g"),
                           ("clang", "Release", None, "-O3"),
                           ("clang", "RelWithDebInfo", None, "-O2 -g"),
                           ("clang", "MinSizeRel", None, "-Os"),
                           ("apple-clang", "Debug", None, "-g"),
                           ("apple-clang", "Release", None, "-O3"),
                           ("apple-clang", "RelWithDebInfo", None, "-O2 -g"),
                           ("apple-clang", "MinSizeRel", None, "-Os"),
                           ("sun-cc", "Debug", None, "-g"),
                           ("sun-cc", "Release", None, "-xO3"),
                           ("sun-cc", "RelWithDebInfo", None, "-xO2 -g"),
                           ("sun-cc", "MinSizeRel", None, "-xO2 -xspace"),
                           ])
    def test_build_type_flags(self, compiler, build_type, vs_toolset, flags):
        settings = MockSettings({"compiler": compiler,
                                 "build_type": build_type,
                                 "compiler.toolset": vs_toolset})
        conanfile = ConanFileMock()
        conanfile.settings = settings
        assert ' '.join(build_type_flags(conanfile)) == flags

    @pytest.mark.parametrize("compiler,build_type,flags", [("clang", "Debug", "-Zi -Ob0 -Od"),
                           ("clang", "Release", "-O2 -Ob2"),
                           ("clang", "RelWithDebInfo", "-Zi -O2 -Ob1"),
                           ("clang", "MinSizeRel", "-O1 -Ob1"),
                           ])
    def test_build_type_flags_clangcl(self, compiler, build_type, flags):
        settings = MockSettings({"compiler": compiler,
                                 "build_type": build_type})
        conanfile = ConanFileMock()
        conanfile.conf.define("tools.build:compiler_executables", {"c": "clang-cl"})
        conanfile.settings = settings
        assert ' '.join(build_type_flags(conanfile)) == flags
