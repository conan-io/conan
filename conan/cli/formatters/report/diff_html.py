diff_html = r"""
{% macro render_folder(folder, folder_info) %}
    {%- for name, sub_folder_info in folder_info["folders"].items() %}
        <li>
        <details open>
            <summary>{{ name }}</summary>
            <ul>
                {{ render_folder(folder + "/" + name, sub_folder_info) }}
            </ul>
        </details>
        </li>
    {%- endfor %}
    {%- for name, file_info in folder_info["files"].items() %}
        <li class="file-{{ "new" if file_info["is_new"] else "old" }}">
            <a href="#diff_{{- safe_filename(file_info["filename"]) -}}" class="side-link">{{ name }}</a>
        </li>
    {%- endfor %}
{% endmacro %}
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
            .sidebar li { line-height: 1.5; list-style: none; }
            .sidebar li.file-new { list-style: circle }
            .sidebar li.file-old { list-style: square; }
            /* .sidebar li.file-old { list-style: initial; list-style-image: url("data:image/svg;base64,PHN2ZyB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICA8Y2lyY2xlIGN4PSI1MCIgY3k9IjUwIiByPSI1MCIgLz4KPC9zdmc+Cg=="); }*/
            .file-list li ul {
                border-left: 2px solid #ddd;
            }
            .file-list ul li::before {
              content: '';
              display: block;
              position: absolute;
              top: calc(25px / -2);
              left: -2px;
              width: calc(25px + 2px);
              height: calc(25px + 1px);
              border: solid #ddd;
              border-width: 0 0 2px 2px;
            }
            li ul { padding-left: 25px; }
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
            .context, .context-header, .diff-content { background-color: #f8f8f8; }
            .context-header { color: gray; }
            .line-number { width: 4ch; display: inline-block; text-align: left; color: #888; }
            .filename { background-color: #f0f0f0; }
            a:visited {
                color: blue;
            }
        </style>
        <script>
            function debounce(func, delay) {
                let timeout;
                return function(...args) {
                    const context = this;
                    clearTimeout(timeout);
                    timeout = setTimeout(() => {
                        func.apply(context, args);
                    }, delay);
                };
            }
            let includeSearchQuery = "";
            let excludeSearchQuery = "";

            async function onSearchInput(event) {
                const sidebar = document.querySelectorAll(".sidebar li");
                const content = document.querySelectorAll(".content .diff-content");
                const searchingIcon = document.getElementById("searching_icon");

                searchingIcon.style.display = "inline-block";

                let emptySearch = true;

                sidebar.forEach(async function(item) {
                    const text = item.textContent.toLowerCase();
                    const shouldInclude = includeSearchQuery === "" || text.includes(includeSearchQuery);
                    const shouldExclude = excludeSearchQuery !== "" && text.includes(excludeSearchQuery);
                    const associatedId = item.querySelector("a").getAttribute("href").substring(1)
                    const contentItem = document.getElementById(associatedId);

                    if (shouldInclude) {
                        if (shouldExclude) {
                            item.style.display = "none";
                            contentItem.style.display = "none";
                        } else {
                            item.style.display = "list-item";
                            contentItem.style.display = "block";
                            emptySearch = false;
                        }
                    } else {
                        item.style.display = "none";
                        contentItem.style.display = "none";
                    }

                });

                searchingIcon.style.display = "none";
                const emptySearchTag = document.getElementById("empty_search");
                if (emptySearch) {
                    emptySearchTag.style.display = "block";
                } else {
                    emptySearchTag.style.display = "none";
                }
            }

            const debouncedOnSearchInput = debounce(onSearchInput, 500);

             async function onExcludeSearchInput(event) {
                excludeSearchQuery = event.currentTarget.value.toLowerCase();
                debouncedOnSearchInput(event);
            }

            async function onIncludeSearchInput(event) {
                includeSearchQuery = event.currentTarget.value.toLowerCase();
                debouncedOnSearchInput(event);
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
                <input type="text" id="search-include" placeholder="Include search..." oninput="onIncludeSearchInput(event)" />
                <input type="text" id="search-exclude" placeholder="Exclude search..." oninput="onExcludeSearchInput(event)" />
                <span id="searching_icon" style="display:none">...</span>
                <ul class="file-list">
                    {{ render_folder("", per_folder) }}
                    <span id="empty_search" style="display:none">No results found</span>
                </ul>
            </div>
            <div class='content'>
                <div><!--placeholder-->
                {%- for filename, lines in content.items() -%}
                    </div>
                    {% set ns = namespace() %}
                    {% set ns.old_line_number = 0 %}
                    {% set ns.new_line_number = 0 %}
                    {% set ns.seen_header = false %}
                    <div id="diff_{{ safe_filename(filename) }}" class="diff-content">
                    {%- for line in lines -%}
                        {%- if loop.first -%}
                            <hr/>
                            <h3 id="diff_{{ safe_filename(filename) }}_filename" class="filename" data-replaced-paths="{{ replace_cache_paths(filename) }}">{{ remove_prefixes(line) }}</h3>
                        {%- elif line.startswith('+++') %}
                            {% set ns.seen_header = true %}
                            <span class="add">{{ replace_paths(line) }}</span>
                            <br/>
                        {%- elif line.startswith('@@') %}
                            {% set lines = get_line_numbers(line) %}
                            {% set ns.old_line_number = lines[0] %}
                            {% set ns.new_line_number = lines[1] %}
                            <span class="context-header">{{ line }}</span>
                            <br/>
                        {%- elif line.startswith('---') %}
                            <span class="del">{{ replace_paths(line) }}</span>
                            <br/>
                        {%- elif line.startswith('+') %}
                            <span class="line-number">{{ ns.new_line_number }}</span><span class="add">{{ line }}</span>
                            <br/>
                            {% set ns.new_line_number = ns.new_line_number + 1 %}
                        {%- elif line.startswith('-') %}
                            <span class="line-number">{{ ns.old_line_number }}</span><span class="del">{{ line }}</span>
                            <br/>
                            {% set ns.old_line_number = ns.old_line_number + 1 %}
                        {%- else %}
                            {% if ns.seen_header %}
                                <span class="line-number">{{ ns.new_line_number }}</span>
                            {% endif %}
                            <span class="context">{{ line }}</span>
                            <br/>
                            {% set ns.new_line_number = ns.new_line_number + 1 %}
                            {% set ns.old_line_number = ns.old_line_number + 1 %}
                        {%- endif %}
                    {%- endfor -%}
                {%- endfor -%}
                <hr/>
                </div>
            </div>
        </div>
    </body>
</html>
"""
