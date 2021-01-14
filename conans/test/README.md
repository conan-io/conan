
# Conan Testing

Conan tests are divided in three categories:

- **Unit tests** in `conans/test/unittests` folder. These tests should test small pieces of code such as
  functions, methods or properties. As long as it is possible they should not rely on anything
  external like the file system or system configuration and in case they need to do, that should be
  mocked.
- **Integration tests** in `conans/test/integration` folder. We consider integration tests the ones that
  only will need pure python to execute but that may test interaction between different Conan
  modules. They may test the result of the execution of one or several Conan commands but should
  never depend on any external tools like compilers, build systems or version-control system tools.
- **Functional tests** in `conans/test/functional` folder. Under this category we add tests that are
  testing the complete Conan functionality. They may call external tools (please read the section
  bellow to check the tools we have installed in the CI). These tests should be avoided as long as
  it's possible as they may take considerable CI time.

## Writting tests

We use [Pytest](https://docs.pytest.org/en/stable/) as the testing framework. There are some
important thing to have in mind regarding test discovery and style.

### Naming files and methods

Pytest follows this [convention](https://docs.pytest.org/en/stable/goodpractices.html) for test
discovery:
- Name your Python tests files ending in `_test.py`.

```
test
├── README.md
├── conftest.py
├── unittests
│   ├── __init__.py
│   ├── basic_build_test.py
│   ...
...
```

- Tests inside those Python files should follow this name convention:
    - test prefixed test functions or methods outside of class.
    - test prefixed test functions or methods inside `Test` prefixed test classes (without an
      `__init__` method).

```python
class TestSomeFunctionality:

    def test_plus_name(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
        ...
```

### Marking tests

Please mark your tests if they need to. Besides the [builtin Pytest
markers](https://docs.pytest.org/en/stable/mark.html#mark) we interpret some markers related to
external tools: `cmake`, `gcc`, `clang`, `visual_studio`, `mingw`, `autotools`, `pkg_config`,
`premake`, `meson`, `file`, `git`, `svn`, `compiler`, `conan`. For example:

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

### Running tests locally

If you want to run the Coman test suite locally, please check the [README in the front
page](https://github.com/conan-io/conan).
