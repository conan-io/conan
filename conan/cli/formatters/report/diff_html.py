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
        <li class="file file-{{ "deleted" if file_info["is_deleted"] else (
                                "new" if file_info["is_new"] else "old") }}"
            data-path="{{ file_info["relative_path"] }}">
            <a href="#diff_{{- safe_filename(file_info["filename"]) -}}" onclick="setDataIsLinked(event)" class="side-link">
                {{ name }}
            </a>
        </li>
    {%- endfor %}
{% endmacro %}
<html lang="en">
    <head>
        <meta charset="utf-8">
        <title>Diff report for {{ old_reference }} - {{ new_reference }}</title>
        <style>
            /* --- Global Styles --- */

            body {
                font-family: monospace;
                margin: 0px;
                background-color: #f8f8f8;
            }

            /* --- Main Layout --- */

            .container {
                display: flex;
                height: 100%;
                overflow: scroll;
            }

            .sidebar {
                width: 17%;
                min-width: 10%;
                max-width: 33%;
                padding: 10px;
                overflow: scroll;
                background: #f4f4f466;
                border-right: 1px solid #ccc;
                resize: horizontal;
                position: sticky;
                top: 0;
            }

            .content {
                padding: 20px;
                background: #f8f8f8;
                width: 100%;
            }

            /* --- Sidebar & File Tree --- */

            #sidebar-contents {
                background: #f4f4f4;
                border-radius: 7px;
                overflow-y: hidden;
                padding-top: 5px;
            }

            .search-area {
                border-bottom: 1px solid #ccc;
            }

            .search-field {
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 5px;
                margin: 5px;
            }

            .file-list {
                padding-left: 10px;
                width: 100%;
                overflow-x: clip;
            }

            .file-list ul li {
                width: 100%;
            }

            .file-list li ul {
                border-left: 1px solid #ddd;
                margin-left: 3px;
            }

            li ul {
                padding-left: 1ch;
            }

            details.folder {
                text-wrap: nowrap;
            }

            .folder > summary {
                cursor: pointer;
                list-style: none;
            }

            .folder > summary:hover {
                background-color: #e0e0e033;
            }

            .folder:not(:open) > summary:before {
                content: "\1F4C1";
                display: inline-block;
                margin-right: 3px;
            }

            .folder:open > summary:before {
                content: "\1F4C2";
                display: inline-block;
                margin-right: 3px;
            }

            details.folder ul:hover {
                border-left: 1px solid #00000066;
            }

            .sidebar li {
                line-height: 1.8;
                list-style: none;
                list-style-position: inside;
                user-select: none;
            }

            .sidebar li a {
                text-decoration: none;
                padding: 5px;
                color: black;
            }

            .sidebar li a:hover {
                text-decoration: none;
                border-radius: 5px;
                background-color: #e0e0e0;
                padding: 5px;
                color: black;
            }

            .sidebar li a:visited {
                color: black;
            }

            .side-link {
                text-wrap: nowrap;
            }

            /* File Status Indicators */
            .sidebar li.file-new,
            .sidebar li.file-old,
            .sidebar li.file-deleted {
                list-style: none;
                padding-left: 0;
            }

            .sidebar li.file-new:before {
                content: "+";
                color: green;
                font-weight: bold;
            }

            .sidebar li.file-old:before {
                content: "\00B1";
                color: gray;
            }

            .sidebar li.file-deleted:before {
                content: "-";
                color: red;
                font-weight: bold;
            }

            /* --- Diff View Components --- */

            .diff-container {
                scroll-margin-top: 10px;
            }

            .diff-content {
                padding-bottom: 7px;
                border: 1px solid black;
                border-radius: 7px;
                margin-bottom: 10px;
                background-color: white;
            }

            .diff-container[data-is-linked="true"] .diff-content {
                border: 2px solid #0078d7;
            }

            details.diff-details summary.diff-summary {
                cursor: pointer;
                display: flex;
                justify-content: space-between;
                align-items: center;
                border-bottom: 1px solid #ccc;
                padding: 5px 0px;
                position: sticky;
                top: 0;
                background-color: #f8f8f8;
                border-radius: 7px 7px 0px 0px;
            }

            details.diff-details summary.diff-summary:hover {
                background-color: #f0f0f0;
            }

            details:open .diff-summary .filename:before {
                content: "\25BC";
                display: inline-block;
            }

            details:not(:open) .diff-summary .filename:before {
                content: "\25B6";
                display: inline-block;
            }

            .diff-header {
                padding: 0px 5px 5px 5px;
            }

            .diff-subheader {
                display: flex;
                justify-content: space-between;
                align-items: center;
            }

            .filename {
                font-size: 1.2em;
                padding-left: 10px;
            }

            .changes-count-container {
                font-size: 0.9em;
                padding-right: 10px;
            }

            .new-lines-count {
                color: green;
                font-weight: bold;
            }

            .old-lines-count {
                color: black;
                font-weight: bold;
            }

            /* --- Diff Line Styles --- */

            .content span {
                white-space: pre-wrap;
            }

            .context-chunk-header {
                list-style: none;
                background-color: #cef8ff;
                color: #888;
                line-height: 1.5;
                cursor: pointer;
            }

            details:open .context-chunk-header .line-number:before {
                content: "\25BC";
                display: inline-block;
            }

            details:not(:open) .context-chunk-header .line-number:before {
                content: "\25B6";
                display: inline-block;
            }

            .diff-lines {
                line-break: anywhere;
            }

            .line-number {
                width: 4ch;
                min-width: 4ch;
                display: inline-block;
                text-align: center;
                user-select: none;
            }

            .context-line {
                color: #888;
            }

            .add {
                background-color: #cbfcd9;
                color: black;
            }

            .del {
                background-color: #ffebe9;
                color: black;
            }

            .add,
            .del,
            .context-line {
                height: 100%;
            }

            .diff-line {
                display: flex;
                box-sizing: border-box;
                line-height: 1.5em;
            }

            .line-number.add {
                background-color: #76ffbb;
            }

            .line-number.del {
                background-color: #fdb9c1;
            }

            .line-number.add,
            .line-number.del {
                height: auto;
            }

            /* --- Utility & Page States --- */

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
                let new_line_index = 0;
                let old_line_index = 0;
                let new_line_count = 0;
                let old_line_count = 0;
                const headerDiv = document.createElement("div");
                let currentDetails = null;
                for (let i = 0; i < lines.length; i++) {
                    const line = lines[i];
                    let spanLine = document.createElement("span");
                    const lineDiv = document.createElement("div");
                    lineDiv.className = "diff-line";
                    let shouldAddLine = true;
                    if (line.startsWith("+++")) {
                        seen_header = true;
                        spanLine.className = "add";
                        spanLine.textContent = line.replace(newPattern, "(new)");
                        headerDiv.appendChild(spanLine);
                        continue;
                    } else if (line.startsWith("---")) {
                        spanLine.className = "del";
                        spanLine.textContent = line.replace(oldPattern, "(old)");
                        headerDiv.appendChild(spanLine);
                        continue;
                    } else if (line.startsWith("@@")) {
                        currentDetails = document.createElement("details");
                        currentDetails.open = true;

                        const summary = document.createElement("summary");
                        summary.className = "context-chunk-header";
                        const summaryArrow = document.createElement("span");
                        summaryArrow.className = "line-number";
                        const summaryText = document.createElement("span");
                        summaryText.textContent = line;

                        summary.appendChild(summaryArrow);
                        summary.appendChild(summaryText);

                        currentDetails.appendChild(summary);
                        element.appendChild(currentDetails);
                        shouldAddLine = false;

                        const lineNumbers = extractLineNumbers(line);
                        old_line_index = lineNumbers[0];
                        new_line_index = lineNumbers[1];
                    } else if (line.startsWith("+")) {
                        spanLine.className = "add";
                        spanLine.textContent = line;

                        const lineNumberSpan = document.createElement("span");
                        lineNumberSpan.className = "line-number add";
                        lineNumberSpan.textContent = new_line_index;
                        lineDiv.appendChild(lineNumberSpan);

                        new_line_index += 1;
                        new_line_count += 1;
                    } else if (line.startsWith("-")) {
                        spanLine.className = "del";
                        spanLine.textContent = line;

                        const lineNumberSpan = document.createElement("span");
                        lineNumberSpan.className = "line-number del";
                        lineNumberSpan.textContent = old_line_index;
                        lineDiv.appendChild(lineNumberSpan);

                        old_line_index += 1;
                        old_line_count += 1;
                    } else {
                        spanLine.className = "context-line";
                        if (!seen_header) {
                            spanLine.textContent = line.replace(oldPattern, "(old)").replace(newPattern, "(new)");
                            headerDiv.appendChild(spanLine);
                            headerDiv.appendChild(document.createElement("br"));
                            continue;
                        } else {
                            spanLine.textContent = line;
                        }

                        const lineNumberSpan = document.createElement("span");
                        lineNumberSpan.className = "line-number context-line";
                        lineNumberSpan.textContent = new_line_index;
                        lineDiv.appendChild(lineNumberSpan);

                        new_line_index += 1;
                        old_line_index += 1;
                    }
                    if (shouldAddLine) {
                        lineDiv.appendChild(spanLine);

                        currentDetails.appendChild(lineDiv);
                        //currentDetails.appendChild(document.createElement("br"));
                    }
                }
                if (!seen_header) {
                    element.appendChild(headerDiv);
                }
                return [element, new_line_count, old_line_count];
            }

            function createChangesCountElement(new_count, old_count) {
                const changes = document.createElement("span");
                changes.className = "changes-count";
                changes.innerHTML = `<span class="new-lines-count">+${new_count}</span> <span class="old-lines-count">-${old_count}</span>`;
                return changes;
            }


            function intersectionCallback(entries) {
              entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    let elem = entry.target;
                    const path = elem.dataset.path;
                    const [lines, new_count, old_count] = makeDiffLines(data[path]);
                    const diffLines = elem.querySelector(".diff-lines")

                    //diffLines.style.height = "auto";
                    diffLines.appendChild(lines);

                    if (new_count !== 0 || old_count !== 0) {
                        elem.querySelector(".changes-count-container").appendChild(createChangesCountElement(new_count, old_count));
                    }

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
                setDataIsLinked(null);
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

                const allDetails = document.querySelectorAll(".sidebar details.folder");
                allDetails.forEach(function(details) {
                    details.style.display = "none";
                    details.querySelectorAll("li.file").forEach(function(li) {
                        if (li.style.display !== "none") {
                            details.style.display = "block";
                            return;
                        }
                    });
                });

            }

            const debouncedOnSearchInput = debounce(onSearchInput, 300);

            async function onExcludeSearchInput(event) {
                excludeSearchQuery = event.currentTarget.value.toLowerCase();
                debouncedOnSearchInput(event);
            }

            async function onIncludeSearchInput(event) {
                includeSearchQuery = event.currentTarget.value.toLowerCase();
                debouncedOnSearchInput(event);
            }

            function setDataIsLinked(event) {
                const hash = event ? event.currentTarget.getAttribute("href").substring(1) : window.location.hash.substring(1);
                document.querySelectorAll('.diff-container').forEach((section) => {
                    if (section.id === hash) {
                        section.setAttribute("data-is-linked", "true");
                    } else {
                        section.setAttribute("data-is-linked", "false");
                    }
                });
            }
        </script>
    </head>
    <body>
        <div class='container'>
            <div class='sidebar'>
                <div id="sidebar-contents">
                    <div class="search-area">
                        <input type="search" class="search-field" id="search-include" placeholder="Include search..." oninput="onIncludeSearchInput(event)" />
                        <input type="search" class="search-field" id="search-exclude" placeholder="Exclude search..." oninput="onExcludeSearchInput(event)" />
                        <span id="searching_icon" style="display:none">...</span>
                        <p>Showing <b id="file-count">{{ content|length }}</b> out of <b>{{ content|length }}</b> files</p>
                    </div>
                    <ul class="file-list">
                        {{ render_folder("", per_folder) }}
                    </ul>
                </div>
                <span id="empty_search" style="display:none">No results found</span>
            </div>
            <div class='content'>
                <div class="diff-header"><div class="diff-header">
                    <h2>Diff Report Between <b class="del">{{ old_reference.repr_notime() }}</b> And <b class="add">{{ new_reference.repr_notime() }}</b></h2>
                    <div class="diff-subheader">
                    </div>
                </div>
                <span id="empty_result" style="display:none">No matches</span>
                {%- for filename, lines in content.items() -%}
                    <div id="diff_{{ safe_filename(filename) }}" data-path="{{ filename }}" class="diff-container">
                        <div class="diff-content">
                            <details open class="diff-details">
                                <summary class="diff-summary">
                                    <b id="diff_{{ safe_filename(filename) }}_filename" class="filename" data-replaced-paths="">
                                        <span>{{ replace_cache_paths(filename) | replace("(old)/", "") | replace("(new)/", "") }}</span>
                                    </b>
                                    <div class="changes-count-container"></div>
                                </summary>
                                <div class="diff-lines">
                                </div>
                            </details>
                        </div>
                    </div>
                {%- endfor -%}
            </div>
        </div>
    </body>
</html>
"""
