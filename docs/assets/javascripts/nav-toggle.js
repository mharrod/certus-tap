document.addEventListener('DOMContentLoaded', () => {
  const toggles = document.querySelectorAll('.md-nav__toggle')

  toggles.forEach((toggle) => {
    const parentItem = toggle.closest('.md-nav__item')
    const activeDescendant = parentItem?.querySelector(
      '.md-nav__link[aria-current="page"], .md-nav__item--active',
    )

    if (!activeDescendant) {
      toggle.checked = false
    }
  })

  const nestedLinks = document.querySelectorAll(
    '.md-nav__item--nested > .md-nav__link',
  )

  nestedLinks.forEach((link) => {
    const toggle = link.previousElementSibling

    if (!toggle || !toggle.classList.contains('md-nav__toggle')) {
      return
    }

    link.addEventListener('click', (event) => {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
        return
      }

      const rect = link.getBoundingClientRect()
      const toggleZoneWidth = 36
      const toggleZoneStart = rect.right - toggleZoneWidth

      if (event.clientX < toggleZoneStart) {
        return
      }

      event.preventDefault()
      toggle.checked = !toggle.checked

      const changeEvent = new Event('change', { bubbles: true })
      toggle.dispatchEvent(changeEvent)
    })
  })
})
