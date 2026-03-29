(function () {
    const uploadForm = document.getElementById('receipt-upload-form');
    const uploadInput = document.getElementById('receipt_image');
    const uploadStatus = document.getElementById('receipt-upload-status');
    const reviewCard = document.getElementById('receipt-review-card');
    const reviewForm = document.getElementById('receipt-review-form');
    const itemsContainer = document.getElementById('receipt-items');
    const itemsEmpty = document.getElementById('receipt-items-empty');
    const addItemButton = document.getElementById('receipt-add-item');
    const shareSummary = document.getElementById('receipt-share-summary');
    const taxParticipants = document.getElementById('tax-participants');
    const tipParticipants = document.getElementById('tip-participants');

    if (!reviewForm) {
        return;
    }

    const members = JSON.parse(document.getElementById('receipt-members-data').textContent || '[]');
    const initialReviewState = JSON.parse(document.getElementById('receipt-review-data').textContent || 'null');

    function memberOptions(selectedValue) {
        const placeholder = '<option value="">Assign participant</option>';
        return placeholder + members.map(member => {
            const selected = String(selectedValue || '') === String(member.id) ? ' selected' : '';
            return `<option value="${member.id}"${selected}>${escapeHtml(member.name)}</option>`;
        }).join('');
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function parseAmount(value) {
        const amount = Number.parseFloat(value);
        if (!Number.isFinite(amount) || amount < 0) {
            return 0;
        }
        return Math.round(amount * 100) / 100;
    }

    function toCents(amount) {
        return Math.round(parseAmount(amount) * 100);
    }

    function fromCents(cents) {
        return (cents / 100).toFixed(2);
    }

    function setFieldValue(id, value) {
        const field = document.getElementById(id);
        if (field) {
            field.value = value == null ? '' : value;
        }
    }

    function renderParticipantCheckboxes(container, fieldName, selectedIds) {
        container.innerHTML = members.map(member => {
            const checked = selectedIds.includes(String(member.id)) ? ' checked' : '';
            return `
                <label class="receipt-member-check">
                    <input type="checkbox" name="${fieldName}" value="${member.id}"${checked}>
                    <span>${escapeHtml(member.name)}</span>
                </label>
            `;
        }).join('');
    }

    function createItemRow(item) {
        const row = document.createElement('div');
        row.className = 'receipt-item-row';
        row.innerHTML = `
            <div class="form-group">
                <label>Item name</label>
                <input class="receipt-input" type="text" name="item_name[]" value="${escapeHtml(item.name || '')}" required>
            </div>
            <div class="form-group">
                <label>Amount</label>
                <input class="receipt-input" type="number" name="item_amount[]" min="0" step="0.01" value="${escapeHtml(item.amount || '')}" required>
            </div>
            <div class="form-group">
                <label>Assigned to</label>
                <select class="receipt-select" name="item_user_id[]" required>${memberOptions(item.assigned_user_id)}</select>
            </div>
            <div class="form-group">
                <label>&nbsp;</label>
                <button type="button" class="btn btn-outline receipt-remove-item">Delete</button>
            </div>
        `;
        row.querySelector('.receipt-remove-item').addEventListener('click', function () {
            row.remove();
            updateItemsEmptyState();
            updateShareSummary();
        });
        row.querySelectorAll('input, select').forEach(field => {
            field.addEventListener('input', updateShareSummary);
            field.addEventListener('change', updateShareSummary);
        });
        itemsContainer.appendChild(row);
        updateItemsEmptyState();
    }

    function updateItemsEmptyState() {
        itemsEmpty.style.display = itemsContainer.children.length ? 'none' : 'block';
    }

    function setReviewState(state) {
        reviewCard.classList.remove('receipt-hidden');

        setFieldValue('description', state.description || '');
        setFieldValue('merchant_name', state.merchant_name || '');
        setFieldValue('currency', state.currency || 'ARS');
        setFieldValue('confidence', state.confidence || '');
        setFieldValue('subtotal_amount', state.subtotal_amount || '');
        setFieldValue('tax_amount', state.tax_amount || '');
        setFieldValue('tip_amount', state.tip_amount || '');
        setFieldValue('total_amount', state.total_amount || '');
        setFieldValue('notes', state.notes || '');
        setFieldValue('payer_id', state.payer_id || '');
        setFieldValue('expense_date', state.expense_date || '');

        itemsContainer.innerHTML = '';
        const items = Array.isArray(state.items) && state.items.length
            ? state.items
            : Array.isArray(state.extracted_items) ? state.extracted_items : [];

        items.forEach(item => createItemRow({
            name: item.name || '',
            amount: item.amount != null ? item.amount : '',
            assigned_user_id: item.assigned_user_id || '',
        }));

        renderParticipantCheckboxes(
            taxParticipants,
            'tax_split_participants',
            (state.selected_tax_participants || members.map(member => String(member.id))).map(String)
        );
        renderParticipantCheckboxes(
            tipParticipants,
            'tip_split_participants',
            (state.selected_tip_participants || members.map(member => String(member.id))).map(String)
        );

        reviewForm.querySelectorAll('#tax-participants input, #tip-participants input, #description, #merchant_name, #currency, #confidence, #subtotal_amount, #tax_amount, #tip_amount, #total_amount, #payer_id, #expense_date, #notes').forEach(field => {
            field.addEventListener('input', updateShareSummary);
            field.addEventListener('change', updateShareSummary);
        });

        updateItemsEmptyState();
        updateShareSummary();
    }

    function collectSelectedParticipantIds(fieldName) {
        return Array.from(reviewForm.querySelectorAll(`input[name="${fieldName}"]:checked`))
            .map(input => Number.parseInt(input.value, 10))
            .filter(Number.isInteger);
    }

    function updateShareSummary() {
        const shareCents = {};
        members.forEach(member => {
            shareCents[member.id] = 0;
        });

        Array.from(itemsContainer.querySelectorAll('.receipt-item-row')).forEach(row => {
            const amount = toCents(row.querySelector('input[name="item_amount[]"]').value);
            const userId = Number.parseInt(row.querySelector('select[name="item_user_id[]"]').value, 10);
            if (Number.isInteger(userId)) {
                shareCents[userId] = (shareCents[userId] || 0) + amount;
            }
        });

        allocateEvenSplit(shareCents, collectSelectedParticipantIds('tax_split_participants'), toCents(document.getElementById('tax_amount').value));
        allocateEvenSplit(shareCents, collectSelectedParticipantIds('tip_split_participants'), toCents(document.getElementById('tip_amount').value));

        const rows = members
            .map(member => ({ member, cents: shareCents[member.id] || 0 }))
            .filter(entry => entry.cents > 0);

        const totalPreview = rows.reduce((sum, entry) => sum + entry.cents, 0);
        const targetTotal = toCents(document.getElementById('total_amount').value);

        if (!rows.length) {
            shareSummary.innerHTML = '<div class="receipt-summary-row"><span>No assigned shares yet.</span><span>$0.00</span></div>';
            return;
        }

        shareSummary.innerHTML = rows.map(entry => `
            <div class="receipt-summary-row">
                <span>${escapeHtml(entry.member.name)}</span>
                <span>$${fromCents(entry.cents)}</span>
            </div>
        `).join('') + `
            <div class="receipt-summary-row">
                <span>Computed total</span>
                <span>$${fromCents(totalPreview)}</span>
            </div>
            <div class="receipt-summary-row">
                <span>Reviewed total</span>
                <span>$${fromCents(targetTotal)}</span>
            </div>
        `;
    }

    function allocateEvenSplit(shareCents, participantIds, amountCents) {
        if (!participantIds.length || amountCents <= 0) {
            return;
        }

        const sorted = [...participantIds].sort((a, b) => a - b);
        const base = Math.floor(amountCents / sorted.length);
        const remainder = amountCents % sorted.length;
        sorted.forEach((userId, index) => {
            shareCents[userId] = (shareCents[userId] || 0) + base + (index < remainder ? 1 : 0);
        });
    }

    if (uploadForm) {
        uploadForm.addEventListener('submit', async function (event) {
            event.preventDefault();
            const file = uploadInput.files[0];
            if (!file) {
                uploadStatus.textContent = 'Choose a receipt image first.';
                return;
            }

            uploadStatus.textContent = 'Extracting receipt draft...';
            const formData = new FormData();
            formData.append('receipt_image', file);

            try {
                const response = await fetch('/api/receipt/draft', {
                    method: 'POST',
                    body: formData,
                });
                const payload = await response.json();
                if (!response.ok) {
                    throw new Error(payload.error || 'Could not extract receipt draft.');
                }

                setReviewState(payload);
                uploadStatus.textContent = 'Draft extracted. Review everything before saving.';
            } catch (error) {
                uploadStatus.textContent = error.message || 'Could not extract receipt draft.';
            }
        });
    }

    addItemButton.addEventListener('click', function () {
        createItemRow({ name: '', amount: '', assigned_user_id: '' });
        updateShareSummary();
    });

    if (initialReviewState) {
        setReviewState(initialReviewState);
    } else {
        renderParticipantCheckboxes(taxParticipants, 'tax_split_participants', members.map(member => String(member.id)));
        renderParticipantCheckboxes(tipParticipants, 'tip_split_participants', members.map(member => String(member.id)));
        updateShareSummary();
    }
})();
