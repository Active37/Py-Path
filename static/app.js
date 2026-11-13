(() => {
  document.documentElement.classList.add("js-ready");
  const navToggle = document.querySelector("[data-nav-toggle]");
  const siteNavigation = navToggle
    ? document.getElementById(navToggle.getAttribute("aria-controls"))
    : null;

  if (navToggle && siteNavigation) {
    const compactNavigation = window.matchMedia("(max-width: 1100px)");
    const label = navToggle.querySelector("[data-nav-toggle-label]");

    function syncNavigation() {
      const isCompact = compactNavigation.matches;
      navToggle.hidden = !isCompact;
      if (!isCompact) {
        navToggle.setAttribute("aria-expanded", "false");
        navToggle.setAttribute("aria-label", "Open navigation");
        if (label) label.textContent = "Menu";
        siteNavigation.hidden = false;
        return;
      }

      const isExpanded = navToggle.getAttribute("aria-expanded") === "true";
      siteNavigation.hidden = !isExpanded;
    }

    navToggle.addEventListener("click", () => {
      const isExpanded = navToggle.getAttribute("aria-expanded") === "true";
      const nextExpanded = !isExpanded;
      navToggle.setAttribute("aria-expanded", String(nextExpanded));
      navToggle.setAttribute("aria-label", nextExpanded ? "Close navigation" : "Open navigation");
      if (label) label.textContent = nextExpanded ? "Close" : "Menu";
      siteNavigation.hidden = compactNavigation.matches && !nextExpanded;
    });

    if (compactNavigation.addEventListener) {
      compactNavigation.addEventListener("change", syncNavigation);
    } else {
      compactNavigation.addListener(syncNavigation);
    }
    window.addEventListener("resize", syncNavigation);
    syncNavigation();
  }

  const installButton = document.querySelector("[data-install-app]");
  const installStatus = document.querySelector("[data-install-status]");
  const installDialog = document.querySelector("[data-install-dialog]");
  const installClose = document.querySelector("[data-install-close]");
  let installPrompt = null;
  const isInstalled = window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true;

  if (installButton) installButton.hidden = isInstalled;

  function showInstallInstructions() {
    if (installDialog && typeof installDialog.showModal === "function") {
      if (!installDialog.open) installDialog.showModal();
    } else if (installDialog) {
      installDialog.setAttribute("open", "");
    } else if (installStatus) {
      installStatus.textContent = "Use your browser menu to install PyPath or add it to your home screen.";
    }
  }

  installClose?.addEventListener("click", () => {
    if (installDialog && typeof installDialog.close === "function") {
      installDialog.close();
    } else {
      installDialog?.removeAttribute("open");
    }
  });

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    installPrompt = event;
    if (installButton) installButton.hidden = false;
  });

  installButton?.addEventListener("click", async () => {
    if (!installPrompt) {
      showInstallInstructions();
      return;
    }

    const prompt = installPrompt;
    installPrompt = null;
    try {
      await prompt.prompt();
      const choice = await prompt.userChoice;
      if (installStatus) {
        installStatus.textContent = choice.outcome === "accepted"
          ? "PyPath is being installed."
          : "Installation was dismissed. You can use the browser menu to install PyPath.";
      }
    } catch (error) {
      console.error("PyPath's browser install prompt could not be opened:", error);
      if (installStatus) {
        installStatus.textContent = "The install prompt could not be opened. Use the browser menu to install PyPath.";
      }
      showInstallInstructions();
    }
  });

  window.addEventListener("appinstalled", () => {
    if (installButton) installButton.hidden = true;
    if (installStatus) installStatus.textContent = "PyPath is installed.";
    if (installDialog?.open) installDialog.close();
  });

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/service-worker.js")
        .catch((error) => console.error("PyPath offline support could not start:", error));
    });
  }

  const revealItems = document.querySelectorAll("[data-reveal]");
  if ("IntersectionObserver" in window && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    const revealObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
    revealItems.forEach((item) => revealObserver.observe(item));
  } else {
    revealItems.forEach((item) => item.classList.add("is-visible"));
  }

  document.querySelectorAll("[data-lesson-checklist]").forEach((checklist) => {
    const storageKey = `pypath-checklist:${checklist.dataset.lessonChecklist}`;
    const checkboxes = Array.from(checklist.querySelectorAll('input[type="checkbox"]'));
    const status = checklist.querySelector("[data-checklist-status]");
    try {
      const saved = new Set((localStorage.getItem(storageKey) || "").split(","));
      checkboxes.forEach((checkbox) => {
        checkbox.checked = saved.has(checkbox.value);
        checkbox.addEventListener("change", () => {
          const checked = checkboxes.filter((item) => item.checked).map((item) => item.value);
          localStorage.setItem(storageKey, checked.join(","));
          if (status) status.textContent = "Checklist saved on this device.";
        });
      });
    } catch (error) {
      if (status) status.textContent = "Device storage is unavailable; this checklist will not persist.";
      console.error("PyPath could not save this lesson checklist:", error);
    }
  });

  const playground = document.querySelector("[data-playground]");
  if (playground) {
    const editors = Object.fromEntries(
      Array.from(playground.querySelectorAll("[data-playground-editor]"))
        .map((editor) => [editor.dataset.playgroundEditor, editor])
    );
    const preview = playground.querySelector("[data-playground-preview]");
    const consoleOutput = playground.querySelector("[data-playground-console]");
    const status = playground.querySelector("[data-playground-status]");
    const nameInput = playground.querySelector("[data-snippet-name]");
    const snippetSelect = playground.querySelector("[data-snippet-list]");
    const storageKey = "pypath-web-playground:v1";
    let consoleLines = [];
    let savedSnippets = [];

    function setPlaygroundStatus(message) {
      if (status) status.textContent = message;
    }

    function readSnippets() {
      try {
        const stored = JSON.parse(localStorage.getItem(storageKey) || "[]");
        return Array.isArray(stored)
          ? stored.filter((item) =>
            item && typeof item.id === "string" && typeof item.name === "string" &&
            typeof item.html === "string" && typeof item.css === "string" &&
            typeof item.js === "string"
          ).slice(0, 25)
          : [];
      } catch (error) {
        console.error("PyPath could not load saved playground projects:", error);
        setPlaygroundStatus("Saved projects could not be read from this device.");
        return [];
      }
    }

    function writeSnippets() {
      try {
        localStorage.setItem(storageKey, JSON.stringify(savedSnippets.slice(0, 25)));
        return true;
      } catch (error) {
        console.error("PyPath could not save this playground project:", error);
        setPlaygroundStatus("This project could not be saved in browser storage.");
        return false;
      }
    }

    function updateSnippetList(selectedId = "") {
      snippetSelect.replaceChildren(new Option("Saved projects…", ""));
      savedSnippets.forEach((snippet) => {
        const option = new Option(snippet.name, snippet.id);
        snippetSelect.add(option);
      });
      snippetSelect.value = selectedId;
    }

    function currentCode() {
      return {
        html: editors.html.value,
        css: editors.css.value,
        js: editors.js.value
      };
    }

    function safeScriptValue(value) {
      return JSON.stringify(value).replace(/</g, "\\u003c");
    }

    function buildPreviewDocument() {
      const code = currentCode();
      const policy = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; " +
        "img-src data: blob:; media-src data: blob:; font-src data:; connect-src 'none'; " +
        "object-src 'none'; base-uri 'none'; form-action 'none'; navigate-to 'none'";
      const bridge = `(function () {
        function format(value) {
          if (typeof value === "string") return value;
          try { return JSON.stringify(value) || String(value); }
          catch (_) { return "[unserializable value]"; }
        }
        function report(level, values) {
          parent.postMessage({
            channel: "pypath-playground",
            level: level,
            text: values.map(format).join(" ").slice(0, 2000)
          }, "*");
        }
        ["log", "info", "warn", "error"].forEach(function (level) {
          var original = console[level].bind(console);
          console[level] = function () {
            var values = Array.from(arguments);
            original.apply(console, values);
            report(level, values);
          };
        });
        window.addEventListener("error", function (event) {
          report("error", [event.message || "Preview error"]);
        });
        window.addEventListener("unhandledrejection", function (event) {
          report("error", [event.reason && event.reason.message || event.reason || "Unhandled promise rejection"]);
        });
        document.addEventListener("click", function (event) {
          var link = event.target.closest && event.target.closest("a");
          if (link) {
            event.preventDefault();
            report("warn", ["Navigation is disabled in the preview sandbox."]);
          }
        });
        document.addEventListener("submit", function (event) {
          event.preventDefault();
          report("warn", ["Form submission is disabled in the preview sandbox."]);
        });
        var style = document.createElement("style");
        style.textContent = ${safeScriptValue(code.css)};
        document.head.appendChild(style);
        document.body.innerHTML = ${safeScriptValue(code.html)};
        var userScript = document.createElement("script");
        userScript.textContent = ${safeScriptValue(code.js)};
        document.body.appendChild(userScript);
        parent.postMessage({ channel: "pypath-playground", level: "ready", text: "Preview updated." }, "*");
      })();`;
      return `<!doctype html><html lang="en"><head><meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta http-equiv="Content-Security-Policy" content="${policy}">
        </head><body><script>${bridge}<\/script></body></html>`;
    }

    function renderConsole() {
      consoleOutput.textContent = consoleLines.length
        ? consoleLines.map((line) => `${line.level === "ready" ? "✓" : line.level.toUpperCase()}  ${line.text}`).join("\n")
        : "Run your project to see console messages and errors.";
      consoleOutput.scrollTop = consoleOutput.scrollHeight;
    }

    function runPreview() {
      consoleLines = [];
      renderConsole();
      preview.srcdoc = buildPreviewDocument();
      setPlaygroundStatus("Running your preview…");
    }

    playground.querySelectorAll("[data-editor-tab]").forEach((tab) => {
      tab.addEventListener("click", () => {
        playground.querySelectorAll("[data-editor-tab]").forEach((candidate) => {
          const selected = candidate === tab;
          candidate.setAttribute("aria-selected", String(selected));
          editors[candidate.dataset.editorTab].hidden = !selected;
          editors[candidate.dataset.editorTab].classList.toggle("is-active", selected);
        });
        editors[tab.dataset.editorTab].focus();
      });
    });

    playground.querySelector("[data-playground-run]").addEventListener("click", runPreview);
    playground.querySelector("[data-playground-reset]").addEventListener("click", () => {
      Object.values(editors).forEach((editor) => {
        editor.value = editor.defaultValue;
      });
      nameInput.value = "My web project";
      runPreview();
      setPlaygroundStatus("Starter project restored.");
    });

    playground.querySelector("[data-snippet-save]").addEventListener("click", () => {
      const name = nameInput.value.trim();
      if (!name || name.length > 60) {
        setPlaygroundStatus("Enter a project name of 1–60 characters.");
        nameInput.focus();
        return;
      }
      const existing = savedSnippets.find((snippet) => snippet.name.toLowerCase() === name.toLowerCase());
      const snippet = {
        id: existing ? existing.id : `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        name,
        ...currentCode(),
        savedAt: new Date().toISOString()
      };
      savedSnippets = [snippet, ...savedSnippets.filter((item) => item.id !== snippet.id)].slice(0, 25);
      if (writeSnippets()) {
        updateSnippetList(snippet.id);
        setPlaygroundStatus("Project saved on this device.");
      }
    });

    playground.querySelector("[data-snippet-load]").addEventListener("click", () => {
      const snippet = savedSnippets.find((item) => item.id === snippetSelect.value);
      if (!snippet) {
        setPlaygroundStatus("Choose a saved project to load.");
        return;
      }
      Object.keys(editors).forEach((key) => {
        editors[key].value = snippet[key];
      });
      nameInput.value = snippet.name;
      runPreview();
      setPlaygroundStatus(`Loaded “${snippet.name}”.`);
    });

    playground.querySelector("[data-snippet-delete]").addEventListener("click", () => {
      const selectedId = snippetSelect.value;
      if (!selectedId) {
        setPlaygroundStatus("Choose a saved project to delete.");
        return;
      }
      savedSnippets = savedSnippets.filter((snippet) => snippet.id !== selectedId);
      if (writeSnippets()) {
        updateSnippetList();
        setPlaygroundStatus("Saved project deleted from this device.");
      }
    });

    playground.querySelector("[data-console-clear]").addEventListener("click", () => {
      consoleLines = [];
      renderConsole();
    });

    playground.querySelector("[data-playground-download]").addEventListener("click", () => {
      const code = currentCode();
      const safeJs = code.js.replace(/<\/script/gi, "<\\/script");
      const documentText = `<!doctype html><html lang="en"><head>
        <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>${nameInput.value.trim().replace(/[<>&"]/g, "") || "My web project"}</title>
        <style>${code.css}</style></head><body>${code.html}<script>${safeJs}<\/script></body></html>`;
      const file = new Blob([documentText], { type: "text/html;charset=utf-8" });
      const url = URL.createObjectURL(file);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${(nameInput.value.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "pypath-project")}.html`;
      link.click();
      URL.revokeObjectURL(url);
      setPlaygroundStatus("Standalone HTML project downloaded.");
    });

    window.addEventListener("message", (event) => {
      if (event.source !== preview.contentWindow || !event.data ||
          event.data.channel !== "pypath-playground" ||
          typeof event.data.text !== "string") return;
      const level = ["log", "info", "warn", "error", "ready"].includes(event.data.level)
        ? event.data.level
        : "log";
      consoleLines.push({ level, text: event.data.text.slice(0, 2000) });
      if (consoleLines.length > 100) consoleLines.shift();
      renderConsole();
      if (level === "ready") setPlaygroundStatus("Preview is up to date.");
    });

    savedSnippets = readSnippets();
    updateSnippetList();
    runPreview();
  }
})();
