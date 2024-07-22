import json
import textwrap

from conans.model.package_ref import PkgReference
from conan.test.utils.tools import TestClient


def test_android_ndk():
    """ emulates the androidndk, a single package per OS-arch, that can target any
    android architecture (not especialized binary per target)
    """
    c = TestClient()

    windows = textwrap.dedent("""\
        [settings]
        os=Windows
        arch=x86_64
        """)
    linux = textwrap.dedent("""\
        [settings]
        os=Linux
        arch=x86_64
        """)
    android = textwrap.dedent("""\
        [settings]
        os=Android
        os.api_level=14
        arch = armv7
        build_type = Release
        compiler=clang
        compiler.version=11
        compiler.libcxx=c++_shared
        compiler.cppstd=14

        [tool_requires]
        androidndk/0.1
        """)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import save, copy
        class Pkg(ConanFile):
            name = "androidndk"
            version = "0.1"
            settings = "os", "arch"

            def build(self):
                save(self, "bin/ndk.compiler", f"MYNDK-{self.settings.os}-{self.settings.arch} exe!")

            def package(self):
                copy(self, "*", src=self.build_folder, dst=self.package_folder)

            def package_info(self):
                arch = self.settings_target.arch
                self.cpp_info.libs = [f"libndklib-{arch}"]
                self.buildenv_info.define("MY_ANDROID_ARCH", f"android-{arch}")
        """)
    test = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import load
        from conan.tools.env import VirtualBuildEnv
        class Pkg(ConanFile):
            settings = "os", "arch", "compiler", "build_type"

            def generate(self):
                ndk = self.dependencies.build["androidndk"]
                self.output.info(f"NDK LIBS: {ndk.cpp_info.libs}!!!")
                compiler = os.path.join(ndk.package_folder, "bin/ndk.compiler")
                self.output.info(load(self, compiler))
                env = VirtualBuildEnv(self).vars()
                self.output.info(f"MY-VAR: {env.get('MY_ANDROID_ARCH')}")

            def test(self):
                pass
        """)

    c.save({"conanfile.py": conanfile,
            "windows": windows,
            "linux": linux,
            "android": android})

    # IMPORTANT: The consumption via test_package define the relation. If not existing
    # I need to pass --build-require

    # Creating the NDK packages for Windows, Linux
    c.run("create . -pr:b=windows -pr:h=android --build-require")
    c.assert_listed_binary({"androidndk/0.1": ("522dcea5982a3f8a5b624c16477e47195da2f84f", "Build")},
                           build=True)
    # The same NDK can be used for different architectures, this should not require a new NDK build
    c.run("create . -pr:b=windows -pr:h=android -s:h arch=armv8 --build=missing  --build-require")
    c.assert_listed_binary({"androidndk/0.1": ("522dcea5982a3f8a5b624c16477e47195da2f84f", "Cache")},
                           build=True)
    assert "androidndk/0.1: Already installed!" in c.out
    # But a different build architecture is a different NDK executable
    c.run("create . -pr:b=windows -s:b arch=x86 -pr:h=android --build-require")
    c.assert_listed_binary({"androidndk/0.1": ("c11e463c49652ba9c5adc62573ee49f966bd8417", "Build")},
                           build=True)
    assert "androidndk/0.1: Calling build()" in c.out
    # But a different build OS is a different NDK executable
    c.run("create . -pr:b=linux -pr:h=android  --build-require")
    c.assert_listed_binary({"androidndk/0.1": ("63fead0844576fc02943e16909f08fcdddd6f44b", "Build")},
                           build=True)
    assert "androidndk/0.1: Calling build()" in c.out

    # IMPORTANT: The consumption via test_package allows specifying the type of requires
    # in this case: None, as this is intended to be injected via profile [tool_requires]
    # can be tested like that
    c.run("remove * -c")
    c.save({"test_package/conanfile.py": test})

    # Creating the NDK packages for Windows, Linux
    c.run("create . -pr:b=windows -pr:h=android --build-require")
    c.assert_listed_binary({"androidndk/0.1": ("522dcea5982a3f8a5b624c16477e47195da2f84f", "Build")},
                           build=True)
    assert "androidndk/0.1 (test package): NDK LIBS: ['libndklib-armv7']!!!" in c.out
    assert "androidndk/0.1 (test package): MYNDK-Windows-x86_64 exe!" in c.out
    assert "androidndk/0.1 (test package): MY-VAR: android-armv7" in c.out
    # The same NDK can be used for different architectures, this should not require a new NDK build
    c.run("create . -pr:b=windows -pr:h=android -s:h arch=armv8 --build=missing --build-require")
    c.assert_listed_binary({"androidndk/0.1": ("522dcea5982a3f8a5b624c16477e47195da2f84f", "Cache")},
                           build=True)
    assert "androidndk/0.1: Already installed!" in c.out
    assert "androidndk/0.1 (test package): NDK LIBS: ['libndklib-armv8']!!!" in c.out
    assert "androidndk/0.1 (test package): MYNDK-Windows-x86_64 exe!" in c.out
    assert "androidndk/0.1 (test package): MY-VAR: android-armv8" in c.out

    # But a different build architecture is a different NDK executable
    c.run("create . -pr:b=windows -s:b arch=x86 -pr:h=android --build=missing --build-require")
    c.assert_listed_binary({"androidndk/0.1": ("c11e463c49652ba9c5adc62573ee49f966bd8417", "Build")},
                           build=True)
    assert "androidndk/0.1: Calling build()" in c.out
    assert "androidndk/0.1 (test package): NDK LIBS: ['libndklib-armv7']!!!" in c.out
    assert "androidndk/0.1 (test package): MYNDK-Windows-x86 exe!" in c.out
    assert "androidndk/0.1 (test package): MY-VAR: android-armv7" in c.out

    # But a different build OS is a different NDK executable
    c.run("create . -pr:b=linux -pr:h=android --build=missing --build-require")
    c.assert_listed_binary({"androidndk/0.1": ("63fead0844576fc02943e16909f08fcdddd6f44b", "Build")},
                           build=True)
    assert "androidndk/0.1: Calling build()" in c.out
    assert "androidndk/0.1 (test package): NDK LIBS: ['libndklib-armv7']!!!" in c.out
    assert "androidndk/0.1 (test package): MYNDK-Linux-x86_64 exe!" in c.out
    assert "androidndk/0.1 (test package): MY-VAR: android-armv7" in c.out

    # Now any other package can use it
    c.save({"conanfile.py": test,
            "windows": windows,
            "linux": linux,
            "android": android}, clean_first=True)
    c.run("install . -pr:b=windows -pr:h=android")
    c.assert_listed_binary({"androidndk/0.1": ("522dcea5982a3f8a5b624c16477e47195da2f84f", "Cache")},
                           build=True)
    assert "conanfile.py: NDK LIBS: ['libndklib-armv7']!!!" in c.out
    assert "conanfile.py: MYNDK-Windows-x86_64 exe!" in c.out
    # And build on the fly the NDK if not binary exists
    c.run("install . -pr:b=linux -s:b arch=x86 -pr:h=android -s:h arch=armv8 --build=missing")
    c.assert_listed_binary({"androidndk/0.1": ("f14494c6e4810a63f050d6f5f37e9776ed48d3c9", "Build")},
                           build=True)
    assert "conanfile.py: NDK LIBS: ['libndklib-armv8']!!!" in c.out
    assert "conanfile.py: MYNDK-Linux-x86 exe!" in c.out
    assert "conanfile.py: MY-VAR: android-armv8" in c.out


