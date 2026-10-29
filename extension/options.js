/*
 * Opciones: si está conectada con CandidatAI y el botón para conectarla (abre la página de la app
 * que lo hace). En «Avanzado», el token a mano (solo en `chrome.storage.local` de este navegador)
 * y la dirección de la app.
 */
;(function () {
  'use strict'

  var token = document.getElementById('token')
  var uiUrl = document.getElementById('uiUrl')
  var status = document.getElementById('status')
  var state = document.getElementById('state')

  function say(node, text, ok) {
    node.textContent = text
    node.className = 'message ' + (ok ? 'ok' : 'error')
  }

  function check() {
    state.className = 'message'
    state.textContent = 'Comprobando la conexión…'
    chrome.storage.local.get(['token'], function (stored) {
      if (!stored.token) {
        say(state, 'Sin conectar con CandidatAI.', false)
        return
      }
      CAI.probe(stored.token).then(function (result) {
        say(state, result.ok ? 'Conectada con CandidatAI.' : result.message, result.ok)
      })
    })
  }

  chrome.storage.local.get(['token', 'uiUrl'], function (stored) {
    token.value = stored.token || ''
    uiUrl.value = stored.uiUrl || CAI.DEFAULT_UI_URL
  })
  check()

  document.getElementById('recheck').addEventListener('click', check)
  document.getElementById('connect').addEventListener('click', function () {
    chrome.storage.local.get(['uiUrl'], function (stored) {
      chrome.tabs.create({ url: CAI.connectUrl(stored.uiUrl) })
    })
  })

  document.getElementById('form').addEventListener('submit', function (event) {
    event.preventDefault()
    var url = uiUrl.value.trim() || CAI.DEFAULT_UI_URL
    if (!/^https?:\/\//.test(url)) {
      say(status, 'La dirección debe empezar por http:// o https://.', false)
      return
    }
    chrome.storage.local.set({ token: token.value.trim(), uiUrl: url }, function () {
      say(status, 'Guardado.', true)
      check()
    })
  })

  document.getElementById('test').addEventListener('click', function () {
    var value = token.value.trim()
    if (!value) {
      say(status, 'Pega primero el token.', false)
      return
    }
    say(status, 'Probando…', true)
    CAI.probe(value).then(function (result) {
      if (result.ok) say(status, 'Todo listo: la app responde y acepta este token. Guarda si aún no lo has hecho.', true)
      else say(status, result.message, false)
    })
  })
})()
