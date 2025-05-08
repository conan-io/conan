compare_html = r"""
<html lang="en">
    <head>
        <meta charset="utf-8">
        <title>{{ old_reference }} - {{ new_reference }}</title>
        <style>
            body { font-family: monospace; margin: 0px; }
            .container { display: flex; height: 100%; }
            .sidebar {
                min-width: 20%;
                padding: 10px;
                overflow-y: scroll;
                background: #f4f4f4;
                border-right: 1px solid #ccc;
            }
            .sidebar li { line-height: 1.5; }
            .content {
                padding: 20px;
                background: #fff;
                overflow-y: scroll;
            }
            .content span {
                white-space: pre-wrap;
            }
            .add { background-color: #76ffbb; }
            .del { background-color: #fdb9c1; }
            .context { background-color: #f8f8f8; }
            .filename { background-color: #ceffff; }
        </style>
    </head>
    <body>
        <div class='container'>
            <div class='sidebar'>
                <div style="white-space: nowrap;">
                    <span class="del">--- (old): <b>{{ old_reference.repr_notime() }}</b></span>
                    <br/>
                    <span class="add">+++ (new): <b>{{ new_reference.repr_notime() }}</b></span>
                </div>
                <h2>File list:</h2>
                <ul>
                    {%- for filename in file_names %}
                        <li><a href="#{{ safe_filename(filename) }}">{{ filename.replace(old_cache_path, "(old)").replace(new_cache_path, "(new)") }}</a></li>
                    {%- endfor %}
                </ul>
            </div>
            <div class='content'>
                {%- for line in diff_text.splitlines() if not line.startswith("index") -%}
                    {%- if line.startswith('diff --git') %}
                        {%- set filename = line.split()[2][1:] %}
                        <hr/>
                        <h1 id="{{ safe_filename(filename) }}" class="filename">{{ filename.replace(old_cache_path, "(old)").replace(new_cache_path, "(new)") }}</h1>
                    {%- elif line.startswith('---') %}
                        <span class="context">{{ replace_path_with_ref(old_cache_path, old_reference, line) }}</span>
                        <br/>
                    {%- elif line.startswith('+++') %}
                        <span class="context">{{ replace_path_with_ref(new_cache_path, new_reference, line) }}</span>
                        <br/>
                    {%- elif line.startswith('+') %}
                        <span class="add">{{ line }}</span>
                        <br/>
                    {%- elif line.startswith('-') %}
                        <span class="del">{{ line }}</span>
                        <br/>
                    {%- else %}
                        <span class="context">{{ line }}</span>
                        <br/>
                    {%- endif %}
                {%- endfor -%}
                <hr/>
            </div>
        </div>
    </body>
</html>
"""