def test_libcxx():
    """ emulates a package for libcxx, containing only a library to link with
    """
    c = TestClient()
    macos = textwrap.dedent("""
        [settings]
        os=Macos
        arch = x86_64
        build_type = Release
        compiler=apple-clang
        compiler.version=12.0
        compiler.cppstd=14
        compiler.libcxx=libc++
        """)
    ios = textwrap.dedent("""\
        [settings]
        os=iOS
        os.version = 14.3
        os.sdk = iphoneos
        arch = armv7
        build_type = Release
        compiler=apple-clang
        compiler.version=11.0
        compiler.cppstd=14
        compiler.libcxx=libc++

        [tool_requires]
        libcxx/0.1
        """)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import save, copy
        class Pkg(ConanFile):
            name = "libcxx"
            version = "0.1"
            settings = "os", "arch", "compiler", "build_type"

            def build(self):
                # HERE IT MUST USE THE SETTINGS-TARGET for CREATING THE BINARIES
                arch = self.settings_target.arch
                os_ = self.settings_target.os
                phone_sdk = self.settings_target.get_safe("os.sdk") or ""
                save(self, f"lib/libcxx-{arch}", f"libcxx{phone_sdk}-{os_}-{arch}!")

            def package(self):
                copy(self, "*", src=self.build_folder, dst=self.package_folder)

            def package_info(self):
                arch = self.settings_target.arch
                self.cpp_info.libs = [f"libcxx-{arch}"]

            def package_id(self):
                self.info.settings.clear()
                self.info.settings_target = self.settings_target
        """)
    test = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import load
        class Pkg(ConanFile):
            settings = "os", "arch", "compiler", "build_type"

            def generate(self):
                libcxx = self.dependencies.build["libcxx"]
                libcxx_lib = libcxx.cpp_info.libs[0]
                self.output.info(f"LIBCXX LIBS: {libcxx_lib}!!!")
                libcxx_path = os.path.join(libcxx.package_folder, "lib", libcxx_lib)
                self.output.info(load(self, libcxx_path))

            def test(self):
                pass
        """)

    c.save({"conanfile.py": conanfile,
            "test_package/conanfile.py": test,
            "macos": macos,
            "ios": ios})

    c.run("create . -pr:b=macos -pr:h=ios --build-require")
    c.assert_listed_binary({"libcxx/0.1": ("cd83035dfa71d83329e31a13b54b03fd38836815", "Build")},
                           build=True)
    assert "libcxx/0.1 (test package): LIBCXX LIBS: libcxx-armv7!!!" in c.out
    assert "libcxx/0.1 (test package): libcxxiphoneos-iOS-armv7!" in c.out

    # Same host profile should be same binary, the build profile is not factored in
    c.run("create . -pr:b=macos -s:b build_type=Debug -s:b arch=armv8 -pr:h=ios "
          "--build=missing --build-require")
    c.assert_listed_binary({"libcxx/0.1": ("cd83035dfa71d83329e31a13b54b03fd38836815", "Cache")},
                           build=True)
    assert "libcxx/0.1 (test package): LIBCXX LIBS: libcxx-armv7!!!" in c.out
    assert "libcxx/0.1 (test package): libcxxiphoneos-iOS-armv7!" in c.out

    # But every change in host, is a different binary
    c.run("create . -pr:b=macos -pr:h=ios -s:h arch=armv8 --build=missing --build-require")
    c.assert_listed_binary({"libcxx/0.1": ("af2d5e0458816f1d7e61c82315d143c20e3db2e3", "Build")},
                           build=True)
    assert "libcxx/0.1 (test package): LIBCXX LIBS: libcxx-armv8!!!" in c.out
    assert "libcxx/0.1 (test package): libcxxiphoneos-iOS-armv8!" in c.out

    # But every change in host, is a different binary
    c.run("create . -pr:b=macos -pr:h=ios -s:h arch=armv8 -s:h os.sdk=iphonesimulator "
          "--build-require")
    c.assert_listed_binary({"libcxx/0.1": ("c7e3b0fbb4fac187f59bf97e7958631b96fda2a6", "Build")},
                           build=True)
    assert "libcxx/0.1 (test package): LIBCXX LIBS: libcxx-armv8!!!" in c.out
    assert "libcxx/0.1 (test package): libcxxiphonesimulator-iOS-armv8!" in c.out

    # Now any other package can use it
    c.save({"conanfile.py": test,
            "macos": macos,
            "ios": ios}, clean_first=True)
    c.run("install . -pr:b=macos -pr:h=ios")
    c.assert_listed_binary({"libcxx/0.1": ("cd83035dfa71d83329e31a13b54b03fd38836815", "Cache")},
                           build=True)
    assert "conanfile.py: LIBCXX LIBS: libcxx-armv7!!!" in c.out
    assert "conanfile.py: libcxxiphoneos-iOS-armv7!" in c.out


