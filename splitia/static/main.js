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
    const writeOptionBtn = document.getElementById('write-option-btn');
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
        appendMessage(
            'assistant',
            '<p><strong>Formulario completado.</strong> Revisá payer, participantes y montos por persona antes de guardar.</p>'
        );
        applyDraftToExpenseForm(draft);
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
                totalHint.textContent = 'Draft currency: ' + (draft.currency || 'ARS') + (draft.expense_date ? ' | Fecha detectada: ' + draft.expense_date : '');
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
        const response = await fetch('/api/audio/parse', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                transcript: transcript,
                group_members: getCurrentGroupMembers(),
                narrator_name: getCurrentNarratorHint()
            })
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

    writeOptionBtn.addEventListener('click', function() {
        composerInput.focus();
        setAttachmentSummary('Escribí el gasto como en un chat. Lo vamos a estructurar y volcar directo al formulario.', false);
    });

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
    const shareSummary = document.getElementById('receipt-share-summary');
    const taxParticipants = document.getElementById('tax-participants');
    const tipParticipants = document.getElementById('tip-participants');
    const membersDataElement = document.getElementById('receipt-members-data');
    const reviewDataElement = document.getElementById('receipt-review-data');

    if (
        !reviewCard ||
        !reviewForm ||
        !receiptInput ||
        !itemsContainer ||
        !itemsEmpty ||
        !addItemButton ||
        !resetButton ||
        !shareSummary ||
        !taxParticipants ||
        !tipParticipants ||
        !membersDataElement ||
        !reviewDataElement
    ) {
        return;
    }

    const members = JSON.parse(membersDataElement.textContent || '[]');
    const initialReviewState = JSON.parse(reviewDataElement.textContent || '{}');

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

    function renderParticipantCheckboxes(container, fieldName, selectedIds) {
        container.innerHTML = members.map(function(member) {
            const checked = selectedIds.includes(String(member.id)) ? ' checked' : '';
            return (
                '<label class="receipt-member-check">' +
                    '<input type="checkbox" name="' + fieldName + '" value="' + member.id + '"' + checked + '>' +
                    '<span>' + escapeHtml(member.name) + '</span>' +
                '</label>'
            );
        }).join('');
    }

    function createItemRow(item) {
        const row = document.createElement('div');
        row.className = 'receipt-item-row';
        row.innerHTML =
            '<div class="form-group">' +
                '<label>Item name</label>' +
                '<input type="text" name="item_name[]" value="' + escapeHtml(item.name || '') + '"' + (item.enabled === false ? '' : ' required') + '>' +
            '</div>' +
            '<div class="form-group">' +
                '<label>Amount</label>' +
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

    function collectSelectedParticipantIds(fieldName) {
        return Array.from(reviewForm.querySelectorAll('input[name="' + fieldName + '"]:checked'))
            .map(function(input) {
                return Number.parseInt(input.value, 10);
            })
            .filter(Number.isInteger);
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

    function updateShareSummary() {
        const shareCents = {};
        members.forEach(function(member) {
            shareCents[member.id] = 0;
        });

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

        allocateEvenSplit(shareCents, collectSelectedParticipantIds('tax_split_participants'), toCents(document.getElementById('tax_amount').value));
        allocateEvenSplit(shareCents, collectSelectedParticipantIds('tip_split_participants'), toCents(document.getElementById('tip_amount').value));

        const rows = members
            .map(function(member) {
                return { member: member, cents: shareCents[member.id] || 0 };
            })
            .filter(function(entry) {
                return entry.cents > 0;
            });

        const totalPreview = rows.reduce(function(sum, entry) {
            return sum + entry.cents;
        }, 0);
        const targetTotal = toCents(document.getElementById('receipt_total_amount').value);

        if (!rows.length) {
            shareSummary.innerHTML = '<div class="receipt-summary-row is-muted"><span>No assigned shares yet.</span><span>$0.00</span></div>';
            return;
        }

        shareSummary.innerHTML = rows.map(function(entry) {
            return (
                '<div class="receipt-summary-row">' +
                    '<span>' + escapeHtml(entry.member.name) + '</span>' +
                    '<span>$' + fromCents(entry.cents) + '</span>' +
                '</div>'
            );
        }).join('') +
            '<div class="receipt-summary-row is-muted"><span>Computed total</span><span>$' + fromCents(totalPreview) + '</span></div>' +
            '<div class="receipt-summary-row is-muted"><span>Reviewed total</span><span>$' + fromCents(targetTotal) + '</span></div>';
    }

    function setReviewState(state) {
        reviewCard.classList.remove('assistant-hidden');

        setFieldValue('receipt_description', state.description || '');
        setFieldValue('merchant_name', state.merchant_name || '');
        setFieldValue('currency', state.currency || 'ARS');
        setFieldValue('confidence', state.confidence || '');
        setFieldValue('subtotal_amount', state.subtotal_amount || '');
        setFieldValue('tax_amount', state.tax_amount || '');
        setFieldValue('tip_amount', state.tip_amount || '');
        setFieldValue('receipt_total_amount', state.total_amount || '');
        setFieldValue('notes', state.notes || '');
        setFieldValue('receipt_payer_id', state.payer_id || '');
        setFieldValue('receipt_expense_date', state.expense_date || '');

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

        renderParticipantCheckboxes(
            taxParticipants,
            'tax_split_participants',
            (state.selected_tax_participants || members.map(function(member) {
                return String(member.id);
            })).map(String)
        );
        renderParticipantCheckboxes(
            tipParticipants,
            'tip_split_participants',
            (state.selected_tip_participants || members.map(function(member) {
                return String(member.id);
            })).map(String)
        );

        reviewForm.querySelectorAll(
            '#tax-participants input, #tip-participants input, #receipt_description, #merchant_name, #currency, #confidence, #subtotal_amount, #tax_amount, #tip_amount, #receipt_total_amount, #receipt_payer_id, #receipt_expense_date, #notes'
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
                setAttachmentSummary('Borrador del ticket listo. Revisá items, tax y tip antes de guardar.', false);
                appendAssistantMessage('<p><strong>Borrador del ticket extraído.</strong> Ya podés revisar cada item y repartir el gasto exacto.</p>');
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
        reviewForm.reset();
        renderParticipantCheckboxes(
            taxParticipants,
            'tax_split_participants',
            members.map(function(member) { return String(member.id); })
        );
        renderParticipantCheckboxes(
            tipParticipants,
            'tip_split_participants',
            members.map(function(member) { return String(member.id); })
        );
        updateItemsEmptyState();
        updateShareSummary();
        setAttachmentSummary('Borrador del ticket descartado. Podés subir otro o seguir con carga manual.', false);
    });

    if (initialReviewState && Array.isArray(initialReviewState.items) && initialReviewState.items.length) {
        setReviewState(initialReviewState);
    } else {
        renderParticipantCheckboxes(
            taxParticipants,
            'tax_split_participants',
            members.map(function(member) { return String(member.id); })
        );
        renderParticipantCheckboxes(
            tipParticipants,
            'tip_split_participants',
            members.map(function(member) { return String(member.id); })
        );
        updateShareSummary();
    }
});
