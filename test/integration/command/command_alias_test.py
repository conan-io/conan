import json
import os
import textwrap

from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient


class TestCommandAlias:
    """ Tests for the CLI command alias system: a single plain-text "command_alias" file in the
    Conan home that translates a CLI input into a real Conan command (+ its arguments), inspired
    by Git aliases. There is no command to manage it, it is just a file, meant to be edited
    directly or distributed via "conan config install"/"conan config install-pkg".
    Not to be confused with the legacy recipe 'alias' feature tested in 'alias_test.py'.
    """

    def test_alias_simple_command(self):
        c = TestClient()
        c.save_home({"command_alias": "home = config home\n"})
        c.run("home")
        assert c.cache_folder in c.out

    def test_alias_with_extra_args(self):
        c = TestClient()
        c.run("remote add myremote https://fake.example.com")
        c.save_home({"command_alias": "rem = remote\n"})
        c.run("rem list")
        assert "myremote" in c.out

    def test_alias_appends_user_args_after_alias_args(self):
        c = TestClient()
        c.run("remote add myremote https://fake.example.com")
        c.save_home({"command_alias": "myremotes = remote list\n"})
        c.run("myremotes --format=json")
        info = json.loads(c.stdout)
        assert info[0]["name"] == "myremote"

    def test_alias_does_not_shadow_real_command(self):
        # A real command always takes precedence over any alias with the same name
        c = TestClient()
        c.run("remote add myremote https://fake.example.com")
        c.save_home({"command_alias": "remote = list *\n"})
        c.run("remote list")
        assert "myremote" in c.out

    def test_alias_not_chained(self):
        # Aliases are only expanded once: an alias expanding to another alias name (instead of
        # a real command) is not resolved further
        c = TestClient()
        c.save_home({"command_alias": textwrap.dedent("""\
            a1 = rem list
            rem = remote
            """)})
        c.run("a1", assert_error=True)
        assert "'rem' is not a Conan command" in c.out

    def test_alias_ignores_comments_and_malformed_lines(self):
        c = TestClient()
        c.save_home({"command_alias": textwrap.dedent("""\
            # this is a comment
            just some text with no equal sign gets skipped by nobody matching it

            home = config home
            """)})
        c.run("home")
        assert c.cache_folder in c.out

    def test_alias_empty_command_errors(self):
        c = TestClient()
        c.save_home({"command_alias": "home =\n"})
        c.run("home", assert_error=True)
        assert "Alias 'home' in" in c.out
        assert "is empty" in c.out

    def test_alias_distributed_via_config_install(self):
        source = temp_folder()
        c = TestClient()
        c.save({"command_alias": "home = config home\n"}, path=source)
        c.run(f'config install "{source}"')
        installed = c.load(os.path.join(c.cache_folder, "command_alias"))
        assert "home = config home" in installed

        c.run("home")
        assert c.cache_folder in c.out
