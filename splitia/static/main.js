// ============================================================================
// MAIN.JS
// ============================================================================
// Minimal JavaScript for SplitIA.
// This file contains:
// - expense form validation
// - chat-like assistant flow for text, audio recording, and file uploads
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
    const body = document.body;
    const header = document.querySelector('header');
    const storageKey = 'splitia-theme';

    function currentTheme() {
        return body.dataset.theme || 'light';
    }

    function applyTheme(theme) {
        body.dataset.theme = theme;
        try {
            localStorage.setItem(storageKey, theme);
        } catch (_error) {
            // Ignore storage issues in private browsing or restricted environments.
        }

        const toggle = document.querySelector('[data-theme-toggle]');
        if (toggle) {
            toggle.textContent = theme === 'dark' ? '☀️ Light mode' : '🌙 Dark mode';
        }
    }

    if (header && !document.querySelector('[data-theme-toggle]')) {
        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'theme-toggle';
        toggle.setAttribute('data-theme-toggle', 'true');
        header.appendChild(toggle);
        toggle.addEventListener('click', function() {
            applyTheme(currentTheme() === 'dark' ? 'light' : 'dark');
        });
    }

    let initialTheme = 'light';
    try {
        initialTheme = localStorage.getItem(storageKey) || (
            window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
                ? 'dark'
                : 'light'
        );
    } catch (_error) {
        initialTheme = 'light';
    }

    applyTheme(initialTheme);
});

document.addEventListener('DOMContentLoaded', function() {
    const expenseForm = document.querySelector('form.form');
    const participantCheckboxes = Array.from(document.querySelectorAll('input[name^="participant_"]'));
    const totalAmountInput = document.getElementById('total_amount');
    const shareInputs = Array.from(document.querySelectorAll('input[name^="share_amount_"]'));
    const shareSumHint = document.getElementById('draft-share-sum-hint');
    const splitEquallyButton = document.getElementById('split-equally-btn');

    if (participantCheckboxes.length > 0 && expenseForm) {
        expenseForm.addEventListener('submit', function(event) {
            const anyChecked = Array.from(participantCheckboxes).some(cb => cb.checked);
            if (!anyChecked) {
                event.preventDefault();
                alert('⚠️ Please select at least one participant for the expense!');
            }
        });
    }

    function getShareInputForCheckbox(checkbox) {
        return document.getElementById('share_amount_' + checkbox.id.replace('participant_', ''));
    }

    function parseMoney(value) {
        const parsed = Number(value || 0);
        return Number.isFinite(parsed) ? parsed : 0;
    }

    function markInputManual(input, isManual) {
        if (!input) {
            return;
        }
        input.dataset.manual = isManual ? 'true' : 'false';
    }

    function isInputManual(input) {
        return Boolean(input) && input.dataset.manual === 'true';
    }

    function splitCents(totalAmount, count) {
        if (!count) {
            return [];
        }

        const totalCents = Math.round(totalAmount * 100);
        const base = Math.floor(totalCents / count);
        const remainder = totalCents - (base * count);
        const shares = [];

        for (let index = 0; index < count; index += 1) {
            shares.push((base + (index < remainder ? 1 : 0)) / 100);
        }

        return shares;
    }

    function selectedCheckboxes() {
        return participantCheckboxes.filter(function(checkbox) {
            return checkbox.checked;
        });
    }

    function selectedShareInputs() {
        return selectedCheckboxes().map(getShareInputForCheckbox).filter(Boolean);
    }

    function updateShareSumHint() {
        if (!shareSumHint || !totalAmountInput) {
            return;
        }

        const totalAmount = parseMoney(totalAmountInput.value);
        const selectedShares = selectedShareInputs().reduce(function(sum, input) {
            return sum + parseMoney(input.value);
        }, 0);
        const difference = Number((totalAmount - selectedShares).toFixed(2));

        if (!totalAmount && !selectedShares) {
            shareSumHint.textContent = '';
            shareSumHint.classList.remove('assistant-error');
            return;
        }

        if (Math.abs(difference) <= 0.01) {
            shareSumHint.textContent = 'La suma por persona coincide con el total.';
            shareSumHint.classList.remove('assistant-error');
            return;
        }

        shareSumHint.textContent = 'La suma por persona da $' + selectedShares.toFixed(2) + ' y difiere del total por $' + Math.abs(difference).toFixed(2) + '.';
        shareSumHint.classList.add('assistant-error');
    }

    function rebalanceAutomaticShares() {
        if (!totalAmountInput) {
            updateShareSumHint();
            return;
        }

        const activeInputs = selectedShareInputs();
        if (!activeInputs.length) {
            updateShareSumHint();
            return;
        }

        const totalAmount = parseMoney(totalAmountInput.value);
        const manualInputs = activeInputs.filter(isInputManual);
        const automaticInputs = activeInputs.filter(function(input) {
            return !isInputManual(input);
        });
        const manualTotal = manualInputs.reduce(function(sum, input) {
            return sum + parseMoney(input.value);
        }, 0);
        const remaining = Number((totalAmount - manualTotal).toFixed(2));

        if (!automaticInputs.length) {
            updateShareSumHint();
            return;
        }

        const distributed = splitCents(Math.max(remaining, 0), automaticInputs.length);
        automaticInputs.forEach(function(input, index) {
            input.value = distributed[index].toFixed(2);
        });

        updateShareSumHint();
    }

    function selectAllAndSplitEqually() {
        participantCheckboxes.forEach(function(checkbox) {
            const shareInput = getShareInputForCheckbox(checkbox);
            checkbox.checked = true;
            if (shareInput) {
                shareInput.disabled = false;
                markInputManual(shareInput, false);
            }
        });
        rebalanceAutomaticShares();
    }

    participantCheckboxes.forEach(function(checkbox) {
        checkbox.addEventListener('change', function() {
            const shareInput = getShareInputForCheckbox(checkbox);
            if (!shareInput) {
                return;
            }

            shareInput.disabled = !checkbox.checked;
            if (!checkbox.checked) {
                shareInput.value = '';
                markInputManual(shareInput, false);
            } else if (!isInputManual(shareInput)) {
                markInputManual(shareInput, false);
            }

            rebalanceAutomaticShares();
        });
    });

    shareInputs.forEach(function(input) {
        input.addEventListener('input', function() {
            markInputManual(input, true);
            rebalanceAutomaticShares();
        });
    });

    if (totalAmountInput) {
        totalAmountInput.addEventListener('input', rebalanceAutomaticShares);
    }

    if (splitEquallyButton) {
        splitEquallyButton.addEventListener('click', selectAllAndSplitEqually);
    }

    shareInputs.forEach(function(input) {
        markInputManual(input, Boolean(input.value && !input.disabled));
    });

    rebalanceAutomaticShares();
});

