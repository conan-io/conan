from conans.errors import ConanException

travis = """os: linux
language: python
sudo: required
services:
  - docker
env:
  global:
    - CONAN_REFERENCE: "{name}/{version}"
    - CONAN_USERNAME: "{user}"
    - CONAN_CHANNEL: "{channel}"
    - CONAN_TOTAL_PAGES: 1
    {upload}
matrix:
   include:
{configs}
install:
  - chmod +x .travis/install.sh
  - ./.travis/install.sh

script:
  - chmod +x .travis/run.sh
  - ./.travis/run.sh
"""

linux_config = """      - os: linux
        services:
          - docker
        sudo: required
        language: python
        env: CONAN_GCC_VERSIONS={version} CONAN_CURRENT_PAGE=gcc_{name} CONAN_USE_DOCKER=1
"""

osx_config = """      - os: osx
        osx_image: xcode{xcode}
        language: generic
        env: CONAN_CURRENT_PAGE=apple-clang_{version}
"""

build_py = """from conan.packager import ConanMultiPackager


if __name__ == "__main__":
    builder = ConanMultiPackager(username="{user}", channel="{channel}",
                                 visual_versions={visual_versions},
                                 gcc_versions={linux_gcc_versions},
                                 apple_clang_versions={osx_clang_versions})
    builder.add_common_builds({shared})
    builder.use_default_named_pages()
    builder.run()
"""

travis_install = """#!/bin/bash

set -e
set -x

if [[ "$(uname -s)" == 'Darwin' ]]; then
    brew update || brew update
    brew outdated pyenv || brew upgrade pyenv
    brew install pyenv-virtualenv
    brew install cmake || true

    if which pyenv > /dev/null; then
        eval "$(pyenv init -)"
    fi

    pyenv install 2.7.10
    pyenv virtualenv 2.7.10 conan
    pyenv rehash
    pyenv activate conan
fi

pip install conan_package_tools # It install conan too
pip install conan --upgrade
conan user
"""


travis_run = """#!/bin/bash

set -e
set -x

if [[ "$(uname -s)" == 'Darwin' ]]; then
    if which pyenv > /dev/null; then
        eval "$(pyenv init -)"
    fi
    pyenv activate conan
fi

python build.py
"""

appveyor = r"""build: false

environment:
    PYTHON: "C:\\Python27"
    PYTHON_VERSION: "2.7.8"
    PYTHON_ARCH: "32"

    CONAN_REFERENCE: "{name}/{version}"
    CONAN_USERNAME: "{user}"
    CONAN_CHANNEL: "{channel}"
    VS150COMNTOOLS: "C:\\Program Files (x86)\\Microsoft Visual Studio\\2017\\Community\\Common7\\Tools\\"
    {upload}
    matrix:
{configs}

install:
  - set PATH=%PATH%;%PYTHON%/Scripts/
  - pip.exe install conan_package_tools # It install conan too
  - pip.exe install conan --upgrade
  - conan user # It creates the conan data directory

test_script:
  - python build.py
"""


def get_build_py(name, user, channel, visual_versions, linux_gcc_versions, osx_clang_versions,
                 shared):
    shared = 'shared_option_name="{}:shared"'.format(name) if shared else ""
    visual_versions = '[%s]' % ", ".join('"%s"' % str(v) for v in visual_versions)
    linux_gcc_versions = '[%s]' % ", ".join('"%s"' % str(v) for v in linux_gcc_versions)
    osx_clang_versions = '[%s]' % ", ".join('"%s"' % str(v) for v in osx_clang_versions)
    return build_py.format(name=name, user=user, channel=channel, visual_versions=visual_versions,
                           linux_gcc_versions=linux_gcc_versions,
                           osx_clang_versions=osx_clang_versions,
                           shared=shared)


def get_travis(name, version, user, channel, linux_gcc_versions, osx_clang_versions, upload_url):
    config = []
    for gcc in linux_gcc_versions:
        config.append(linux_config.format(version=gcc, name=gcc.replace(".", "")))

    xcode_map = {"8.1": "8.3",
                 "8.0": "8.2",
                 "7.3": "7.3"}
    for apple_clang in osx_clang_versions:
        xcode = xcode_map[apple_clang]
        config.append(osx_config.format(xcode=xcode, version=apple_clang.replace(".", "")))

    configs = "".join(config)
    upload = ("- CONAN_UPLOAD: %s\n" % upload_url) if upload_url else ""
    files = {".travis.yml": travis.format(name=name, version=version, user=user, channel=channel,
                                          configs=configs, upload=upload),
             ".travis/install.sh": travis_install,
             ".travis/run.sh": travis_run}
    return files


def get_appveyor(name, version, user, channel, visual_versions, upload_url):
    config = []
    visual_config = """        - APPVEYOR_BUILD_WORKER_IMAGE: Visual Studio {image}
          CONAN_CURRENT_PAGE: VisualStudio_{version}_x86{arch}
"""
    for visual_version in visual_versions:
        image = "2017" if visual_version == "15" else "2015"
        if visual_version in ["12", "14", "15"]:
            config.append(visual_config.format(image=image, version=visual_version, arch="_64"))
        config.append(visual_config.format(image=image, version=visual_version, arch=""))

    configs = "".join(config)
    upload = ("CONAN_UPLOAD: %s\n" % upload_url) if upload_url else ""
    files = {"appveyor.yml": appveyor.format(name=name, version=version, user=user,
                                             channel=channel, configs=configs, upload=upload)}
    return files


def ci_get_files(name, version, user, channel, visual_versions, linux_gcc_versions,
                 osx_clang_versions, shared, upload_url):
    if shared and not (visual_versions or linux_gcc_versions or osx_clang_versions):
        raise ConanException("Trying to specify 'shared' in CI, but no CI system specified")
    if not (visual_versions or linux_gcc_versions or osx_clang_versions):
        return {}
    if visual_versions is True:
        visual_versions = ["12", "14", "15"]
    if linux_gcc_versions is True:
        linux_gcc_versions = ["4.9", "5.4", "6.3"]
    if osx_clang_versions is True:
        osx_clang_versions = ["7.3", "8.0", "8.1"]
    if not visual_versions:
        visual_versions = []
    if not linux_gcc_versions:
        linux_gcc_versions = []
    if not osx_clang_versions:
        osx_clang_versions = []
    build_py = get_build_py(name, user, channel, visual_versions, linux_gcc_versions,
                            osx_clang_versions, shared)
    files = {"build.py": build_py}
    if linux_gcc_versions or osx_clang_versions:
        files.update(get_travis(name, version, user, channel, linux_gcc_versions,
                                osx_clang_versions, upload_url))
    if visual_versions:
        files.update(get_appveyor(name, version, user, channel, visual_versions, upload_url))

    return files
