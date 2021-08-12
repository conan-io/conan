from collections import OrderedDict
from unittest.mock import Mock

import pytest

from conans import ConanFile
from conans.model.conanfile_interface import ConanFileInterface
from conans.model.dependencies import Requirement, ConanFileDependencies
from conans.model.ref import ConanFileReference

@pytest.fixture
def dependencies_object():

    dep1 = ConanFile(Mock(), None)
    dep1._conan_node = Mock()
    dep1._conan_node.ref = ConanFileReference.loads("dep1/1.0")

    dep2 = ConanFile(Mock(), None)
    dep2._conan_node = Mock()
    dep2._conan_node.ref = ConanFileReference.loads("dep2/1.0")

    req1 = Requirement(ConanFileReference.loads("dep1/1.0"))
    req2 = Requirement(ConanFileReference.loads("dep2/1.0"))
    deps = OrderedDict()
    deps[req1] = ConanFileInterface(dep1)
    deps[req2] = ConanFileInterface(dep2)
    return ConanFileDependencies(deps)


def test_in_operator(dependencies_object):
    assert "dep1" in dependencies_object
    assert "dep2" in dependencies_object
    assert "foo" not in dependencies_object