document.addEventListener('DOMContentLoaded', function() {
    const guardedForms = document.querySelectorAll('form[data-single-submit="true"]');

    guardedForms.forEach(function(form) {
        let submitted = false;

        form.addEventListener('submit', function(event) {
            if (submitted) {
                event.preventDefault();
                return;
            }

            submitted = true;

            const submitButton = form.querySelector('button[type="submit"]');
            if (submitButton) {
                submitButton.disabled = true;
                submitButton.textContent = 'Saving...';
            }
        });
    });
});


document.addEventListener('DOMContentLoaded', function() {
    const assistantThread = document.getElementById('assistant-thread');
    const composerInput = document.getElementById('assistant-composer-input');
    const composerSendBtn = document.getElementById('composer-send-btn');
    const micRecordBtn = document.getElementById('mic-record-btn');
    const recordOptionBtn = document.getElementById('record-option-btn');
    const uploadAudioBtn = document.getElementById('upload-audio-btn');
    const uploadTicketBtn = document.getElementById('upload-ticket-btn');
    const audioFileInput = document.getElementById('audio_file');
    const receiptInput = document.getElementById('receipt_image');
    const attachmentSummary = document.getElementById('attachment-summary');
    const recordingIndicator = document.getElementById('recording-indicator');
    const recordingTimer = document.getElementById('recording-timer');
    const transcriptPreviewCard = document.getElementById('transcript-preview-card');
    const transcriptPreviewText = document.getElementById('transcript_preview_text');

    if (
        !assistantThread ||
        !composerInput ||
        !composerSendBtn ||
        !micRecordBtn ||
        !audioFileInput ||
        !transcriptPreviewCard ||
        !transcriptPreviewText
    ) {
        return;
    }

    let mediaRecorder = null;
    let recordedChunks = [];
    let currentTranscript = '';
    let currentTranscriptSource = 'typed';
    let recordingStream = null;
    let recordingIntervalId = null;
    let recordingStartedAt = null;

    function getCurrentGroupMembers() {
        return Array.from(document.querySelectorAll('.split-member-row label')).map(function(label) {
            return (label.textContent || '').trim();
        }).filter(Boolean);
    }

    function getCurrentNarratorHint() {
        const payerSelect = document.getElementById('payer_id');
        if (!payerSelect || !payerSelect.value) {
            return '';
        }

        const selectedOption = payerSelect.options[payerSelect.selectedIndex];
        return selectedOption ? selectedOption.text.trim() : '';
    }

    function getRecordingFormat() {
        if (!window.MediaRecorder || typeof window.MediaRecorder.isTypeSupported !== 'function') {
            return { mimeType: '', extension: 'webm' };
        }

        const candidates = [
            { mimeType: 'audio/webm;codecs=opus', extension: 'webm' },
            { mimeType: 'audio/webm', extension: 'webm' },
            { mimeType: 'audio/mp4', extension: 'm4a' },
            { mimeType: 'audio/ogg;codecs=opus', extension: 'ogg' },
            { mimeType: 'audio/ogg', extension: 'ogg' }
        ];

        return candidates.find(function(candidate) {
            return window.MediaRecorder.isTypeSupported(candidate.mimeType);
        }) || { mimeType: '', extension: 'webm' };
    }

    function escapeHtml(value) {
        return (value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function showElement(element) {
        if (element) {
            element.classList.remove('assistant-hidden');
        }
    }

    function hideElement(element) {
        if (element) {
            element.classList.add('assistant-hidden');
        }
    }

    function scrollThreadToBottom() {
        assistantThread.scrollTop = assistantThread.scrollHeight;
    }

    function formatDuration(seconds) {
        const mins = String(Math.floor(seconds / 60)).padStart(2, '0');
        const secs = String(seconds % 60).padStart(2, '0');
        return mins + ':' + secs;
    }

    function appendMessage(role, html) {
        const article = document.createElement('article');
        article.className = 'assistant-message ' + (role === 'user' ? 'assistant-message-user' : 'assistant-message-ai');
        article.innerHTML =
            '<div class="assistant-avatar">' + (role === 'user' ? 'You' : 'AI') + '</div>' +
            '<div class="assistant-bubble">' + html + '</div>';
        assistantThread.appendChild(article);
        scrollThreadToBottom();
    }

    function setAttachmentSummary(message, isError) {
        attachmentSummary.textContent = message;
        attachmentSummary.classList.toggle('assistant-error', Boolean(isError));
    }

    function resetRecordingUI() {
        hideElement(recordingIndicator);
        micRecordBtn.classList.remove('assistant-icon-btn-recording');
        micRecordBtn.textContent = '🎤';
        if (recordingIntervalId) {
            window.clearInterval(recordingIntervalId);
            recordingIntervalId = null;
        }
        if (recordingTimer) {
            recordingTimer.textContent = '00:00';
        }
    }

    function startRecordingTimer() {
        recordingStartedAt = Date.now();
        showElement(recordingIndicator);
        recordingIntervalId = window.setInterval(function() {
            const elapsedSeconds = Math.floor((Date.now() - recordingStartedAt) / 1000);
            recordingTimer.textContent = formatDuration(elapsedSeconds);
        }, 250);
    }

    function showTranscriptPreview(transcript, sourceLabel) {
        currentTranscript = transcript;
        transcriptPreviewText.textContent = transcript;
        showElement(transcriptPreviewCard);
        appendMessage(
            'assistant',
            '<p><strong>Transcripción lista.</strong> Ya completé el formulario con esta lectura.</p>' +
            '<p class="assistant-inline-note">Fuente: ' + escapeHtml(sourceLabel) + '</p>'
        );
    }

    function handleParsedDraft(draft) {
        const payload = draft && draft.draft ? draft : { draft: draft };

        appendMessage(
            'assistant',
            '<p><strong>Formulario completado.</strong> Revisá payer, participantes y montos por persona antes de guardar.</p>'
        );
        applyDraftToExpenseForm(payload.draft || {});

        if (
            payload.ticket_assignment &&
            window.splitiaReceiptBridge &&
            typeof window.splitiaReceiptBridge.applyTicketAssignment === 'function'
        ) {
            window.splitiaReceiptBridge.applyTicketAssignment(payload.ticket_assignment);
        }
    }

    function applyDraftToExpenseForm(draft) {
        const descriptionInput = document.getElementById('description');
        const totalAmountInput = document.getElementById('total_amount');
        const payerSelect = document.getElementById('payer_id');
        const expenseDateInput = document.getElementById('expense_date');
        const participantCheckboxes = document.querySelectorAll('input[name^="participant_"]');
        const totalHint = document.getElementById('draft-total-hint');
        const payerHint = document.getElementById('draft-payer-hint');
        const participantHint = document.getElementById('draft-participant-hint');
        const shareSumHint = document.getElementById('draft-share-sum-hint');

        if (descriptionInput && draft.description) {
            descriptionInput.value = draft.description;
        }

        if (totalAmountInput && typeof draft.total_amount === 'number') {
            totalAmountInput.value = draft.total_amount;
            if (totalHint) {
                totalHint.textContent = draft.expense_date
                    ? 'Fecha detectada: ' + draft.expense_date
                    : 'Monto en pesos detectado automáticamente.';
            }
        }

        if (expenseDateInput && draft.expense_date) {
            expenseDateInput.value = draft.expense_date;
        }

        if (payerSelect && draft.payer_name) {
            let payerMatched = false;

            Array.from(payerSelect.options).forEach(option => {
                option.selected = false;
                if (option.text.trim().toLowerCase() === draft.payer_name.trim().toLowerCase()) {
                    option.selected = true;
                    payerMatched = true;
                }
            });

            if (payerHint) {
                payerHint.textContent = payerMatched
                    ? 'Draft payer matched automatically.'
                    : 'Draft payer "' + draft.payer_name + '" was not matched to a member yet.';
            }
        }

        if (participantCheckboxes.length > 0 && Array.isArray(draft.participants)) {
            const participantMap = {};
            draft.participants.forEach(function(participant) {
                participantMap[participant.name.toLowerCase()] = Number(participant.amount || 0);
            });

            participantCheckboxes.forEach(function(checkbox) {
                const label = document.querySelector('label[for="' + checkbox.id + '"]');
                const checkboxName = label ? label.textContent.trim().toLowerCase() : '';
                const isSelected = Object.prototype.hasOwnProperty.call(participantMap, checkboxName);
                const shareInput = document.getElementById('share_amount_' + checkbox.id.replace('participant_', ''));

                checkbox.checked = isSelected;
                if (shareInput) {
                    shareInput.disabled = !isSelected;
                    shareInput.value = isSelected ? participantMap[checkboxName].toFixed(2) : '';
                    shareInput.dataset.manual = isSelected ? 'true' : 'false';
                }
            });

            if (participantHint) {
                if (draft.participants.length > 0) {
                    participantHint.textContent = 'Draft split: ' + draft.participants.map(function(participant) {
                        return participant.name + ': $' + Number(participant.amount || 0).toFixed(2);
                    }).join(' | ');
                } else {
                    participantHint.textContent = 'Draft did not detect participants. Please select them manually.';
                }
            }

            if (shareSumHint) {
                const sum = draft.participants.reduce(function(total, participant) {
                    return total + Number(participant.amount || 0);
                }, 0);
                shareSumHint.textContent = 'Montos sugeridos por persona: $' + sum.toFixed(2);
                shareSumHint.classList.remove('assistant-error');
            }
        }

        if (totalAmountInput) {
            totalAmountInput.dispatchEvent(new Event('input', { bubbles: true }));
        }
    }

    async function requestTranscriptFromAudio(file) {
        const formData = new FormData();
        formData.append('audio', file);

        const response = await fetch('/api/audio/transcribe', {
            method: 'POST',
            body: formData
        });

        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.error || 'Audio transcription failed');
        }

        return payload;
    }

    async function requestDraftFromTranscript(transcript) {
        const requestBody = {
            transcript: transcript,
            group_members: getCurrentGroupMembers(),
            narrator_name: getCurrentNarratorHint()
        };

        if (
            window.splitiaReceiptBridge &&
            typeof window.splitiaReceiptBridge.getTicketContext === 'function'
        ) {
            const ticketContext = window.splitiaReceiptBridge.getTicketContext();
            if (ticketContext) {
                Object.assign(requestBody, ticketContext);
            }
        }

        const response = await fetch('/api/audio/parse', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });

        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.error || 'Transcript parsing failed');
        }

        return payload;
    }

    async function handleAudioFile(file, originLabel) {
        appendMessage(
            'user',
            '<p><strong>' + escapeHtml(originLabel) + '</strong></p><p class="assistant-inline-note">' +
            escapeHtml(file.name || 'audio.webm') + '</p>'
        );
        setAttachmentSummary('Transcribiendo audio...', false);

        try {
            const payload = await requestTranscriptFromAudio(file);
            currentTranscriptSource = payload.source || 'audio';
            showTranscriptPreview(payload.transcript, currentTranscriptSource);
            setAttachmentSummary('Audio transcripto. Completando el formulario automáticamente...', false);
            const draft = await requestDraftFromTranscript(payload.transcript);
            handleParsedDraft(draft);
            setAttachmentSummary('Formulario autocompletado desde el audio. Ajustalo si hace falta.', false);
        } catch (error) {
            setAttachmentSummary(error.message, true);
            appendMessage('assistant', '<p>No pude transcribir ese audio. Probá con otro archivo o escribilo manualmente.</p>');
        }
    }

    async function toggleRecording() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) {
            setAttachmentSummary('Este navegador no soporta grabación desde micrófono. Subí un audio o escribilo manualmente.', true);
            return;
        }

        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
            return;
        }

        try {
            recordingStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            recordedChunks = [];
            const recordingFormat = getRecordingFormat();
            mediaRecorder = recordingFormat.mimeType
                ? new MediaRecorder(recordingStream, { mimeType: recordingFormat.mimeType })
                : new MediaRecorder(recordingStream);

            mediaRecorder.addEventListener('dataavailable', function(event) {
                if (event.data && event.data.size > 0) {
                    recordedChunks.push(event.data);
                }
            });

            mediaRecorder.addEventListener('stop', async function() {
                resetRecordingUI();
                if (recordingStream) {
                    recordingStream.getTracks().forEach(function(track) {
                        track.stop();
                    });
                }

                if (!recordedChunks.length) {
                    setAttachmentSummary('La grabación salió vacía. Probá de nuevo o subí un audio manualmente.', true);
                    appendMessage('assistant', '<p>No pude leer nada del audio grabado. Probá otra vez o usá "Subir audio".</p>');
                    return;
                }

                const audioBlob = new Blob(recordedChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
                const fileExtension = recordingFormat.extension || 'webm';
                const recordedAudioFile = new File([audioBlob], 'splitia-recording.' + fileExtension, {
                    type: audioBlob.type || 'audio/webm'
                });

                await handleAudioFile(recordedAudioFile, 'Audio grabado');
            });

            mediaRecorder.start(250);
            micRecordBtn.classList.add('assistant-icon-btn-recording');
            micRecordBtn.textContent = '■';
            setAttachmentSummary(
                'Grabando audio en ' + ((mediaRecorder.mimeType || recordingFormat.mimeType || 'formato automático')) +
                '... contame quién pagó y quiénes participaron.',
                false
            );
            startRecordingTimer();
        } catch (_error) {
            resetRecordingUI();
            setAttachmentSummary('No pude acceder al micrófono. Revisá los permisos del navegador.', true);
        }
    }

    composerSendBtn.addEventListener('click', function() {
        const text = composerInput.value.trim();
        if (!text) {
            setAttachmentSummary('Escribí algo o usá el micrófono para arrancar.', true);
            return;
        }

        appendMessage('user', '<p>' + escapeHtml(text) + '</p>');
        composerInput.value = '';
        currentTranscriptSource = 'typed';
        showTranscriptPreview(text, 'texto manual');
        setAttachmentSummary('Texto recibido. Completando el formulario automáticamente...', false);
        requestDraftFromTranscript(text)
            .then(function(draft) {
                handleParsedDraft(draft);
                setAttachmentSummary('Formulario autocompletado desde el texto. Ajustalo si hace falta.', false);
            })
            .catch(function(error) {
                setAttachmentSummary(error.message, true);
                appendMessage('assistant', '<p>No pude estructurar ese texto. Probá escribirlo más explícito.</p>');
            });
    });

    composerInput.addEventListener('keydown', function(event) {
        if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
            composerSendBtn.click();
        }
    });

    micRecordBtn.addEventListener('click', toggleRecording);
    recordOptionBtn.addEventListener('click', toggleRecording);

    uploadAudioBtn.addEventListener('click', function() {
        audioFileInput.click();
    });

    if (uploadTicketBtn && receiptInput) {
        uploadTicketBtn.addEventListener('click', function() {
            receiptInput.click();
        });
    }

    audioFileInput.addEventListener('change', function() {
        const selectedFile = audioFileInput.files && audioFileInput.files[0];
        if (!selectedFile) {
            return;
        }
        handleAudioFile(selectedFile, 'Audio subido');
        audioFileInput.value = '';
    });

    if (receiptInput) {
        receiptInput.addEventListener('change', function() {
            const ticketFile = receiptInput.files && receiptInput.files[0];
            if (!ticketFile) {
                setAttachmentSummary('No se seleccionó ningún ticket.', false);
                return;
            }

            appendMessage(
                'user',
                '<p><strong>Ticket adjunto</strong></p><p class="assistant-inline-note">' + escapeHtml(ticketFile.name) + '</p>'
            );
            setAttachmentSummary('Ticket recibido. Extrayendo borrador para revisar items...', false);
            scrollThreadToBottom();
        });
    }
});

