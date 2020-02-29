from conans.errors import ConanException

travis = """
env:
   global:
     - CONAN_REFERENCE: "{name}/{version}"
     - CONAN_USERNAME: "{user}"
     - CONAN_LOGIN_USERNAME: "{user}"
     - CONAN_CHANNEL: "{channel}"
     {upload}
linux: &linux
   os: linux
   dist: xenial
   language: python
   python: "3.7"
   services:
     - docker
osx: &osx
   os: osx
   language: generic
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

linux_config = """
      - <<: *linux"""


linux_config_gcc = linux_config + """
        env: CONAN_GCC_VERSIONS={version} CONAN_DOCKER_IMAGE=conanio/gcc{name}
"""

linux_config_clang = linux_config + """
        env: CONAN_CLANG_VERSIONS={version} CONAN_DOCKER_IMAGE=conanio/clang{name}
"""

osx_config = """
      - <<: *osx
        osx_image: xcode{xcode}
        env: CONAN_APPLE_CLANG_VERSIONS={version}
"""

build_py = """from cpt.packager import ConanMultiPackager


if __name__ == "__main__":
    builder = ConanMultiPackager()
    builder.add_common_builds({shared})
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

pip install conan --upgrade
pip install conan_package_tools

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
    PYTHON: "C:\\Python37"

    CONAN_REFERENCE: "{name}/{version}"
    CONAN_USERNAME: "{user}"
    CONAN_LOGIN_USERNAME: "{user}"
    CONAN_CHANNEL: "{channel}"
    {upload}
    matrix:
{configs}

install:
  - set PATH=%PATH%;%PYTHON%/Scripts/
  - pip.exe install conan --upgrade
  - pip.exe install conan_package_tools
  - conan user # It creates the conan data directory

test_script:
  - python build.py
"""

gitlab = """
variables:
    CONAN_USERNAME: "{user}"
    CONAN_REFERENCE: "{name}/{version}"
    CONAN_CHANNEL: "{channel}"
    CONAN_LOGIN_USERNAME: "{user}"
    {upload}
.build-template: &build-template
    before_script:
        - sudo pip install --upgrade conan_package_tools
        - conan user
    script:
        - python build.py
{configs}
"""

gitlab_config_gcc = """
gcc-{version}:
    image: conanio/gcc{name}
    variables:
        CONAN_GCC_VERSIONS: "{version}"
    <<: *build-template
"""

gitlab_config_clang = """
clang-{version}:
    image: conanio/clang{name}
    variables:
        CONAN_CLANG_VERSIONS: "{version}"
    <<: *build-template
"""

circleci = """
version: 2
.conan-steps: &conan-steps
  steps:
    - checkout
    - run:
        name: Update Conan package
        command: |
          chmod +x .circleci/install.sh
          .circleci/install.sh
    - run:
        name: Build recipe
        command: |
          chmod +x .circleci/run.sh
          .circleci/run.sh
        environment:
          CONAN_REFERENCE: "{name}/{version}"
          CONAN_USERNAME: "{user}"
          CONAN_CHANNEL: "{channel}"
          {upload}
jobs:
{configs}
{workflow}
"""

circleci_config_gcc = """
  gcc-{name}:
      docker:
        - image: conanio/gcc{name}
      environment:
        - CONAN_GCC_VERSIONS: "{version}"
      <<: *conan-steps
"""

circleci_config_clang = """
  clang-{name}:
      docker:
        - image: conanio/clang{name}
      environment:
        - CONAN_CLANG_VERSIONS: "{version}"
      <<: *conan-steps
"""

circleci_config_osx = """
  xcode-{name}:
      macos:
        xcode: "{name}"
      environment:
        - CONAN_APPLE_CLANG_VERSIONS: "{version}"
      <<: *conan-steps
"""

circleci_install = """
#!/bin/bash

set -e
set -x

SUDO=sudo

if [[ "$(uname -s)" == 'Darwin' ]]; then
    brew update || brew update
    brew install cmake || true
    SUDO=
