const code = document.forms[0].code;

// remove the "required" error message that overflows the page
code.addEventListener('invalid', (event) => event.preventDefault());
code.addEventListener('keydown', (event) => {
  if (event.code === 'Tab') {
    // prevents tab from being used to navigate between browser elements
    event.preventDefault();
    const { value, selectionStart, selectionEnd } = code;

    // inserts tab at the position of the caret
    code.value = value.slice(0, selectionStart) + '\t' + value.slice(selectionEnd);

    // puts caret after the newly inserted tab char
    const caretPos = selectionStart + 1;
    code.focus();
    code.setSelectionRange(caretPos, caretPos);
  }
});
