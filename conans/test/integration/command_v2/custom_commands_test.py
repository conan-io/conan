import os
import textwrap

from conans.test.utils.tools import TestClient


class TestCustomCommands:
    def test_new_custom_command(self):
        mycommand = textwrap.dedent("""
            import json

            from conans.cli.output import cli_out_write
            from conans.cli.command import conan_command

            def output_mycommand_cli(info):
                cli_out_write(f"Conan cache folder is: {info.get('cache_folder')}")

            def output_mycommand_json(info):
                cli_out_write(json.dumps(info))

            @conan_command(group="custom commands",
                           formatters={"cli": output_mycommand_cli,
                                       "json": output_mycommand_json})
            def mycommand(conan_api, parser, *args, **kwargs):
                \"""
                this is my custom command, it will print the location of the cache folder
                \"""
                info = {"cache_folder": conan_api.cache_folder}
                return info
            """)

        client = TestClient()
        command_file_path = os.path.join(client.cache_folder, 'commands', 'cmd_mycommand.py')
        client.save({f"{command_file_path}": mycommand})
        client.run("mycommand")
        assert f"Conan cache folder is: {client.cache_folder}" in client.out
        client.run("mycommand -f json")
        assert f'{{"cache_folder": "{client.cache_folder}"}}' in client.out
