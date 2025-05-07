import json
import subprocess
import os

from conan.errors import ConanException
from conan.api.conan_api import ConanAPI
from conan.api.output import ConanOutput
from conan.cli.command import conan_command
from conan.internal.util.files import chdir
from conan.api.model import RecipeReference, ListPattern

def output_json(msg):
    return json.dumps({"greet": msg})


@conan_command(group="Security", formatters={"json": output_json})
def compare(conan_api: ConanAPI, parser, *args):
    """
    Command to get the diff between versions
    """

    parser.add_argument("-op", "--old-path", help="Path to the old recipe")
    parser.add_argument("-ov", "--old-reference", help='Old reference "mylib/1.0"')
    parser.add_argument("-or", "--old-require", help='Old reference "mylib/1.0"')

    parser.add_argument("-np", "--new-path", help="Path to the new recipe")
    parser.add_argument("-nv", "--new-reference", help="New reference")
    parser.add_argument("-nr", "--new-require", help='New reference "mylib/1.0"')

    parser.add_argument("-s", "--split_diff", action="store_true")
    parser.add_argument("--encoding", default="utf-8", help="Encoding to read diff")
    parser.add_argument("-r", "--remote", action="append", default=None,
                       help='Look in the specified remote or remotes server')

    args = parser.parse_args(*args)

    cwd = os.getcwd()
    enabled_remotes = conan_api.remotes.list(args.remote or "*")

    def _download_ref_from_remote(reference):
        ref = RecipeReference().loads(reference)
        full_ref, matching_remote = None, None
        for remote in enabled_remotes:
            if ref.revision:
                no_rrev_ref = RecipeReference.loads(reference)
                no_rrev_ref.revision = None
                try:
                    remote_revisions = conan_api.list.recipe_revisions(no_rrev_ref, remote)
                    if ref in remote_revisions:
                        full_ref = ref
                        matching_remote = remote
                        break
                except:
                    continue
            else:
                try:
                    latest_recipe_revision = conan_api.list.latest_recipe_revision(ref, remote)
                except:
                    continue
                if full_ref is None or (latest_recipe_revision.timestamp > full_ref.timestamp):
                    full_ref = latest_recipe_revision
                    matching_remote = remote
        if full_ref is None or matching_remote is None:
            raise ConanException(f"No matching reference for {reference} in remotes")

        conan_api.download.recipe(full_ref, matching_remote)
        cache_path = conan_api.cache.export_path(ref)
        return ref, cache_path

    def _export_recipe_from_path(path_to_conanfile, reference):
        path = conan_api.local.get_conanfile_path(path_to_conanfile, cwd, py=True)
        ref = RecipeReference.loads(reference)
        export_ref, conanfile = conan_api.export.export(path=path,
                                                        name=ref.name, version=ref.version,
                                                        user=ref.user, channel=ref.channel,
                                                        lockfile=None,
                                                        remotes=enabled_remotes)
        cache_path = conan_api.cache.export_path(export_ref)
        return export_ref, cache_path

    def _source(path_to_conanfile, reference, required_ref):
        if required_ref is not None:
            export_ref, cache_path = _download_ref_from_remote(required_ref)
        else:
            export_ref, cache_path = _export_recipe_from_path(path_to_conanfile, reference)
        exported_path = conan_api.local.get_conanfile_path(cache_path, cwd, py=True)
        conan_api.local.source(exported_path, name=export_ref.name, version=str(export_ref.version), user=export_ref.user,
                               channel=export_ref.channel, remotes=enabled_remotes)
        return export_ref, cache_path

    old_export_ref, old_cache_path = _source(args.old_path, args.old_reference, args.old_require)
    new_export_ref, new_cache_path = _source(args.new_path, args.new_reference, args.new_require)


    with open(f"diff{old_export_ref.version}-{new_export_ref.version}.patch", "w") as f:
        subprocess.run(["git", "diff", old_cache_path, new_cache_path], stdout=f, check=False)

    with open(f"diff{old_export_ref.version}-{new_export_ref.version}.patch", "r", encoding=args.encoding) as file:
        diff_text = file.read()
        ConanOutput().info(f"diff ready")
    name = f"{old_export_ref.version}-{new_export_ref.version}"
    #name = f"{old_export_ref.repr_notime().replace("/", "_")}-{new_export_ref.repr_notime().replace("/", "_")}"

    if args.split_diff:
        diff_to_multi_html(name, diff_text, old_cache_path[1:], new_cache_path[1:])
    else:
        diff_to_single_html(name, diff_text, old_cache_path[1:], new_cache_path[1:])
    subprocess.run(["open", os.path.join(cwd, f"diff_{old_export_ref.version}-{new_export_ref.version}.html")])

