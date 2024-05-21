import json
import os
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_upload_bundle():
    """ Test how a custom command can create an upload bundle and print it
    """
    c = TestClient(default_server_user=True)
    mycommand = textwrap.dedent("""
        import json
        import os

        from conan.cli.command import conan_command, OnceArgument
        from conan.api.model import ListPattern
        from conan.api.output import cli_out_write

        @conan_command(group="custom commands")
        def upload_bundle(conan_api, parser, *args, **kwargs):
            \"""
            create an upload bundle
            \"""
            parser.add_argument('reference',
                                help="Recipe reference or package reference, can contain * as "
                                      "wildcard at any reference field.")
            # using required, we may want to pass this as a positional argument?
            parser.add_argument("-r", "--remote", action=OnceArgument, required=True,
                                help='Upload to this specific remote')
            args = parser.parse_args(*args)

            remote = conan_api.remotes.get(args.remote)
            enabled_remotes = conan_api.remotes.list()

            ref_pattern = ListPattern(args.reference, package_id="*")
            package_list = conan_api.list.select(ref_pattern)
            if not package_list.recipes:
                raise ConanException("No recipes found matching pattern '{}'".format(args.reference))

            # Check if the recipes/packages are in the remote
            conan_api.upload.check_upstream(package_list, remote, enabled_remotes)
            conan_api.upload.prepare(package_list, enabled_remotes)
            cli_out_write(json.dumps(package_list.serialize(), indent=4))
        """)

    command_file_path = os.path.join(c.cache_folder, 'extensions',
                                     'commands', 'cmd_upload_bundle.py')
    c.save({command_file_path: mycommand})
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .")
    c.run('upload-bundle "*" -r=default', redirect_stdout="mybundle.json")
    bundle = c.load("mybundle.json")
    bundle = json.loads(bundle)
    assert bundle["pkg/0.1"]["revisions"]["485dad6cb11e2fa99d9afbe44a57a164"]["upload"] is True
