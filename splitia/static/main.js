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
        !receiptInput ||
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

    uploadTicketBtn.addEventListener('click', function() {
        receiptInput.click();
    });

    audioFileInput.addEventListener('change', function() {
        const selectedFile = audioFileInput.files && audioFileInput.files[0];
        if (!selectedFile) {
            return;
        }
        handleAudioFile(selectedFile, 'Audio subido');
        audioFileInput.value = '';
    });

    receiptInput.addEventListener('change', function() {
        const ticketFile = receiptInput.files && receiptInput.files[0];
        if (!ticketFile) {
            setAttachmentSummary('El ticket es opcional y solo queda como referencia visual por ahora.', false);
            return;
        }

        appendMessage(
            'user',
            '<p><strong>Ticket adjunto</strong></p><p class="assistant-inline-note">' + escapeHtml(ticketFile.name) + '</p>'
        );
        setAttachmentSummary('Ticket adjunto como referencia. Ahora podés escribir o grabar el audio igual que antes.', false);
        scrollThreadToBottom();
    });
});
