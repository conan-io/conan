import os
import shutil

import pytest

from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient


@pytest.fixture(scope="session")
def _matrix_client():
    """
    engine/1.0->matrix/1.0
    """
    c = TestClient()
    c.run("new cmake_lib -d name=matrix -d version=1.0")
    c.run("create . -tf=")
    return c


@pytest.fixture()
def matrix_client(_matrix_client):
    c = TestClient()
    c.cache_folder = os.path.join(temp_folder(), ".conan2")
    shutil.copytree(_matrix_client.cache_folder, c.cache_folder)
    return c


@pytest.fixture(scope="session")
def _transitive_libraries(_matrix_client):
    """
    engine/1.0->matrix/1.0
    """
    c = TestClient()
    c.cache_folder = os.path.join(temp_folder(), ".conan2")
    shutil.copytree(_matrix_client.cache_folder, c.cache_folder)
    c.save({}, clean_first=True)
    c.run("new cmake_lib -d name=engine -d version=1.0 -d requires=matrix/1.0")
    # create both static and shared
    c.run("create . -tf=")
    c.run("create . -o engine/*:shared=True -tf=")
    return c


@pytest.fixture()
def transitive_libraries(_transitive_libraries):
    c = TestClient()
    c.cache_folder = os.path.join(temp_folder(), ".conan2")
    shutil.copytree(_transitive_libraries.cache_folder, c.cache_folder)
    return c