fi

$SUDO pip install conan --upgrade
$SUDO pip install conan_package_tools
conan user
"""

circleci_run = """
#!/bin/bash

set -e
set -x

python build.py
"""

circleci_workflow = """
workflows:
  version: 2
  build_and_test:
    jobs:
{jobs}
"""

circleci_job = """      - {job}
"""


def get_build_py(name, shared):
    shared = 'shared_option_name="{}:shared"'.format(name) if shared else ""
    return build_py.format(name=name, shared=shared)


def get_travis(name, version, user, channel, linux_gcc_versions, linux_clang_versions,
               osx_clang_versions, upload_url):
    config = []

    if linux_gcc_versions:
        for gcc in linux_gcc_versions:
            config.append(linux_config_gcc.format(version=gcc, name=gcc.replace(".", "")))

    if linux_clang_versions:
        for clang in linux_clang_versions:
            config.append(linux_config_clang.format(version=clang, name=clang.replace(".", "")))

    xcode_map = {"7.3": "7.3",
                 "8.1": "8.3",
                 "9.0": "9.2",
                 "9.1": "9.3",
                 "10.0": "10"}
    for apple_clang in osx_clang_versions:
        xcode = xcode_map[apple_clang]
        config.append(osx_config.format(xcode=xcode, version=apple_clang))

    configs = "".join(config)
    upload = ('- CONAN_UPLOAD: "%s"\n' % upload_url) if upload_url else ""
    files = {".travis.yml": travis.format(name=name, version=version, user=user, channel=channel,
                                          configs=configs, upload=upload),
             ".travis/install.sh": travis_install,
             ".travis/run.sh": travis_run}
    return files


def get_appveyor(name, version, user, channel, visual_versions, upload_url):
    config = []
    visual_config = """        - APPVEYOR_BUILD_WORKER_IMAGE: Visual Studio {image}
          CONAN_VISUAL_VERSIONS: {version}
