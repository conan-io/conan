import os

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.files import save


@pytest.mark.tool("fish")
def test_virtualenv_fish():
    cache_folder = os.path.join(temp_folder(), "[sub] folder")
    client = TestClient(cache_folder)
    conanfile = str(GenConanfile("pkg", "0.1"))
    conanfile += """

    def package_info(self):
        self.buildenv_info.define_path("MYPATH1", "/path/to/ar")
    """
    client.save({"conanfile.py": conanfile})
    client.run("create .")
    save(client.cache.new_config_path, "tools.env.virtualenv:fish=True\n")
    client.save({"conanfile.py": GenConanfile("app", "0.1").with_requires("pkg/0.1")})
    client.run("install . -s:a os=Linux")

    assert not os.path.exists(os.path.join(client.current_folder, "conanbuildenv.sh"))
    assert not os.path.exists(os.path.join(client.current_folder, "conanbuildenv.bat"))
    assert not os.path.exists(os.path.join(client.current_folder, "conanrunenv.sh"))
    assert not os.path.exists(os.path.join(client.current_folder, "conanrunenv.bat"))

    assert os.path.exists(os.path.join(client.current_folder, "conanbuildenv.fish"))
    assert os.path.exists(os.path.join(client.current_folder, "conanrunenv.fish"))

    with open(os.path.join(client.current_folder, "conanbuildenv.fish"), "r") as f:
        buildenv = f.read()
        assert 'set -gx MYPATH1 "/path/to/ar"' in buildenv

    client.run_command("fish -c 'source conanbuildenv.fish && set'")
    assert 'MYPATH1 /path/to/ar' in client.out

    client.run_command("fish -c 'source conanbuildenv.fish && set && source deactivate_conanbuildenv.fish && set'")
    assert str(client.out).count('MYPATH1 /path/to/ar') == 1
