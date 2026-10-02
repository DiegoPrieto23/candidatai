/* Opciones: el token (solo en `chrome.storage.local` de este navegador) y la dirección de la UI. */
;(function () {
  'use strict'

  var token = document.getElementById('token')
  var uiUrl = document.getElementById('uiUrl')
  var status = document.getElementById('status')

  function say(text, ok) {
    status.textContent = text
    status.className = 'message ' + (ok ? 'ok' : 'error')
  }

  chrome.storage.local.get(['token', 'uiUrl'], function (stored) {
    token.value = stored.token || ''
    uiUrl.value = stored.uiUrl || JH.DEFAULT_UI_URL
  })

  document.getElementById('form').addEventListener('submit', function (event) {
    event.preventDefault()
    var url = uiUrl.value.trim() || JH.DEFAULT_UI_URL
    if (!/^https?:\/\//.test(url)) {
      say('La dirección de la UI debe empezar por http:// o https://.', false)
      return
    }
    chrome.storage.local.set({ token: token.value.trim(), uiUrl: url }, function () {
      say('Guardado.', true)
    })
  })

  // Prueba la app y el token sin crear nada: un cuerpo vacío. La app comprueba origen y token antes
  // que el cuerpo, así que un 422 (cuerpo no válido) significa que el token vale.
  document.getElementById('test').addEventListener('click', function () {
    var value = token.value.trim()
    if (!value) {
      say('Pega primero el token.', false)
      return
    }
    say('Probando…', true)
    fetch(JH.API_URL + '/capture', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + value },
      body: '{}',
    })
      .then(function (response) {
        if (response.status === 422) {
          say('Todo listo: la app responde y acepta este token. Guarda si aún no lo has hecho.', true)
          return
        }
        return response.json().then(
          function (body) {
            say(JH.describe(response.status, body).message, false)
          },
          function () {
            say('La app respondió con un error (' + response.status + ').', false)
          },
        )
      })
      .catch(function () {
        say('La app no responde en ' + JH.API_URL + '. ¿Está «jh serve» en marcha?', false)
      })
  })
})()
