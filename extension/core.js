/*
 * Lo que comparten el service worker, el popup y las opciones: dónde está la API, cómo se presenta
 * la respuesta de `POST /capture` y cómo se comprueba un token. Sin dependencias.
 */
var CAI = (function () {
  'use strict'

  var API_URL = 'http://127.0.0.1:8000'
  // `cai start` sirve la UI en la misma dirección que la API. Al conectar desde la app, se guarda
  // la dirección desde la que se conectó (con `pnpm dev`, la de Vite).
  var DEFAULT_UI_URL = 'http://127.0.0.1:8000'
  // La página de la app que guía la instalación y conecta la extensión.
  var CONNECT_PATH = '/fuentes/extension'
  var CONNECT_HINT = 'Pulsa «Conectar con CandidatAI» y, en la app, «Conectar».'

  var STATUS = {
    new: { label: 'Nueva', badge: '✓', color: '#0f766e' },
    completed: { label: 'Completada', badge: '✓', color: '#0f766e' },
    existing: { label: 'Ya estaba', badge: '=', color: '#52525b' },
  }

  var ERRORS = {
    unauthorized: 'La conexión con CandidatAI ya no vale (se volvió a conectar). ' + CONNECT_HINT,
    forbidden:
      'La app no acepta esta extensión. Revisa CAI_CAPTURE_EXTENSION_ID en .env y reinicia CandidatAI.',
    capture_not_configured: 'Falta conectar la extensión con CandidatAI. ' + CONNECT_HINT,
    database_not_ready: 'La base de datos no está al día: ejecuta «cai db upgrade».',
  }

  // Lo que se arregla conectando desde la app: el popup ofrece ese botón.
  var NEEDS_CONNECT = ['no_token', 'unauthorized', 'capture_not_configured']

  function base(uiUrl) {
    return String(uiUrl || DEFAULT_UI_URL).replace(/\/+$/, '')
  }

  function jobUrl(uiUrl, jobId) {
    return base(uiUrl) + '/jobs/' + jobId
  }

  function connectUrl(uiUrl) {
    return base(uiUrl) + CONNECT_PATH
  }

  /** Solo la app, en este equipo, puede conectar la extensión (`externally_connectable`). */
  function isAppOrigin(origin) {
    return /^http:\/\/(127\.0\.0\.1|localhost)(:\d{1,5})?$/.test(String(origin || ''))
  }

  /** Respuesta de la API → lo que enseñan el popup y el badge. */
  function describe(httpStatus, body, uiUrl) {
    if (httpStatus === 200 && body && STATUS[body.status]) {
      var status = STATUS[body.status]
      return {
        ok: true,
        kind: body.status,
        label: status.label,
        message: body.message,
        title: body.title,
        company: body.company,
        jobUrl: jobUrl(uiUrl, body.job_id),
        risk: (body.risk_flags || []).length > 0,
        badge: { text: status.badge, color: status.color },
      }
    }
    var error = (body && body.error) || {}
    return {
      ok: false,
      kind: error.type || 'error',
      label: 'Error',
      message: ERRORS[error.type] || error.message || 'La app respondió con un error (' + httpStatus + ').',
      badge: { text: '!', color: '#b91c1c' },
    }
  }

  function failure(kind, message) {
    return { ok: false, kind: kind, label: 'Error', message: message, badge: { text: '!', color: '#b91c1c' } }
  }

  /**
   * Prueba la app y un token sin crear nada: un cuerpo vacío. La app comprueba origen y token antes
   * que el cuerpo, así que un 422 (cuerpo no válido) significa que lo acepta.
   */
  function probe(token) {
    return fetch(API_URL + '/capture', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
      body: '{}',
    }).then(
      function (response) {
        if (response.status === 422) return { ok: true, kind: 'connected', label: 'Conectada', message: '' }
        return response.json().then(
          function (body) {
            return describe(response.status, body)
          },
          function () {
            return describe(response.status, null)
          },
        )
      },
      function () {
        return failure('offline', 'CandidatAI no responde en ' + API_URL + '. Ábrelo y vuelve a probar.')
      },
    )
  }

  return {
    API_URL: API_URL,
    DEFAULT_UI_URL: DEFAULT_UI_URL,
    NEEDS_CONNECT: NEEDS_CONNECT,
    connectUrl: connectUrl,
    describe: describe,
    failure: failure,
    isAppOrigin: isAppOrigin,
    probe: probe,
  }
})()
