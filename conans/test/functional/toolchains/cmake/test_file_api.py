import os
import textwrap

import pytest

from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.utils.tools import TestClient


@pytest.mark.tool_cmake
def test_file_api():
    """
    simple library providing 3 targets:
    - decoder
    - encoder
    - transcoder (requires decoder and encoder)
    generates the following targets:
    - triunfo::decoder
    - triunfo::encoder
    - triunfo::transcoder (depends on triunfo::decoder and triunfo::encoder)
    consumer uses find_package(triunfo COMPONENTS <component>)
    """
    client = TestClient()

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake, CMakeFileAPI
        from conan.tools.files import CppPackage

        class Triunfo(ConanFile):
            name = "triunfo"
            version = "1.0"
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "*CMakeLists.txt", "*.cpp", "*.h"
            generators = "CMakeToolchain"

            def build(self):
                file_api = CMakeFileAPI(self)
                file_api.query(CMakeFileAPI.CODEMODELV2)
                cmake = CMake(self)
                cmake.configure()
                reply = file_api.reply(CMakeFileAPI.CODEMODELV2)
                package = reply.to_conan_package()
                package.save()
                cmake.build()

            def package(self):
                cmake = CMake(self)
                cmake.install()
                self.copy(CppPackage.DEFAULT_FILENAME)

            def package_info(self):
                cpp_package = CppPackage.load(CppPackage.DEFAULT_FILENAME)
                cpp_package.package_info(self)
    """)

    decoder_cpp = gen_function_cpp(name="decoder", includes=["decoder"])
    encoder_cpp = gen_function_cpp(name="encoder", includes=["encoder"])
    transcoder_cpp = gen_function_cpp(name="transcoder", calls=["decoder", "encoder"],
                                      includes=["transcoder", "../decoder/decoder", "../encoder/encoder"])
    decoder_h = gen_function_h(name="decoder")
    encoder_h = gen_function_h(name="encoder")
    transcoder_h = gen_function_h(name="transcoder")
    decoder_cmake = gen_cmakelists(libname="decoder", libsources=["decoder.cpp"], install=True,
                                   public_header="decoder.h")
    encoder_cmake = gen_cmakelists(libname="encoder", libsources=["encoder.cpp"], install=True,
                                   public_header="encoder.h")
    transcoder_cmake = gen_cmakelists(libname="transcoder", libsources=["transcoder.cpp"], install=True,
                                      public_header="transcoder.h", deps=["decoder", "encoder"])
    common_cmake = textwrap.dedent("""
        cmake_minimum_required(VERSION 2.8)
        project(triunfo)
        add_subdirectory(decoder)
        add_subdirectory(encoder)
        add_subdirectory(transcoder)
    """)

    client.save({"conanfile.py": conanfile,
                 os.path.join("decoder", "decoder.cpp"): decoder_cpp,
                 os.path.join("encoder", "encoder.cpp"): encoder_cpp,
                 os.path.join("transcoder", "transcoder.cpp"): transcoder_cpp,
                 os.path.join("decoder", "decoder.h"): decoder_h,
                 os.path.join("encoder", "encoder.h"): encoder_h,
                 os.path.join("transcoder", "transcoder.h"): transcoder_h,
                 os.path.join("decoder", "CMakeLists.txt"): decoder_cmake,
                 os.path.join("encoder", "CMakeLists.txt"): encoder_cmake,
                 os.path.join("transcoder", "CMakeLists.txt"): transcoder_cmake,
                 "CMakeLists.txt": common_cmake,
                 })
    client.run("create .")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake, CMakeFileAPI
        from conan.tools.files import CppPackage

        class Elogio(ConanFile):
            name = "elogio"
            version = "1.0"
            requires = "triunfo/1.0"
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "*CMakeLists.txt", "*.cpp", "*.h"
            generators = "CMakeDeps", "CMakeToolchain"

            def build(self):
                file_api = CMakeFileAPI(self)
                file_api.query(CMakeFileAPI.CODEMODELV2)
                cmake = CMake(self)
                cmake.configure()
                reply = file_api.reply(CMakeFileAPI.CODEMODELV2)
                package = reply.to_conan_package()
                package.save()
                cmake.build()
    """)

    use_decoder_cpp = gen_function_cpp(name="main", includes=["decoder"], calls=["decoder"])
    use_encoder_cpp = gen_function_cpp(name="main", includes=["encoder"], calls=["encoder"])
    use_transcoder_cpp = gen_function_cpp(name="main", includes=["transcoder"], calls=["transcoder"])
    use_decoder_cmake = gen_cmakelists(appname="use_decoder", appsources=["use_decoder.cpp"],
                                       find_package={"triunfo": "decoder"})
    use_encoder_cmake = gen_cmakelists(appname="use_encoder", appsources=["use_encoder.cpp"],
                                       find_package={"triunfo": "encoder"})
    use_transcoder_cmake = gen_cmakelists(appname="use_transcoder", appsources=["use_transcoder.cpp"],
                                          find_package={"triunfo": "transcoder"})
    common_cmake = textwrap.dedent("""
        cmake_minimum_required(VERSION 2.8)
        project(elogio)
        add_subdirectory(use_decoder)
        add_subdirectory(use_encoder)
        add_subdirectory(use_transcoder)
    """)

    client.save({"conanfile.py": conanfile,
                 os.path.join("use_decoder", "use_decoder.cpp"): use_decoder_cpp,
                 os.path.join("use_encoder", "use_encoder.cpp"): use_encoder_cpp,
                 os.path.join("use_transcoder", "use_transcoder.cpp"): use_transcoder_cpp,
                 os.path.join("use_decoder", "CMakeLists.txt"): use_decoder_cmake,
                 os.path.join("use_encoder", "CMakeLists.txt"): use_encoder_cmake,
                 os.path.join("use_transcoder", "CMakeLists.txt"): use_transcoder_cmake,
                 "CMakeLists.txt": common_cmake,
                 }, clean_first=True)

    client.run("install .")
    client.run("build .")
