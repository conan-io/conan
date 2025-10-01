diff_html = r"""
{% macro render_folder(folder, folder_info) %}
    {%- for name, sub_folder_info in folder_info["folders"].items() %}
        {% set folder_name = folder + "/" + name %}
        <li>
            <details open class="folder">
                <summary>{{ name }}</summary>
                <ul>
                    {{ render_folder(folder_name, sub_folder_info) }}
                </ul>
            </details>
        </li>
    {%- endfor %}
    {%- for name, file_info in folder_info["files"].items() %}
        <li class="file-{{ "new" if file_info["is_new"] else "old" }}"
            data-path="{{ file_info["relative_path"] }}">
            <a href="#diff_{{- safe_filename(file_info["filename"]) -}}" class="side-link">
                {{ name }}
            </a>
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
                width: 17%;
                min-width: 10%;
                max-width: 20%;
                padding: 10px;
                overflow: scroll;
                background: #f4f4f466;
                border-right: 1px solid #ccc;
                resize: horizontal;
            }
            #sidebar-contents {
                background: #f4f4f4;
                border-radius: 7px;
                //border: 1px solid #ccc;
            }
            details.folder {
                text-wrap: nowrap;
            }

            .sidebar li { line-height: 1.5; list-style: none; list-style-position: inside; }
            .sidebar li.file-new { list-style: none; padding-left: 0; }
            .sidebar li.file-new:before { content: "+"; color: green; font-weight: bold; }
            .sidebar li.file-old { list-style: none; padding-left: 0;  }
            .sidebar li.file-old:before { content: "*"; color: black; }
            .sidebar li a {
                text-decoration: none;
            }
            .sidebar li a:hover {
                text-decoration: underline;
            }
            .side-link {
                text-wrap: nowrap;
            }
            .file-list { padding-left: 10px; }
            .file-list li ul {
                border-left: 2px solid #ddd;
                margin-left: 3px;
            }
            li ul { padding-left: 1ch; }
            .content {
                padding: 20px;
                background: #fff;
                overflow-y: scroll;
                width: 100%;
            }
            .content span {
                white-space: pre-wrap;
            }
            .add { background-color: #76ffbb; }
            .del { background-color: #fdb9c1; }
            .context, .context-header, .diff-content { background-color: #f8f8f8; }
            .diff-content {
                padding: 0px 0px 3px 3px;
                border: 1px solid black;
                border-radius: 7px;
                margin-bottom: 10;
                box-shadow: 6px 6px #00808022;
             }
            details.folder ul:hover {
                background-color: #e0e0e033;
                border-left: 2px solid #00000066;
            }
            details.diff-details summary { cursor: pointer; margin-top: 5px; }
            .context-header { color: gray; }
            .line-number { width: 4ch; display: inline-block; text-align: left; color: #888; user-select: none; }
            hr { margin-left: -3px;}
            .filename {
                font-size: 1.2em;
            }
            #empty_result {
                justify-content: center;
                align-items: center;
                color: black;
                font-weight: bold;
                font-size: 4em;
                text-align: center;
            }
        </style>
        <script>

            const data = {{ content | tojson | safe }};

            const oldPattern = "{{ src_prefix[:-1] }}{{ old_cache_path }}";
            const newPattern = "{{ dst_prefix[:-1] }}{{ new_cache_path }}";

            function extractLineNumbers(hunkHeader) {
                const regex = /@@ -(\d+),\d+ \+(\d+),\d+ @@/;
                const match = hunkHeader.match(regex);
                if (!match) {
                    return [0, 0];
                }
                return [parseInt(match[1]), parseInt(match[2])];
            }


            function makeDiffLines(lines) {
                const element = document.createElement("div");
                let seen_header = false;
                let new_line_number = 0;
                let old_line_number = 0;
                for (let i = 0; i < lines.length; i++) {
                    const line = lines[i];
                    let spanLine = document.createElement("span");
                    if (line.startsWith("+++")) {
                        seen_header = true;
                        spanLine.className = "add";
                        spanLine.textContent = line.replace(newPattern, "(new)");
                    } else if (line.startsWith("---")) {
                        spanLine.className = "del";
                        spanLine.textContent = line.replace(oldPattern, "(old)");
                    } else if (line.startsWith("@@")) {
                        const lineNumbers = extractLineNumbers(line);
                        old_line_number = lineNumbers[0];
                        new_line_number = lineNumbers[1];
                        spanLine.className = "context-header";
                        spanLine.textContent = line;
                    } else if (line.startsWith("+")) {
                        spanLine.className = "add";
                        spanLine.textContent = line;

                        const lineNumberSpan = document.createElement("span");
                        lineNumberSpan.className = "line-number";
                        lineNumberSpan.textContent = new_line_number;
                        element.appendChild(lineNumberSpan);

                        new_line_number += 1;
                    } else if (line.startsWith("-")) {
                        spanLine.className = "del";
                        spanLine.textContent = line;

                        const lineNumberSpan = document.createElement("span");
                        lineNumberSpan.className = "line-number";
                        lineNumberSpan.textContent = old_line_number;
                        element.appendChild(lineNumberSpan);

                        old_line_number += 1;
                    } else {
                        const lineNumberSpan = document.createElement("span");
                        lineNumberSpan.className = "line-number";
                        if (seen_header) {
                            lineNumberSpan.textContent = new_line_number;
                            spanLine.className = "context";
                            spanLine.textContent = line;
                        } else {
                            spanLine.textContent = line.replace(oldPattern, "(old)").replace(newPattern, "(new)");
                            spanLine.className = "context-header";
                        }
                        element.appendChild(lineNumberSpan);


                        new_line_number += 1;
                        old_line_number += 1;
                    }
                    element.appendChild(spanLine);
                    element.appendChild(document.createElement("br"));
                }
                return element;
            }


            function intersectionCallback(entries) {
              entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    let elem = entry.target;
                    const path = elem.dataset.path;
                    elem.querySelector(".diff-lines").appendChild(makeDiffLines(data[path]));
                    observer.unobserve(elem);
                }
              });
            }

            const options = {
                root: document.querySelector('.content'),
                rootMargin: "0px",
                scrollMargin: "0px",
                threshold: 0.05,
            };

            const observer = new IntersectionObserver(intersectionCallback, options);


            document.addEventListener("DOMContentLoaded", (e) => {
                document.querySelectorAll('.diff-container').forEach((section) => {
                    observer.observe(section);
                });
            });

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
                const fileList = document.querySelector(".file-list");
                const content = document.querySelectorAll(".content .diff-container .diff-content");
                const searchingIcon = document.getElementById("searching_icon");

                searchingIcon.style.display = "inline-block";

                let emptySearch = true;
                let includedFiles = 0;

                sidebar.forEach(async function(item) {
                    const text = item.dataset.path.toLowerCase();
                    const shouldInclude = includeSearchQuery === "" || text.includes(includeSearchQuery);
                    const shouldExclude = excludeSearchQuery !== "" && text.includes(excludeSearchQuery);
                    const associatedId = item.querySelector("a").getAttribute("href").substring(1)
                    const contentItem = document.getElementById(associatedId);

                    if (shouldInclude) {
                        if (shouldExclude) {
                            item.style.display = "none";
                            contentItem.style.display = "none";
                        } else {
                            includedFiles += 1;
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
                const emptyResultTag = document.getElementById("empty_result");
                if (emptySearch) {
                    emptySearchTag.style.display = "block";
                    emptyResultTag.style.display = "block";
                    fileList.style.display = "none";
                } else {
                    emptySearchTag.style.display = "none";
                    emptyResultTag.style.display = "none";
                    fileList.style.display = "block";
                }

                const fileCountTag = document.getElementById("file-count");
                fileCountTag.textContent = includedFiles;

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

            function toggleSidebar() {
                const contents = document.querySelector('#sidebar-contents');
                const sidebar = document.querySelector('.sidebar');
                if (contents.style.display === 'none') {
                    contents.style.display = 'initial';
                    sidebar.style.minWidth = '17%';
                    event.srcElement.textContent = 'Hide';
                } else {
                    contents.style.display = 'none';
                    sidebar.style.minWidth = 'unset';
                    event.srcElement.textContent = 'Show';
                }
            }
        </script>
    </head>
    <body>
        <div class='container'>
            <div class='sidebar'>
                <button onclick="toggleSidebar()">Hide</button>
                <div id="sidebar-contents">
                    <h2>File list:</h2>
                    <input type="text" id="search-include" placeholder="Include search..." oninput="onIncludeSearchInput(event)" />
                    <input type="text" id="search-exclude" placeholder="Exclude search..." oninput="onExcludeSearchInput(event)" />
                    <span id="searching_icon" style="display:none">...</span>
                    <ul class="file-list">
                        {{ render_folder("", per_folder) }}
                    </ul>
                    <span id="empty_search" style="display:none">No results found</span>
                </div>
            </div>
            <div class='content'>
                <div class="diff-header">
                    <h2>Diff Report Between <b>{{ old_reference.repr_notime() }}</b> And <b>{{ new_reference.repr_notime() }}</b></h2>
                    <p>Showing a total of <b id="file-count">{{ content|length }}</b> files</p>
                    <span class="del" style="white-space: nowrap;">
                        --- (old) belongs to the <b>{{ old_reference.repr_notime() }}</b> reference
                    </span>
                    <br/>
                    <span class="add" style="white-space: nowrap;">
                        +++ (new) belongs to the <b>{{ new_reference.repr_notime() }}</b> reference
                    </span>
                </div>
                <span id="empty_result" style="display:none">No matches</span>
                {%- for filename, lines in content.items() -%}
                    <div id="diff_{{ safe_filename(filename) }}" data-path="{{ filename }}" class="diff-container">
                        <div class="diff-content">
                            <details open class="diff-details">
                                <summary>
                                    <b id="diff_{{ safe_filename(filename) }}_filename" class="filename" data-replaced-paths="">
                                        {{ replace_cache_paths(filename) | replace("(old)/", "") | replace("(new)/", "") }}
                                    </b>
                                    <hr/>
                                </summary>
                                <div class="diff-lines"></div>
                            </details>

                        </div>
                    </div>
                {%- endfor -%}

            </div>
        </div>
    </body>
</html>
"""
