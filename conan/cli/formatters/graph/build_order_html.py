from jinja2 import select_autoescape, Template
from conan.api.output import cli_out_write

build_order_html = r"""
<!DOCTYPE html>
<html lang="en">
<head>
  <link rel="icon" type="image/png" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAABCFBMVEUAAAA+uf4Ah/2p3PxyvPqNzPkSmP6b0/qTz/mIyPeGx/eIyPeZ0vonpv1qu/ii2fx1wviGx/cFjP0erf+p3PyAxfeAxPcWof6q3PyHyPeKyfgJi/2HzfxCuv4Lk/6p3Pyd2PyGx/cBh/0cqP+Hx/ep3PyGx/dTrvmp3PyGx/cRm/6p3Pya1vyGx/eJyPcGjf0brf+Y0vqp3PwXov6ExvcMlf6p3Pyi2vwap/+FzP2IyPeHyPcPmf4Jkv4Di/16w/gerf8VoP6Ex/hErftft/o8t/4vrv4Ljv2h2Pwsn/xStvtZuvpZtPpNsPpvwvlVsfl0wPh/xPcdrP8Un/40pfwjnPw8qfuLyvgsmPXHAAAANnRSTlMA/sR/BxT+/v7CpjQr/v729fX06ufn59nZ2c/HxMDAp6Wcj46Eg4B8cG9tW1JRUE1FRTYkHRKiySDqAAAAsklEQVQY003P1RqCQBQE4KNid3d3N+quugrYUub7v4ko8sFczfx3A2o8xZoV9FibSYScPeo/qa4TS9czF3C5f9vtCsrs88Wz+3O0MgGoxxASD1eM8GUv4NQQ0icf4g48kRlCsONoAfPaxkri6cExmLHT9BdWS++FEOZtX8w0uM93gmNG67Cd30zKMMJGgyqUQkaItIHq52wa+PMjUDJtxVXIdLQ343J4d0w0jH8H2YJHbR8fvSVyLKSviQAAAABJRU5ErkJggg==">
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Conan Order Visualizer</title>
  <style>
    :root {
      --bg: #f4f6fb;
      --surface: #ffffff;
      --surface2: #f1f5f9;
      --surface-glass: rgba(255, 255, 255, 0.78);
      --border: #e2e8f0;
      --border-light: #f1f5f9;
      --text: #1e293b;
      --muted: #64748b;
      --accent: #6366f1;
      --accent-light: #818cf8;
      --accent-dark: #4f46e5;
      --accent-soft: rgba(99, 102, 241, 0.1);
      --cache: #10b981;
      --cache-soft: rgba(16, 185, 129, 0.12);
      --download: #3b82f6;
      --download-soft: rgba(59, 130, 246, 0.12);
      --missing: #f43f5e;
      --missing-soft: rgba(244, 63, 94, 0.12);
      --cache-strong: #059669;
      --cache-strong-bg: rgba(16, 185, 129, 0.22);
      --download-strong: #2563eb;
      --download-strong-bg: rgba(59, 130, 246, 0.22);
      --missing-strong: #e11d48;
      --missing-strong-bg: rgba(244, 63, 94, 0.22);
      --build: #f59e0b;
      --build-soft: rgba(245, 158, 11, 0.12);
      --build-strong: #d97706;
      --build-strong-bg: rgba(245, 158, 11, 0.22);
      --level-bg: rgba(255, 255, 255, 0.55);
      --shadow-xs: 0 1px 2px rgba(15, 23, 42, 0.04);
      --shadow-sm: 0 2px 8px rgba(15, 23, 42, 0.05);
      --shadow-md: 0 6px 20px rgba(15, 23, 42, 0.07);
      --shadow-lg: 0 12px 32px rgba(15, 23, 42, 0.09);
      --radius: 14px;
      --radius-sm: 10px;
      --radius-xs: 6px;
      --mono: "SF Mono", "Fira Code", "Cascadia Code", Consolas, monospace;
      --sans: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: var(--sans);
      background:
        radial-gradient(ellipse 70% 55% at 8% -5%, rgba(99, 102, 241, 0.09), transparent 55%),
        radial-gradient(ellipse 55% 45% at 95% 0%, rgba(16, 185, 129, 0.07), transparent 50%),
        radial-gradient(ellipse 50% 40% at 50% 100%, rgba(59, 130, 246, 0.05), transparent 55%),
        var(--bg);
      color: var(--text);
      line-height: 1.5;
      height: 100vh;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      -webkit-font-smoothing: antialiased;
    }

    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb {
      background: rgba(100, 116, 139, 0.28);
      border-radius: 999px;
    }
    ::-webkit-scrollbar-thumb:hover { background: rgba(100, 116, 139, 0.42); }

    header {
      background: var(--surface-glass);
      backdrop-filter: blur(14px) saturate(1.25);
      -webkit-backdrop-filter: blur(14px) saturate(1.25);
      border-bottom: 1px solid rgba(226, 232, 240, 0.85);
      padding: 0.65rem 1.35rem;
      flex-shrink: 0;
      z-index: 100;
      box-shadow: var(--shadow-xs);
    }

    .header-top {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem 1.25rem;
      flex-wrap: wrap;
    }

    .header-brand {
      display: flex;
      align-items: baseline;
      gap: 0.45rem;
      min-width: 0;
      flex-shrink: 0;
    }

    header h1 {
      font-size: 1.02rem;
      font-weight: 700;
      letter-spacing: -0.03em;
      line-height: 1.2;
      background: linear-gradient(135deg, #1e293b 0%, #4f46e5 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }

    .header-sub {
      color: var(--muted);
      font-size: 0.74rem;
      font-weight: 500;
      line-height: 1.2;
      white-space: nowrap;
    }

    .header-sub::before {
      content: "\00B7";
      margin-right: 0.45rem;
      color: #cbd5e1;
    }

    .header-toolbar {
      display: flex;
      align-items: center;
      gap: 0.85rem;
      margin-top: 0.5rem;
    }

    .search-wrap {
      position: relative;
      flex: 0 0 auto;
    }

    .search-wrap::before {
      content: "";
      position: absolute;
      left: 0.55rem;
      top: 50%;
      transform: translateY(-50%);
      width: 0.9rem;
      height: 0.9rem;
      opacity: 0.45;
      background: currentColor;
      mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='black' stroke-width='2.5'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' d='M21 21l-4.35-4.35M11 18a7 7 0 100-14 7 7 0 000 14z'/%3E%3C/svg%3E") center / contain no-repeat;
      -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='black' stroke-width='2.5'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' d='M21 21l-4.35-4.35M11 18a7 7 0 100-14 7 7 0 000 14z'/%3E%3C/svg%3E") center / contain no-repeat;
      pointer-events: none;
      color: var(--muted);
    }

    .header-toolbar input[type="search"] {
      font-family: var(--sans);
      font-size: 0.78rem;
      font-weight: 500;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--text);
      padding: 0.34rem 0.75rem 0.34rem 1.85rem;
      width: 220px;
      max-width: 100%;
      box-shadow: var(--shadow-xs);
      transition: border-color 0.2s, box-shadow 0.2s;
    }

    .header-toolbar input[type="search"]::placeholder { color: #94a3b8; }

    .header-toolbar input[type="search"]:focus {
      outline: none;
      border-color: var(--accent-light);
      box-shadow: 0 0 0 3px var(--accent-soft), var(--shadow-xs);
    }

    .meta-bar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: flex-end;
      gap: 0.35rem;
      flex: 1;
      min-width: 0;
    }

    .meta-chip {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 0.2rem 0.6rem;
      font-size: 0.7rem;
      font-weight: 500;
      display: flex;
      align-items: center;
      gap: 0.3rem;
      white-space: nowrap;
      box-shadow: var(--shadow-xs);
    }

    .meta-chip strong { color: var(--accent-dark); font-weight: 600; }

    .meta-chip.meta-muted {
      background: transparent;
      border-color: var(--border-light);
      box-shadow: none;
    }

    .meta-chip.meta-muted strong { color: var(--muted); font-weight: 500; }

    main {
      flex: 1;
      min-height: 0;
      padding: 0.65rem 1rem 1rem;
      width: 100%;
      overflow: hidden;
    }

    .levels {
      display: flex;
      flex-direction: row;
      align-items: stretch;
      gap: 0.55rem;
      height: 100%;
      max-height: 100%;
      width: 100%;
    }

    .level {
      flex: 1 1 0;
      min-width: 0;
      height: 100%;
      max-height: 100%;
      display: flex;
      flex-direction: column;
      background: var(--level-bg);
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
      border: 1px solid rgba(226, 232, 240, 0.9);
      border-radius: var(--radius-sm);
      overflow: hidden;
      box-shadow: var(--shadow-sm);
      transition: box-shadow 0.2s;
    }

    .level:hover { box-shadow: var(--shadow-md); }

    .level-scroll {
      position: relative;
      flex: 1;
      min-height: 0;
      display: flex;
      flex-direction: column;
    }

    .level-header {
      display: flex;
      flex-direction: row;
      align-items: center;
      justify-content: space-between;
      gap: 0.5rem;
      padding: 0.5rem 0.65rem;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.96) 0%, rgba(248, 250, 252, 0.92) 100%);
      border-bottom: 1px solid var(--border-light);
      border-top: 3px solid var(--accent);
      flex-shrink: 0;
    }

    .level-label {
      display: flex;
      flex-direction: column;
      gap: 0.1rem;
      min-width: 0;
    }

    .level-name {
      font-size: 0.74rem;
      font-weight: 600;
      color: var(--text);
      letter-spacing: -0.01em;
      line-height: 1.2;
    }

    .level-name span {
      color: var(--accent-dark);
      font-weight: 700;
    }

    .level-sub {
      font-size: 0.66rem;
      font-weight: 500;
      color: var(--muted);
      line-height: 1.2;
    }

    .level-stats {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: flex-end;
      gap: 0.28rem;
      flex-shrink: 0;
    }

    .stat-chip {
      display: inline-flex;
      align-items: center;
      gap: 0.22rem;
      font-size: 0.66rem;
      font-weight: 600;
      color: var(--muted);
      padding: 0.14rem 0.38rem;
      border-radius: 999px;
      background: var(--surface2);
      border: 1px solid var(--border-light);
      line-height: 1;
    }

    .stat-chip .dot { width: 6px; height: 6px; box-shadow: none; }

    .level-body {
      display: flex;
      flex-direction: column;
      gap: 0.35rem;
      padding: 0.45rem;
      flex: 1;
      min-height: 0;
      overflow-y: auto;
      overflow-x: hidden;
      position: relative;
      z-index: 1;
    }

    .scroll-hint {
      position: absolute;
      left: 0.4rem;
      right: 0.4rem;
      z-index: 50;
      display: none;
      align-items: center;
      justify-content: center;
      gap: 0.35rem;
      padding: 0.38rem 0.55rem;
      font-size: 0.76rem;
      font-weight: 600;
      border-radius: 999px;
      cursor: pointer;
      border: 1px solid rgba(99, 102, 241, 0.25);
      color: var(--accent-dark);
      background: rgba(255, 255, 255, 0.92);
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
      box-shadow: var(--shadow-md);
      user-select: none;
      pointer-events: auto;
      transition: transform 0.15s, box-shadow 0.15s, background 0.15s;
    }

    .scroll-hint.is-visible { display: flex; }

    .scroll-hint-up { top: 0.4rem; }

    .scroll-hint-down { bottom: 0.4rem; }

    .scroll-hint:hover {
      background: #fff;
      transform: translateY(-1px);
      box-shadow: var(--shadow-lg);
    }

    .scroll-hint .hint-icon {
      font-size: 1rem;
      line-height: 1;
    }

    .scroll-hint .hint-label {
      font-size: 0.68rem;
      opacity: 0.85;
    }

    .pkg {
      position: relative;
      border-radius: var(--radius-xs);
      overflow: hidden;
      transition: border-color 0.2s, box-shadow 0.2s, transform 0.15s, background 0.2s;
      flex-shrink: 0;
      border: 1px solid var(--border);
      box-shadow: var(--shadow-xs);
    }

    .pkg.pkg-cache {
      background: linear-gradient(135deg, var(--cache-soft) 0%, rgba(255, 255, 255, 0.7) 100%);
      border-color: rgba(16, 185, 129, 0.22);
      border-left: 3px solid var(--cache);
    }

    .pkg.pkg-download {
      background: linear-gradient(135deg, var(--download-soft) 0%, rgba(255, 255, 255, 0.7) 100%);
      border-color: rgba(59, 130, 246, 0.22);
      border-left: 3px solid var(--download);
    }


    .pkg.pkg-build {
      background: linear-gradient(135deg, var(--build-soft) 0%, rgba(255, 255, 255, 0.7) 100%);
      border-color: rgba(245, 158, 11, 0.22);
      border-left: 3px solid var(--build);
    }

    .pkg.pkg-build.active,
    .pkg.pkg-build.dep-linked {
      background: var(--build-strong-bg);
      border-color: var(--build-strong);
      box-shadow: 0 0 0 2px rgba(217, 119, 6, 0.25), var(--shadow-sm);
    }

    .pkg.pkg-build.active {
      box-shadow: 0 0 0 3px rgba(217, 119, 6, 0.3), 0 0 0 6px rgba(217, 119, 6, 0.1), var(--shadow-sm);
    }

    .pkg.pkg-build.active .pkg-name,
    .pkg.pkg-build.dep-linked .pkg-name { color: #92400e; }

    .pkg.pkg-missing {
      background: linear-gradient(135deg, var(--missing-soft) 0%, rgba(255, 255, 255, 0.7) 100%);
      border-color: rgba(244, 63, 94, 0.22);
      border-left: 3px solid var(--missing);
    }

    .pkg.pkg-other {
      background: var(--surface);
      border-color: var(--border);
      border-left: 3px solid #cbd5e1;
    }

    .pkg:hover {
      border-color: rgba(99, 102, 241, 0.35);
      box-shadow: var(--shadow-sm);
      transform: translateY(-1px);
    }

    .pkg.highlight { border-color: var(--accent-light); box-shadow: 0 0 0 2px var(--accent-soft); }
    .pkg.hidden { display: none; }

    .pkg.pkg-cache.active,
    .pkg.pkg-cache.dep-linked {
      background: var(--cache-strong-bg);
      border-color: var(--cache-strong);
      box-shadow: 0 0 0 2px rgba(5, 150, 105, 0.25), var(--shadow-sm);
    }

    .pkg.pkg-cache.active {
      box-shadow: 0 0 0 3px rgba(5, 150, 105, 0.3), 0 0 0 6px rgba(5, 150, 105, 0.1), var(--shadow-sm);
    }

    .pkg.pkg-download.active,
    .pkg.pkg-download.dep-linked {
      background: var(--download-strong-bg);
      border-color: var(--download-strong);
      box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.25), var(--shadow-sm);
    }

    .pkg.pkg-download.active {
      box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.3), 0 0 0 6px rgba(37, 99, 235, 0.1), var(--shadow-sm);
    }

    .pkg.pkg-missing.active,
    .pkg.pkg-missing.dep-linked {
      background: var(--missing-strong-bg);
      border-color: var(--missing-strong);
      box-shadow: 0 0 0 2px rgba(225, 29, 72, 0.25), var(--shadow-sm);
    }

    .pkg.pkg-missing.active {
      box-shadow: 0 0 0 3px rgba(225, 29, 72, 0.3), 0 0 0 6px rgba(225, 29, 72, 0.1), var(--shadow-sm);
    }

    .pkg.pkg-other.active,
    .pkg.pkg-other.dep-linked {
      background: var(--accent-soft);
      border-color: var(--accent-light);
      box-shadow: 0 0 0 2px var(--accent-soft), var(--shadow-sm);
    }

    .pkg.pkg-cache.active .pkg-name,
    .pkg.pkg-cache.dep-linked .pkg-name { color: #065f46; }

    .pkg.pkg-download.active .pkg-name,
    .pkg.pkg-download.dep-linked .pkg-name { color: #1e40af; }

    .pkg.pkg-missing.active .pkg-name,
    .pkg.pkg-missing.dep-linked .pkg-name { color: #9f1239; }

    .pkg.search-hit {
      box-shadow:
        0 0 0 2px rgba(99, 102, 241, 0.45),
        0 4px 16px rgba(99, 102, 241, 0.15);
    }

    .pkg.search-hit::before {
      content: "";
      position: absolute;
      left: 0;
      top: 0;
      bottom: 0;
      width: 3px;
      background: linear-gradient(180deg, var(--accent-light) 0%, var(--accent-dark) 100%);
      pointer-events: none;
      z-index: 1;
    }

    .pkg.search-hit::after {
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(90deg, rgba(255, 255, 255, 0.5) 0%, rgba(255, 255, 255, 0.15) 45%, transparent 80%);
      pointer-events: none;
      z-index: 0;
    }

    .pkg.search-hit .pkg-name {
      font-weight: 600;
      color: var(--text);
    }

    .pkg-head {
      padding: 0.42rem 0.55rem 0.42rem 0.5rem;
      cursor: pointer;
      display: flex;
      flex-direction: row;
      align-items: center;
      gap: 0.4rem;
      min-height: 2.05rem;
      line-height: 1.25;
      position: relative;
      z-index: 2;
    }

    .pkg-label {
      flex: 1;
      min-width: 0;
      display: flex;
      align-items: baseline;
      gap: 0.28rem;
      overflow: hidden;
      white-space: nowrap;
    }

    .pkg-name {
      font-weight: 600;
      font-size: 0.86rem;
      flex-shrink: 0;
      max-width: 45%;
      overflow: hidden;
      text-overflow: ellipsis;
      letter-spacing: -0.01em;
    }

    .pkg-version {
      color: var(--muted);
      font-weight: 500;
      font-size: 0.78rem;
      overflow: hidden;
      text-overflow: ellipsis;
      min-width: 0;
    }

    .pkg-version::before {
      content: "/";
      margin-right: 0.18rem;
      color: #cbd5e1;
    }

    .pkg-tags {
      display: flex;
      flex-shrink: 0;
      gap: 0.18rem;
      align-items: center;
    }

    .tag {
      font-size: 0.68rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.02em;
      padding: 0.12rem 0.4rem;
      border-radius: 999px;
      line-height: 1.2;
      white-space: nowrap;
    }

    .tag-deps-down {
      background: rgba(255, 255, 255, 0.85);
      color: #6366f1;
      border: 1px solid rgba(99, 102, 241, 0.15);
      text-transform: none;
      letter-spacing: 0;
    }

    .tag-deps-up {
      background: rgba(255, 255, 255, 0.85);
      color: #d97706;
      border: 1px solid rgba(217, 119, 6, 0.15);
      text-transform: none;
      letter-spacing: 0;
    }

    .pkg-body {
      display: none;
      border-top: 1px solid var(--border-light);
      padding: 0.65rem 0.7rem;
      font-size: 0.82rem;
      background: rgba(255, 255, 255, 0.88);
      max-height: 340px;
      overflow-y: auto;
      position: relative;
      z-index: 2;
    }

    .pkg.open {
      box-shadow: var(--shadow-md);
      transform: none;
    }

    .pkg.open .pkg-body { display: block; }

    .section { margin-bottom: 0.6rem; }
    .section:last-child { margin-bottom: 0; }

    .section-title {
      font-size: 0.68rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--muted);
      margin-bottom: 0.35rem;
      font-weight: 600;
    }

    .section-title.down,
    .section-title.up { color: var(--text); }

    .details-heading {
      font-size: 0.76rem;
      font-weight: 700;
      color: var(--text);
      letter-spacing: -0.01em;
      margin-bottom: 0.5rem;
    }

    .rel-section:not(:empty) + .details-section {
      margin-top: 0.65rem;
      padding-top: 0.65rem;
      border-top: 1px solid var(--border-light);
    }

    .details-section .section-title {
      font-size: 0.64rem;
      letter-spacing: 0.05em;
    }

    .tag-context {
      background: rgba(99, 102, 241, 0.1);
      color: var(--accent-dark);
      text-transform: lowercase;
      font-size: 0.64rem;
      letter-spacing: 0;
    }

    .tag-context.tag-context-build {
      background: rgba(217, 119, 6, 0.12);
      color: #b45309;
    }

    .legend-sep {
      color: #cbd5e1;
      font-size: 0.7rem;
      user-select: none;
    }

    .legend .legend-tag {
      font-size: 0.62rem;
      padding: 0.08rem 0.32rem;
      pointer-events: none;
    }

    .rel-list { list-style: none; }
    .rel-list li {
      font-size: 0.8rem;
      font-weight: 500;
      padding: 0.38rem 0.5rem;
      margin-bottom: 0.28rem;
      border-radius: var(--radius-xs);
      background: var(--surface2);
      border: 1px solid var(--border-light);
      cursor: pointer;
      line-height: 1.35;
      word-break: break-word;
      transition: background 0.15s, border-color 0.15s, transform 0.12s;
    }

    .rel-list li:hover {
      background: var(--accent-soft);
      border-color: rgba(99, 102, 241, 0.25);
      transform: translateX(2px);
    }

    .rel-list li .lvl {
      font-size: 0.7rem;
      color: var(--muted);
      margin-left: 0.25rem;
      font-family: var(--mono);
    }

    .rel-empty {
      font-size: 0.78rem;
      color: var(--muted);
      font-style: italic;
      padding: 0.15rem 0;
    }

    .kv-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 0.3rem 0.4rem;
    }

    .kv {
      display: inline-flex;
      flex-direction: row;
      align-items: baseline;
      gap: 0.3rem;
      padding: 0.2rem 0.45rem;
      border-radius: 999px;
      background: var(--surface2);
      border: 1px solid var(--border-light);
      max-width: 100%;
      line-height: 1.25;
    }

    .kv-key {
      color: var(--muted);
      font-size: 0.7rem;
      font-weight: 500;
      white-space: nowrap;
    }

    .kv-key::after {
      content: ":";
      margin-left: 0.05rem;
    }

    .kv-val {
      font-family: var(--mono);
      font-size: 0.7rem;
      word-break: break-word;
      color: var(--text);
    }

    .opt-table {
      width: 100%;
      border-collapse: separate;
      border-spacing: 0;
      font-size: 0.72rem;
      border: 1px solid var(--border-light);
      border-radius: var(--radius-xs);
      overflow: hidden;
      background: #fafbfd;
      box-shadow: var(--shadow-xs);
    }

    .opt-table th,
    .opt-table td {
      padding: 0.32rem 0.5rem;
      border-bottom: 1px solid var(--border-light);
      text-align: left;
      vertical-align: top;
      background: #fafbfd;
    }

    .opt-table th {
      color: var(--muted);
      font-weight: 600;
      font-size: 0.64rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      background: #f1f5f9;
    }

    .opt-table td.opt-key {
      color: var(--muted);
      font-weight: 500;
      width: 42%;
      word-break: break-word;
      border-right: 1px solid var(--border-light);
    }

    .opt-table td.opt-val {
      font-family: var(--mono);
      word-break: break-word;
      color: var(--text);
    }

    .opt-table tr:last-child td {
      border-bottom: none;
    }

    .depends-list { list-style: none; }
    .depends-list li {
      font-family: var(--mono);
      font-size: 0.74rem;
      padding: 0.12rem 0;
      color: var(--accent-dark);
      word-break: break-all;
      line-height: 1.3;
    }

    .depends-list li::before { content: "\2192 "; color: var(--muted); }

    .hash { display: none; }

    .empty-msg {
      text-align: center;
      padding: 3rem;
      color: var(--muted);
      font-weight: 500;
    }

    .legend {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.55rem;
      font-size: 0.7rem;
      font-weight: 500;
      color: var(--muted);
      flex-shrink: 0;
      padding: 0.22rem 0.55rem;
      background: var(--surface);
      border: 1px solid var(--border-light);
      border-radius: 999px;
      box-shadow: var(--shadow-xs);
    }

    .legend span { display: flex; align-items: center; gap: 0.32rem; }
    .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.8);
    }
    .dot-cache { background: var(--cache); }
    .dot-download { background: var(--download); }
    .dot-missing { background: var(--missing); }
    .dot-build { background: var(--build); }

    @media (max-width: 640px) {
      header, main { padding-left: 0.5rem; padding-right: 0.5rem; }
      .header-top { flex-direction: column; align-items: flex-start; }
      .meta-bar { justify-content: flex-start; }
      .header-toolbar { flex-wrap: wrap; }
      .legend { width: 100%; }
      main { overflow-x: auto; }
      .levels { min-width: min(100%, 700px); }
    }
  </style>
</head>
<body>
  <header>
    <div class="header-top">
      <div class="header-brand">
        <h1>Conan Dependency Order</h1>
        <p class="header-sub">Build order by levels</p>
      </div>
      <div class="meta-bar" id="meta-bar"></div>
    </div>
    <div class="header-toolbar">
      <div class="search-wrap">
        <input type="search" id="search" placeholder="Search packages...">
      </div>
      <div class="legend">
        <span><span class="dot dot-cache"></span> Cache</span>
        <span><span class="dot dot-download"></span> Download</span>
        <span><span class="dot dot-missing"></span> Missing</span>
        <span><span class="dot dot-build"></span> Build</span>
        <span class="legend-sep">|</span>
        <span><span class="tag tag-deps-down legend-tag">&darr;</span> Depends on</span>
        <span><span class="tag tag-deps-up legend-tag">&uarr;</span> Depended on by</span>
      </div>
    </div>
  </header>

  <main>
    <div class="levels" id="levels"></div>
    <div class="empty-msg" id="empty" style="display:none">No packages match the filter.</div>
  </main>

  <script>
    const BUILD_ORDER = {{ build_order | tojson }};

    /*
     * Adapt Conan build-order JSON to the UI package-card model.
     *
     * Build-order JSON is always:
     *   { order_by, reduced, profiles, order: [ ... ] }
     * where order_by is "recipe" or "configuration".
     *
     * "Normalized" data is the same wrapper with order flattened to
     *   [ [packageCard, ...], ... ]
     * where each packageCard has a unique pref, and depends points to other
     * prefs (so the UI can index and link packages the same way for both
     * --order-by modes).
     */

    /** Build a package reference string (ref:package_id[#prev]). */
    function makePref(ref, packageId, prev) {
      let pref = `${ref}:${packageId}`;
      if (prev) pref += `#${prev}`;
      return pref;
    }

    /**
     * Expand one recipe level into flat package cards.
     * Recipe depends are kept temporarily as _recipe_depends for later
     * resolution into pref-based depends.
     */
    function flattenRecipeLevel(level) {
      const flat = [];
      for (const item of level) {
        const ref = item.ref;
        const recipeDepends = item.depends || [];
        for (const packageLevel of item.packages) {
          for (const pkg of packageLevel) {
            flat.push({
              ref,
              pref: makePref(ref, pkg.package_id, pkg.prev),
              package_id: pkg.package_id,
              prev: pkg.prev ?? null,
              context: pkg.context,
              binary: pkg.binary,
              options: pkg.options || [],
              filenames: pkg.filenames || [],
              depends: [...(pkg.depends || [])],
              overrides: pkg.overrides || {},
              build_args: pkg.build_args ?? null,
              info: pkg.info || {},
              _recipe_depends: [...recipeDepends],
            });
          }
        }
      }
      return flat;
    }

    /**
     * Turn recipe-level depends (recipe refs) into package-level depends (prefs).
     * Mutates the flattened levels in place.
     */
    function resolveRecipeDepends(normalizedOrder) {
      const refToPrefs = new Map();
      for (const level of normalizedOrder) {
        for (const pkg of level) {
          if (pkg.ref && pkg.pref) {
            if (!refToPrefs.has(pkg.ref)) refToPrefs.set(pkg.ref, []);
            refToPrefs.get(pkg.ref).push(pkg.pref);
          }
        }
      }

      for (const level of normalizedOrder) {
        for (const pkg of level) {
          if (pkg._recipe_depends) {
            const deps = [];
            for (const depRef of pkg._recipe_depends) {
              deps.push(...(refToPrefs.get(depRef) || []));
            }
            pkg.depends = deps;
            delete pkg._recipe_depends;
          }
        }
      }
    }

    /**
     * Convert build-order JSON into the UI package-card model.
     * Returns { order_by, reduced, profiles, order } with flat package cards
     * keyed by pref, for both recipe and configuration order_by.
     */
    function normalizeOrderData(data) {
      const orderBy = data.order_by;
      const order = data.order || [];
      let normalizedOrder;

      if (orderBy === "recipe") {
        normalizedOrder = order.map(flattenRecipeLevel);
        resolveRecipeDepends(normalizedOrder);
      } else {
        // configuration: already flat package cards with pref
        normalizedOrder = order;
      }

      return {
        order_by: orderBy,
        reduced: data.reduced ?? false,
        order: normalizedOrder,
        profiles: data.profiles || {},
      };
    }

    const ORDER_DATA = normalizeOrderData(BUILD_ORDER);

    function parseRef(ref) {
      const m = ref.match(/^([^/]+)\/([^#]+)/);
      return m ? { name: m[1], version: m[2] } : { name: ref, version: "" };
    }

    function binaryClass(binary) {
      const map = { Cache: "pkg-cache", Download: "pkg-download", Missing: "pkg-missing", Build: "pkg-build", EditableBuild: "pkg-build" };
      return map[binary] || "pkg-other";
    }

    function renderKV(obj) {
      if (!obj || typeof obj !== "object" || Object.keys(obj).length === 0) return "";
      return `<div class="kv-grid">${Object.entries(obj).map(([k, v]) =>
        `<div class="kv"><span class="kv-key">${escapeHtml(k)}</span><span class="kv-val">${escapeHtml(String(v ?? "null"))}</span></div>`
      ).join("")}</div>`;
    }

    function renderOptionsTable(obj) {
      if (!obj || typeof obj !== "object" || Object.keys(obj).length === 0) return "";
      const rows = Object.entries(obj).map(([k, v]) =>
        `<tr><td class="opt-key">${escapeHtml(k)}</td><td class="opt-val">${escapeHtml(String(v ?? "null"))}</td></tr>`
      ).join("");
      return `<table class="opt-table"><thead><tr><th>Option</th><th>Value</th></tr></thead><tbody>${rows}</tbody></table>`;
    }

    function renderList(title, items) {
      if (!items || items.length === 0) return "";
      const lis = items.map(i => `<li>${escapeHtml(i)}</li>`).join("");
      return `<div class="section"><div class="section-title">${title}</div><ul class="depends-list">${lis}</ul></div>`;
    }

    function escapeHtml(s) {
      return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
    }

    function countByBinary(order) {
      const counts = { Cache: 0, Download: 0, Missing: 0, Build: 0, Other: 0 };
      order.forEach(level => level.forEach(pkg => {
        if (pkg.binary === "EditableBuild") counts.Build++;
        else if (counts[pkg.binary] !== undefined) counts[pkg.binary]++;
        else counts.Other++;
      }));
      return counts;
    }

    function renderMeta(data) {
      const total = data.order.reduce((s, l) => s + l.length, 0);
      const counts = countByBinary(data.order);
      const bar = document.getElementById("meta-bar");
      bar.innerHTML = [
        `<span class="meta-chip"><strong>packages</strong> ${total}</span>`,
        `<span class="meta-chip"><strong>levels</strong> ${data.order.length}</span>`,
        `<span class="meta-chip"><strong>Cache</strong> ${counts.Cache}</span>`,
        `<span class="meta-chip"><strong>Download</strong> ${counts.Download}</span>`,
        `<span class="meta-chip"><strong>Missing</strong> ${counts.Missing}</span>`,
        counts.Build ? `<span class="meta-chip"><strong>Build</strong> ${counts.Build}</span>` : "",
        `<span class="meta-chip meta-muted"><strong>order_by</strong> ${escapeHtml(data.order_by)}</span>`,
        `<span class="meta-chip meta-muted"><strong>reduced</strong> ${data.reduced}</span>`,
      ].join("");
    }

    const PACKAGE_INDEX = new Map();
    const DEPENDENTS_INDEX = new Map();

    function buildIndexes(data) {
      PACKAGE_INDEX.clear();
      DEPENDENTS_INDEX.clear();

      data.order.forEach((level, levelIdx) => {
        level.forEach((pkg, pkgIdx) => {
          PACKAGE_INDEX.set(pkg.pref, { pkg, levelIdx, pkgIdx, id: `pkg-${levelIdx}-${pkgIdx}` });
        });
      });

      PACKAGE_INDEX.forEach(entry => {
        entry.pkg.depends.forEach(depPref => {
          if (!DEPENDENTS_INDEX.has(depPref)) DEPENDENTS_INDEX.set(depPref, []);
          DEPENDENTS_INDEX.get(depPref).push(entry);
        });
      });
    }

    function getRelations(pref) {
      const entry = PACKAGE_INDEX.get(pref);
      if (!entry) return { deps: [], dependents: [] };
      const deps = entry.pkg.depends
        .map(d => PACKAGE_INDEX.get(d))
        .filter(Boolean)
        .sort((a, b) => a.levelIdx - b.levelIdx || parseRef(a.pkg.ref).name.localeCompare(parseRef(b.pkg.ref).name));
      const dependents = (DEPENDENTS_INDEX.get(pref) || [])
        .slice()
        .sort((a, b) => a.levelIdx - b.levelIdx || parseRef(a.pkg.ref).name.localeCompare(parseRef(b.pkg.ref).name));
      return { deps, dependents };
    }

    function renderRelItem(entry) {
      const { name, version } = parseRef(entry.pkg.ref);
      const label = version ? `${name}/${version}` : name;
      return `<li data-target="${entry.id}" title="Go to ${escapeHtml(label)}">${escapeHtml(label)}<span class="lvl">L${entry.levelIdx}</span></li>`;
    }

    function renderRelations(pref) {
      const { deps, dependents } = getRelations(pref);
      const parts = [];

      if (deps.length) {
        parts.push(`
          <div class="section">
            <div class="section-title down">Depends on (${deps.length})</div>
            <ul class="rel-list rel-down">${deps.map(renderRelItem).join("")}</ul>
          </div>`);
      }

      if (dependents.length) {
        parts.push(`
          <div class="section">
            <div class="section-title up">Depended on by (${dependents.length})</div>
            <ul class="rel-list rel-up">${dependents.map(renderRelItem).join("")}</ul>
          </div>`);
      }

      return parts.join("");
    }

    function renderDetails(pkg, info) {
      const parts = [];

      if (pkg.context) {
        parts.push(`<div class="section"><div class="section-title">Context</div>${renderKV({ context: pkg.context })}</div>`);
      }

      parts.push(`
        <div class="section"><div class="section-title">Ref</div>
          <div class="kv-grid">
            <div class="kv"><span class="kv-val">${escapeHtml(pkg.ref)}</span></div>
            <div class="kv"><span class="kv-key">package_id</span><span class="kv-val">${escapeHtml(pkg.package_id || "")}</span></div>
          </div>
        </div>`);

      if (info.settings) {
        parts.push(`<div class="section"><div class="section-title">Settings</div>${renderKV(info.settings)}</div>`);
      }
      if (info.options) {
        parts.push(`<div class="section"><div class="section-title">Options</div>${renderOptionsTable(info.options)}</div>`);
      }
      if (info.requires) {
        parts.push(renderList("Requires", info.requires));
      }
      if (pkg.build_args) {
        parts.push(`<div class="section"><div class="section-title">Build args</div><div class="kv-grid"><div class="kv"><span class="kv-val">${escapeHtml(pkg.build_args)}</span></div></div></div>`);
      }
      if (pkg.filenames && pkg.filenames.length) {
        parts.push(renderList("Sources", pkg.filenames));
      }
      if (pkg.options && pkg.options.length) {
        parts.push(renderList("Override", pkg.options));
      }
      if (info.compatibility_delta) {
        parts.push(`<div class="section"><div class="section-title">Compatibility</div>${renderKV({ settings: JSON.stringify(info.compatibility_delta.settings) })}</div>`);
      }

      return `<div class="details-section"><div class="details-heading">Details</div>${parts.join("")}</div>`;
    }

    function clearHighlightClasses() {
      document.querySelectorAll(".pkg").forEach(p => {
        p.classList.remove("active", "dep-linked");
      });
    }

    function clearHighlights() {
      clearHighlightClasses();
      updateScrollHints();
    }

    function getLinkedPackages(body) {
      return [...body.querySelectorAll(".pkg.active, .pkg.dep-linked, .pkg.search-hit")]
        .filter(p => !p.classList.contains("hidden"));
    }

    function isLinkedAbove(body, el) {
      const bodyRect = body.getBoundingClientRect();
      const elRect = el.getBoundingClientRect();
      return elRect.bottom < bodyRect.top + 6 || elRect.top < bodyRect.top + 6;
    }

    function isLinkedBelow(body, el) {
      const bodyRect = body.getBoundingClientRect();
      const elRect = el.getBoundingClientRect();
      return elRect.top > bodyRect.bottom - 6 || elRect.bottom > bodyRect.bottom - 6;
    }

    function setHintState(hint, visible, count, label) {
      hint.classList.toggle("is-visible", visible);
      hint.querySelector(".hint-count").textContent = visible ? String(count) : "";
      hint.querySelector(".hint-label").textContent = visible ? label : "";
    }

    function updateScrollHints() {
      document.querySelectorAll(".level").forEach(level => {
        const body = level.querySelector(".level-body");
        const hintUp = level.querySelector(".scroll-hint-up");
        const hintDown = level.querySelector(".scroll-hint-down");
        if (!body || !hintUp || !hintDown) return;

        const linked = getLinkedPackages(body);
        if (!linked.length) {
          setHintState(hintUp, false, 0, "");
          setHintState(hintDown, false, 0, "");
          return;
        }

        const above = linked.filter(pkg => isLinkedAbove(body, pkg));
        const below = linked.filter(pkg => isLinkedBelow(body, pkg));

        setHintState(hintUp, above.length > 0, above.length, "above");
        setHintState(hintDown, below.length > 0, below.length, "below");
      });
    }

    function scrollToLinked(body, direction) {
      const linked = getLinkedPackages(body);
      let target = null;

      if (direction === "up") {
        target = linked
          .filter(pkg => isLinkedAbove(body, pkg))
          .sort((a, b) => b.getBoundingClientRect().top - a.getBoundingClientRect().top)[0];
      } else {
        target = linked
          .filter(pkg => isLinkedBelow(body, pkg))
          .sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top)[0];
      }

      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "nearest" });
        setTimeout(updateScrollHints, 400);
      }
    }

    function highlightRelations(pref) {
      clearHighlightClasses();
      const { deps, dependents } = getRelations(pref);
      const self = PACKAGE_INDEX.get(pref);
      if (self) document.getElementById(self.id)?.classList.add("active");
      deps.forEach(e => document.getElementById(e.id)?.classList.add("dep-linked"));
      dependents.forEach(e => document.getElementById(e.id)?.classList.add("dep-linked"));
      requestAnimationFrame(() => {
        updateScrollHints();
        setTimeout(updateScrollHints, 100);
      });
    }

    function focusPackage(id) {
      const el = document.getElementById(id);
      if (!el) return;
      document.querySelectorAll(".pkg.open").forEach(p => {
        if (p !== el) p.classList.remove("open");
      });
      el.classList.add("open");
      const rel = el.querySelector(".rel-section");
      if (rel) rel.innerHTML = renderRelations(el.dataset.pref);
      highlightRelations(el.dataset.pref);
      el.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
      setTimeout(updateScrollHints, 350);
    }

    function renderPackage(pkg, levelIdx, pkgIdx) {
      const { name, version } = parseRef(pkg.ref);
      const id = `pkg-${levelIdx}-${pkgIdx}`;
      const info = pkg.info || {};
      const { deps, dependents } = getRelations(pkg.pref);
      const contextClass = pkg.context === "build" ? " tag-context-build" : "";

      return `
        <article class="pkg ${binaryClass(pkg.binary)}" id="${id}" data-pref="${escapeHtml(pkg.pref)}" data-ref="${escapeHtml(pkg.ref)}" data-binary="${escapeHtml(pkg.binary)}" data-search="${escapeHtml([pkg.ref, pkg.pref, pkg.package_id, pkg.prev, pkg.context, name].filter(Boolean).join(" ").toLowerCase())}">
          <div class="pkg-head" title="${escapeHtml(pkg.ref)} &bull; ${escapeHtml(pkg.binary)}${pkg.context ? ` &bull; ${escapeHtml(pkg.context)}` : ""}">
            <span class="pkg-label">
              <span class="pkg-name">${escapeHtml(name)}</span>
              <span class="pkg-version">${escapeHtml(version)}</span>
            </span>
            <span class="pkg-tags">
              ${pkg.context ? `<span class="tag tag-context${contextClass}" title="Context">${escapeHtml(pkg.context)}</span>` : ""}
              ${deps.length ? `<span class="tag tag-deps-down" title="Depends on">&darr;${deps.length}</span>` : ""}
              ${dependents.length ? `<span class="tag tag-deps-up" title="Depended on by">&uarr;${dependents.length}</span>` : ""}
            </span>
          </div>
          <div class="pkg-body">
            <div class="rel-section"></div>
            ${renderDetails(pkg, info)}
          </div>
        </article>`;
    }

    function renderLevels(data) {
      const container = document.getElementById("levels");
      container.innerHTML = data.order.map((level, i) => {
        const cache = level.filter(p => p.binary === "Cache").length;
        const download = level.filter(p => p.binary === "Download").length;
        const missing = level.filter(p => p.binary === "Missing").length;
        const build = level.filter(p => p.binary === "Build" || p.binary === "EditableBuild").length;
        const pkgs = level.map((p, j) => renderPackage(p, i, j)).join("");
        const pkgLabel = level.length === 1 ? "package" : "packages";
        return `
          <section class="level" data-level="${i}">
            <div class="level-header" title="Level ${i}">
              <div class="level-label">
                <div class="level-name">Level <span>${i}</span></div>
                <div class="level-sub">${level.length} ${pkgLabel}</div>
              </div>
              <div class="level-stats">
                ${cache ? `<span class="stat-chip"><span class="dot dot-cache"></span>${cache}</span>` : ""}
                ${download ? `<span class="stat-chip"><span class="dot dot-download"></span>${download}</span>` : ""}
                ${missing ? `<span class="stat-chip"><span class="dot dot-missing"></span>${missing}</span>` : ""}
                ${build ? `<span class="stat-chip"><span class="dot dot-build"></span>${build}</span>` : ""}
              </div>
            </div>
            <div class="level-scroll">
              <div class="level-body">${pkgs}</div>
              <button type="button" class="scroll-hint scroll-hint-up" title="Related items above">
                <span class="hint-icon">&#9650;</span>
                <span class="hint-count"></span>
                <span class="hint-label"></span>
              </button>
              <button type="button" class="scroll-hint scroll-hint-down" title="Related items below">
                <span class="hint-icon">&#9660;</span>
                <span class="hint-count"></span>
                <span class="hint-label"></span>
              </button>
            </div>
          </section>`;
      }).join("");
    }

    function applyFilters() {
      const q = document.getElementById("search").value.trim().toLowerCase();
      let visible = 0;

      document.querySelectorAll(".pkg").forEach(el => {
        const matchSearch = !q || el.dataset.search.includes(q);
        el.classList.remove("hidden");
        el.classList.toggle("search-hit", !!q && matchSearch);
        if (matchSearch) visible++;
      });

      document.querySelectorAll(".level").forEach(level => {
        level.style.display = "";
      });

      document.getElementById("empty").style.display = q && visible === 0 ? "" : "none";
    }

    function bindEvents() {
      document.getElementById("search").addEventListener("input", () => {
        applyFilters();
        updateScrollHints();
      });

      document.getElementById("levels").addEventListener("click", e => {
        const hint = e.target.closest(".scroll-hint");
        if (hint) {
          e.stopPropagation();
          const level = hint.closest(".level");
          const body = level?.querySelector(".level-body");
          if (body) scrollToLinked(body, hint.classList.contains("scroll-hint-up") ? "up" : "down");
          return;
        }

        const relItem = e.target.closest(".rel-list li[data-target]");
        if (relItem) {
          e.stopPropagation();
          focusPackage(relItem.dataset.target);
          return;
        }

        const pkgHead = e.target.closest(".pkg-head");
        if (!pkgHead) return;

        const pkgEl = pkgHead.closest(".pkg");
        const wasOpen = pkgEl.classList.contains("open");
        document.querySelectorAll(".pkg.open").forEach(p => p.classList.remove("open"));
        clearHighlights();

        if (!wasOpen) {
          pkgEl.classList.add("open");
          const rel = pkgEl.querySelector(".rel-section");
          if (rel) rel.innerHTML = renderRelations(pkgEl.dataset.pref);
          highlightRelations(pkgEl.dataset.pref);
        }
      });

      document.querySelectorAll(".level-body").forEach(body => {
        body.addEventListener("scroll", updateScrollHints, { passive: true });
      });

      window.addEventListener("resize", updateScrollHints, { passive: true });
    }

    buildIndexes(ORDER_DATA);
    renderMeta(ORDER_DATA);
    renderLevels(ORDER_DATA);
    bindEvents();
  </script>
</body>
</html>
"""


def format_build_order_html(result):
    build_order = result["build_order"]
    template = Template(build_order_html, autoescape=select_autoescape(['html', 'xml']))
    cli_out_write(template.render({"build_order": build_order}))
