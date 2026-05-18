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
    // 3. Stamp row-state classes on each changelist row so CSS can colour them.
    //    Pure-CSS :has(td.field-enabled input:not(:checked)) is unreliable when
    //    a row also contains td.field-paused — the class approach is explicit.
    // -----------------------------------------------------------------------
    function stampRowStates() {
        form.querySelectorAll('tr').forEach(function (row) {
            var enabledCb = row.querySelector('td.field-enabled input[type="checkbox"]');
            var pausedCb  = row.querySelector('td.field-paused  input[type="checkbox"]');
            row.classList.toggle('ophix-row-disabled', !!(enabledCb && !enabledCb.checked));
            row.classList.toggle('ophix-row-paused',   !!(pausedCb  &&  pausedCb.checked));
        });
    }
    stampRowStates();

    // -----------------------------------------------------------------------
    // 4. Auto-save on checkbox change.
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
