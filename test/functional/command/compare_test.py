import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.mark.parametrize("old_args", [
    "-op=. -or=pkg/1.0",
    "-or=pkg/1.0"
])
@pytest.mark.parametrize("new_args", [
    "-np=. -nr=pkg/2.0",
    "-nr=pkg/2.0#a9ec2e5fbb166568d4670a9cd1ef4b26",
])
@pytest.mark.parametrize("formatter", [
    "-f=json",
    "-f=html"
])
@pytest.mark.tool("git")
def test_compare_paths(old_args, new_args, formatter):
    tc = TestClient(light=True, default_server_user=True)
    tc.save({"conanfile.py": GenConanfile("pkg")})
    tc.run("create . --version=1.0")
    tc.run("create . --version=2.0")

    tc.run("upload * -r=default -c")
    tc.run("remove * -c")

    tc.run(f"compare {old_args} {new_args} {formatter}")
    # Does not crash
    # TODO: check output?
