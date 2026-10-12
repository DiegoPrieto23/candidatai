/*
 * Service worker de «Enviar a CandidatAI». Solo hace algo cuando el popup se lo pide, es decir,
 * cuando pulsas el botón: lee la pestaña activa (permiso `activeTab`), manda los datos a la API
 * local con el token y deja el resultado en el badge de esa pestaña. No lee cookies, no recorre
 * páginas y no tiene scripts permanentes en ninguna web.
 */
importScripts('core.js')

async function setBadge(tabId, outcome) {
  try {
    await chrome.action.setBadgeText({ tabId: tabId, text: outcome.badge.text })
    await chrome.action.setBadgeBackgroundColor({ tabId: tabId, color: outcome.badge.color })
    await chrome.action.setTitle({ tabId: tabId, title: 'CandidatAI: ' + outcome.label })
  } catch {
    // La pestaña se cerró mientras tanto: no pasa nada.
  }
}

async function captureTab(tabId) {
  var tab = typeof tabId === 'number' ? { id: tabId } : null
  if (!tab) return CAI.failure('no_tab', 'No hay ninguna pestaña activa.')

  var stored = await chrome.storage.local.get(['token', 'uiUrl'])
  if (!stored.token) {
    return CAI.failure('no_token', 'Falta el token: genera uno con «cai capture token» y pégalo en las opciones.')
  }

  var data
  try {
    var results = await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['extractors.js'] })
    data = results && results[0] && results[0].result
  } catch {
    var outcome = CAI.failure(
      'no_access',
      'No se puede leer esta página (las del navegador y las tiendas de extensiones no se dejan).',
    )
    await setBadge(tab.id, outcome)
    return outcome
  }
  if (!data) return CAI.failure('no_data', 'No se pudo leer la página.')

  var response
  try {
    response = await fetch(CAI.API_URL + '/capture', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + stored.token },
      body: JSON.stringify(data),
    })
  } catch {
    var offline = CAI.failure('offline', 'La app no responde. ¿Está «cai serve» en marcha?')
    await setBadge(tab.id, offline)
    return offline
  }
  var body = null
  try {
    body = await response.json()
  } catch {
    body = null
  }
  var result = CAI.describe(response.status, body, stored.uiUrl)
  result.site = data.site
  result.usedSelection = Boolean(data.selection)
  await setBadge(tab.id, result)
  return result
}

chrome.runtime.onMessage.addListener(function (message, sender, sendResponse) {
  // Solo el popup de esta extensión: nada que venga de una página web ni de otra extensión.
  var fromPopup = sender.id === chrome.runtime.id && !sender.tab && sender.url === chrome.runtime.getURL('popup.html')
  if (!message || message.type !== 'capture' || !fromPopup) return false
  // El popup dice qué pestaña es: desde el service worker, «la ventana actual» es ambigua.
  captureTab(message.tabId).then(sendResponse, function (error) {
    sendResponse(CAI.failure('error', 'Error inesperado: ' + (error && error.message)))
  })
  return true
})
