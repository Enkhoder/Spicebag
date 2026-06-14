document.addEventListener("DOMContentLoaded", () => {
    // Tab Switching
    const navBtns = document.querySelectorAll(".nav-btn");
    const tabs = document.querySelectorAll(".tab-content");

    navBtns.forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.preventDefault();
            const targetId = btn.getAttribute("data-target");

            navBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");

            tabs.forEach(tab => {
                if (tab.id === targetId) {
                    tab.classList.remove("hidden");
                } else {
                    tab.classList.add("hidden");
                }
            });

            // Re-sync validation state when returning to encode tab
            if (targetId === 'encode-tab' && typeof resyncValidation === 'function') {
                resyncValidation();
            }
        });
    });

    // Scrolling Background Logic
    function updateBackgroundRows() {
        const container = document.querySelector('.scrolling-bg-container');
        if (!container) return;

        const rowHeight = 130;
        const targetRowCount = Math.ceil(window.innerHeight / rowHeight);
        const currentRowCount = container.children.length;

        if (targetRowCount > currentRowCount) {
            for (let i = currentRowCount; i < targetRowCount; i++) {
                const row = document.createElement('div');
                const directionClass = (i % 2 === 0) ? 'scroll-left' : 'scroll-right';
                row.className = `scroll-row ${directionClass}`;
                container.appendChild(row);
            }
        }

        else if (targetRowCount < currentRowCount) {
            for (let i = currentRowCount - 1; i >= targetRowCount; i--) {
                container.removeChild(container.children[i]);
            }
        }
    }

    updateBackgroundRows();
    window.addEventListener('resize', updateBackgroundRows);

    // Warning Banner Logic
    const understandBtn = document.getElementById("understandBtn");
    const warningBanner = document.getElementById("warningBanner");
    let warningTimeLeft = 3;

    if (understandBtn && warningBanner) {
        const warningInterval = setInterval(() => {
            warningTimeLeft--;
            if (warningTimeLeft > 0) {
                understandBtn.textContent = `I UNDERSTAND (${warningTimeLeft}s)`;
            } else {
                clearInterval(warningInterval);
                understandBtn.textContent = 'I UNDERSTAND';
                understandBtn.disabled = false;
            }
        }, 1000);

        understandBtn.addEventListener('click', () => {
            warningBanner.style.height = warningBanner.offsetHeight + 'px';
            void warningBanner.offsetHeight;
            warningBanner.classList.add('hidden-banner');
            setTimeout(() => { warningBanner.style.display = 'none'; }, 400); // Remove from DOM flow completely after anim
        });
    }

    // Bulk Mode Toggle
    const toggleBulk = document.getElementById("bulkToggle");
    const bulkCountGroup = document.getElementById("bulkCountGroup");
    const bulkToggleContainer = document.getElementById("bulkToggleContainer");

    toggleBulk.addEventListener("change", (e) => {
        if (e.target.checked) {
            bulkCountGroup.classList.add("expanded");
            bulkToggleContainer.classList.add("ticked");
        } else {
            bulkCountGroup.classList.remove("expanded");
            bulkToggleContainer.classList.remove("ticked");
        }
    });

    // Visibility Toggle logic for Salting fields (3s)
    const toggleBtns = document.querySelectorAll('.btn-toggle-vis:not(#toggleMnemonic)');
    const visibilityTimers = {};

    toggleBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.id.replace('toggle', '');
            const targetInput = document.getElementById(targetId.charAt(0).toLowerCase() + targetId.slice(1));

            if (!targetInput) return;

            const timerOverlay = btn.querySelector('.timer-overlay');

            if (visibilityTimers[targetInput.id]) {
                clearTimeout(visibilityTimers[targetInput.id]);
                visibilityTimers[targetInput.id] = null;
                targetInput.type = 'password';
                targetInput.classList.remove('visible-text');
                btn.classList.remove('is-visible');
                timerOverlay.classList.remove('active');
                return;
            }

            targetInput.type = 'text';
            targetInput.classList.add('visible-text');
            btn.classList.add('is-visible');
            timerOverlay.classList.remove('active');

            void timerOverlay.offsetWidth;
            timerOverlay.classList.add('active');

            const timeout = setTimeout(() => {
                targetInput.type = 'password';
                targetInput.classList.remove('visible-text');
                btn.classList.remove('is-visible');
                timerOverlay.classList.remove('active');
                visibilityTimers[targetInput.id] = null;
            }, 3000);

            visibilityTimers[targetInput.id] = timeout;
        });
    });

    // Seed Grid Logic with Overriding 3s Timers
    const seedGrid = document.getElementById('seedGrid');
    const mnemonicHidden = document.getElementById('mnemonicHidden');
    const toggleMnemonicBtn = document.getElementById('toggleMnemonic');
    let globalHideTime = 0;

    function updateHiddenMnemonic() {
        if (!seedGrid || !mnemonicHidden) return;
        const words = Array.from(seedGrid.querySelectorAll('input')).map(i => {
            if (i.dataset.masked === 'true') {
                return i.dataset.realValue || '';
            } else {
                return i.value.trim();
            }
        }).filter(w => w !== '');
        mnemonicHidden.value = words.join(' ');
    }

    function updateWordPlaceholders() {
        if (!seedGrid) return;
        const wrappers = seedGrid.querySelectorAll('.word-box-wrapper');
        wrappers.forEach((wrapper, index) => {
            const box = wrapper.querySelector('input.word-box-input');
            const badge = wrapper.querySelector('.word-box-index');
            const hasValue = box.dataset.masked === 'true'
                ? (box.dataset.realValue && box.dataset.realValue.trim().length > 0)
                : (box.value.trim().length > 0);

            if (box) box.placeholder = `Word #${index + 1}`;
            if (badge) {
                badge.textContent = `${index + 1}`;
                badge.style.display = hasValue ? 'block' : 'none';
            }
        });
    }

    function updateWordVisibility(input) {
        const now = Date.now();
        const isGlobalVisible = now < globalHideTime;
        const isHoveredOrFocused = input === document.activeElement || input.matches(':hover');
        const isVisible = isGlobalVisible || isHoveredOrFocused;

        if (isVisible) {
            if (input.dataset.masked === 'true') {
                input.dataset.masked = 'false';
                input.type = 'text';
                input.value = input.dataset.realValue || '';
                input.classList.add('visible-text');
                input.classList.remove('masked-input');
            }
        } else {
            if (input.dataset.masked !== 'true') {
                const currentVal = input.value;
                if (currentVal !== '********') {
                    input.dataset.realValue = currentVal;
                }
                input.dataset.masked = 'true';
                input.type = 'password';
                input.value = (input.dataset.realValue || '').length > 0 ? '********' : '';
                input.classList.remove('visible-text');
                input.classList.add('masked-input');
            }
        }
    }

    let heightTransitionTimer = null;
    function withSmoothGridHeight(action) {
        const grid = document.getElementById('seedGrid');
        if (!grid) return action();

        if (!grid.style.height || grid.style.height === 'auto') {
            grid.style.height = grid.offsetHeight + 'px';
            grid.style.transition = 'none';
        }

        action();
        clearTimeout(heightTransitionTimer);

        requestAnimationFrame(() => {
            const currentExplicit = grid.style.height;
            grid.style.height = 'auto';
            const targetHeight = grid.offsetHeight;
            grid.style.height = currentExplicit;
            
            void grid.offsetHeight; // reflow
            
            grid.style.transition = 'height 0.25s cubic-bezier(0.2, 0.8, 0.2, 1)';
            grid.style.height = targetHeight + 'px';
            
            heightTransitionTimer = setTimeout(() => {
                grid.style.height = 'auto';
                grid.style.transition = 'none';
            }, 250);
        });
    }

    function createWordBox(value = '', insertBeforeNode = null) {
        const wrapper = document.createElement('div');
        wrapper.className = 'word-box-wrapper appearing';
        setTimeout(() => wrapper.classList.remove('appearing'), 10);

        const input = document.createElement('input');
        input.type = 'password';
        input.className = 'word-box-input masked-input';
        input.dataset.masked = 'true';
        input.dataset.realValue = value;
        input.value = value.length > 0 ? '********' : '';

        // FIX: Unmask IMMEDIATELY on click so the cursor lands in the right spot
        input.addEventListener('mousedown', () => {
            if (input.dataset.masked === 'true') {
                input.dataset.masked = 'false';
                input.type = 'text';
                input.value = input.dataset.realValue || '';
                input.classList.add('visible-text');
                input.classList.remove('masked-input');
            }
        });

        input.addEventListener('mouseenter', () => updateWordVisibility(input));
        input.addEventListener('mouseleave', () => updateWordVisibility(input));
        input.addEventListener('focus', () => updateWordVisibility(input));
        input.addEventListener('blur', () => updateWordVisibility(input));

        const indexBadge = document.createElement('span');
        indexBadge.className = 'word-box-index';

        input.addEventListener('keydown', (e) => {
            const allWrappers = Array.from(seedGrid.querySelectorAll('.word-box-wrapper'));
            const currentIndex = allWrappers.indexOf(wrapper);

            if (e.key === ' ' || e.key === 'Enter') {
                e.preventDefault();
                const allWrappers = Array.from(seedGrid.querySelectorAll('.word-box-wrapper'));
                const currentIndex = allWrappers.indexOf(wrapper);
                const currentCount = allWrappers.length;

                // Validate the current word immediately on space/enter
                validateSpecificBox(wrapper);
                syncInvalidWordsDiagnostic();

                const nextNode = wrapper.nextElementSibling;
                const nextInput = nextNode ? nextNode.querySelector('input') : null;

                const realVal = (input.dataset.masked === 'true') ? (input.dataset.realValue || '') : input.value;
                const textLen = realVal.length;

                if (currentCount >= 33) {
                    if (nextInput) nextInput.focus();
                    return;
                }

                let cursorStart = textLen;
                let selEnd = textLen;
                try {
                    cursorStart = input.selectionStart ?? textLen;
                    selEnd = input.selectionEnd ?? textLen;
                } catch(err) {
                    // type='password' throws InvalidStateError on selectionStart
                }
                const isCursor = cursorStart === selEnd;

                if (textLen === 0) {
                    if (nextInput) {
                        if ((nextInput.dataset.realValue || nextInput.value) === '') {
                            nextInput.focus();
                        } else {
                            createWordBox('', nextNode);
                        }
                    }
                    return;
                }

                if (isCursor) {
                    if (cursorStart > 0 && cursorStart < textLen) {
                        const leftPart = realVal.substring(0, cursorStart);
                        const rightPart = realVal.substring(cursorStart);
                        input.value = leftPart;
                        input.dataset.realValue = leftPart;
                        input.dataset.masked = 'false';

                        createWordBox(rightPart, nextNode);
                        return;
                    }

                    if (cursorStart === 0) {
                        createWordBox('', wrapper);
                        return;
                    }

                    if (cursorStart >= textLen) {
                        const nextRealVal = nextInput
                            ? (nextInput.dataset.realValue || nextInput.value)
                            : '';
                        if (nextInput && nextRealVal === '') {
                            nextInput.focus();
                        } else {
                            createWordBox('', nextNode);
                        }
                        return;
                    }
                }
            } else if (e.key === 'Backspace' && (input.dataset.masked === 'true' ? input.dataset.realValue : input.value) === '') {
                e.preventDefault();
                if (wrapper.previousElementSibling) {
                    wrapper.previousElementSibling.querySelector('input').focus();
                    wrapper.classList.add('removing');
                    setTimeout(() => {
                        withSmoothGridHeight(() => {
                            wrapper.remove();
                        });
                        clearFullPhraseDiagnostics();
                        syncInvalidWordsDiagnostic();
                        updateHiddenMnemonic();
                        updateWordPlaceholders();
                    }, 200);
                }
            } else if (e.key === 'ArrowLeft') {
                if (input.selectionStart === 0 && currentIndex > 0) {
                    e.preventDefault();
                    const prevInput = allWrappers[currentIndex - 1].querySelector('input');
                    prevInput.focus();
                }
            } else if (e.key === 'ArrowRight') {
                if (input.selectionEnd === input.value.length && currentIndex < allWrappers.length - 1) {
                    e.preventDefault();
                    const nextInput = allWrappers[currentIndex + 1].querySelector('input');
                    nextInput.focus();

                    setTimeout(() => {
                        nextInput.setSelectionRange(0, 0);
                    }, 1);
                }
            } else if (e.key === 'ArrowUp') {
                if (currentIndex >= 6) {
                    e.preventDefault();
                    allWrappers[currentIndex - 6].querySelector('input').focus();
                }
            } else if (e.key === 'ArrowDown') {
                if (currentIndex + 6 < allWrappers.length) {
                    e.preventDefault();
                    allWrappers[currentIndex + 6].querySelector('input').focus();
                }
            }
        });

        input.addEventListener('paste', (e) => {
            const pasteData = (e.clipboardData || window.clipboardData).getData('text');
            e.preventDefault();

            const rawWords = pasteData.trim().split(/\s+/).filter(w => w !== '');
            if (rawWords.length === 0) return;

            const allWrappers = Array.from(seedGrid.querySelectorAll('.word-box-wrapper'));
            const currentWrapperIdx = allWrappers.indexOf(wrapper);
            const currentRealVal = (input.dataset.masked === 'true' ? input.dataset.realValue : input.value || '').trim();
            const currentIsEmpty = currentRealVal === '';

            // Determine where paste starts
            let targetIdx;
            if (rawWords.length === 1) {
                // Single word: always paste into current box
                input.value = rawWords[0];
                input.dataset.realValue = rawWords[0];
                input.dataset.masked = 'false';
                input.type = 'text';
                input.classList.remove('masked-input');
                input.classList.add('visible-text');
                updateHiddenMnemonic();
                updateWordPlaceholders();
                return;
            }

            if (currentIsEmpty || allWrappers.length >= 33) {
                // Paste at current box
                targetIdx = currentWrapperIdx;
            } else {
                // Box has content — start pasting at next box
                targetIdx = currentWrapperIdx + 1;
            }

            // Only trailing words that aren't empty get shifted
            const trailing = allWrappers.slice(targetIdx).map(w => {
                const inp = w.querySelector('input.word-box-input');
                return (inp.dataset.masked === 'true' ? (inp.dataset.realValue || '') : (inp.value || '')).trim();
            }).filter(v => v !== '');

            // Max words that can fit from targetIdx to box 33
            const maxSlots = 33 - targetIdx;

            // Preserve trailing words; cut paste to fit (never cut existing words)
            const trailingKeep = Math.min(trailing.length, maxSlots);
            const pasteSlots   = Math.max(0, maxSlots - trailingKeep);
            const pasteWords   = rawWords.slice(0, pasteSlots);
            const finalWords   = [...pasteWords, ...trailing.slice(0, trailingKeep)];

            withSmoothGridHeight(() => {
                // Remove boxes from targetIdx onward and recreate
                for (let i = allWrappers.length - 1; i >= targetIdx; i--) {
                    allWrappers[i].remove();
                }
                for (const word of finalWords) {
                    createWordBox(word);
                }
            });

            updateHiddenMnemonic();
            updateWordPlaceholders();

            // Focus the last pasted word and validate all pasted words
            setTimeout(() => {
                const boxes = seedGrid.querySelectorAll('.word-box-wrapper');
                const focusIdx = Math.min(targetIdx + pasteWords.length - 1, boxes.length - 1);
                if (focusIdx >= 0 && boxes[focusIdx]) {
                    boxes[focusIdx].querySelector('input').focus();
                }
                // Validate all words after paste
                for (let i = 0; i < boxes.length; i++) {
                    validateSpecificBox(boxes[i], false);
                }
                syncInvalidWordsDiagnostic();
            }, 10);
        });

        input.addEventListener('input', () => {
            if (input.dataset.masked !== 'true') {
                input.dataset.realValue = input.value;
            }
            const currentWord = ((input.dataset.masked === 'true') ? (input.dataset.realValue || '') : input.value).trim().toLowerCase();
            if (currentWord === '' || (wordlistSet.size > 0 && wordlistSet.has(currentWord))) {
               input.classList.remove('word-invalid');
            }
            input.classList.remove('word-valid'); // clear green glow on any edit
            // Clear "no seed phrase" as soon as any character is typed anywhere
            if (getAllWords().length > 0) {
                setDiagnostic('empty', null);
            }
            // Don't clear phrase-level diagnostics during typing —
            // they persist until re-validated on space/enter/generate.
            syncInvalidWordsDiagnostic();
            updateHiddenMnemonic();
            updateWordPlaceholders();
        });

        input.addEventListener('blur', () => {
            validateSpecificBox(wrapper, false);
            syncInvalidWordsDiagnostic();
        });

        wrapper.appendChild(input);
        wrapper.appendChild(indexBadge);

        withSmoothGridHeight(() => {
            if (insertBeforeNode) {
                seedGrid.insertBefore(wrapper, insertBeforeNode);
            } else {
                seedGrid.appendChild(wrapper);
            }
        });

        input.focus();
        updateHiddenMnemonic();
        updateWordPlaceholders();
        updateWordVisibility(input);
    }

    if (seedGrid) {
        createWordBox();
        // Initial state: button disabled until valid phrase is entered
        updateGenerateButtonState();
    }

    let globalTimer = null;
    if (toggleMnemonicBtn) {
        toggleMnemonicBtn.addEventListener('click', () => {
            const overlay = toggleMnemonicBtn.querySelector('.timer-overlay');

            if (globalHideTime > Date.now()) {
                globalHideTime = 0;
                clearTimeout(globalTimer);
                overlay.classList.remove('active');
                toggleMnemonicBtn.classList.remove('is-visible');
            } else {
                globalHideTime = Date.now() + 3000;
                toggleMnemonicBtn.classList.add('is-visible');
                overlay.classList.remove('active');
                void overlay.offsetWidth;
                overlay.classList.add('active');

                globalTimer = setTimeout(() => {
                    overlay.classList.remove('active');
                    toggleMnemonicBtn.classList.remove('is-visible');
                }, 3000);
            }

            seedGrid.querySelectorAll('.word-box-wrapper').forEach(wrapper => {
                updateWordVisibility(wrapper.querySelector('input'));
            });
        });
    }

    setInterval(() => {
        if (!seedGrid) return;
        seedGrid.querySelectorAll('.word-box-wrapper').forEach(wrapper => {
            updateWordVisibility(wrapper.querySelector('input'));
        });
    }, 100);

    // Image Preview
    const imageUpload = document.getElementById('imageUpload');
    const imagePreview = document.getElementById('imagePreview');
    const imageUploadPlaceholder = document.getElementById('imageUploadPlaceholder');

    if (imageUpload) {
        imageUpload.addEventListener('change', function () {
            const file = this.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function (e) {
                    imagePreview.src = e.target.result;
                    imagePreview.style.display = 'block';
                    imageUploadPlaceholder.style.display = 'none';
                }
                reader.readAsDataURL(file);
            } else {
                imagePreview.src = '';
                imagePreview.style.display = 'none';
                imageUploadPlaceholder.style.display = 'block';
            }
        });
    }

    // Number Inputs Logic
    const upBtns = document.querySelectorAll('.up-btn');
    const downBtns = document.querySelectorAll('.down-btn');

    // Strict integer-only inputs
    const integerInputs = document.querySelectorAll('#cellPx, #count');
    integerInputs.forEach(input => {
        // Block any non-numeric key (allow: digits, Backspace, Delete, arrows, Tab, Home, End)
        input.addEventListener('keydown', (e) => {
            const allowed = ['Backspace', 'Delete', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Tab', 'Home', 'End'];
            if (!allowed.includes(e.key) && !/^\d$/.test(e.key)) {
                e.preventDefault();
            }
        });

        // Block paste of non-numeric content
        input.addEventListener('paste', (e) => {
            const pasted = (e.clipboardData || window.clipboardData).getData('text');
            if (!/^\d+$/.test(pasted)) e.preventDefault();
        });

        // On blur: if value is empty, 0, or below min, silently reset to 1
        input.addEventListener('blur', () => {
            const val = parseInt(input.value, 10);
            const min = parseInt(input.min, 10) || 1;
            if (isNaN(val) || val < min) {
                input.value = min;
            }
        });
    });

    function setupHoldableButton(btn, isUp) {
        let pressTimer;
        let pressInterval;

        const startChange = () => {
            const targetId = btn.getAttribute('data-target');
            const targetInput = document.getElementById(targetId);
            if (!targetInput) return;

            if (isUp) targetInput.stepUp(); else targetInput.stepDown();

            pressTimer = setTimeout(() => {
                pressInterval = setInterval(() => {
                    if (isUp) targetInput.stepUp(); else targetInput.stepDown();
                }, 50);
            }, 400);
        };

        const stopChange = () => {
            clearTimeout(pressTimer);
            clearInterval(pressInterval);
        };

        btn.addEventListener('mousedown', startChange);
        btn.addEventListener('touchstart', (e) => {
            e.preventDefault();
            startChange();
        });

        btn.addEventListener('mouseup', stopChange);
        btn.addEventListener('mouseleave', stopChange);
        btn.addEventListener('touchend', stopChange);
    }

    upBtns.forEach(btn => setupHoldableButton(btn, true));
    downBtns.forEach(btn => setupHoldableButton(btn, false));

    // ─── SEED PHRASE VALIDATION ENGINE ─────────────────────────────
    const VALID_WORD_COUNTS = [12, 15, 18, 20, 21, 24, 33];
    let wordlistSet = new Set();
    let validationState = { valid: false, invalidWords: [], invalidLength: false, checksumFail: false, errors: [] };
    const seedErrorBar = document.getElementById('seedErrorBar');

    // Load wordlist on startup
    fetch('/api/wordlist')
        .then(r => r.json())
        .then(data => { wordlistSet = new Set(data.words); })
        .catch(() => { console.warn('Could not load wordlist — validation disabled'); });

    function getWordAt(index) {
        const wrappers = seedGrid.querySelectorAll('.word-box-wrapper');
        if (index >= wrappers.length) return '';
        const inp = wrappers[index].querySelector('input.word-box-input');
        return ((inp.dataset.masked === 'true') ? (inp.dataset.realValue || '') : inp.value).trim().toLowerCase();
    }

    function getAllWords() {
        const wrappers = seedGrid.querySelectorAll('.word-box-wrapper');
        return Array.from(wrappers).map((w, i) => getWordAt(i)).filter(w => w !== '');
    }

    // errorContainer holds 0-N individual error boxes
    const errorContainer = document.getElementById('seedErrorContainer');
    const activeErrors = new Map();

    function setDiagnostic(id, text, level) {
        if (!text) {
            activeErrors.delete(id);
        } else {
            activeErrors.set(id, { id, text, level });
        }
        renderErrorBoxes(Array.from(activeErrors.values()));
        updateGenerateButtonState();
    }

    function renderErrorBoxes(entries) {
        if (!errorContainer) return;
        
        const newIds = new Set(entries.map(e => e.id));
        
        // Remove old entries smoothly
        Array.from(errorContainer.children).forEach(el => {
            if (!newIds.has(el.dataset.errorId)) {
                if (!el.classList.contains('error-box-exit')) {
                    el.classList.remove('error-box-enter');
                    el.classList.add('error-box-exit');
                    setTimeout(() => el.remove(), 250);
                }
            }
        });

        // Add or update
        entries.forEach(entry => {
            let el = Array.from(errorContainer.children).find(c => c.dataset.errorId === entry.id && !c.classList.contains('error-box-exit'));
            if (el) {
                if (el.textContent !== entry.text) {
                    el.textContent = entry.text;
                }
            } else {
                const box = document.createElement('div');
                box.dataset.errorId = entry.id;
                box.className = 'seed-error-box' + (entry.level === 'warning' ? ' warning-level' : '');
                box.textContent = entry.text;
                errorContainer.appendChild(box);
                void box.offsetWidth;
                box.classList.add('error-box-enter');
            }
        });
    }

    function formatIndices(indices) {
        if (indices.length === 0) return '';
        const sorted = [...new Set(indices)].sort((a,b) => a-b);
        let result = [];
        let start = sorted[0];
        let end = sorted[0];
        for (let i = 1; i < sorted.length; i++) {
            if (sorted[i] === end + 1) {
                end = sorted[i];
            } else {
                result.push(start === end ? `${start}` : `${start}-${end}`);
                start = sorted[i];
                end = sorted[i];
            }
        }
        result.push(start === end ? `${start}` : `${start}-${end}`);
        return result.join(', ');
    }

    function syncInvalidWordsDiagnostic() {
        const wrappers = Array.from(seedGrid.querySelectorAll('.word-box-wrapper'));
        const invalidIndices = [];
        wrappers.forEach((w, i) => {
            const inp = w.querySelector('input.word-box-input');
            if (inp.classList.contains('word-invalid')) {
                invalidIndices.push(i + 1);
            }
        });

        if (invalidIndices.length > 0) {
            const fmt = formatIndices(invalidIndices);
            const text = invalidIndices.length === 1 
                ? `Unrecognized word at position ${fmt}.`
                : `Unrecognized words at position ${fmt}.`;
            setDiagnostic('invalid-words', text, 'error');
        } else {
            setDiagnostic('invalid-words', null);
        }
    }

    function clearFullPhraseDiagnostics() {
        setDiagnostic('empty', null);
        setDiagnostic('invalid-length', null);
        setDiagnostic('checksum', null);
        seedGrid.querySelectorAll('input.word-box-input').forEach(inp => inp.classList.remove('word-warning'));
    }

    function clearAllValidationStyles() {
        seedGrid.querySelectorAll('input.word-box-input').forEach(inp => {
            inp.classList.remove('word-invalid', 'word-warning', 'word-valid');
        });
        activeErrors.clear();
        renderErrorBoxes([]);
        updateGenerateButtonState();
    }

    function applyFlickerClass(input, cls) {
        input.classList.remove(cls);
        void input.offsetWidth; // force reflow
        input.classList.add(cls);
    }

    function flashValidSuccess() {
        const wrappers = Array.from(seedGrid.querySelectorAll('.word-box-wrapper'));
        wrappers.forEach(w => {
            const inp = w.querySelector('input.word-box-input');
            const word = ((inp.dataset.masked === 'true') ? (inp.dataset.realValue || '') : inp.value).trim();
            if (word !== '') {
                // Clear any leftover error classes first
                inp.classList.remove('word-invalid', 'word-warning');
                applyFlickerClass(inp, 'word-valid');
            }
        });
    }

    function updateGenerateButtonState() {
        const btn = document.getElementById('encodeSubmitBtn');
        if (!btn) return;
        
        if (activeErrors.size > 0 || getAllWords().length === 0) {
            btn.classList.add('btn-disabled');
        } else {
            btn.classList.remove('btn-disabled');
        }
    }

    function validateSpecificBox(wrapper, shouldFlicker=true) {
        if (wordlistSet.size === 0) return;
        const inp = wrapper.querySelector('input.word-box-input');
        const word = ((inp.dataset.masked === 'true') ? (inp.dataset.realValue || '') : inp.value).trim().toLowerCase();
        
        if (word !== '') {
            if (!wordlistSet.has(word)) {
                if (shouldFlicker) {
                    applyFlickerClass(inp, 'word-invalid');
                } else {
                    inp.classList.add('word-invalid');
                }
            } else {
                inp.classList.remove('word-invalid');
            }
        } else {
            inp.classList.remove('word-invalid');
        }
    }

    // Full mnemonic validation — called on generate click attempt
    // calledFromButton: true when user clicked generate, false for tab-switch resync
    async function validateFullMnemonic(calledFromButton = false) {
        const words = getAllWords();
        
        const wrappers = Array.from(seedGrid.querySelectorAll('.word-box-wrapper'));
        // Clear stale valid-success glow before re-evaluating
        wrappers.forEach(w => w.querySelector('input.word-box-input').classList.remove('word-valid'));
        // Pass "true" to re-trigger the CSS flicker animation on boxes when the button is clicked again
        wrappers.forEach(w => validateSpecificBox(w, true));
        syncInvalidWordsDiagnostic();

        if (words.length === 0) {
            // Only show "no seed phrase" when the user explicitly clicks the generate button
            if (calledFromButton) {
                setDiagnostic('empty', 'No seed phrase entered.', 'error');
            }
            updateGenerateButtonState();
            return { valid: false, errors: ['No seed phrase entered.'] };
        } else {
            setDiagnostic('empty', null);
        }

        // Check for any invalid words still present
        const hasInvalidWords = wrappers.some(w => {
            const inp = w.querySelector('input.word-box-input');
            return inp.classList.contains('word-invalid');
        });

        try {
            const resp = await fetch('/api/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mnemonic: words.join(' ') })
            });
            const result = await resp.json();

            // Clear full phrase diagnostics if resolved
            if (!result.invalidLength) setDiagnostic('invalid-length', null);

            // Strip warning class globally before reapplying to ensure it vanishes if resolved
            wrappers.forEach(w => w.querySelector('input.word-box-input').classList.remove('word-warning'));

            if (result.invalidLength) {
                setDiagnostic('invalid-length', `Invalid mnemonic length: ${words.length} ${words.length === 1 ? 'word' : 'words'}. Valid counts: ${VALID_WORD_COUNTS.join(', ')}.`, 'warning');
                // If length is invalid, checksum is meaningless — clear it
                setDiagnostic('checksum', null);
            }

            // Checksum only makes sense if length is valid AND all words are recognized
            if (!result.invalidLength && !hasInvalidWords) {
                if (result.checksumFail) {
                    setDiagnostic('checksum', 'Mnemonic checksum failed. The seed phrase is not valid for any supported standard.', 'warning');
                } else {
                    setDiagnostic('checksum', null);
                }
            } else {
                // Clear checksum if preconditions not met
                setDiagnostic('checksum', null);
            }

            // Apply warning glow (orange) if either phrase-level error exists
            if (activeErrors.has('invalid-length') || activeErrors.has('checksum')) {
                wrappers.forEach(w => {
                    const inp = w.querySelector('input.word-box-input');
                    if (getWordAt(wrappers.indexOf(w)) !== '') {
                        applyFlickerClass(inp, 'word-warning');
                    }
                });
            }

            updateGenerateButtonState();

            // Flash green on success
            if (result.valid) {
                flashValidSuccess();
            }

            return result;
        } catch (err) {
            console.error('Validation fetch failed:', err);
            return { valid: true, errors: [] }; // fail open if server is down
        }
    }

    // Re-sync all validation visuals & diagnostics (e.g. after tab switch)
    // Does NOT show "no seed phrase" — that only appears on explicit button click
    function resyncValidation() {
        validateFullMnemonic(false);
    }

    // Encode Form
    const encodeForm = document.getElementById("encodeForm");
    const encodeSubmitBtn = document.getElementById("encodeSubmitBtn");
    const encodeResult = document.getElementById("encodeResult");

    encodeForm.addEventListener("submit", async (e) => {
        e.preventDefault();

        // Run full validation first (calledFromButton=true)
        const valResult = await validateFullMnemonic(true);
        if (!valResult.valid) {
            // Button stays enabled so user can re-attempt after fixing
            return;
        }

        encodeSubmitBtn.textContent = "Processing...";
        encodeSubmitBtn.disabled = true;
        encodeResult.classList.add("hidden");

        const mnemonic = document.getElementById("mnemonicHidden").value.trim();
        const salt = document.getElementById("salt").value;
        const cellPx = document.getElementById("cellPx").value;
        const isBulk = document.getElementById("bulkToggle").checked;
        const count = document.getElementById("count").value;

        const formData = new FormData();
        formData.append("mnemonic", mnemonic);
        formData.append("salt", salt);
        formData.append("cellPx", cellPx);

        let endpoint = "/api/encode";
        if (isBulk) {
            endpoint = "/api/encode_bulk";
            formData.append("count", count);
        }

        try {
            const response = await fetch(endpoint, {
                method: "POST",
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || "Failed to generate image.");
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.style.display = "none";
            a.href = url;
            a.download = isBulk ? "spicebag_mnemonics.zip" : "spicebag_mnemonic.png";
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);

            if (!isBulk) {
                encodeResult.innerHTML = `
                    <div>Success! Downloading ${a.download}...</div>
                    <img class="web-preview-img" src="${url}" alt="Spicebag Mnemonic">
                `;
            } else {
                encodeResult.textContent = `Success! Check your downloads for ${a.download}.`;
            }
            encodeResult.classList.remove("hidden");
            encodeResult.style.color = "black";
        } catch (error) {
            encodeResult.textContent = `${error.message}`;
            encodeResult.classList.remove("hidden");
            encodeResult.style.color = "red";
        } finally {
            encodeSubmitBtn.textContent = "Generate Image";
            encodeSubmitBtn.disabled = false;
        }
    });

    // Decode Form
    const decodeForm = document.getElementById("decodeForm");
    const decodeSubmitBtn = document.getElementById("decodeSubmitBtn");
    const decodeResult = document.getElementById("decodeResult");
    const decodedText = document.getElementById("decodedText");
    const copyBtn = document.getElementById("copyBtn");

    decodeForm.addEventListener("submit", async (e) => {
        e.preventDefault();

        decodeSubmitBtn.textContent = "Decoding...";
        decodeSubmitBtn.disabled = true;
        decodeResult.classList.add("hidden");

        const imageFile = document.getElementById("imageUpload").files[0];
        const salt = document.getElementById("decodeSalt").value;

        const formData = new FormData();
        formData.append("image", imageFile);
        formData.append("salt", salt);

        try {
            const response = await fetch("/api/decode", {
                method: "POST",
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || "Failed to decode image.");
            }

            const data = await response.json();

            decodedText.textContent = data.mnemonic;
            decodeResult.classList.remove("hidden");
        } catch (error) {
            alert(`${error.message}`);
        } finally {
            decodeSubmitBtn.textContent = "Decode Image";
            decodeSubmitBtn.disabled = false;
        }
    });

    copyBtn.addEventListener("click", () => {
        const text = decodedText.textContent;
        navigator.clipboard.writeText(text).then(() => {
            const oldText = copyBtn.textContent;
            copyBtn.textContent = "Copied!";
            setTimeout(() => {
                copyBtn.textContent = oldText;
            }, 2000);
        });
    });
});