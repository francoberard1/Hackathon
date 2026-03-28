// ============================================================================
// MAIN.JS
// ============================================================================
// Minimal JavaScript for SplitIA.
// This file contains simple interactions to enhance UX.
// 
// Note: We keep this VERY minimal:
// - Form validation
// - Helper UI enhancements
// - No complex frameworks like React
// ============================================================================


// ============================================================================
// FORM VALIDATION AND HELPERS
// ============================================================================

/**
 * When adding an expense, ensure the user selected at least one participant
 */
document.addEventListener('DOMContentLoaded', function() {
    const expenseForm = document.querySelector('form');
    
    // Check if we're on the add_expense page by looking for participant checkboxes
    const participantCheckboxes = document.querySelectorAll('input[name^="participant_"]');
    
    if (participantCheckboxes.length > 0 && expenseForm) {
        // This is the add expense form
        expenseForm.addEventListener('submit', function(event) {
            // Check if at least one participant is selected
            const anyChecked = Array.from(participantCheckboxes).some(cb => cb.checked);
            
            if (!anyChecked) {
                event.preventDefault();
                alert('⚠️ Please select at least one participant for the expense!');
            }
        });
    }
});


/**
 * Format currency amounts in the UI
 * If you want to add thousands separators, this is the place
 */
function formatCurrency(amount) {
    return '$' + parseFloat(amount).toFixed(2);
}


/**
 * Copy transaction text to clipboard
 * Useful for sharing settle instructions
 */
function copyToClipboard(text) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(function() {
            alert('✅ Copied to clipboard!');
        });
    }
}


/**
 * Simple tooltip/info pop-ups
 * Example: hover over a term to see explanation
 */
document.addEventListener('DOMContentLoaded', function() {
    const infoElements = document.querySelectorAll('[data-tooltip]');
    infoElements.forEach(element => {
        element.addEventListener('hover', function(e) {
            const tooltip = this.getAttribute('data-tooltip');
            console.log(tooltip);
        });
    });
});


// ============================================================================
// FUTURE ENHANCEMENTS (Placeholders)
// ============================================================================

/**
 * PLACEHOLDER: Real-time expense preview
 * As user types amount, show preview of what each person owes
 */
function previewExpenseShares() {
    // TODO: Implement this when complex features needed
    // - Read amount from input
    // - Count checked participants
    // - Show live preview: "Each person pays $X"
}


/**
 * PLACEHOLDER: Delete functionality
 * Users might want to delete expenses or members
 */
function deleteExpense(expenseId) {
    // TODO: Implement with a confirmation dialog
    // if (confirm('Delete this expense?')) {
    //     // Send DELETE request to server
    // }
}


/**
 * PLACEHOLDER: Edit functionality
 * Allow editing expenses or members
 */
function editExpense(expenseId) {
    // TODO: Implement when needed
    // - Load expense data
    // - Show edit form
    // - Submit changes
}


/**
 * PLACEHOLDER: Auto-select participants
 * Quick button to select/deselect all participants
 */
function toggleAllParticipants(selectAll) {
    const checkboxes = document.querySelectorAll('input[name^="participant_"]');
    checkboxes.forEach(cb => {
        cb.checked = selectAll;
    });
}


// ============================================================================
// KEYBOARD SHORTCUTS (Optional)
// ============================================================================

/**
 * PLACEHOLDER: Keyboard shortcuts for power users
 * e.g., Ctrl+S to submit form, Escape to cancel
 */
document.addEventListener('keydown', function(event) {
    // Ctrl+S or Cmd+S to submit the current form
    if ((event.ctrlKey || event.metaKey) && event.key === 's') {
        event.preventDefault();
        const form = document.querySelector('form');
        if (form) {
            form.submit();
        }
    }
    
    // Escape to go back
    if (event.key === 'Escape') {
        // Optional: navigate back or close modal
        // window.history.back();
    }
});


// ============================================================================
// LOGGING / DEBUGGING (Development only)
// ============================================================================

/**
 * Log page information to console (useful for debugging)
 */
function logPageInfo() {
    console.log('=== SplitIA Page Info ===');
    console.log('URL:', window.location.href);
    console.log('Page Title:', document.title);
    
    const form = document.querySelector('form');
    if (form) {
        console.log('Form found:', form.method, form.action);
    }
}

// Uncomment to debug
// logPageInfo();
