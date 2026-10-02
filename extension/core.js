/*
 * Lo que comparten el service worker y el popup: dónde está la API y cómo se presenta la
 * respuesta de `POST /capture`. Sin dependencias.
 */
var JH = (function () {
  'use strict'

  var API_URL = 'http://127.0.0.1:8000'
  var DEFAULT_UI_URL = 'http://127.0.0.1:5173'

  var STATUS = {
    new: { label: 'Nueva', badge: '✓', color: '#0f766e' },
    completed: { label: 'Completada', badge: '✓', color: '#0f766e' },
    existing: { label: 'Ya estaba', badge: '=', color: '#52525b' },
  }

  var ERRORS = {
    unauthorized: 'El token no vale. Genera uno con «jh capture token» y pégalo en las opciones.',
    forbidden:
      'La app no acepta esta extensión. Revisa JH_CAPTURE_EXTENSION_ID en .env y reinicia «jh serve».',
    capture_not_configured: 'Falta crear el token: ejecuta «jh capture token» y pégalo en las opciones.',
    database_not_ready: 'La base de datos no está al día: ejecuta «jh db upgrade».',
  }

  function jobUrl(uiUrl, jobId) {
    return String(uiUrl || DEFAULT_UI_URL).replace(/\/+$/, '') + '/jobs/' + jobId
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

  return { API_URL: API_URL, DEFAULT_UI_URL: DEFAULT_UI_URL, describe: describe, failure: failure }
})()
