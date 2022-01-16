import textwrap

from conans.test.utils.tools import TestClient


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
        from conan.tools.files import save
        class Pkg(ConanFile):
            name = "androidndk"
            version = "0.1"
            settings = "os", "arch"

            def build(self):
                save(self, "bin/ndk.compiler", f"MYNDK-{self.settings.os}-{self.settings.arch} exe!")

            def package(self):
                self.copy("*")

            def package_info(self):
                arch = self.settings_target.arch
                self.cpp_info.libs = [f"libndklib-{arch}"]
        """)
    test = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import load
        class Pkg(ConanFile):
            settings = "os", "arch", "compiler", "build_type"

            def generate(self):
                ndk = self.dependencies.build["androidndk"]
                self.output.info(f"NDK LIBS: {ndk.cpp_info.libs}!!!")
                compiler = os.path.join(ndk.package_folder, "bin/ndk.compiler")
                self.output.info(load(self, compiler))

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
    assert "androidndk/0.1:e340edd75790e7156c595edebd3d98b10a2e091e - Build" in c.out
    # The same NDK can be used for different architectures, this should not require a new NDK build
    c.run("create . -pr:b=windows -pr:h=android -s:h arch=armv8 --build=missing  --build-require")
    assert "androidndk/0.1:e340edd75790e7156c595edebd3d98b10a2e091e - Cache" in c.out
    assert "androidndk/0.1: Already installed!" in c.out
    # But a different build architecture is a different NDK executable
    c.run("create . -pr:b=windows -s:b arch=x86 -pr:h=android --build-require")
    assert "androidndk/0.1:e24801f77febd5dd0f5f3eae7444b4132644a856 - Build" in c.out
    assert "androidndk/0.1: Calling build()" in c.out
    # But a different build OS is a different NDK executable
    c.run("create . -pr:b=linux -pr:h=android  --build-require")
    assert "androidndk/0.1:bd2c61d8ce335cd78bd92489d2a54435785a7653 - Build" in c.out
    assert "androidndk/0.1: Calling build()" in c.out

    # IMPORTANT: The consumption via test_package allows specifying the type of requires
    # in this case: None, as this is intended to be injected via profile [tool_requires]
    # can be tested like that
    c.run("remove * -f")
    c.save({"test_package/conanfile.py": test})

    # Creating the NDK packages for Windows, Linux
    c.run("create . -pr:b=windows -pr:h=android")
    assert "androidndk/0.1:e340edd75790e7156c595edebd3d98b10a2e091e - Build" in c.out
    assert "androidndk/0.1 (test package): NDK LIBS: ['libndklib-armv7']!!!" in c.out
    assert "androidndk/0.1 (test package): MYNDK-Windows-x86_64 exe!" in c.out
    # The same NDK can be used for different architectures, this should not require a new NDK build
    c.run("create . -pr:b=windows -pr:h=android -s:h arch=armv8 --build=missing")
    assert "androidndk/0.1:e340edd75790e7156c595edebd3d98b10a2e091e - Cache" in c.out
    assert "androidndk/0.1: Already installed!" in c.out
    assert "androidndk/0.1 (test package): NDK LIBS: ['libndklib-armv8']!!!" in c.out
    assert "androidndk/0.1 (test package): MYNDK-Windows-x86_64 exe!" in c.out

    # But a different build architecture is a different NDK executable
    c.run("create . -pr:b=windows -s:b arch=x86 -pr:h=android --build=missing")
    assert "androidndk/0.1:e24801f77febd5dd0f5f3eae7444b4132644a856 - Build" in c.out
    assert "androidndk/0.1: Calling build()" in c.out
    assert "androidndk/0.1 (test package): NDK LIBS: ['libndklib-armv7']!!!" in c.out
    assert "androidndk/0.1 (test package): MYNDK-Windows-x86 exe!" in c.out

    # But a different build OS is a different NDK executable
    c.run("create . -pr:b=linux -pr:h=android --build=missing")
    assert "androidndk/0.1:bd2c61d8ce335cd78bd92489d2a54435785a7653 - Build" in c.out
    assert "androidndk/0.1: Calling build()" in c.out
    assert "androidndk/0.1 (test package): NDK LIBS: ['libndklib-armv7']!!!" in c.out
    assert "androidndk/0.1 (test package): MYNDK-Linux-x86_64 exe!" in c.out

    # Now any other package can use it
    c.save({"conanfile.py": test,
            "windows": windows,
            "linux": linux,
            "android": android}, clean_first=True)
    c.run("install . -pr:b=windows -pr:h=android")
    assert "androidndk/0.1:e340edd75790e7156c595edebd3d98b10a2e091e - Cache" in c.out
    assert "conanfile.py: NDK LIBS: ['libndklib-armv7']!!!" in c.out
    assert "conanfile.py: MYNDK-Windows-x86_64 exe!" in c.out
    # And build on the fly the NDK if not binary exists
    c.run("install . -pr:b=linux -s:b arch=x86 -pr:h=android -s:h arch=armv8 --build=missing")
    assert "androidndk/0.1:ad53c1725b66f2a80456fbc4d5fb7698978bbe2e - Build" in c.out
    assert "conanfile.py: NDK LIBS: ['libndklib-armv8']!!!" in c.out
    assert "conanfile.py: MYNDK-Linux-x86 exe!" in c.out


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
        from conan.tools.files import save
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
                self.copy("*")

            def package_info(self):
                arch = self.settings_target.arch
                self.cpp_info.libs = [f"libcxx-{arch}"]

            def package_id(self):
                self.info.settings.clear()
                self.info.settings_target = self.settings_target.values
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

    c.run("create . -pr:b=macos -pr:h=ios")
    assert "libcxx/0.1:f65d02463a7f8279217290c51994d38b5a0329e2 - Build" in c.out
    assert "libcxx/0.1 (test package): LIBCXX LIBS: libcxx-armv7!!!" in c.out
    assert "libcxx/0.1 (test package): libcxxiphoneos-iOS-armv7!" in c.out

    # Same host profile should be same binary, the build profile is not factored in
    c.run("create . -pr:b=macos -s:b build_type=Debug -s:b arch=armv8 -pr:h=ios --build=missing")
    assert "libcxx/0.1:f65d02463a7f8279217290c51994d38b5a0329e2 - Cache" in c.out
    assert "libcxx/0.1 (test package): LIBCXX LIBS: libcxx-armv7!!!" in c.out
    assert "libcxx/0.1 (test package): libcxxiphoneos-iOS-armv7!" in c.out

    # But every change in host, is a different binary
    c.run("create . -pr:b=macos -pr:h=ios -s:h arch=armv8 --build=missing")
    assert "libcxx/0.1:52d228521d318515b19d400e3d2e2b572b640017 - Build" in c.out
    assert "libcxx/0.1 (test package): LIBCXX LIBS: libcxx-armv8!!!" in c.out
    assert "libcxx/0.1 (test package): libcxxiphoneos-iOS-armv8!" in c.out

    # But every change in host, is a different binary
    c.run("create . -pr:b=macos -pr:h=ios -s:h arch=armv8 -s:h os.sdk=iphonesimulator ")
    assert "libcxx/0.1:2827aeb92fb9ce8833bfde468ee78c1861aef094 - Build" in c.out
    assert "libcxx/0.1 (test package): LIBCXX LIBS: libcxx-armv8!!!" in c.out
    assert "libcxx/0.1 (test package): libcxxiphonesimulator-iOS-armv8!" in c.out

    # Now any other package can use it
    c.save({"conanfile.py": test,
            "macos": macos,
            "ios": ios}, clean_first=True)
    c.run("install . -pr:b=macos -pr:h=ios")
    assert "libcxx/0.1:f65d02463a7f8279217290c51994d38b5a0329e2 - Cache" in c.out
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
        from conan.tools.files import save
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
                self.copy("*")

            def package_info(self):
                arch = self.settings_target.arch
                self.cpp_info.libs = [f"libcxx-{arch}"]

            def package_id(self):
                self.info.settings_target = self.settings_target.values
        """)
    test = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import load
        class Pkg(ConanFile):
            settings = "os", "arch", "compiler", "build_type"

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

    c.run("create . -pr:b=linux -pr:h=rpi")
    assert "gcc/0.1:306563637ff16730bf4ab6d268187c7f4a0dfa67 - Build" in c.out
    assert "gcc/0.1 (test package): LIBCXX LIBS: libcxx-armv7!!!" in c.out
    assert "gcc/0.1 (test package): libcxx-Linux-armv7!" in c.out
    assert "gcc/0.1 (test package): gcc-Linux-x86_64" in c.out

    # Same host profile, but different build profile is a different binary
    c.run("create . -pr:b=linux  -s:b os=Windows -s:b arch=armv8 -pr:h=rpi")
    assert "gcc/0.1:88f59266a5a12bbf78bccb0b609e9ae96460acd7 - Build" in c.out
    assert "gcc/0.1 (test package): LIBCXX LIBS: libcxx-armv7!!!" in c.out
    assert "gcc/0.1 (test package): libcxx-Linux-armv7!" in c.out
    assert "gcc/0.1 (test package): gcc-Windows-armv8" in c.out

    # Same build but different host is also a new binary
    c.run("create . -pr:b=linux -pr:h=rpi -s:h arch=armv8 --build=missing")
    assert "gcc/0.1:3b2683e2fa3b48f169ba78d05e493438601cf51e - Build" in c.out
    assert "gcc/0.1 (test package): LIBCXX LIBS: libcxx-armv8!!!" in c.out
    assert "gcc/0.1 (test package): libcxx-Linux-armv8!" in c.out
    assert "gcc/0.1 (test package): gcc-Linux-x86_64" in c.out
