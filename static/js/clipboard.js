document.addEventListener('DOMContentLoaded', function() {
  console.log('Setup clipboard buttons');

  const DEBUG = false;
  function debug(...arg) {
    if (DEBUG) {
      console.debug(...arg);
    }
  }

  const numEj = /num_ej=([0-9]+)/.exec(window.location.search)[1];

  initStandAloneButtons();
  initTables();


  /// FUNCTIONS

  function initTables() {
    // Find all containers
    const tableContainers = document.querySelectorAll('.copyable');
    tableContainers.forEach(function (container) {
      const tables = container.querySelectorAll('.copyable table');
      // Process each table
      tables.forEach(function (table) {
        // If there are headers in table, it's a full table
        if (!!table.querySelector('th')) {
          initTableFull(table);
        }
        // If no table headers, it's a key / value table (2 cols)
        else {
          initTableKeyValue(table);
        }
      });
    });
  }

  function initStandAloneButtons() {
    // Find all buttons
    const copyButtons = document.querySelectorAll('.btn-copy.btn-copy-standalone');
    copyButtons.forEach(function(button) {
      const fieldName = button.getAttribute('x-copy-fieldname');
      const copyValue = button.getAttribute('x-copy-value');
      addOnClickListener(button, fieldName, copyValue);
    });
  }

  /**
   * Simple table, 2 columns, first column contains keys, second column contains values
   */
  function initTableKeyValue(table) {
    // Find all rows in the table
    const rows = table.querySelectorAll('tr');

    // Process each row
    rows.forEach(function (row) {
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

        const copyButton = createCopyButton(fieldName, cellContent);

        // Add button to the cell
        secondCell.appendChild(copyButton);
      }
    });
  }

  function initTableFull(table) {
    // Headers
    const headers = Array.from(table.querySelectorAll('th')).map(el => el.textContent.trim());

    // Find all rows in the table
    const rows = table.querySelectorAll('tr');

    // Process each row
    rows.forEach(function (row) {
      // Get all cells in the row
      const cells = row.querySelectorAll('td');

      cells.forEach(function(cell, cellIdx) {
        const fieldName = headers[cellIdx];

        // Store the original content
        const cellContent = cell.textContent.trim();

        // Ignore empty cells
        if (!cellContent) {
          return;
        }

        // Create the copy button
        const copyButton = createCopyButton(fieldName, cellContent);

        // Add button to the cell
        cell.appendChild(copyButton);
      });
    });
  }

  function createCopyButton(fieldName, cellContent) {
    // Create the copy button
    const copyButton = document.createElement('button');
    copyButton.textContent = 'Copier';
    copyButton.className = 'btn-copy fr-badge fr-badge--sm fr-ml-1w';
    copyButton.setAttribute('x-copy-fieldname', JSON.stringify(fieldName));

    // Add click event to copy content
    addOnClickListener(copyButton, fieldName, cellContent);

    return copyButton;
  }

  function addOnClickListener(copyButton, fieldName, copyValue) {
    copyButton.addEventListener('click', function (e) {
      e.stopPropagation();
      copyToClipboard(copyValue, copyButton);
      trackEvent('interaction', 'copy', fieldName, numEj);
    });
  }

  function copyToClipboard(cellContent, copyButton) {
    debug('copy', cellContent, copyButton);
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
    debug('track event [category:', category, '] [action:', action, '] [name:', name, '] [numEj:', numEj, ']');
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