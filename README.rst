|Logo|

Conan
=====

Decentralized, open-source (MIT), C/C++ package manager.

- Homepage: https://conan.io/
- Github: https://github.com/conan-io/conan
- Docs: https://docs.conan.io/en/latest/
- Slack: https://cpplang-inviter.cppalliance.org/ (#conan channel)
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
- Extensible: Its python based recipes, together with extensions points allows for great power and flexibility.
- Large and active community, especially in Github (https://github.com/conan-io/conan) and Slack (https://cpplang-inviter.cppalliance.org/ #conan channel).
  This community also creates and maintains packages in ConanCenter and Bincrafters repositories in Bintray.
- Stable. Used in production by many companies, since 1.0 there is a commitment not to break package recipes and documented behavior.



+-------------------------+-------------------------+
| **develop**             |    **Code Climate**     |
+=========================+=========================+
| |Build Status Develop|  |   |Develop climate|     |
+-------------------------+-------------------------+


Setup
=====

Please read https://docs.conan.io/en/latest/installation.html to know how to
install and start using Conan. TL;DR:

.. code-block::

   $ pip install conan


Install a development version
-----------------------------

You can run **Conan** client and server in Windows, MacOS, and Linux.

- **Install pip following** `pip docs`_.

- **Clone Conan repository:**

  .. code-block:: bash

      $ git clone https://github.com/conan-io/conan.git conan-io

 NOTE: repository directory name matters, some directories are known to be problematic to run tests (e.g. `conan`). `conan-io` directory name was tested and guaranteed to be working.

- **Install in editable mode**

  .. code-block:: bash

      $ cd conan-io && sudo pip install -e .

  If you are in Windows, using ``sudo`` is not required.

- **You are ready, try to run Conan:**

  .. code-block::

    $ conan --help

    Consumer commands
      install    Installs the requirements specified in a recipe (conanfile.py or conanfile.txt).
      config     Manages Conan configuration.
      get        Gets a file or list a directory of a given reference or package.
      info       Gets information about the dependency graph of a recipe.
      search     Searches package recipes and binaries in the local cache or a remote. Unless a
                 remote is specified only the local cache is searched.
    Creator commands
      new        Creates a new package recipe template with a 'conanfile.py' and optionally,
                 'test_package' testing files.
      create     Builds a binary package for a recipe (conanfile.py).
      upload     Uploads a recipe and binary packages to a remote.
      export     Copies the recipe (conanfile.py & associated files) to your local cache.
      export-pkg Exports a recipe, then creates a package from local source and build folders.
      test       Tests a package consuming it from a conanfile.py with a test() method.
    Package development commands
      source     Calls your local conanfile.py 'source()' method.
      build      Calls your local conanfile.py 'build()' method.
      package    Calls your local conanfile.py 'package()' method.
      editable   Manages editable packages (packages that reside in the user workspace, but are
                 consumed as if they were in the cache).
      workspace  Manages a workspace (a set of packages consumed from the user workspace that
                 belongs to the same project).
    Misc commands
      profile    Lists profiles in the '.conan/profiles' folder, or shows profile details.
      remote     Manages the remote list and the package recipes associated with a remote.
      user       Authenticates against a remote with user/pass, caching the auth token.
      imports    Calls your local conanfile.py or conanfile.txt 'imports' method.
      copy       Copies conan recipes and packages to another user/channel.
      remove     Removes packages or binaries matching pattern from local cache or remote.
      alias      Creates and exports an 'alias package recipe'.
      download   Downloads recipe and binaries to the local cache, without using settings.
      inspect    Displays conanfile attributes, like name, version, and options. Works locally,
                 in local cache and remote.
      help       Shows help for a specific command.
      lock       Generates and manipulates lock files.
      frogarian  Conan The Frogarian
    
    Conan commands. Type "conan <command> -h" for help

Contributing to the project
===========================

Feedback and contribution are always welcome in this project.
Please read our `contributing guide <https://github.com/conan-io/conan/blob/develop/.github/CONTRIBUTING.md>`_.
Also, if you plan to contribute, please add some testing for your changes. You can read the `Conan
tests guidelines section <https://github.com/conan-io/conan/blob/develop/conans/test/README.md>`_ for
some advise on how to write tests for Conan.

Running the tests
=================

Using tox
---------

.. code-block:: bash

    $ python -m tox

It will install the needed requirements and launch `pytest` skipping some heavy and slow tests.
If you want to run the full test suite:

.. code-block:: bash

    $ python -m tox -e full

Without tox
-----------

**Install python requirements**

.. code-block:: bash

    $ python -m pip install -r conans/requirements.txt
    $ python -m pip install -r conans/requirements_server.txt
    $ python -m pip install -r conans/requirements_dev.txt

If you are not Windows and you are not using a python virtual environment, you will need to run these
commands using `sudo`.

Before you can run the tests, you need to set a few environment variables first.

.. code-block:: bash

    $ export PYTHONPATH=$PYTHONPATH:$(pwd)

On Windows it would be (while being in the Conan root directory):

.. code-block:: bash

    $ set PYTHONPATH=.

Ensure that your ``cmake`` has version 2.8 or later. You can see the
version with the following command:

.. code-block:: bash

    $ cmake --version

The appropriate values of ``CONAN_COMPILER`` and ``CONAN_COMPILER_VERSION`` depend on your
operating system and your requirements.

These should work for the GCC from ``build-essential`` on Ubuntu 14.04:

.. code-block:: bash

    $ export CONAN_COMPILER=gcc
    $ export CONAN_COMPILER_VERSION=4.8

These should work for OS X:

.. code-block:: bash

    $ export CONAN_COMPILER=clang
    $ export CONAN_COMPILER_VERSION=3.5

You can run the actual tests like this:

.. code-block:: bash

    $ python -m pytest .


There are a couple of test attributes defined, as ``slow`` that you can use
to filter the tests, and do not execute them:

.. code-block:: bash

    $ python -m pytest . -m "not slow"

A few minutes later it should print ``OK``:

.. code-block:: bash

    ............................................................................................
    ----------------------------------------------------------------------
    Ran 146 tests in 50.993s

    OK

To run specific tests, you can specify the test name too, something like:

.. code-block:: bash

    $ python -m pytest conans/test/unittests/client/cmd/export_test.py::ExportTest::test_export_warning -s

The ``-s`` argument can be useful to see some output that otherwise is captured by pytest.

Also, you can run tests against an instance of Artifactory. Those tests should add the attribute
``artifactory_ready``.

.. code-block:: bash

    $ python -m pytest . -m artifactory_ready

Some environment variables have to be defined to run them. For example, for an
Artifactory instance that is running on the localhost with default user and password configured, the
variables could take the values:

.. code-block:: bash

    $ export CONAN_TEST_WITH_ARTIFACTORY=1
    $ export ARTIFACTORY_DEFAULT_URL=http://localhost:8081/artifactory
    $ export ARTIFACTORY_DEFAULT_USER=admin
    $ export ARTIFACTORY_DEFAULT_PASSWORD=password

``ARTIFACTORY_DEFAULT_URL`` is the base url for the Artifactory repo, not one for a specific
repository. Running the tests with a real Artifactory instance will create repos on the fly so please
use a separate server for testing purposes.

License
-------

`MIT LICENSE <./LICENSE.md>`__

.. |Build Status Develop| image:: https://ci.conan.io/buildStatus/icon?job=ConanTestSuite/develop
   :target: https://ci.conan.io/job/ConanTestSuite/job/develop/

.. |Develop climate| image:: https://api.codeclimate.com/v1/badges/081b53e570d5220b34e4/maintainability.svg
   :target: https://codeclimate.com/github/conan-io/conan/maintainability

.. |Logo| image:: https://conan.io/img/jfrog_conan_logo.png


.. _`pip docs`: https://pip.pypa.io/en/stable/installation/
