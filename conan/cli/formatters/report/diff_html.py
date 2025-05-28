diff_html = r"""
<html lang="en">
    <head>
        <meta charset="utf-8">
        <title>{{ old_reference }} - {{ new_reference }}</title>
        <style>
            body { font-family: monospace; margin: 0px; }
            .container { display: flex; height: 100%; }
            .sidebar {
                min-width: 20%;
                max-width: 20%;
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
            a:visited {
                color: blue;
            }
        </style>
        <script>
            async function onSearchInput(event) {
                const searchInput = event.currentTarget;
                const sidebar = document.querySelectorAll(".sidebar li");
                const content = document.querySelectorAll(".content .filename");
                const query = searchInput.value.toLowerCase();

                if (query.length === 0) {
                    sidebar.forEach(async function(item) {
                        item.style.display = "list-item";
                    });
                    content.forEach(async function(item) {
                        const associated_diff = document.getElementById("diff_" + item.id);
                        associated_diff.style.display = "block";
                    });
                    return;
                } else {
                    sidebar.forEach(async function(item) {
                        const text = item.textContent.toLowerCase();
                        if (text.includes(query)) {
                            item.style.display = "list-item";
                        } else {
                            item.style.display = "none";
                        }
                    });

                    content.forEach(async function(item) {
                        const text = item.textContent.toLowerCase();
                        const associated_diff = document.getElementById("diff_" + item.id);
                        if (text.includes(query)) {
                            associated_diff.style.display = "block";
                        } else {
                            associated_diff.style.display = "none";
                        }
                    });
                }
            }
        </script>
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
                <input type="text" id="search" placeholder="Search..." oninput="onSearchInput(event)" />
                <ul>
                    {%- for filename in file_names %}
                        <li><a href="#diff_{{- safe_filename(filename) -}}" class="side-link">{{ filename.replace(old_cache_path, "(old)").replace(new_cache_path, "(new)") }}</a></li>
                    {%- endfor %}
                </ul>
            </div>
            <div class='content'>
                <div><!--placeholder-->
                {%- for line in diff_text.splitlines() -%}
                    {%- if line.startswith('diff --git') %}
                        </div>
                        {%- set filename = get_diff_filename(line) -%}
                        <div id="diff_{{ safe_filename(filename) }}">
                        <h3 class="filename">{{ line }}</h3>
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
        </div>
    </body>
</html>
"""
