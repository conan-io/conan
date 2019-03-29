"""A setuptools based setup module.
See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

import os
import platform
import re
# To use a consistent encoding
from codecs import open
from os import path

# Always prefer setuptools over distutils
from setuptools import find_packages, setup

here = path.abspath(path.dirname(__file__))


def get_requires(filename):
    requirements = []
    with open(filename, "rt") as req_file:
        for line in req_file.read().splitlines():
            if not line.strip().startswith("#"):
                requirements.append(line)
    return requirements


project_requirements = get_requires("conans/requirements.txt")
if platform.system() == "Darwin":
    project_requirements.extend(get_requires("conans/requirements_osx.txt"))
project_requirements.extend(get_requires("conans/requirements_server.txt"))
dev_requirements = get_requires("conans/requirements_dev.txt")
# The tests utils are used by conan-package-tools
exclude_test_packages = ["conans.test.{}*".format(d)
                         for d in os.listdir(os.path.join(here, "conans/test"))
                         if os.path.isdir(os.path.join(here, "conans/test", d)) and d != "utils"]


def load_version():
    '''Loads a file content'''
    filename = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                            "conans", "__init__.py"))
    with open(filename, "rt") as version_file:
        conan_init = version_file.read()
        version = re.search("__version__ = '([0-9a-z.-]+)'", conan_init).group(1)
        return version


# def generate_long_description_file():
#     import pypandoc
#
#     output = pypandoc.convert('README.md', 'rst')
#     return output

setup(
    name='conan',
    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version=load_version(),  # + ".rc1",

    description='Conan C/C++ package manager',
    # long_description="An open source, decentralized package manager, to automate building and sharing of packages",
    # long_description=generate_long_description_file(),

    # The project's main homepage.
    url='https://conan.io',

    # Author details
    author='JFrog LTD',
    author_email='luism@jfrog.com',

    # Choose your license
    license='MIT',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6'
    ],

    # What does your project relate to?
    keywords=['C/C++', 'package', 'libraries', 'developer', 'manager',
              'dependency', 'tool', 'c', 'c++', 'cpp'],

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=find_packages(exclude=exclude_test_packages),

    # Alternatively, if you want to distribute just a my_module.py, uncomment
    # this:
    #   py_modules=["my_module"],

    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=project_requirements,

    # List additional groups of dependencies here (e.g. development
    # dependencies). You can install these using the following syntax,
    # for example:
    # $ pip install -e .[dev,test]
    extras_require={
        'dev': dev_requirements,
        'test': dev_requirements,
    },

    # If there are data files included in your packages that need to be
    # installed, specify them here.  If using Python 2.6 or less, then these
    # have to be included in MANIFEST.in as well.
    package_data={
        'conans': ['*.txt'],
    },

    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages. See:
    # http://docs.python.org/3.4/distutils/setupscript.html#installing-additional-files # noqa
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
    # data_files=[('my_data', ['data/data_file'])],

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    entry_points={
        'console_scripts': [
            'conan=conans.conan:run',
            'conan_server=conans.conan_server:run',
            'conan_build_info=conans.build_info.command:run'
        ],
    },
)
