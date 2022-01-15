import textwrap

from conans.test.utils.tools import TestClient


def test_android_ndk():
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
    c.run("create . -pr:b=Linux -pr:h=android  --build-require")
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
    c.run("create . -pr:b=Linux -pr:h=android --build=missing")
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
                arch = self.settings_target.arch
                os_ = self.settings_target.os
                phone_sdk = self.settings_target.get_safe("os.sdk") or ""
                save(self, f"lib/libcxx-{arch}", f"libcxx{phone_sdk}-{os_}-{arch} exe!")

            def package(self):
                self.copy("*")

            def package_info(self):
                arch = self.settings_target.arch
                self.cpp_info.libs = [f"libcxx-{arch}"]

            def package_id(self):
                self.info.settings = self.settings_target.values
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
    assert "libcxx/0.1:bc5c242823f6a61e98b47903b67f8575bbb4adfb - Build" in c.out
    assert "libcxx/0.1 (test package): LIBCXX LIBS: libcxx-armv7!!!" in c.out
    assert "libcxx/0.1 (test package): libcxxiphoneos-iOS-armv7 exe!" in c.out

    # Same host profile should be same binary, the build profile is not factored in
    c.run("create . -pr:b=macos -s:b build_type=Debug -s:b arch=armv8 -pr:h=ios --build=missing")
    assert "libcxx/0.1:bc5c242823f6a61e98b47903b67f8575bbb4adfb - Cache" in c.out
    assert "libcxx/0.1 (test package): LIBCXX LIBS: libcxx-armv7!!!" in c.out
    assert "libcxx/0.1 (test package): libcxxiphoneos-iOS-armv7 exe!" in c.out

    # But every change in host, is a different binary
    c.run("create . -pr:b=macos -pr:h=ios -s:h arch=armv8 --build=missing")
    assert "libcxx/0.1:a409ac0ceb64e743dc0ad53e80c32d1db3317193 - Build" in c.out
    assert "libcxx/0.1 (test package): LIBCXX LIBS: libcxx-armv8!!!" in c.out
    assert "libcxx/0.1 (test package): libcxxiphoneos-iOS-armv8 exe!" in c.out

    # But every change in host, is a different binary
    c.run("create . -pr:b=macos -pr:h=ios -s:h arch=armv8 -s:h os.sdk=iphonesimulator ")
    assert "libcxx/0.1:738b7c9a296c7d9150ba28bd60e67f4fe740adbe - Build" in c.out
    assert "libcxx/0.1 (test package): LIBCXX LIBS: libcxx-armv8!!!" in c.out
    assert "libcxx/0.1 (test package): libcxxiphonesimulator-iOS-armv8 exe!" in c.out
