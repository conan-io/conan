# Conan

 A binary dependency manager and hosting service for developers

# Setup

## From binaries

We have installers for [most plattforms here](http://conan.io) but you can run **conan** from sources if you want 

## From source

You can run **conan** client and server in Windows, MacOS, and Linux.

### Install *python and pip*, search in google instructions for your operating system.
### Clone conan repository


    $ git clone https://github.com/conan-co/conan


### Install python requirements

Client:

	$ sudo pip install -r requirements.txt (for running client)
Server:

	$ sudo apt-get install python-dev
    $ sudo pip install -r requirements_server.txt
	
Development:

	$ sudo pip install -r requirements_dev.txt

You can also run the tests:

	$ nosetests .


### Create a launcher
Conan entry point is "conans.conan.main" module. Fill the absolute path of the cloned repository folder:


    #!/usr/bin/env python
    import sys
    sys.path.append('/home/user/conanco/conan') # EDIT!!

    from conans.conan import main
    main(sys.argv[1:])

If you are a Windows user, you can name this file "conan.py" and create a file "conan.bat" that calls the python module:

	CALL python C:/Users/user/conan.py %*

Then add that 'conan' file to your PATH and you are ready:

    $ conan --help

    Conan commands. Type $conan "command" -h for help
      build      calls your project conanfile.py "build" method.
      export     copies a conanfile.py and associated (export) files to your local store,
      install    install in the local store the given requirements.
      remove     Remove any folder from your local/remote store
      search     show local/remote packages
      test       build and run your package test. Must have conanfile.py with "test"
      upload     uploads a conanfile or binary packages from the local store to any remote.
      user       shows or change the current user 

  

## License

[MIT LICENSE](./LICENSE.md)
