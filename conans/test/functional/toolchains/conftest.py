import os
import shutil

import pytest

from conans.test.assets.pkg_cmake import pkg_cmake
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient


@pytest.fixture(scope="session")
def _transitive_libraries():
    c = TestClient()

    c.save(pkg_cmake("liba", "0.1"))
    c.run("create .")
    c.save(pkg_cmake("libb", "0.1", requires=["liba/0.1"]), clean_first=True)
    c.run("create .")
    c.run("create . -o libb/*:shared=True")
    return c


@pytest.fixture()
def transitive_libraries(_transitive_libraries):
    c = TestClient()
    c.cache_folder = os.path.join(temp_folder(), ".conan2")
    shutil.copytree(_transitive_libraries.cache_folder, c.cache_folder)
    return c
