
# Conan Testing

Conan tests fall into three categories:

- **Unit tests** in `conans/test/unittests` folder. These tests should test small pieces of code like
  functions, methods, or properties. As long as it's possible they should not rely on anything
  external like the file system or system configuration,  and in case they need to do it should be
  mocked.

- **Integration tests** in `conans/test/integration` folder. We consider integration tests the ones that
  only will need pure python to execute, but that may test the interaction between different Conan
  modules. They could test the result of the execution of one or several Conan commands, but shouldn't
  depend on any external tools like compilers, build systems, or version-control system
  tools.

- **Functional tests** in `conans/test/functional` folder. Under this category, we add tests that are
  testing the complete Conan functionality. They may call external tools (please read the section
  below to check the tools installed on the CI). These tests should be avoided as long as
  it's possible as they may take considerable CI time.

## Writing tests

We use [Pytest](https://docs.pytest.org/en/stable/) as the testing framework. There are some
important things to have in mind regarding test discovery and style.

### Naming files and methods

Pytest follows this [convention](https://docs.pytest.org/en/stable/goodpractices.html) for test
discovery:
- Name your Python test files starting in `test_`.

```
test
├── README.md
├── conftest.py
├── unittests
│   ├── __init__.py
│   ├── test_mytest.py
│   ...
...
```

- Tests inside those Python files should follow this name convention:
    - `test` prefixed test functions or methods outside of class.
    - `test` prefixed test functions or methods inside `Test` prefixed test classes (without an
      `__init__` method).

```python
class TestSomeFunctionality:

    def test_plus_name(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
        ...
```

### Marking tests

Please mark your tests if they need to. Besides the [built-in Pytest
markers](https://docs.pytest.org/en/stable/mark.html#mark) we interpret some markers related to
external tools: `cmake`, `gcc`, `clang`, `visual_studio`, `mingw`, `autotools`, `pkg_config`,
`premake`, `meson`, `file`, `git`, `svn`, `compiler` and `conan`. For example:

```python
@pytest.mark.skipif(platform.system() != "Windows", reason="Needs windows for vcvars")
@pytest.mark.visual_studio
def test_vcvars_priority(self):
    client = TestClient()
    ...
```

If the test needs any of those tools to run it should be marked as using that tool and moved to the `conans/test/functional` folder.

### Parametrizing tests

Please, if you need to run several combinations of the same testing code use parameterization. You can use the builtin `pytest.mark.parametrize` decorator to enable parametrization of arguments for a test function:

```python
    @pytest.mark.parametrize("use_components", [False, True])
    def test_build_modules_alias_target(self, use_components):
        ...
```

## Running tests locally

If you want to run the Coman test suite locally, please check the [README on the front
page](https://github.com/conan-io/conan#running-the-tests).


## Installation of tools

Work in progress!

### Windows msys2, mingw64 and mingw32

Download msys2 (64 bit) from msys2.org
To install mingw64 and mingw32 open a msys2 terminal and type:

```
$ pacman -Syuu
$ pacman -S mingw-w64-x86_64-toolchain
$ pacman -S mingw-w64-i686-toolchain
$ pacman -S base-devel gcc
$ pacman -S autoconf-wrapper
$ pacman -S automake

```
