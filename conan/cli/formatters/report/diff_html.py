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
            .context, .diff-content { background-color: #f8f8f8; }
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
                <ul>
                    {%- for filename in content.keys() %}
                        <li><a href="#diff_{{- safe_filename(filename) -}}" class="side-link">{{ replace_cache_paths(filename) }}</a></li>
                    {%- endfor %}
                    <span id="empty_search" style="display:none">No results found</span>
                </ul>
            </div>
            <div class='content'>
                <div><!--placeholder-->
                {%- for filename, lines in content.items() -%}
                    </div>
                    <div id="diff_{{ safe_filename(filename) }}" class="diff-content">
                    {%- for line in lines -%}
                        {%- if loop.first -%}
                            <hr/>
                            <h3 id="diff_{{ safe_filename(filename) }}_filename" class="filename" data-replaced-paths="{{ replace_cache_paths(filename) }}">{{ remove_prefixes(line) }}</h3>
                        {%- elif line.startswith('+++') %}
                            <span class="add">{{ replace_paths(line) }}</span>
                            <br/>
                        {%- elif line.startswith('---') %}
                            <span class="del">{{ replace_paths(line) }}</span>
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
                {%- endfor -%}
                <hr/>
                </div>
            </div>
        </div>
    </body>
</html>
"""