def diff_to_multi_html(name, diff_text, old_cache_path, new_cache_path):
    file_diffs = {}
    current_file = None
    current_lines = []

    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            if current_file and current_lines:
                file_diffs[current_file] = list(current_lines)
            parts = line.split()
            current_file = parts[2][2:]
            current_lines = [line]
        elif current_file:
            current_lines.append(line)

    if current_file and current_lines:
        file_diffs[current_file] = current_lines

    # Generate small html files
    output_dir = "html_diffs"
    subprocess.run(["mkdir", output_dir])
    for file_name, lines in file_diffs.items():
        output_path = os.path.join(output_dir, f"{file_name.replace('/', '_')}.html")
        html_lines = [
            f"<html><head><title>{name}</title><style>",
            ".container { display: flex; height: 100%; }",
            ".content { flex-grow: 1; padding: 20px; background: #fff; overflow-y: auto; }",
            ".add { background-color: #76ffbb; }",
            ".del { background-color: #fdb9c1; }",
            ".context { background-color: #f8f8f8; }",
            ".filename { background-color: #ceffff; }",
            "body{ font-family: monospace; white-space: pre; margin: 0px}",
            "</style></head><body>"
        ]
        for line in lines:
            if line.startswith('+++') or line.startswith('---') or line.startswith('index'):
                pass
            elif line.startswith('+'):
                html_lines.append(f'<span class="add">{line}</span>')
            elif line.startswith('-'):
                html_lines.append(f'<span class="del">{line}</span>')
            elif line.startswith('diff --git'):
                _name = line.split(" ")[2][2:]
                html_lines.append(f'<h1 id="{_name}" class="filename">{_name}</h1>')
            else:
                html_lines.append(f'<span class="context">{line}</span>')
        html_lines.append("</div></body></html>")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write('\n'.join(html_lines))

    # Generate the main html
    with open(f"diff_{name}.html", "w", encoding="utf-8") as f:

        f.write(f"<html><head><title>{name}</title>")
        f.write("""<style>
            .container { display: flex; height: 100%; }
            .sidebar { width: 300px; padding: 10px; background: #f4f4f4; overflow-y: auto; border-right: 1px solid #ccc; }
            .content { flex-grow: 1; padding: 20px; background: #fff; overflow-y: auto; display: flex}
            .add { background-color: #76ffbb; }
            .del { background-color: #fdb9c1; }
            .context { background-color: #f8f8f8; }
            .filename { background-color: #ceffff; }
            iframe { flex-grow: 1; border: 0px}
            body { font-family: monospace; white-space: pre; margin: 0px }
            </style></head><body><pre><div class="container"><div class="sidebar">""")
        f.write(f"<h2>{name}</h2><h2>File list:</h2><ul>")
        # Table of content
        for file_name in file_diffs:
            safe_name = file_name.replace('/', '_')
            f.write(f'<li><a href="{output_dir}/{safe_name}.html" target="diff-frame">{file_name.replace(old_cache_path, "(old)").replace(new_cache_path, "(new)")}</a></li>\n')

        f.write("""
                </ul>
            </div>
            <div class="content">
                <iframe name="diff-frame" src=""></iframe>
            </div>
            </div></pre></body></html>
        """)


def diff_to_single_html(name, diff_text, old_cache_path, new_cache_path):
    html_lines = [
        f"<html><head><title>{name}</title><style>",
        ".container { display: flex; height: 100%; }",
        ".sidebar { min-width: 20%; padding: 10px; overflow-y: scroll;background: #f4f4f4; border-right: 1px solid #ccc; }",
        ".content { flex-grow: 1; padding: 20px; background: #fff; overflow-y: auto; }",
        ".add { background-color: #76ffbb; }",
        ".del { background-color: #fdb9c1; }",
        ".context { background-color: #f8f8f8; }",
        ".filename { background-color: #ceffff; }",
        "body { font-family: monospace; white-space: pre; margin: 0px}",
        "</style></head><body><pre>"
    ]

    file_names = [line.split()[2][2:] for line in diff_text.splitlines() if line.startswith("diff --git")]

    html_lines.append(f"<div class='container'><div class='sidebar'><h2>{name}</h2><h2>File list:</h2><ul>")
    for file in sorted(file_names):
        html_lines.append(f'<li><a href="#{file}">{file.replace(old_cache_path, "(old)").replace(new_cache_path, "(new)")}</a></li>')
    html_lines.append("</ul></div><div class='content'>")

    for line in diff_text.splitlines():
        if line.startswith('+++') or line.startswith('---') or line.startswith('index'):
            continue
        # Escape HTML characters so the diff is displayed correctly
        line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if line.startswith('+'):
            html_lines.append(f'<span class="add">{line}</span>')
        elif line.startswith('-'):
            html_lines.append(f'<span class="del">{line}</span>')
        elif line.startswith('diff --git'):
            _name = line.split(" ")[2][2:]
            html_lines.append(f'<hr/>')
            html_lines.append(f'<h1 id="{_name}" class="filename">{_name}</h1>')
        else:
            html_lines.append(f'<span class="context">{line}</span>')
    html_lines.append(f'<hr/></div></div>')

    html_lines.append("</pre></body></html>")

    with open(f"diff_{name}.html", "w", encoding="utf-8") as f:
        f.write('\n'.join(html_lines))
        ConanOutput().info(f"html generated")
