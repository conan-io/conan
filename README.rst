Conan
=====

A distributed, open-source, C/C++ package manager.

+------------------------+-------------------------+
| **master**             | **develop**             |
+========================+=========================+
| |Build Status Master|  | |Build Status Develop|  |
+------------------------+-------------------------+


+------------------------+---------------------------+---------------------------------------------+
| **Coverage master**    | **Coverage develop**      | **Coverage graph**                          |
+========================+===========================+=============================================+
| |Master coverage|      | |Develop coverage|        | |Coverage graph|                            |
+------------------------+---------------------------+---------------------------------------------+


Setup
======

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

- **Install python requirements**

  - For running the client:

    .. code-block:: bash

        $ sudo pip install -r conans/requirements.txt


    In OSX you should also install:

    .. code-block:: bash

        $ sudo pip install -r conans/requirements_osx.txt

  - For running the server:

    .. code-block:: bash

        $ sudo apt-get install python-dev
        $ sudo pip install -r conans/requirements_server.txt

  - Development (for running the tests):

    .. code-block:: bash

        $ sudo pip install -r conans/requirements_dev.txt

  If you are in Windows, using ``sudo`` is not required.


- **Create a launcher**

  Conan entry point is "conans.conan.main" module. Fill the absolute path
  of the cloned repository folder:

  .. code-block:: bash

      #!/usr/bin/env python
      import sys
      conan_sources_dir = '/home/user/conan'  # EDIT!!

      sys.path.insert(1, conan_sources_dir)
      # Or append to sys.path to prioritize a binary installation before the source code one
      # sys.path.append(conan_sources_dir)

      from conans.conan import main
      main(sys.argv[1:])

  If you are a Windows user, you can name this file *conan.py* and create
  a file *conan.bat* that calls the python module:

  .. code-block:: bash

      CALL python C:/Users/user/conan.py %*

- **Then add that 'conan' file to your PATH and you are ready:**

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
      create     Builds a binary package for recipe (conanfile.py) located in current dir.
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
      remote     Manages the remote list and the package recipes associated to a remote.
      user       Authenticates against a remote with user/pass, caching the auth token.
      imports    Calls your local conanfile.py or conanfile.txt 'imports' method.
      copy       Copies conan recipes and packages to another user/channel.
      remove     Removes packages or binaries matching pattern from local cache or remote.
      alias      Creates and exports an 'alias recipe'.
      download   Downloads recipe and binaries to the local cache, without using settings.

    Conan commands. Type "conan <command> -h" for help

Running the tests
=================

Make sure that the Python requirements for testing have been installed, as explained above.

Before you can run the tests, you need to set a few environment
variables first.

.. code-block:: bash

    $ export PYTHONPATH=$PYTHONPATH:$(pwd)

On Windows it would be (while being in the conan root directory):

.. code-block:: bash

    $ set PYTHONPATH=.

Ensure that your ``cmake`` has version 2.8 or later. You can see the
version with the following command:

.. code-block:: bash

    $ cmake --version

The appropriate values of ``CONAN_COMPILER`` and
``CONAN_COMPILER_VERSION`` depend on your operating system and your
requirements.

These should work for the GCC from ``build-essential`` on Ubuntu 14.04:

.. code-block:: bash

    $ export CONAN_COMPILER=gcc
    $ export CONAN_COMPILER_VERSION=4.8

These should work for OS X:

.. code-block:: bash

    $ export CONAN_COMPILER=clang
    $ export CONAN_COMPILER_VERSION=3.5

Finally, there are some tests that use conan to package Go-lang
libraries, so you might **need to install go-lang** in your computer and
add it to the path.

You can run the actual tests like this:

.. code-block:: bash

    $ nosetests .


There are a couple of test attributes defined, as ``slow``, or ``golang`` that you can use
to filter the tests, and do not execute them:

.. code-block:: bash

    $ nosetests . -a !golang

A few minutes later it should print ``OK``:

.. code-block:: bash

    ............................................................................................
    ----------------------------------------------------------------------
    Ran 146 tests in 50.993s

    OK

To run specific tests, you can specify the test name too, something like:

.. code-block:: bash

    $ nosetests conans.test.integration.flat_requirements_test --nocapture

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

.. _`pip docs`: https://pip.pypa.io/en/stable/installing/

.. _`brew homepage`: http://brew.sh/
