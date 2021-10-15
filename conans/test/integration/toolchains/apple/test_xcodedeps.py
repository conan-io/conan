import os
import platform

import pytest

from conans.test.utils.tools import TestClient


def get_name(configuration, architecture, sdk):
    props = [("configuration", configuration),
             ("architecture", architecture),
             ("sdk", sdk)]
    name = "".join("_{}".format(v) for _, v in props if v is not None)
    return name.lower()


def expected_files(current_folder, configuration, architecture, sdk=None):
    files = []
    name = get_name(configuration, architecture, sdk)
    deps = ["hello", "goodbye"]
    files.extend([os.path.join(current_folder, "conan_{}{}.xcconfig".format(dep, name)) for dep in deps])
    files.extend([os.path.join(current_folder, "conan_{}_vars{}.xcconfig".format(dep, name)) for dep in deps])
    files.append(os.path.join(current_folder, "conandeps.xcconfig"))
    return files


def check_contents(client, deps, configuration, architecture, sdk=None):
    for dep_name in deps:
        dep_xconfig = client.load("conan_{}.xcconfig".format(dep_name))
        conf_name = "conan_{}{}.xcconfig".format(dep_name,
                                                 get_name(configuration, architecture, sdk))

        assert '#include "{}"'.format(conf_name) in dep_xconfig

        vars_name = "conan_{}_vars{}.xcconfig".format(dep_name,
                                                      get_name(configuration, architecture, sdk))
        conan_vars = client.load(vars_name)
        for var in _expected_vars_xconfig:
            assert var.format(name=dep_name) in conan_vars

        conan_conf = client.load(conf_name)
        sdk_condition = "*" if not sdk else "{}*".format(sdk)
        for var in _expected_conf_xconfig:
            assert var.format(vars_name=vars_name, name=dep_name, sdk=sdk_condition,
                              configuration=configuration) in conan_conf


_expected_vars_xconfig = [
    "CONAN_{name}_ROOT_FOLDER",
    "CONAN_{name}_BINARY_DIRECTORIES = $(CONAN_{name}_ROOT_FOLDER)/bin",
    "CONAN_{name}_C_COMPILER_FLAGS =",
    "CONAN_{name}_CXX_COMPILER_FLAGS =",
    "CONAN_{name}_LINKER_FLAGS =",
    "CONAN_{name}_PREPROCESSOR_DEFINITIONS =",
    "CONAN_{name}_INCLUDE_DIRECTORIES = $(CONAN_{name}_ROOT_FOLDER)/include",
    "CONAN_{name}_RESOURCE_DIRECTORIES = $(CONAN_{name}_ROOT_FOLDER)/res",
    "CONAN_{name}_LIBRARY_DIRECTORIES = $(CONAN_{name}_ROOT_FOLDER)/lib",
    "CONAN_{name}_LIBRARIES = -l{name}",
    "CONAN_{name}_SYSTEM_LIBS =",
    "CONAN_{name}_FRAMEWORKS_DIRECTORIES =",
    "CONAN_{name}_FRAMEWORKS ="
]

_expected_conf_xconfig = [
    "#include \"{vars_name}\"",
    "HEADER_SEARCH_PATHS[config={configuration}][arch=x86_64][sdk={sdk}] = $(inherited) $(CONAN_{name}_INCLUDE_DIRECTORIES)",
    "GCC_PREPROCESSOR_DEFINITIONS[config={configuration}][arch=x86_64][sdk={sdk}] = $(inherited) $(CONAN_{name}_PREPROCESSOR_DEFINITIONS)",
    "OTHER_CFLAGS[config={configuration}][arch=x86_64][sdk={sdk}] = $(inherited) $(CONAN_{name}_C_COMPILER_FLAGS)",
    "OTHER_CPLUSPLUSFLAGS[config={configuration}][arch=x86_64][sdk={sdk}] = $(inherited) $(CONAN_{name}_CXX_COMPILER_FLAGS)",
    "FRAMEWORK_SEARCH_PATHS[config={configuration}][arch=x86_64][sdk={sdk}] = $(inherited) $(CONAN_{name}_FRAMEWORKS_DIRECTORIES)",
    "LIBRARY_SEARCH_PATHS[config={configuration}][arch=x86_64][sdk={sdk}] = $(inherited) $(CONAN_{name}_LIBRARY_DIRECTORIES)",
    "OTHER_LDFLAGS[config={configuration}][arch=x86_64][sdk={sdk}] = $(inherited) $(CONAN_{name}_LINKER_FLAGS) $(CONAN_{name}_LIBRARIES) $(CONAN_{name}_SYSTEM_LIBS) $(CONAN_{name}_FRAMEWORKS)"
]


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
def test_generator_files():
    client = TestClient()
    client.run("new hello/0.1 -m=cmake_lib")
    client.run("export .")
    client.run("new goodbye/0.1 -m=cmake_lib")
    client.run("export .")
    client.save({"conanfile.txt": "[requires]\nhello/0.1\ngoodbye/0.1\n"}, clean_first=True)

    for sdk in [None, "macosx"]:
        for build_type in ["Release", "Debug"]:

            sdk_setting = "-s os.sdk={}".format(sdk) if sdk else ""
            client.run("install . -g XcodeDeps --build=missing -s build_type={} -s arch=x86_64 {}".
                       format(build_type, sdk_setting))

            for config_file in expected_files(client.current_folder, build_type, "x86_64", sdk):
                assert os.path.isfile(config_file)

            conandeps = client.load("conandeps.xcconfig")
            assert '#include "conan_hello.xcconfig"' in conandeps
            assert '#include "conan_goodbye.xcconfig"' in conandeps

            check_contents(client, ["hello", "goodbye"], build_type, "x86_64", sdk)
