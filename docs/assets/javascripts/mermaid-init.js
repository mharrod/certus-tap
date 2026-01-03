;(function () {
  const BASE_CONFIG = {
    startOnLoad: false,
    securityLevel: 'strict',
    suppressErrorRendering: true,
    theme: 'base',
    themeVariables: {
      primaryColor: 'var(--md-mermaid-node-bg-color)',
      primaryTextColor: 'var(--md-mermaid-label-fg-color)',
      primaryBorderColor: 'var(--md-mermaid-edge-color)',
      lineColor: 'var(--md-mermaid-edge-color)',
      secondaryColor: 'var(--md-mermaid-node-bg-color)',
      tertiaryColor: 'var(--md-mermaid-label-bg-color)',
      mainBkg: 'var(--md-mermaid-node-bg-color)',
      secondBkg: 'var(--md-mermaid-label-bg-color)',
      mainContrastColor: 'var(--md-mermaid-label-fg-color)',
      darkMode: false,
    },
    flowchart: {
      useMaxWidth: true,
      htmlLabels: true,
      curve: 'basis',
    },
    sequence: {
      useMaxWidth: true,
      actorBkg: 'var(--md-mermaid-sequence-actor-bg-color)',
      actorBorder: 'var(--md-mermaid-sequence-actor-border-color)',
      actorTextColor: 'var(--md-mermaid-sequence-actor-fg-color)',
      actorLineColor: 'var(--md-mermaid-sequence-actor-line-color)',
      signalColor: 'var(--md-mermaid-sequence-message-line-color)',
      signalTextColor: 'var(--md-mermaid-sequence-message-fg-color)',
      labelBoxBkgColor: 'var(--md-mermaid-sequence-label-bg-color)',
      labelTextColor: 'var(--md-mermaid-sequence-label-fg-color)',
      loopTextColor: 'var(--md-mermaid-sequence-loop-fg-color)',
      noteBkgColor: 'var(--md-mermaid-sequence-note-bg-color)',
      noteBorderColor: 'var(--md-mermaid-sequence-note-border-color)',
      noteTextColor: 'var(--md-mermaid-sequence-note-fg-color)',
    },
  }

  function getComputedThemeVariables() {
    const style = getComputedStyle(document.documentElement)
    return {
      primaryColor:
        style.getPropertyValue('--md-mermaid-node-bg-color').trim() ||
        '#f5f5f2',
      primaryTextColor:
        style.getPropertyValue('--md-mermaid-label-fg-color').trim() ||
        '#5e6568',
      primaryBorderColor:
        style.getPropertyValue('--md-mermaid-edge-color').trim() || '#a9b2a8',
      lineColor:
        style.getPropertyValue('--md-mermaid-edge-color').trim() || '#a9b2a8',
      secondaryColor:
        style.getPropertyValue('--md-mermaid-node-bg-color').trim() ||
        '#f5f5f2',
      tertiaryColor:
        style.getPropertyValue('--md-mermaid-label-bg-color').trim() ||
        '#f5f5f2',
      mainBkg:
        style.getPropertyValue('--md-mermaid-node-bg-color').trim() ||
        '#f5f5f2',
      secondBkg:
        style.getPropertyValue('--md-mermaid-label-bg-color').trim() ||
        '#f5f5f2',
      mainContrastColor:
        style.getPropertyValue('--md-mermaid-label-fg-color').trim() ||
        '#5e6568',
      textColor:
        style.getPropertyValue('--md-mermaid-label-fg-color').trim() ||
        '#5e6568',
      noteBkgColor:
        style.getPropertyValue('--md-mermaid-sequence-note-bg-color').trim() ||
        '#c8d0c9',
      noteBorderColor:
        style
          .getPropertyValue('--md-mermaid-sequence-note-border-color')
          .trim() || '#a9b2a8',
      noteTextColor:
        style.getPropertyValue('--md-mermaid-sequence-note-fg-color').trim() ||
        '#5e6568',
    }
  }

  function resetNodes() {
    document.querySelectorAll('.mermaid').forEach((node) => {
      if (!node.dataset.raw) {
        node.dataset.raw = node.textContent
      }
      node.innerHTML = node.dataset.raw
      node.removeAttribute('data-processed')
    })
  }

  async function renderMermaid() {
    if (!window.mermaid) {
      return
    }

    resetNodes()
    await new Promise((resolve) => setTimeout(resolve, 0))

    const nodes = document.querySelectorAll('.mermaid')
    // Filter out nodes with empty or whitespace-only content
    const validNodes = Array.from(nodes).filter((node) => {
      const content = node.textContent?.trim()
      return content && content.length > 0
    })

    if (validNodes.length > 0) {
      // Get theme variables from CSS
      const themeVars = getComputedThemeVariables()

      // Reinitialize Mermaid with computed theme variables
      window.mermaid.initialize({
        ...BASE_CONFIG,
        theme: 'base',
        themeVariables: themeVars,
      })

      try {
        // Render each diagram individually to ensure theme is applied
        for (const node of validNodes) {
          if (!node.hasAttribute('data-processed')) {
            const id = `mermaid-${Math.random().toString(36).substring(7)}`
            const graphDefinition = node.textContent.trim()

            try {
              const { svg } = await window.mermaid.render(id, graphDefinition)
              node.innerHTML = svg
              node.setAttribute('data-processed', 'true')
            } catch (err) {
              console.error('Error rendering individual mermaid diagram:', err)
            }
          }
        }
      } catch (error) {
        console.error('Mermaid rendering error:', error)
      }
    }
  }

  if (window.document$) {
    window.document$.subscribe(() => renderMermaid())
  } else {
    document.addEventListener('DOMContentLoaded', () => renderMermaid())
  }

  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (
        mutation.type === 'attributes' &&
        mutation.attributeName === 'data-md-color-scheme'
      ) {
        renderMermaid()
      }
    })
  })

  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-md-color-scheme'],
  })
})()
