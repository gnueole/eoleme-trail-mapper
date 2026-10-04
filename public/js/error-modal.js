// An accessible error dialog on the app's own modal styles. One instance,
// filled per call: role=dialog, aria-modal, labelled by its title, focus moved
// in on open and trapped while open, Esc or the backdrop to close, focus given
// back to whoever opened it. No library: the app ships none.

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])';

let opener = null;
let keyHandler = null;

function el(id) {
    return document.getElementById(id);
}

export function closeErrorModal() {
    const modal = el('error-modal');
    if (!modal) return;
    modal.style.display = 'none';
    if (keyHandler) {
        document.removeEventListener('keydown', keyHandler, true);
        keyHandler = null;
    }
    if (opener && typeof opener.focus === 'function') opener.focus();
    opener = null;
}

/**
 * @param {Object} content
 * @param {string} content.title
 * @param {string} content.body
 * @param {string} [content.hint]       A quieter line under the body
 * @param {string} [content.sourceUrl]  Shown as the address the source was asked for
 * @param {Array}  content.buttons      [{ label, onClick, primary, href }] left to right;
 *                                      the first primary one gets focus
 * @param {string} [content.labels.source]  Caption before the address
 * @param {string} [content.labels.close]   aria-label of the × button
 */
export function showErrorModal(content) {
    const modal = el('error-modal');
    if (!modal) return;
    opener = document.activeElement;

    el('error-modal-title').textContent = content.title || '';
    el('error-modal-body').textContent = content.body || '';
    const hint = el('error-modal-hint');
    hint.textContent = content.hint || '';
    hint.style.display = content.hint ? '' : 'none';

    const sourceRow = el('error-modal-source');
    const sourceLink = el('error-modal-source-url');
    if (content.sourceUrl) {
        el('error-modal-source-label').textContent = (content.labels && content.labels.source) || '';
        sourceLink.textContent = content.sourceUrl;
        sourceLink.setAttribute('href', content.sourceUrl);
        sourceRow.style.display = '';
    } else {
        sourceLink.removeAttribute('href');
        sourceRow.style.display = 'none';
    }

    const actions = el('error-modal-actions');
    actions.innerHTML = '';
    let first = null;
    (content.buttons || []).forEach(btn => {
        const node = document.createElement(btn.href ? 'a' : 'button');
        node.className = `btn ${btn.primary ? 'btn-primary' : 'btn-secondary'}`;
        node.textContent = btn.label;
        if (btn.href) {
            node.setAttribute('href', btn.href);
            node.setAttribute('target', '_blank');
            node.setAttribute('rel', 'noopener noreferrer');
        } else {
            node.setAttribute('type', 'button');
        }
        node.addEventListener('click', (e) => {
            if (!btn.href) e.preventDefault();
            if (typeof btn.onClick === 'function') btn.onClick();
        });
        actions.appendChild(node);
        if (btn.primary && !first) first = node;
    });

    const closeBtn = el('btn-close-error');
    closeBtn.setAttribute('aria-label', (content.labels && content.labels.close) || 'Close');

    modal.style.display = 'flex';

    keyHandler = (e) => {
        if (e.key === 'Escape') {
            e.preventDefault();
            closeErrorModal();
            return;
        }
        if (e.key !== 'Tab') return;
        const focusable = [...modal.querySelectorAll(FOCUSABLE)].filter(n => n.offsetParent !== null);
        if (focusable.length === 0) return;
        const firstNode = focusable[0];
        const lastNode = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === firstNode) {
            e.preventDefault();
            lastNode.focus();
        } else if (!e.shiftKey && document.activeElement === lastNode) {
            e.preventDefault();
            firstNode.focus();
        }
    };
    document.addEventListener('keydown', keyHandler, true);

    (first || actions.querySelector(FOCUSABLE) || closeBtn).focus();
}

/** Wires the static parts once: the × button and a click on the backdrop. */
export function initErrorModal() {
    const modal = el('error-modal');
    if (!modal) return;
    el('btn-close-error').addEventListener('click', closeErrorModal);
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeErrorModal();
    });
}