document.addEventListener('DOMContentLoaded', function() {
    const reviewCard = document.getElementById('receipt-review-card');
    const reviewForm = document.getElementById('receipt-review-form');
    const receiptInput = document.getElementById('receipt_image');
    const attachmentSummary = document.getElementById('attachment-summary');
    const assistantThread = document.getElementById('assistant-thread');
    const itemsContainer = document.getElementById('receipt-items');
    const itemsEmpty = document.getElementById('receipt-items-empty');
    const addItemButton = document.getElementById('receipt-add-item');
    const resetButton = document.getElementById('receipt-reset-btn');
    const membersDataElement = document.getElementById('receipt-members-data');
    const reviewDataElement = document.getElementById('receipt-review-data');
    const descriptionInput = document.getElementById('description');
    const totalAmountInput = document.getElementById('total_amount');
    const expenseDateInput = document.getElementById('expense_date');
    const totalHint = document.getElementById('draft-total-hint');
    const participantHint = document.getElementById('draft-participant-hint');
    const shareSumHint = document.getElementById('draft-share-sum-hint');

    if (
        !reviewCard ||
        !reviewForm ||
        !receiptInput ||
        !itemsContainer ||
        !itemsEmpty ||
        !addItemButton ||
        !resetButton ||
        !membersDataElement ||
        !reviewDataElement ||
        !descriptionInput ||
        !totalAmountInput ||
        !expenseDateInput
    ) {
        return;
    }

    const members = JSON.parse(membersDataElement.textContent || '[]');
    const initialReviewState = JSON.parse(reviewDataElement.textContent || '{}');
    const todayIso = new Date().toLocaleDateString('en-CA');
    let shareOverrideByMemberId = null;
    let applyingTicketAssignment = false;

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function appendAssistantMessage(html) {
        if (!assistantThread) {
            return;
        }

        const article = document.createElement('article');
        article.className = 'assistant-message assistant-message-ai';
        article.innerHTML =
            '<div class="assistant-avatar">AI</div>' +
            '<div class="assistant-bubble">' + html + '</div>';
        assistantThread.appendChild(article);
        assistantThread.scrollTop = assistantThread.scrollHeight;
    }

    function setAttachmentSummary(message, isError) {
        if (!attachmentSummary) {
            return;
        }
        attachmentSummary.textContent = message;
        attachmentSummary.classList.toggle('assistant-error', Boolean(isError));
    }

    function memberOptions(selectedValue) {
        const placeholder = '<option value="">Assign participant</option>';
        return placeholder + members.map(function(member) {
            const selected = String(selectedValue || '') === String(member.id) ? ' selected' : '';
            return '<option value="' + member.id + '"' + selected + '>' + escapeHtml(member.name) + '</option>';
        }).join('');
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

    function normalizeMatchText(value) {
        return String(value || '')
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLowerCase()
            .replace(/[^a-z0-9\s]/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
    }

    function clearShareOverride() {
        shareOverrideByMemberId = null;
    }

    function memberIdByName(name) {
        const normalized = normalizeMatchText(name);
        const match = members.find(function(member) {
            return normalizeMatchText(member.name) === normalized;
        });
        return match ? String(match.id) : '';
    }

    function getTicketContext() {
        const activeRows = Array.from(itemsContainer.querySelectorAll('.receipt-item-row'));
        if (!activeRows.length || reviewCard.classList.contains('assistant-hidden')) {
            return null;
        }

        const ticketItems = activeRows
            .map(function(row) {
                const enabled = row.querySelector('input[name="item_enabled[]"]').value !== '0';
                if (!enabled) {
                    return null;
                }
                return {
                    name: row.querySelector('input[name="item_name[]"]').value,
                    amount: row.querySelector('input[name="item_amount[]"]').value,
                };
            })
            .filter(Boolean);

        if (!ticketItems.length) {
            return null;
        }

        return {
            ticket_items: ticketItems,
            ticket_total: document.getElementById('receipt_total_amount').value,
            ticket_tax_amount: document.getElementById('tax_amount').value,
            ticket_tip_amount: document.getElementById('tip_amount').value,
            ticket_merchant_name: document.getElementById('merchant_name').value,
            ticket_expense_date: document.getElementById('receipt_expense_date').value,
        };
    }

    function createItemRow(item) {
        const row = document.createElement('div');
        row.className = 'receipt-item-row';
        row.dataset.assignmentMode = item.assignment_mode || 'auto';
        row.innerHTML =
            '<div class="form-group">' +
                '<label>Item name</label>' +
                '<input type="text" name="item_name[]" value="' + escapeHtml(item.name || '') + '"' + (item.enabled === false ? '' : ' required') + '>' +
            '</div>' +
            '<div class="form-group">' +
                '<label>Amount ($)</label>' +
                '<input type="number" name="item_amount[]" min="0" step="0.01" value="' + escapeHtml(item.amount || '') + '"' + (item.enabled === false ? '' : ' required') + '>' +
            '</div>' +
            '<div class="form-group">' +
                '<label>Assigned to</label>' +
                '<select name="item_user_id[]"' + (item.enabled === false ? '' : ' required') + '>' + memberOptions(item.assigned_user_id) + '</select>' +
            '</div>' +
            '<div class="receipt-row-actions">' +
                '<label class="receipt-item-toggle">' +
                    '<input type="checkbox" class="receipt-item-enabled"' + (item.enabled === false ? '' : ' checked') + '>' +
                    '<span>Keep item</span>' +
                '</label>' +
                '<input type="hidden" name="item_enabled[]" value="' + (item.enabled === false ? '0' : '1') + '">' +
                '<button type="button" class="btn btn-outline btn-small receipt-remove-item">Delete</button>' +
            '</div>';

        function syncEnabledState() {
            const enabledCheckbox = row.querySelector('.receipt-item-enabled');
            const enabled = enabledCheckbox.checked;
            row.classList.toggle('is-disabled', !enabled);
            row.querySelector('input[name="item_enabled[]"]').value = enabled ? '1' : '0';
            row.querySelectorAll('input[name="item_name[]"], input[name="item_amount[]"], select[name="item_user_id[]"]').forEach(function(field) {
                field.disabled = !enabled;
                field.required = enabled;
            });
            updateShareSummary();
        }

        row.querySelector('.receipt-remove-item').addEventListener('click', function() {
            row.remove();
            updateItemsEmptyState();
            updateShareSummary();
        });

        row.querySelectorAll('input, select').forEach(function(field) {
            if (field.name === 'item_user_id[]') {
                field.addEventListener('change', function() {
                    if (!applyingTicketAssignment) {
                        row.dataset.assignmentMode = 'manual';
                        clearShareOverride();
                    }
                });
            } else if (!applyingTicketAssignment) {
                field.addEventListener('input', clearShareOverride);
                field.addEventListener('change', clearShareOverride);
            }
            field.addEventListener('input', updateShareSummary);
            field.addEventListener('change', updateShareSummary);
        });
        row.querySelector('.receipt-item-enabled').addEventListener('change', syncEnabledState);

        itemsContainer.appendChild(row);
        syncEnabledState();
        updateItemsEmptyState();
    }

    function updateItemsEmptyState() {
        itemsEmpty.style.display = itemsContainer.children.length ? 'none' : 'block';
    }

    function allocateEvenSplit(shareCents, participantIds, amountCents) {
        if (!participantIds.length || amountCents <= 0) {
            return;
        }

        const sorted = participantIds.slice().sort(function(a, b) {
            return a - b;
        });
        const base = Math.floor(amountCents / sorted.length);
        const remainder = amountCents % sorted.length;
        sorted.forEach(function(userId, index) {
            shareCents[userId] = (shareCents[userId] || 0) + base + (index < remainder ? 1 : 0);
        });
    }

    function syncMainForm(shareCents, merchantName, totalAmount, expenseDate) {
        const participantCheckboxes = Array.from(document.querySelectorAll('input[name^="participant_"]'));

        descriptionInput.value = merchantName || 'Ticket';
        totalAmountInput.value = totalAmount || '';
        expenseDateInput.value = expenseDate || todayIso;

        if (totalHint) {
            totalHint.textContent = expenseDateInput.value
                ? 'Fecha detectada: ' + expenseDateInput.value
                : 'Monto extraído del ticket.';
        }

        participantCheckboxes.forEach(function(checkbox) {
            const memberId = checkbox.id.replace('participant_', '');
            const shareInput = document.getElementById('share_amount_' + memberId);
            const cents = shareCents[memberId] || 0;
            const isActive = cents > 0;

            checkbox.checked = isActive;
            if (shareInput) {
                shareInput.disabled = !isActive;
                shareInput.value = isActive ? fromCents(cents) : '';
                shareInput.dataset.manual = isActive ? 'true' : 'false';
            }
        });

        if (participantHint) {
            const summary = members
                .filter(function(member) { return (shareCents[member.id] || 0) > 0; })
                .map(function(member) {
                    return member.name + ': $' + fromCents(shareCents[member.id]);
                });
            participantHint.textContent = summary.length
                ? 'Ticket split: ' + summary.join(' | ')
                : 'Activá a cada persona y ajustá cuánto debe cada una.';
        }

        if (shareSumHint) {
            const totalCents = Object.values(shareCents).reduce(function(sum, cents) {
                return sum + cents;
            }, 0);
            shareSumHint.textContent = 'Montos por persona desde ticket: $' + fromCents(totalCents);
            shareSumHint.classList.remove('assistant-error');
        }

        totalAmountInput.dispatchEvent(new Event('input', { bubbles: true }));
    }

    function updateShareSummary() {
        const shareCents = {};
        members.forEach(function(member) {
            shareCents[member.id] = 0;
        });

        if (shareOverrideByMemberId) {
            Object.keys(shareOverrideByMemberId).forEach(function(memberId) {
                shareCents[memberId] = shareOverrideByMemberId[memberId] || 0;
            });

            syncMainForm(
                shareCents,
                document.getElementById('merchant_name').value,
                document.getElementById('receipt_total_amount').value,
                document.getElementById('receipt_expense_date').value
            );
            return;
        }

        Array.from(itemsContainer.querySelectorAll('.receipt-item-row')).forEach(function(row) {
            const enabled = row.querySelector('input[name="item_enabled[]"]').value !== '0';
            if (!enabled) {
                return;
            }

            const amount = toCents(row.querySelector('input[name="item_amount[]"]').value);
            const userId = Number.parseInt(row.querySelector('select[name="item_user_id[]"]').value, 10);
            if (Number.isInteger(userId)) {
                shareCents[userId] = (shareCents[userId] || 0) + amount;
            }
        });

        const activeParticipantIds = members
            .map(function(member) { return member.id; })
            .filter(function(memberId) { return (shareCents[memberId] || 0) > 0; });

        allocateEvenSplit(shareCents, activeParticipantIds, toCents(document.getElementById('tax_amount').value));
        allocateEvenSplit(shareCents, activeParticipantIds, toCents(document.getElementById('tip_amount').value));

        syncMainForm(
            shareCents,
            document.getElementById('merchant_name').value,
            document.getElementById('receipt_total_amount').value,
            document.getElementById('receipt_expense_date').value
        );
    }

    function applyTicketAssignment(ticketAssignment) {
        if (!ticketAssignment || !Array.isArray(ticketAssignment.item_assignments)) {
            return;
        }

        const rows = Array.from(itemsContainer.querySelectorAll('.receipt-item-row'));
        const override = {};
        members.forEach(function(member) {
            override[String(member.id)] = 0;
        });

        Object.entries(ticketAssignment.share_amounts_by_user_name || {}).forEach(function(entry) {
            const memberId = memberIdByName(entry[0]);
            const amount = Number.parseFloat(entry[1] || 0);
            if (memberId && Number.isFinite(amount) && amount > 0) {
                override[memberId] = Math.round(amount * 100);
            }
        });

        applyingTicketAssignment = true;
        try {
            ticketAssignment.item_assignments.forEach(function(assignment) {
                const row = rows[assignment.item_index];
                if (!row || row.dataset.assignmentMode === 'manual') {
                    return;
                }

                const select = row.querySelector('select[name="item_user_id[]"]');
                const memberId = memberIdByName(assignment.assigned_user_name);
                if (!select || !memberId) {
                    return;
                }

                select.value = memberId;
                row.dataset.assignmentMode = 'auto';
            });
        } finally {
            applyingTicketAssignment = false;
        }

        shareOverrideByMemberId = override;
        updateShareSummary();

        const assignedCount = ticketAssignment.item_assignments.length;
        const unmatchedCount = (ticketAssignment.unmatched_audio_mentions || []).length;
        setAttachmentSummary(
            'Audio aplicado sobre ticket. ' + assignedCount + ' item(s) asignados' +
            (unmatchedCount ? ', ' + unmatchedCount + ' mención(es) quedaron en remanente.' : '.'),
            false
        );
        appendAssistantMessage(
            '<p><strong>Audio aplicado sobre el ticket.</strong> ' +
            assignedCount + ' item(s) quedaron asignados y el resto se repartió automáticamente.</p>'
        );
    }

    function setReviewState(state) {
        reviewCard.classList.remove('assistant-hidden');
        clearShareOverride();

        setFieldValue('merchant_name', state.merchant_name || '');
        setFieldValue('subtotal_amount', state.subtotal_amount || '');
        setFieldValue('tax_amount', state.tax_amount || '');
        setFieldValue('tip_amount', state.tip_amount || '');
        setFieldValue('receipt_total_amount', state.total_amount || '');
        setFieldValue('receipt_expense_date', state.expense_date || todayIso);

        itemsContainer.innerHTML = '';
        const items = Array.isArray(state.items) && state.items.length
            ? state.items
            : (Array.isArray(state.extracted_items) ? state.extracted_items : []);

        items.forEach(function(item) {
            createItemRow({
                name: item.name || '',
                amount: item.amount != null ? item.amount : '',
                assigned_user_id: item.assigned_user_id || '',
                enabled: item.enabled !== false,
            });
        });

        reviewForm.querySelectorAll(
            '#merchant_name, #subtotal_amount, #tax_amount, #tip_amount, #receipt_total_amount, #receipt_expense_date'
        ).forEach(function(field) {
            field.addEventListener('input', updateShareSummary);
            field.addEventListener('change', updateShareSummary);
        });

        updateItemsEmptyState();
        updateShareSummary();
    }

    async function requestReceiptDraft(file) {
        const formData = new FormData();
        formData.append('receipt_image', file);

        const response = await fetch('/api/receipt/draft', {
            method: 'POST',
            body: formData
        });

        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.error || 'Could not extract receipt draft.');
        }

        return payload;
    }

    receiptInput.addEventListener('change', function() {
        const file = receiptInput.files && receiptInput.files[0];
        if (!file) {
            return;
        }

        requestReceiptDraft(file)
            .then(function(payload) {
                setReviewState(payload);
                setAttachmentSummary('Ticket leído. Revisá merchant, total e items antes de guardar.', false);
                appendAssistantMessage('<p><strong>Ticket procesado.</strong> Completé el formulario principal y dejé los items listos para revisar.</p>');
            })
            .catch(function(error) {
                setAttachmentSummary(error.message || 'No pudimos extraer el ticket.', true);
                appendAssistantMessage('<p>No pude extraer un borrador usable del ticket. Probá con otra foto o cargá el gasto manualmente.</p>');
            })
            .finally(function() {
                receiptInput.value = '';
            });
    });

    addItemButton.addEventListener('click', function() {
        createItemRow({ name: '', amount: '', assigned_user_id: '', enabled: true });
        updateShareSummary();
    });

    resetButton.addEventListener('click', function() {
        reviewCard.classList.add('assistant-hidden');
        itemsContainer.innerHTML = '';
        clearShareOverride();
        reviewForm.querySelectorAll('input').forEach(function(input) {
            input.value = '';
        });
        setFieldValue('receipt_expense_date', todayIso);
        updateItemsEmptyState();
        updateShareSummary();
        setAttachmentSummary('Borrador del ticket descartado. Podés subir otro o seguir con carga manual.', false);
    });

    window.splitiaReceiptBridge = {
        getTicketContext: getTicketContext,
        applyTicketAssignment: applyTicketAssignment,
    };

    if (initialReviewState && Array.isArray(initialReviewState.items) && initialReviewState.items.length) {
        setReviewState(initialReviewState);
    } else {
        setFieldValue('receipt_expense_date', todayIso);
        updateShareSummary();
    }
});
