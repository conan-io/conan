|Logo|

Conan
=====

Decentralized, open-source (MIT), C/C++ package manager.

- Homepage: https://conan.io/
- Github: https://github.com/conan-io/conan
- Docs: https://docs.conan.io/en/latest/
- Slack: https://cpplang.now.sh/ (#conan channel)
- Twitter: https://twitter.com/conan_io


Conan is a package manager for C and C++ developers:

- It is fully decentralized. Users can host their packages in their servers, privately. Integrates with Artifactory and Bintray.
- Portable. Works across all platforms, including Linux, OSX, Windows (with native and first-class support, WSL, MinGW),
  Solaris, FreeBSD, embedded and cross-compiling, docker, WSL
- Manage binaries. It can create, upload and download binaries for any configuration and platform,
  even cross-compiling, saving lots of time in development and continuous integration. The binary compatibility
  can be configured and customized. Manage all your artifacts in the same way on all platforms.
- Integrates with any build system, including any proprietary and custom one. Provides tested support for major build systems
  (CMake, MSBuild, Makefiles, Meson, etc).
- Extensible: Its python based recipes, together with extensions points allows for great power and flexibility.
- Large and active community, especially in Github (https://github.com/conan-io/conan) and Slack (https://cpplang.now.sh/ #conan channel).
  This community also creates and maintains packages in Conan-center and Bincrafters repositories in Bintray.
- Stable. Used in production by many companies, since 1.0 there is a commitment not to break package recipes and documented behavior. 



+------------------------+-------------------------+-------------------------+-------------------------+
| **master**             | **develop**             |  **Coverage**           |    **Code Climate**     |
+========================+=========================+=========================+=========================+
| |Build Status Master|  | |Build Status Develop|  |  |Develop coverage|     |   |Develop climate|     |
+------------------------+-------------------------+-------------------------+-------------------------+


Setup
=====

Please read https://docs.conan.io/en/latest/installation.html

From binaries
-------------

We have installers for `most platforms here <http://conan.io>`__ but you
can run **conan** from sources if you want.

From pip
--------

Conan is compatible with Python 2 and Python 3.

- Install pip following `pip docs`_.
- Install conan:

    .. code-block:: bash

        $ pip install conan

You can also use `test.pypi.org <https://test.pypi.org/project/conan/#history>`_ repository to install development (non-stable) Conan versions:


    .. code-block:: bash

        $ pip install --index-url https://test.pypi.org/simple/ conan


From Homebrew (OSx)
-------------------

- Install Homebrew following `brew homepage`_.

  .. code-block:: bash

      $ brew update
      $ brew install conan

From source
-----------

You can run **conan** client and server in Windows, MacOS, and Linux.

- **Install pip following** `pip docs`_.

- **Clone conan repository:**

  .. code-block:: bash

      $ git clone https://github.com/conan-io/conan.git

- **Install in editable mode**

    .. code-block:: bash

        $ cd conan && sudo pip install -e .

  If you are in Windows, using ``sudo`` is not required.

- **You are ready, try to run conan:**

  .. code-block::

    $ conan --help

    Consumer commands
      install    Installs the requirements specified in a conanfile (.py or .txt).
      config     Manages configuration. Edits the conan.conf or installs config files.
      get        Gets a file or list a directory of a given reference or package.
      info       Gets information about the dependency graph of a recipe.
      search     Searches package recipes and binaries in the local cache or in a remote.
    Creator commands
      new        Creates a new package recipe template with a 'conanfile.py'.
      create     Builds a binary package for a recipe (conanfile.py) located in the current dir.
      upload     Uploads a recipe and binary packages to a remote.
      export     Copies the recipe (conanfile.py & associated files) to your local cache.
      export-pkg Exports a recipe & creates a package with given files calling 'package'.
      test       Test a package, consuming it with a conanfile recipe with a test() method.
    Package development commands
      source     Calls your local conanfile.py 'source()' method.
      build      Calls your local conanfile.py 'build()' method.
      package    Calls your local conanfile.py 'package()' method.
    Misc commands
      profile    Lists profiles in the '.conan/profiles' folder, or shows profile details.
      remote     Manages the remote list and the package recipes associated with a remote.
      user       Authenticates against a remote with user/pass, caching the auth token.
      imports    Calls your local conanfile.py or conanfile.txt 'imports' method.
      copy       Copies conan recipes and packages to another user/channel.
      remove     Removes packages or binaries matching pattern from local cache or remote.
      alias      Creates and exports an 'alias recipe'.
      download   Downloads recipe and binaries to the local cache, without using settings.

    Conan commands. Type "conan <command> -h" for help

Contributing to the project
===========================

Feedback and contribution are always welcome in this project.
Please read our `contributing guide <https://github.com/conan-io/conan/blob/develop/.github/CONTRIBUTING.md>`_.

Running the tests
=================

Using tox
---------

.. code-block:: bash

    $ tox

It will install the needed requirements and launch `nose` skipping some heavy and slow tests.
If you want to run the full test suite:

.. code-block:: bash

    $ tox -e full

Without tox
-----------

**Install python requirements**

.. code-block:: bash

    $ pip install -r conans/requirements.txt
    $ pip install -r conans/requirements_server.txt
    $ pip install -r conans/requirements_dev.txt


Only in OSX:

.. code-block:: bash

    $ pip install -r conans/requirements_osx.txt # You can omit this one if not running OSX


If you are not Windows and you are not using a python virtual environment, you will need to run these
commands using `sudo`.

Before you can run the tests, you need to set a few environment variables first.

.. code-block:: bash

    $ export PYTHONPATH=$PYTHONPATH:$(pwd)

On Windows it would be (while being in the conan root directory):

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

    $ nosetests .


There are a couple of test attributes defined, as ``slow`` that you can use
to filter the tests, and do not execute them:

.. code-block:: bash

    $ nosetests . -a !slow

A few minutes later it should print ``OK``:

.. code-block:: bash

    ............................................................................................
    ----------------------------------------------------------------------
    Ran 146 tests in 50.993s

    OK

To run specific tests, you can specify the test name too, something like:

.. code-block:: bash

    $ nosetests conans.test.command.config_install_test:ConfigInstallTest.install_file_test --nocapture

The ``--nocapture`` argument can be useful to see some output that otherwise is captured by nosetests.

License
-------

`MIT LICENSE <./LICENSE.md>`__

.. |Build Status Master| image:: https://conan-ci.jfrog.info/buildStatus/icon?job=ConanTestSuite/master
   :target: https://conan-ci.jfrog.info/job/ConanTestSuite/job/master

.. |Build Status Develop| image:: https://conan-ci.jfrog.info/buildStatus/icon?job=ConanTestSuite/develop
   :target: https://conan-ci.jfrog.info/job/ConanTestSuite/job/develop

.. |Master coverage| image:: https://codecov.io/gh/conan-io/conan/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/conan-io/conan/branch/master

.. |Develop coverage| image:: https://codecov.io/gh/conan-io/conan/branch/develop/graph/badge.svg
   :target: https://codecov.io/gh/conan-io/conan/branch/develop

.. |Coverage graph| image:: https://codecov.io/gh/conan-io/conan/branch/develop/graphs/tree.svg
   :height: 50px
   :width: 50 px
   :alt: Conan develop coverage

.. |Develop climate| image:: https://api.codeclimate.com/v1/badges/081b53e570d5220b34e4/maintainability.svg
   :target: https://codeclimate.com/github/conan-io/conan/maintainability
   
.. |Logo| image:: https://conan.io/img/jfrog_conan_logo.png


.. _`pip docs`: https://pip.pypa.io/en/stable/installing/

.. _`brew homepage`: http://brew.sh/
