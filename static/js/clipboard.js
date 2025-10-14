document.addEventListener('DOMContentLoaded', function() {
  console.log('Setup clipboard buttons');

  const numEj = /num_ej=([0-9]+)/.exec(window.location.search)[1];

  // Find all tables
  const tables = document.querySelectorAll('.copyable table');
  // Process each table
  tables.forEach(function(table) {
    // Find all rows in the table
    const rows = table.querySelectorAll('tr');

    // Process each row
    rows.forEach(function(row) {
      // Get all cells in the row
      const cells = row.querySelectorAll('td');

      // Check if there are at least 2 cells in the row
      if (cells.length >= 2) {
        const firstCell = cells[0];
        const fieldName = firstCell.textContent.trim();

        // Get the second cell (index 1)
        const secondCell = cells[1];

        // Store the original content
        const cellContent = secondCell.textContent.trim();

        // Ignore empty cells
        if (!cellContent) {
          return;
        }

        // Create the copy button
        const copyButton = document.createElement('button');
        copyButton.textContent = 'Copier';
        copyButton.className = 'fr-badge fr-badge--sm fr-ml-1w';
        copyButton.style.fontSize = '12px';
        copyButton.style.padding = '2px 6px';

        // Add click event to copy content
        copyButton.addEventListener('click', function(e) {
          e.stopPropagation();
          copyToClipboard(cellContent, copyButton);
          trackEvent('interaction', 'copy', fieldName, numEj);
        });

        // Add button to the cell
        secondCell.appendChild(copyButton);
      }
    });
  });

  function copyToClipboard(cellContent, copyButton) {
    // Cross-browser clipboard copy
    if (navigator.clipboard && window.isSecureContext) {
      // For modern browsers in secure contexts
      navigator.clipboard.writeText(cellContent)
        .then(function() {
          // Visual feedback
          showCopySuccess(copyButton);
        })
        .catch(function() {
          // Fallback for errors
          fallbackCopyTextToClipboard(cellContent, copyButton);
        });
    } else {
      // Fallback for older browsers or non-secure contexts
      fallbackCopyTextToClipboard(cellContent, copyButton);
    }
  }

  // Fallback copy method for older browsers
  function fallbackCopyTextToClipboard(text, button) {
    const textArea = document.createElement('textarea');
    textArea.value = text;

    // Make the textarea out of viewport
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';
    document.body.appendChild(textArea);

    // Select and copy
    textArea.focus();
    textArea.select();

    let success = false;
    try {
      success = document.execCommand('copy');
    } catch (err) {
      console.error('Unable to copy to clipboard', err);
    }

    document.body.removeChild(textArea);

    if (success) {
      showCopySuccess(button);
    }
    else {
      showCopyError(button);
    }
  }

  // Visual feedback when copy is successful
  function showCopySuccess(button) {
    button.style.backgroundColor = '#4CAF50';
    button.style.color = 'white';

    // Reset button after 1 second
    setTimeout(function() {
      button.style.backgroundColor = '';
      button.style.color = '';
    }, 1000);
  }

  // Visual feedback when copy failed
  function showCopyError(button) {
    button.style.backgroundColor = '#e21432';
    button.style.color = 'white';

    // Reset button after 1 second
    setTimeout(function() {
      button.style.backgroundColor = '';
      button.style.color = '';
    }, 1000);
  }

  /**
   * Sends a tracking event to the server using fetch API
   */
  function trackEvent(category, action, name, numEj) {
    // Create the full payload
    const payload = {
      category: category,
      action: action,
      name: name,
      num_ej: numEj,
    };

    const csrftoken = getCookie('csrftoken');

    // Use fetch with keepalive to ensure the request completes
    // even if the page is unloading
    return fetch('/t/events', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrftoken,
      },
      mode: 'same-origin',
      keepalive: true, // Ensures request completes even if page is changing
      body: JSON.stringify(payload)
    })
      .catch(error => {
        // Silently catch errors since this is tracking
        console.error('Failed to send tracking event:', error);
      });
  }

  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        // Does this cookie string begin with the name we want?
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

});