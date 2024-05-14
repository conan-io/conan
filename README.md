<picture>
  <!-- These are also used for https://github.com/conan-io/.github/blob/main/profile/README.md -->
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/conan-io/conan/develop2/.github/conan2-logo-for-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/conan-io/conan/develop2/.github/conan2-logo-for-light.svg">
  <img alt="JFrog | Conan 2.0 Logo" src="https://raw.githubusercontent.com/conan-io/conan/develop2/.github/conan2-logo-with-bg.svg">
</picture>

# Conan

Decentralized, open-source (MIT), C/C++ package manager.

- Homepage: https://conan.io/
- Github: https://github.com/conan-io/conan
- Docs: https://docs.conan.io
- Slack: https://cpplang.slack.com (#conan channel. Please, click [here](https://join.slack.com/t/cpplang/shared_invite/zt-1snzdn6rp-rOUxF3166oz1_11Tr5H~xg) to get an invitation)
- Twitter: https://twitter.com/conan_io


Conan is a package manager for C and C++ developers:

- It is fully decentralized. Users can host their packages on their servers, privately. Integrates with Artifactory and Bintray.
- Portable. Works across all platforms, including Linux, OSX, Windows (with native and first-class support, WSL, MinGW),
  Solaris, FreeBSD, embedded and cross-compiling, docker, WSL
- Manage binaries. It can create, upload and download binaries for any configuration and platform,
  even cross-compiling, saving lots of time in development and continuous integration. The binary compatibility can be configured
  and customized. Manage all your artifacts in the same way on all platforms.
- Integrates with any build system, including any proprietary and custom one. Provides tested support for major build systems
  (CMake, MSBuild, Makefiles, Meson, etc).
- Extensible: Its Python-based recipes, together with extension points allow for great power and flexibility.
- Large and active community, especially in GitHub (https://github.com/conan-io/conan) and Slack (https://cppalliance.org/slack/ #conan channel).
  This community also creates and maintains packages in ConanCenter and Bincrafters repositories in Bintray.
- Stable. Used in production by many companies, since 1.0 there is a commitment not to break package recipes and documented behavior.


This is the **developer/maintainer** documentation. For user documentation, go to https://docs.conan.io


## Setup

You can run Conan from source in Windows, MacOS, and Linux:

- **Install pip following** [pip docs](https://pip.pypa.io/en/stable/installation/).

- **Clone Conan repository:**

  ```bash
  $ git clone https://github.com/conan-io/conan.git conan-io
  ```

  > **Note**: repository directory name matters, some directories are known to be problematic to run tests (e.g. `conan`). `conan-io` directory name was tested and guaranteed to be working.

- **Install in editable mode**

  ```bash
  $ cd conan-io && sudo pip install -e .
  ```

  If you are in Windows, using ``sudo`` is not required. Some Linux distros won't allow you to put Python packages in editable mode in the root Python installation, and creating a virtual environment ``venv`` first, is mandatory.

- **You are ready, try to run Conan:**

  ```bash
  $ conan --help

  Consumer commands
    install    Installs the requirements specified in a recipe (conanfile.py or conanfile.txt).
    ...

    Conan commands. Type "conan <command> -h" for help
  ```

## Contributing to the project


Feedback and contribution are always welcome in this project.
Please read our [contributing guide](https://github.com/conan-io/conan/blob/develop2/.github/CONTRIBUTING.md).
Also, if you plan to contribute, please add some testing for your changes. You can read the [Conan
tests guidelines section](https://github.com/conan-io/conan/blob/develop2/conans/test/README.md) for
some advice on how to write tests for Conan.

### Running the tests


**Install Python requirements**

```bash
$ python -m pip install -r conans/requirements_server.txt
$ python -m pip install -r conans/requirements_dev.txt
```

If you are not on Windows and you are not using a Python virtual environment, you will need to run these
commands using `sudo`.

Before you can run the tests, you need to set a few environment variables first.

```bash
$ export PYTHONPATH=$PYTHONPATH:$(pwd)
```

On Windows it would be (while being in the Conan root directory):

```bash
$ set PYTHONPATH=.
```

Conan test suite defines and configures some required tools (CMake, Ninja, etc) in the
``conftest.py`` and allows to define a custom ``conftest_user.py``.
Some specific versions, like cmake>=3.15 are necessary.


You can run the tests like this:

```bash
$ python -m pytest .
```

A few minutes later it should print ``OK``:

```bash
............................................................................................
----------------------------------------------------------------------
Ran 146 tests in 50.993s

OK
```

To run specific tests, you can specify the test name too, something like:

```bash
$ python -m pytest conans/test/functional/command/export_test.py::TestRevisionModeSCM::test_revision_mode_scm -s
```

The `-s` argument can be useful to see some output that otherwise is captured by *pytest*.

Also, you can run tests against an instance of Artifactory. Those tests should add the attribute
`artifactory_ready`.

```bash
$ python -m pytest . -m artifactory_ready
```

Some environment variables have to be defined to run them. For example, for an
Artifactory instance that is running on the localhost with default user and password configured, the
variables could take the values:

```bash
$ export CONAN_TEST_WITH_ARTIFACTORY=1
$ export ARTIFACTORY_DEFAULT_URL=http://localhost:8081/artifactory
$ export ARTIFACTORY_DEFAULT_USER=admin
$ export ARTIFACTORY_DEFAULT_PASSWORD=password
```

`ARTIFACTORY_DEFAULT_URL` is the base URL for the Artifactory repo, not one for a specific
repository. Running the tests with a real Artifactory instance will create repos on the fly so please
use a separate server for testing purposes.

## License

[MIT LICENSE](LICENSE.md)
