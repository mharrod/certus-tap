// Force dark mode as default on first visit
;(function () {
  const palette = localStorage.getItem('.__palette')

  // Only set if user hasn't made a choice yet
  if (!palette) {
    localStorage.setItem('.__palette', JSON.stringify({ index: 0, color: { scheme: 'slate' } }))
    document.documentElement.setAttribute('data-md-color-scheme', 'slate')
  }
})()