def test_compiler_gcc():
    """ this is testing a gcc-like cross-compiler that needs the gcc.exe binary to compile
    and can also contain a specific libcxx for the target architecture
    """
    c = TestClient()
    # build machine
    linux = textwrap.dedent("""
        [settings]
        os=Linux
        arch = x86_64
        build_type = Release
        compiler=gcc
        compiler.version=11
        compiler.cppstd=14
        compiler.libcxx=libstdc++11
        """)
    rpi = textwrap.dedent("""\
        [settings]
        os=Linux
        arch = armv7
        build_type = Release

        [tool_requires]
        gcc/0.1
        """)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import save, copy
        class Pkg(ConanFile):
            name = "gcc"
            version = "0.1"
            settings = "os", "arch", "compiler", "build_type"

            def build(self):
                # HERE IT MUST USE THE SETTINGS-TARGET for CREATING THE LIBCXX
                # BUT SETTINGS for CREATING THE GCC.EXE
                arch = self.settings_target.arch
                os_ = self.settings_target.os
                save(self, f"lib/libcxx-{arch}", f"libcxx-{os_}-{arch}!")
                save(self, "bin/gcc", f"gcc-{self.settings.os}-{self.settings.arch}")

            def package(self):
                copy(self, "*", src=self.build_folder, dst=self.package_folder)

            def package_info(self):
                arch = self.settings_target.arch
                self.cpp_info.libs = [f"libcxx-{arch}"]

            def package_id(self):
                self.info.settings_target = self.settings_target
        """)
    test = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import load
        class Pkg(ConanFile):
            settings = "os", "arch", "build_type"

            def generate(self):
                gcc = self.dependencies.build["gcc"]
                libcxx_lib = gcc.cpp_info.libs[0]
                self.output.info(f"LIBCXX LIBS: {libcxx_lib}!!!")
                libcxx_path = os.path.join(gcc.package_folder, "lib", libcxx_lib)
                self.output.info(load(self, libcxx_path))
                gcc_path = os.path.join(gcc.package_folder, "bin/gcc")
                self.output.info(load(self, gcc_path))

            def test(self):
                pass
        """)

    c.save({"conanfile.py": conanfile,
            "test_package/conanfile.py": test,
            "linux": linux,
            "rpi": rpi})

    c.run("create . -pr:b=linux -pr:h=rpi --build-require")
    c.assert_listed_binary({"gcc/0.1": ("6190ea2804cd4777609ec7174ccfdee22c6318c3", "Build")},
                           build=True)
    assert "gcc/0.1 (test package): LIBCXX LIBS: libcxx-armv7!!!" in c.out
    assert "gcc/0.1 (test package): libcxx-Linux-armv7!" in c.out
    assert "gcc/0.1 (test package): gcc-Linux-x86_64" in c.out

    # Same host profile, but different build profile is a different binary
    c.run("create . -pr:b=linux  -s:b os=Windows -s:b arch=armv8 -pr:h=rpi --build-require")
    c.assert_listed_binary({"gcc/0.1": ("687fdc5f43017300a98643948869b4c5560ca82c", "Build")},
                           build=True)
    assert "gcc/0.1 (test package): LIBCXX LIBS: libcxx-armv7!!!" in c.out
    assert "gcc/0.1 (test package): libcxx-Linux-armv7!" in c.out
    assert "gcc/0.1 (test package): gcc-Windows-armv8" in c.out

    # Same build but different host is also a new binary
    c.run("create . -pr:b=linux -pr:h=rpi -s:h arch=armv8 --build=missing --build-require")
    c.assert_listed_binary({"gcc/0.1": ("0521de9a6b94083bd47474a51570a3b856b77406", "Build")},
                           build=True)
    assert "gcc/0.1 (test package): LIBCXX LIBS: libcxx-armv8!!!" in c.out
    assert "gcc/0.1 (test package): libcxx-Linux-armv8!" in c.out
    assert "gcc/0.1 (test package): gcc-Linux-x86_64" in c.out
    # check the list packages
    c.run("list gcc/0.1:* --format=json", redirect_stdout="packages.json")
    pkgs_json = json.loads(c.load("packages.json"))
    pref = PkgReference.loads("gcc/0.1#a8d725d9988de633accf410fb04cd162:6190ea2804cd4777609ec7174ccfdee22c6318c3")
    settings_target = {
        "arch": "armv7",
        "build_type": "Release",
        "os": "Linux"
    }
    revision_dict = pkgs_json["Local Cache"]["gcc/0.1"]["revisions"][pref.ref.revision]
    assert settings_target == revision_dict["packages"][pref.package_id]["info"]["settings_target"]
