/* ophix admin — persist changelist filter state across page loads
 *
 * Saves active filter/search/ordering params to localStorage (keyed by
 * pathname) so they survive navigation away and back.  Page number is never
 * persisted.  A "Reset filters" link in object-tools lets the operator clear
 * saved state and return to the unfiltered view.
 */
document.addEventListener('DOMContentLoaded', function () {
    if (!document.getElementById('changelist')) return;

    var PREFIX      = 'ophix-filter:';
    var RESET_FLAG  = 'ophix-filter-reset:';
    var pathname    = window.location.pathname;
    var storageKey  = PREFIX + pathname;
    var resetKey    = RESET_FLAG + pathname;

    function getFilterString() {
        var params = new URLSearchParams(window.location.search);
        params.delete('p');  // never persist page number
        return params.toString();
    }

    var filterStr = getFilterString();

    if (filterStr) {
        // Filters active — save current state
        localStorage.setItem(storageKey, filterStr);
    } else if (sessionStorage.getItem(resetKey)) {
        // User just clicked "Reset filters" — clear saved state, don't redirect
        sessionStorage.removeItem(resetKey);
        localStorage.removeItem(storageKey);
    } else {
        var saved = localStorage.getItem(storageKey);
        if (saved) {
            window.location.replace(pathname + '?' + saved);
            return;
        }
    }

    // Show "Reset filters" in object-tools whenever saved state exists
    var hasSaved = localStorage.getItem(storageKey);
    if (hasSaved) {
        var tools = document.querySelector('.object-tools');
        if (tools) {
            var li = document.createElement('li');
            var a  = document.createElement('a');
            a.href      = '#';
            a.textContent = 'Reset filters';
            a.addEventListener('click', function (e) {
                e.preventDefault();
                sessionStorage.setItem(resetKey, '1');
                window.location.href = pathname;
            });
            li.appendChild(a);
            tools.appendChild(li);
        }
    }
});

/* ophix admin — list-view checkbox auto-save
 *
 * When a list_editable checkbox is toggled in the changelist:
 *   1. The form is submitted automatically (no manual Save click required).
 *   2. The Save button is hidden when checkboxes are the only editable fields.
 *   3. The "N rows updated" success message is suppressed after an auto-save.
 *
 * Only fires on data checkboxes inside <td> cells.  Row-selection checkboxes
 * (action-select / action-toggle) are explicitly excluded.
 */
/* ophix admin — normalise inline "Add another X" → "Add X" globally
 *
 * Django generates this text in JavaScript from inline_formset_data, so it
 * cannot be changed via template override. Strip "another " from every
 * add-row link text after the page loads and again whenever Django's inline
 * JS adds new rows (which re-renders the link via MutationObserver).
 */
document.addEventListener('DOMContentLoaded', function () {
    function normaliseAddLinks(root) {
        (root || document).querySelectorAll('tr.add-row a').forEach(function (a) {
            a.textContent = a.textContent.replace(/^Add another /, 'Add ');
        });
    }

    normaliseAddLinks();

    // Re-run when Django's inline JS dynamically adds/updates rows
    var observer = new MutationObserver(function (mutations) {
        mutations.forEach(function (m) {
            m.addedNodes.forEach(function (node) {
                if (node.nodeType === 1) normaliseAddLinks(node);
            });
        });
    });
    observer.observe(document.body, { childList: true, subtree: true });
});

document.addEventListener('DOMContentLoaded', function () {
    var form = document.getElementById('changelist-form');
    if (!form) return;

    // -----------------------------------------------------------------------
    // 1. Suppress the success message that follows an auto-save.
    //    sessionStorage carries a flag across Django's post-redirect-get.
    // -----------------------------------------------------------------------
    if (sessionStorage.getItem('ophix_autosave_pending')) {
        sessionStorage.removeItem('ophix_autosave_pending');
        var msgList = document.querySelector('.messagelist');
        if (msgList) msgList.remove();
    }

    // -----------------------------------------------------------------------
    // 2. Hide the Save button when the only list_editable fields are
    //    checkboxes — it is unreachable without auto-save anyway.
    //    If a future model adds a text/select field to list_editable the
    //    button stays visible so the user can still save those fields.
    // -----------------------------------------------------------------------
    var saveBtn = form.querySelector('[name="_save"]');
    if (saveBtn) {
        var nonCheckboxEditables = form.querySelectorAll(
            'td input:not([type="hidden"]):not([type="checkbox"]), td select, td textarea'
        );
        if (nonCheckboxEditables.length === 0) {
            saveBtn.style.display = 'none';
        }
    }

    // -----------------------------------------------------------------------
    // 3. Auto-save on checkbox change.
    //    Hidden buttons still respond to .click() and include their
    //    name/value in the form submission, so this works even after step 2.
    // -----------------------------------------------------------------------
    form.addEventListener('change', function (e) {
        var target = e.target;
        if (target.type !== 'checkbox') return;
        if (target.classList.contains('action-select')) return;
        if (target.id === 'action-toggle') return;
        if (!target.closest('td')) return;

        sessionStorage.setItem('ophix_autosave_pending', '1');
        var btn = form.querySelector('[name="_save"]');
        if (btn) btn.click();
    });
});
