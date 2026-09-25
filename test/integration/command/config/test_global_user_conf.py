from conan.test.utils.tools import TestClient


def test_global_user_conf_overrides():
    tc = TestClient(light=True)
    tc.save_home({
        "global.conf": "tools.build:jobs=4\n",
        "global_user.conf": "tools.build:jobs=16\n",
    })
    tc.run("config show *")
    assert "tools.build:jobs: 16" in tc.out


def test_global_user_conf_adds_new_key():
    tc = TestClient(light=True)
    tc.save_home({
        "global.conf": "tools.build:jobs=4\n",
        "global_user.conf": "tools.build:verbosity=verbose\n",
    })
    tc.run("config show *")
    assert "tools.build:verbosity: verbose" in tc.out
    assert "tools.build:jobs: 4" in tc.out
