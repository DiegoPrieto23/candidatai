/* Popup: al abrirse (al pulsar el botón) pide la captura al service worker y enseña el resultado. */
;(function () {
  'use strict'

  var root = document.getElementById('result')
  var KINDS = ['new', 'completed', 'existing']

  function el(tag, className, text) {
    var node = document.createElement(tag)
    if (className) node.className = className
    if (text) node.textContent = text // siempre texto: lo que viene de la página no es HTML fiable
    return node
  }

  function render(outcome) {
    root.textContent = ''
    var kind = outcome.ok && KINDS.indexOf(outcome.kind) >= 0 ? outcome.kind : 'error'
    var status = el('p', 'status status-' + kind, outcome.label)
    root.appendChild(status)
    if (outcome.title) {
      var job = el('p', 'job')
      job.appendChild(el('strong', null, outcome.title))
      if (outcome.company) job.appendChild(el('span', 'muted', ' · ' + outcome.company))
      root.appendChild(job)
    }
    if (outcome.message) root.appendChild(el('p', 'message', outcome.message))
    if (outcome.risk) {
      root.appendChild(el('p', 'warning', 'Aviso: la oferta tiene texto que parece dirigido a una IA.'))
    }
    if (outcome.ok && outcome.usedSelection) {
      root.appendChild(el('p', 'muted small', 'Se envió el texto que tenías seleccionado.'))
    }
    if (outcome.jobUrl) {
      var open = el('button', 'primary', 'Abrir ficha')
      open.type = 'button'
      open.addEventListener('click', function () {
        chrome.tabs.create({ url: outcome.jobUrl })
        window.close()
      })
      root.appendChild(open)
    } else if (outcome.kind === 'no_token' || outcome.kind === 'unauthorized') {
      var options = el('button', 'primary', 'Abrir opciones')
      options.type = 'button'
      options.addEventListener('click', function () {
        chrome.runtime.openOptionsPage()
      })
      root.appendChild(options)
    }
  }

  document.getElementById('options').addEventListener('click', function () {
    chrome.runtime.openOptionsPage()
  })

  // La pestaña activa de la ventana en la que se abrió el popup: la que acabas de pulsar.
  chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
    var tab = tabs && tabs[0]
    chrome.runtime.sendMessage({ type: 'capture', tabId: tab && tab.id }, function (outcome) {
      if (chrome.runtime.lastError || !outcome) {
        render(JH.failure('error', 'No se pudo hablar con la extensión. Vuelve a pulsar el botón.'))
        return
      }
      render(outcome)
    })
  })
})()
