import os
import platform

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.integration.toolchains.apple.test_xcodetoolchain import _get_filename
from conans.test.utils.tools import TestClient

_expected_dep_xconfig = [
    "HEADER_SEARCH_PATHS = $(inherited) $(HEADER_SEARCH_PATHS_{name}_{name})",
    "GCC_PREPROCESSOR_DEFINITIONS = $(inherited) $(GCC_PREPROCESSOR_DEFINITIONS_{name}_{name})",
    "OTHER_CFLAGS = $(inherited) $(OTHER_CFLAGS_{name}_{name})",
    "OTHER_CPLUSPLUSFLAGS = $(inherited) $(OTHER_CPLUSPLUSFLAGS_{name}_{name})",
    "FRAMEWORK_SEARCH_PATHS = $(inherited) $(FRAMEWORK_SEARCH_PATHS_{name}_{name})",
    "LIBRARY_SEARCH_PATHS = $(inherited) $(LIBRARY_SEARCH_PATHS_{name}_{name})",
    "OTHER_LDFLAGS = $(inherited) $(OTHER_LDFLAGS_{name}_{name})",
]

_expected_conf_xconfig = [
    "HEADER_SEARCH_PATHS_{name}_{name}[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] = ",
    "GCC_PREPROCESSOR_DEFINITIONS_{name}_{name}[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] = ",
    "OTHER_CFLAGS_{name}_{name}[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] = ",
    "OTHER_CPLUSPLUSFLAGS_{name}_{name}[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] = ",
    "FRAMEWORK_SEARCH_PATHS_{name}_{name}[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] = ",
    "LIBRARY_SEARCH_PATHS_{name}_{name}[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] = ",
    "OTHER_LDFLAGS_{name}_{name}[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] = "
]


def expected_files(current_folder, configuration, architecture, sdk, sdk_version):
    files = []
    name = _get_filename(configuration, architecture, sdk, sdk_version)
    deps = ["hello", "goodbye"]
    files.extend(
        [os.path.join(current_folder, "conan_{dep}_{dep}{name}.xcconfig".format(dep=dep, name=name)) for dep in deps])
    files.append(os.path.join(current_folder, "conandeps.xcconfig"))
    return files


def check_contents(client, deps, configuration, architecture, sdk, sdk_version):
    for dep_name in deps:
        dep_xconfig = client.load("conan_{dep}_{dep}.xcconfig".format(dep=dep_name))
        conf_name = "conan_{}_{}{}.xcconfig".format(dep_name, dep_name,
                                                 _get_filename(configuration, architecture, sdk, sdk_version))

        assert '#include "{}"'.format(conf_name) in dep_xconfig
        for var in _expected_dep_xconfig:
            line = var.format(name=dep_name)
            assert line in dep_xconfig

        conan_conf = client.load(conf_name)
        for var in _expected_conf_xconfig:
            assert var.format(name=dep_name, configuration=configuration, architecture=architecture,
                              sdk=sdk, sdk_version=sdk_version) in conan_conf


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

        client.run("install . -g XcodeDeps -s build_type={} -s arch=x86_64 -s os.sdk=macosx -s os.sdk_version=12.1 --build missing".format(build_type))

        for config_file in expected_files(client.current_folder, build_type, "x86_64", "macosx", "12.1"):
            assert os.path.isfile(config_file)

        conandeps = client.load("conandeps.xcconfig")
        assert '#include "conan_hello.xcconfig"' in conandeps
        assert '#include "conan_goodbye.xcconfig"' in conandeps

        conan_config = client.load("conan_config.xcconfig")
        assert '#include "conandeps.xcconfig"' in conan_config

        check_contents(client, ["hello", "goodbye"], build_type, "x86_64", "macosx", "12.1")