"""
    for visual_version in visual_versions:
        image = "2017" if visual_version == "15" else "2015"
        config.append(visual_config.format(image=image, version=visual_version))

    configs = "".join(config)
    upload = ('CONAN_UPLOAD: "%s"\n' % upload_url) if upload_url else ""
    files = {"appveyor.yml": appveyor.format(name=name, version=version, user=user,
                                             channel=channel, configs=configs, upload=upload)}
    return files


def get_gitlab(name, version, user, channel, linux_gcc_versions, linux_clang_versions, upload_url):
    config = []

    if linux_gcc_versions:
        for gcc in linux_gcc_versions:
            config.append(gitlab_config_gcc.format(version=gcc, name=gcc.replace(".", "")))

    if linux_clang_versions:
        for clang in linux_clang_versions:
            config.append(gitlab_config_clang.format(version=clang, name=clang.replace(".", "")))

    configs = "".join(config)
    upload = ('CONAN_UPLOAD: "%s"\n' % upload_url) if upload_url else ""
    files = {".gitlab-ci.yml": gitlab.format(name=name, version=version, user=user, channel=channel,
                                             configs=configs, upload=upload)}
    return files


def get_circleci(name, version, user, channel, linux_gcc_versions, linux_clang_versions,
                 osx_clang_versions, upload_url):
    config = []
    jobs = []

    if linux_gcc_versions:
        for gcc in linux_gcc_versions:
            gcc_name = gcc.replace(".", "")
            config.append(circleci_config_gcc.format(version=gcc, name=gcc_name))
            jobs.append(circleci_job.format(job='gcc-{}'.format(gcc_name)))

    if linux_clang_versions:
        for clang in linux_clang_versions:
            clang_name = clang.replace(".", "")
            config.append(circleci_config_clang.format(version=clang, name=clang_name))
            jobs.append(circleci_job.format(job='clang-{}'.format(clang_name)))

    xcode_map = {"7.3": "7.3",
                 "8.1": "8.3.3",
                 "9.0": "9.2"}
    for apple_clang in osx_clang_versions:
        osx_name = xcode_map[apple_clang]
        config.append(circleci_config_osx.format(name=osx_name, version=apple_clang))
        jobs.append(circleci_job.format(job='xcode-{}'.format(osx_name)))

    configs = "".join(config)
    workflow = circleci_workflow.format(jobs="".join(jobs))
    upload = ('CONAN_UPLOAD: "%s"\n' % upload_url) if upload_url else ""
    files = {".circleci/config.yml": circleci.format(name=name, version=version, user=user,
                                                     channel=channel, configs=configs,
                                                     workflow=workflow, upload=upload),
             ".circleci/install.sh": circleci_install,
             ".circleci/run.sh": circleci_run}
    return files


def ci_get_files(name, version, user, channel, visual_versions, linux_gcc_versions,
                 linux_clang_versions, osx_clang_versions, shared, upload_url, gitlab_gcc_versions,
                 gitlab_clang_versions, circleci_gcc_versions, circleci_clang_versions,
                 circleci_osx_versions):
    if shared and not (visual_versions or linux_gcc_versions or linux_clang_versions or
                       osx_clang_versions or gitlab_gcc_versions or gitlab_clang_versions or
                       circleci_gcc_versions or circleci_clang_versions or circleci_osx_versions):
        raise ConanException("Trying to specify 'shared' in CI, but no CI system specified")
    if not (visual_versions or linux_gcc_versions or linux_clang_versions or osx_clang_versions or
            gitlab_gcc_versions or gitlab_clang_versions or circleci_gcc_versions or
            circleci_clang_versions or circleci_osx_versions):
        return {}
    gcc_versions = ["4.9", "5", "6", "7", "8"]
    clang_versions = ["3.9", "4.0", "5.0", "6.0", "7.0", "7.1"]
    if visual_versions is True:
        visual_versions = ["12", "14", "15"]
    if linux_gcc_versions is True:
        linux_gcc_versions = gcc_versions
    if gitlab_gcc_versions is True:
        gitlab_gcc_versions = gcc_versions
    if circleci_gcc_versions is True:
        circleci_gcc_versions = gcc_versions
    if linux_clang_versions is True:
        linux_clang_versions = clang_versions
    if gitlab_clang_versions is True:
        gitlab_clang_versions = clang_versions
    if circleci_clang_versions is True:
        circleci_clang_versions = clang_versions
    if osx_clang_versions is True:
        osx_clang_versions = ["7.3", "8.1", "9.0", "9.1", "10.0"]
    if circleci_osx_versions is True:
        circleci_osx_versions = ["7.3", "8.1", "9.0"]
    if not visual_versions:
        visual_versions = []
    if not linux_gcc_versions:
        linux_gcc_versions = []
    if not linux_clang_versions:
        linux_clang_versions = []
    if not osx_clang_versions:
        osx_clang_versions = []
    if not gitlab_gcc_versions:
        gitlab_gcc_versions = []
    if not gitlab_clang_versions:
        gitlab_clang_versions = []
    if not circleci_gcc_versions:
        circleci_gcc_versions = []
    if not circleci_clang_versions:
        circleci_clang_versions = []
    if not circleci_osx_versions:
        circleci_osx_versions = []
    files = {"build.py": get_build_py(name, shared)}
    if linux_gcc_versions or osx_clang_versions or linux_clang_versions:
        files.update(get_travis(name, version, user, channel, linux_gcc_versions,
                                linux_clang_versions, osx_clang_versions, upload_url))

    if gitlab_gcc_versions or gitlab_clang_versions:
        files.update(get_gitlab(name, version, user, channel, gitlab_gcc_versions,
                                gitlab_clang_versions, upload_url))

    if circleci_gcc_versions or circleci_clang_versions or circleci_osx_versions:
        files.update(get_circleci(name, version, user, channel, circleci_gcc_versions,
                                  circleci_clang_versions, circleci_osx_versions, upload_url))

    if visual_versions:
        files.update(get_appveyor(name, version, user, channel, visual_versions, upload_url))

    return files
