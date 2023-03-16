list_packages_html_template = r"""
<!DOCTYPE html>
<html lang="en">

<head>
    <title>conan list results</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css" rel="stylesheet"
        integrity="sha384-rbsA2VBKQhggwzxH7pPCaAqO46MgnOM80zW1RWuH61DGLwZJEdK2Kadq2F9CUG65" crossorigin="anonymous">
    <style>
        body {
            font-family: SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
            font-size: 0.75rem;
        }

        .accordion-button {
            padding: 0.25rem 0.25rem;
        }

        .list-group {
            max-height: 100vh;
            overflow: auto;
        }

        .list-group-item {
            padding: 0.2rem 0.35rem;
            border: 0px;
        }
    </style>
    <script>
        var list_results = {{ results| safe }};

        function getRefLink(origin, ref) {
            return origin + "_" + ref.replaceAll(".", "_").replaceAll("/", "_").replaceAll("#", "_").replaceAll("@", "_").replaceAll(":", "_").replaceAll(" ", "_")
        }

        function getPackagesCount(revInfo) {
            if ("packages" in revInfo) {
                return Object.keys(revInfo["packages"]).length;
            }
            return 0;
        }

        function formatDate(timeStamp) {
            var options = {
                year: "numeric",
                month: "2-digit",
                day: "2-digit",
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
                hour12: false
            };
            return new Date(timeStamp * 1000).toLocaleDateString('en', options);
        }

        function getInfoFieldsBadges(property, info) {
            let style = '';
            let badges = '';
            if (property in info) {
                for (const [key, value] of Object.entries(info[property])) {
                    style = (key == 'os') ? 'text-bg-info' : 'text-bg-secondary';
                    badges += `<span class="badge ${style}">${key}: ${value}</span>&nbsp;`
                }
            }
            return badges;
        }

        function getTabContent(tabID, revID, revInfo) {

            tabContent = `<div class="tab-pane" id="${tabID}" role="tabpanel">`;

            if ("packages" in revInfo && Object.entries(revInfo["packages"]).length > 0) {

                tabContent += `<h3>Packages for revision ${revID}</h3>`;
                for (const [package, packageInfo] of Object.entries(revInfo["packages"])) {

                    tabContent += `<div class="bg-light">`;
                    tabContent += `<h6 class="mb-1">${package}</h6>`;
                    tabContent += `${getInfoFieldsBadges("settings", packageInfo["info"])}${getInfoFieldsBadges("options", packageInfo["info"])}`;
                    tabContent += `<br><br><b>Package revisions:</>`;
                    tabContent += `<ul>`;
                    for (const [packageRev, packageRevInfo] of Object.entries(packageInfo["revisions"])) {
                        tabContent += `<li>${packageRev}&nbsp(${formatDate(packageRevInfo["timestamp"])})</li>`;
                    }
                    tabContent += `</ul>`;
                    tabContent += `</div>`;
                    tabContent += `<br>`;
                }
            }
            tabContent += `<h3>JSON</h3>`;
            tabContent += `<pre class="p-3 mb-2 bg-light text-dark">${JSON.stringify(revInfo, null, 2)}</pre>`;
            tabContent += `</div>`
            return tabContent;
        }

        let menu = `<div class="list-group list-group-flush" id="leftTabs" role="tablist">`;
        let tabs = `<div class="tab-content">`;

        for (const [origin, references] of Object.entries(list_results)) {
            if (Object.keys(references).length>0) {
                menu += `<li class="list-group-item"><b>${origin}</b>`;
                if ("error" in references) {
                    menu += `<pre>${references["error"]}</pre>`;
                }
                else {
                    for (const [reference, revisions] of Object.entries(references)) {
                        let originStr = origin.replaceAll(" ", "_");
                        const refLink = getRefLink(originStr, reference);

                        menu += `<div class="accordion accordion-flush" id="accordion_${originStr}">`;
                        menu += `<div class="accordion-item">`;
                        menu += `<h2 class="accordion-header" id="heading_${refLink}">`;
                        menu += `<button class="accordion-button collapsed" type="button" id="left_${refLink}" data-bs-toggle="collapse" data-bs-target="#rev_list_${refLink}" aria-expanded="false" aria-controls="${refLink}">${reference}</button>`;
                        menu += `</h2>`;
                        menu += `<div id="rev_list_${refLink}" class="accordion-collapse collapse" aria-labelledby="heading_${refLink}" data-bs-parent="#accordion_${originStr}">`

                        if ("revisions" in revisions) {
                            for (const [revision, revInfo] of Object.entries(revisions["revisions"])) {
                                let packageCount = getPackagesCount(revInfo);
                                packageBadge = (packageCount == 0) ? '' : `&nbsp<span class="badge rounded-pill text-bg-success">${packageCount}</span>`;
                                let tabID = `${originStr}_${revision}`;
                                menu += `<a class="list-group-item list-group-item-action" id="left_${revision}" data-bs-toggle="list" href="#${tabID}" role="tab" aria-controls="list-home">${revision.substring(0, 6)}&nbsp(${formatDate(revInfo["timestamp"])})${packageBadge}</a>`;
                                tabs += getTabContent(tabID, revision, revInfo);
                            }
                        }
                        menu += `</div>`
                        menu += '</div>';
                        menu += '</div>';
                    }

                }

                menu += "</li>";
            }
        }
        menu += "</div>";
        tabs += "</div>";

        document.addEventListener("DOMContentLoaded", function () {
            let leftMenu = document.getElementById("leftmenu");
            let rightMenu = document.getElementById("rightmenu");
            leftMenu.innerHTML = menu;
            rightMenu.innerHTML = tabs;

            var triggerTabList = [].slice.call(document.querySelectorAll('#leftTabs a'))
            triggerTabList.forEach(function (triggerEl) {
                var tabTrigger = new bootstrap.Tab(triggerEl)
                triggerEl.addEventListener('click', function (event) {
                    // remove active from all, so only .list-group-item is selected
                    var listItems = document.querySelectorAll('.list-group-item');
                    for (var i = 0; i < listItems.length; i++) {
                        listItems[i].classList.remove('active');
                    }
                    event.preventDefault()
                    tabTrigger.show()
                })
            })
        });
    </script>
</head>

<body>
    <nav class="navbar navbar-expand-lg bg-light">
        <div class="container-fluid">
            <a class="navbar-brand">conan list results</a>
        </div>
    </nav>

    <div class="container-fluid">
        <div class="row">
            <div class="col-2" id="leftmenu"></div>
            <div class="col-10" id="rightmenu"></div>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js"
        integrity="sha384-kenU1KFdBIe4zVF0s0G1M5b4hcpxyD9F7jL+jjXkk+Q2h455rYXK/7HAuoJl+0I4"
        crossorigin="anonymous"></script>
</body>

<footer>
    <div class="text-center p-2" style="background-color: rgba(0, 0, 0, 0.05);">
        Conan <b>{{ version }}</b>
        <script>
            document.write(new Date().getFullYear());
        </script>
        JFrog LTD. <a href="https://conan.io">https://conan.io</a>
    </div>
</footer>

</html>
"""
