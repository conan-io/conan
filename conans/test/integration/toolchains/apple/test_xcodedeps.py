import os
import platform

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient

_expected_dep_xconfig = [
    "HEADER_SEARCH_PATHS = $(inherited) $(HEADER_SEARCH_PATHS_{name}_$(CONFIGURATION))",
    "GCC_PREPROCESSOR_DEFINITIONS = $(inherited) $(GCC_PREPROCESSOR_DEFINITIONS_{name}_$(CONFIGURATION))",
    "OTHER_CFLAGS = $(inherited) $(OTHER_CFLAGS_{name}_$(CONFIGURATION))",
    "OTHER_CPLUSPLUSFLAGS = $(inherited) $(OTHER_CPLUSPLUSFLAGS_{name}_$(CONFIGURATION))",
    "FRAMEWORK_SEARCH_PATHS = $(inherited) $(FRAMEWORK_SEARCH_PATHS_{name}_$(CONFIGURATION))",
    "LIBRARY_SEARCH_PATHS = $(inherited) $(LIBRARY_SEARCH_PATHS_{name}_$(CONFIGURATION))",
    "OTHER_LDFLAGS = $(inherited) $(OTHER_LDFLAGS_{name}_$(CONFIGURATION))",
]

_expected_vars_xconfig = [
    "CONAN_{name}_ROOT_FOLDER_{configuration}",
    "CONAN_{name}_BINARY_DIRECTORIES_{configuration} = $(CONAN_{name}_ROOT_FOLDER_{configuration})/bin",
    "CONAN_{name}_C_COMPILER_FLAGS_{configuration} =",
    "CONAN_{name}_CXX_COMPILER_FLAGS_{configuration} =",
    "CONAN_{name}_LINKER_FLAGS_{configuration} =",
    "CONAN_{name}_PREPROCESSOR_DEFINITIONS_{configuration} =",
    "CONAN_{name}_INCLUDE_DIRECTORIES_{configuration} = $(CONAN_{name}_ROOT_FOLDER_{configuration})/include",
    "CONAN_{name}_RESOURCE_DIRECTORIES_{configuration} = $(CONAN_{name}_ROOT_FOLDER_{configuration})/res",
    "CONAN_{name}_LIBRARY_DIRECTORIES_{configuration} = $(CONAN_{name}_ROOT_FOLDER_{configuration})/lib",
    "CONAN_{name}_LIBRARIES_{configuration} = -l{name}",
    "CONAN_{name}_SYSTEM_LIBS_{configuration} =",
    "CONAN_{name}_FRAMEWORKS_DIRECTORIES_{configuration} =",
    "CONAN_{name}_FRAMEWORKS_{configuration} = -framework framework_{name}"
]

_expected_conf_xconfig = [
    "#include \"{vars_name}\"",
    "HEADER_SEARCH_PATHS_{name}_{configuration}[arch=x86_64] = $(CONAN_{name}_INCLUDE_DIRECTORIES_{configuration})",
    "GCC_PREPROCESSOR_DEFINITIONS_{name}_{configuration}[arch=x86_64] = $(CONAN_{name}_PREPROCESSOR_DEFINITIONS_{configuration})",
    "OTHER_CFLAGS_{name}_{configuration}[arch=x86_64] = $(CONAN_{name}_C_COMPILER_FLAGS_{configuration})",
    "OTHER_CPLUSPLUSFLAGS_{name}_{configuration}[arch=x86_64] = $(CONAN_{name}_CXX_COMPILER_FLAGS_{configuration})",
    "FRAMEWORK_SEARCH_PATHS_{name}_{configuration}[arch=x86_64] = $(CONAN_{name}_FRAMEWORKS_DIRECTORIES_{configuration})",
    "LIBRARY_SEARCH_PATHS_{name}_{configuration}[arch=x86_64] = $(CONAN_{name}_LIBRARY_DIRECTORIES_{configuration})",
    "OTHER_LDFLAGS_{name}_{configuration}[arch=x86_64] = $(CONAN_{name}_LINKER_FLAGS_{configuration}) $(CONAN_{name}_LIBRARIES_{configuration}) $(CONAN_{name}_SYSTEM_LIBS_{configuration}) $(CONAN_{name}_FRAMEWORKS_{configuration})"
]


def get_name(configuration, architecture):
    props = [("configuration", configuration),
             ("architecture", architecture)]
    name = "".join("_{}".format(v) for _, v in props if v is not None)
    return name.lower()


def expected_files(current_folder, configuration, architecture):
    files = []
    name = get_name(configuration, architecture)
    deps = ["hello", "goodbye"]
    files.extend(
        [os.path.join(current_folder, "conan_{}{}.xcconfig".format(dep, name)) for dep in deps])
    files.extend(
        [os.path.join(current_folder, "conan_{}_vars{}.xcconfig".format(dep, name)) for dep in deps])
    files.append(os.path.join(current_folder, "conandeps.xcconfig"))
    return files


def check_contents(client, deps, configuration, architecture):
    for dep_name in deps:
        dep_xconfig = client.load("conan_{}.xcconfig".format(dep_name))
        conf_name = "conan_{}{}.xcconfig".format(dep_name,
                                                 get_name(configuration, architecture))

        assert '#include "{}"'.format(conf_name) in dep_xconfig
        for var in _expected_dep_xconfig:
            line = var.format(name=dep_name)
            assert line in dep_xconfig

        vars_name = "conan_{}_vars{}.xcconfig".format(dep_name,
                                                      get_name(configuration, architecture))
        conan_vars = client.load(vars_name)
        for var in _expected_vars_xconfig:
            line = var.format(name=dep_name, configuration=configuration)
            assert line in conan_vars

        conan_conf = client.load(conf_name)
        for var in _expected_conf_xconfig:
            assert var.format(vars_name=vars_name, name=dep_name, configuration=configuration) in conan_conf


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
def test_generator_files():
    client = TestClient()
    client.save({"hello.py": GenConanfile().with_settings("os", "arch", "compiler", "build_type")
                                           .with_package_info(cpp_info={"libs": ["hello"],
                                                                        "frameworks": ['framework_hello']},
                                                              env_info={})})
    client.run("export hello.py hello/0.1@")
    client.save({"goodbye.py": GenConanfile().with_settings("os", "arch", "compiler", "build_type")
                                             .with_package_info(cpp_info={"libs": ["goodbye"],
                                                                          "frameworks": ['framework_goodbye']},
                                                                env_info={})})
    client.run("export goodbye.py goodbye/0.1@")
    client.save({"conanfile.txt": "[requires]\nhello/0.1\ngoodbye/0.1\n"}, clean_first=True)

    for build_type in ["Release", "Debug"]:

        client.run("install . -g XcodeDeps -s build_type={} -s arch=x86_64 --build missing".format(build_type))

        for config_file in expected_files(client.current_folder, build_type, "x86_64"):
            assert os.path.isfile(config_file)

        conandeps = client.load("conandeps.xcconfig")
        assert '#include "conan_hello.xcconfig"' in conandeps
        assert '#include "conan_goodbye.xcconfig"' in conandeps

        check_contents(client, ["hello", "goodbye"], build_type, "x86_64")
