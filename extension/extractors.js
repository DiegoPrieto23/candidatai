/*
 * Extractor de la oferta que estás viendo. El service worker lo inyecta en la pestaña activa solo
 * cuando pulsas el botón (`chrome.scripting.executeScript`, permiso `activeTab`); no se queda
 * cargado en ninguna web. El valor de la última línea es lo que recibe el service worker.
 *
 * Orden: el texto seleccionado (si lo hay, se manda aparte y la app lo prefiere), el extractor del
 * sitio (LinkedIn, InfoJobs, Indeed, Tecnoempleo), el JSON-LD `JobPosting` de la página y, como
 * último recurso, `main`. Los selectores de los portales cambian: cada campo prueba varios.
 *
 * JavaScript plano y sin dependencias. `var` (no `const`) para poder inyectarlo varias veces en la
 * misma página.
 */
var jhExtract = (function () {
  'use strict'

  var MAX_TEXT = 100000
  var MAX_HTML = 500000
  var MAX_FIELD = 300 // empresa y ubicación, como admite la app
  var MAX_URL = 4000
  var SKIP = { script: 1, style: 1, noscript: 1, template: 1, svg: 1, button: 1, iframe: 1 }
  var BLOCK = {
    address: 1, article: 1, aside: 1, blockquote: 1, dd: 1, div: 1, dl: 1, dt: 1, fieldset: 1,
    figcaption: 1, figure: 1, footer: 1, form: 1, h1: 1, h2: 1, h3: 1, h4: 1, h5: 1, h6: 1,
    header: 1, hr: 1, li: 1, main: 1, nav: 1, ol: 1, p: 1, pre: 1, section: 1, table: 1, tr: 1,
    ul: 1,
  }

  var SITES = [
    {
      name: 'linkedin',
      host: /(^|\.)linkedin\.com$/,
      title: [
        '.job-details-jobs-unified-top-card__job-title h1',
        '.job-details-jobs-unified-top-card__job-title',
        '.jobs-unified-top-card__job-title',
        '.top-card-layout__title',
        'h1.t-24',
      ],
      company: [
        '.job-details-jobs-unified-top-card__company-name a',
        '.job-details-jobs-unified-top-card__company-name',
        '.jobs-unified-top-card__company-name a',
        '.jobs-unified-top-card__company-name',
        '.topcard__org-name-link',
        '.top-card-layout__second-subline a',
      ],
      location: [
        '.job-details-jobs-unified-top-card__primary-description-container .tvm__text',
        '.job-details-jobs-unified-top-card__primary-description-container',
        '.job-details-jobs-unified-top-card__bullet',
        '.jobs-unified-top-card__bullet',
        '.topcard__flavor--bullet',
      ],
      // Rediseño de /jobs/view/ (2026): clases ofuscadas; solo `componentkey` y `data-testid` son
      // estables. El texto completo está en el DOM aunque se vea plegado tras «… más».
      card: linkedinTopCard,
      description: [
        '[componentkey^="JobDetails_AboutTheJob_"] [data-testid="expandable-text-box"]',
        '[componentkey^="JobDetails_AboutTheJob_"]',
        '.jobs-description__content .jobs-box__html-content',
        '.jobs-description-content__text',
        '#job-details',
        '.jobs-description__content',
        '.show-more-less-html__markup',
        '.description__text',
      ],
    },
    {
      name: 'indeed',
      host: /(^|\.)indeed\.(com|[a-z]{2}|co\.[a-z]{2}|com\.[a-z]{2})$/,
      title: [
        '[data-testid="jobsearch-JobInfoHeader-title"]',
        'h1.jobsearch-JobInfoHeader-title',
        '.jobsearch-JobInfoHeader-title',
      ],
      company: [
        '[data-testid="inlineHeader-companyName"] a',
        '[data-testid="inlineHeader-companyName"]',
        '[data-company-name="true"]',
        '.jobsearch-CompanyInfoContainer a',
      ],
      location: [
        '[data-testid="inlineHeader-companyLocation"]',
        '[data-testid="job-location"]',
        '[data-testid="jobsearch-JobInfoHeader-companyLocation"]',
      ],
      description: ['#jobDescriptionText', '.jobsearch-jobDescriptionText'],
    },
    {
      name: 'infojobs',
      host: /(^|\.)infojobs\.net$/,
      title: ['#prefijoPuesto', '.ij-OfferDetailHeader-title', 'h1'],
      company: ['#prefijoEmpresa', '.ij-OfferDetailHeader-companyLogo + * a', '.ij-OfferDetailHeader a'],
      // Sin selectores genéricos de ubicación: el primer `li` de la cabecera puede ser el contrato,
      // y la ubicación entra en la huella. Si falta, la da el JSON-LD.
      location: ['#prefijoPoblacion'],
      description: ['#prefijoDescripcion1', '.ij-OfferDetail-description', '.ij-Box-description'],
    },
    {
      name: 'tecnoempleo',
      host: /(^|\.)tecnoempleo\.com$/,
      title: ['[itemprop="title"]', 'h1'],
      company: ['[itemprop="hiringOrganization"] [itemprop="name"]', '[itemprop="hiringOrganization"]'],
      location: ['[itemprop="jobLocation"] [itemprop="addressLocality"]', '[itemprop="jobLocation"]'],
      description: ['[itemprop="description"]'],
    },
  ]

  // --- Texto -----------------------------------------------------------------------------------

  function clean(value, limit) {
    var lines = String(value || '')
      .replace(/\r\n?/g, '\n')
      .split('\n')
      .map(function (line) {
        return line.replace(/[\s ]+/g, ' ').trim()
      })
    var out = []
    for (var i = 0; i < lines.length; i++) {
      if (lines[i] || (out.length && out[out.length - 1])) out.push(lines[i])
    }
    return out.join('\n').trim().slice(0, limit || MAX_TEXT)
  }

  function oneLine(value) {
    return clean(value, 500).replace(/\n+/g, ' ').trim()
  }

  function hiddenInline(el) {
    if (el.hidden || el.getAttribute('aria-hidden') === 'true') return true
    var style = el.getAttribute('style') || ''
    return /display\s*:\s*none|visibility\s*:\s*hidden/i.test(style)
  }

  /** Un salto de línea, sin apilarlos: un bloque tras otro no deja líneas en blanco. */
  function newline(out) {
    for (var i = out.length - 1; i >= 0; i--) {
      if (/\n[ \t]*$/.test(out[i])) return // ya acaba en salto de línea
      if (/\S/.test(out[i])) break
    }
    if (out.length) out.push('\n')
  }

  function walk(node, out) {
    if (node.nodeType === 3) {
      // Como el navegador: los saltos y espacios del código HTML son un espacio.
      out.push(String(node.nodeValue).replace(/\s+/g, ' '))
      return
    }
    if (node.nodeType !== 1) return
    var tag = node.tagName.toLowerCase()
    if (SKIP[tag] || hiddenInline(node)) return
    if (tag === 'br') {
      out.push('\n')
      return
    }
    var block = BLOCK[tag]
    if (block) newline(out)
    if (tag === 'li') out.push('• ')
    if (tag === 'td' || tag === 'th') out.push(' ')
    for (var child = node.firstChild; child; child = child.nextSibling) walk(child, out)
    if (block) newline(out)
  }

  /** Texto visible: `innerText` en el navegador (respeta el CSS); en su defecto, un recorrido. */
  function textOf(el) {
    if (!el) return ''
    if (typeof el.innerText === 'string' && el.isConnected) return clean(el.innerText)
    var out = []
    walk(el, out)
    return clean(out.join(''))
  }

  function first(doc, selectors) {
    for (var i = 0; i < (selectors || []).length; i++) {
      var found = doc.querySelectorAll(selectors[i])
      for (var j = 0; j < found.length; j++) {
        if (textOf(found[j])) return found[j]
      }
    }
    return null
  }

  /** El texto de `el` sin el de sus botones («… más»), que `innerText` sí incluye. */
  function textWithoutButtons(el) {
    var text = textOf(el)
    var buttons = el.querySelectorAll('button, [role="button"]')
    for (var i = buttons.length - 1; i >= 0; i--) {
      var label = clean(buttons[i].innerText || buttons[i].textContent || '')
      if (label && text.slice(-label.length) === label) text = clean(text.slice(0, -label.length))
    }
    return text
  }

  /**
   * Cabecera del LinkedIn rediseñado, sin clases fiables: el bloque que rodea al enlace de la
   * empresa y tiene la línea «Ciudad · hace 2 días · …». Sus párrafos son empresa, puesto y esa
   * línea, en ese orden.
   */
  function linkedinTopCard(doc) {
    var links = doc.querySelectorAll('main a[href*="/company/"]')
    for (var i = 0; i < links.length; i++) {
      var company = oneLine(textOf(links[i]))
      if (!company) continue
      var card = links[i].parentElement
      for (var depth = 0; card && depth < 10; depth++, card = card.parentElement) {
        var paragraphs = card.querySelectorAll('p')
        var texts = []
        for (var j = 0; j < paragraphs.length; j++) texts.push(oneLine(textOf(paragraphs[j])))
        var at = texts.indexOf(company)
        var meta = -1
        for (j = at + 1; at >= 0 && j < texts.length; j++) {
          if (texts[j].indexOf(' · ') >= 0) {
            meta = j
            break
          }
        }
        if (meta < 0) continue
        var title = ''
        for (j = at + 1; j < meta && !title; j++) title = texts[j]
        title = title || linkedinTitleFromDocument(doc, company)
        return { company: company, title: title, location: texts[meta] }
      }
    }
    return null
  }

  /** «(3) Data Engineer | Empresa | LinkedIn» → «Data Engineer», si la empresa coincide. */
  function linkedinTitleFromDocument(doc, company) {
    var title = oneLine(doc.title).replace(/^\(\d+\+?\)\s*/, '').replace(/\s*\|\s*LinkedIn$/i, '')
    var suffix = ' | ' + company
    if (!company || title.slice(-suffix.length) !== suffix) return ''
    return title.slice(0, -suffix.length).trim()
  }

  // --- JSON-LD ---------------------------------------------------------------------------------

  function isPosting(node) {
    var type = node && node['@type']
    return type === 'JobPosting' || (Array.isArray(type) && type.indexOf('JobPosting') >= 0)
  }

  function findPosting(data, depth) {
    if (!data || typeof data !== 'object' || depth > 6) return null
    if (Array.isArray(data)) {
      for (var i = 0; i < data.length; i++) {
        var hit = findPosting(data[i], depth + 1)
        if (hit) return hit
      }
      return null
    }
    if (isPosting(data)) return data
    return findPosting(data['@graph'], depth + 1)
  }

  function name(value) {
    if (!value) return ''
    if (typeof value === 'string') return value
    if (Array.isArray(value)) return name(value[0])
    return value.name || ''
  }

  function postingLocation(posting) {
    var places = [].concat(posting.jobLocation || [])
    var parts = []
    places.forEach(function (place) {
      var address = (place && place.address) || {}
      if (typeof address === 'string') parts.push(address)
      else {
        var bits = [address.addressLocality, address.addressRegion, name(address.addressCountry)]
        var text = bits.filter(Boolean).join(', ')
        if (text) parts.push(text)
      }
    })
    if (posting.jobLocationType === 'TELECOMMUTE') parts.push('Remoto')
    return parts.join(' / ')
  }

  function htmlToText(doc, html) {
    var parsed = new DOMParser().parseFromString(String(html), 'text/html')
    var out = []
    walk(parsed.body, out)
    return clean(out.join(''))
  }

  function fromJsonLd(doc) {
    var scripts = doc.querySelectorAll('script[type="application/ld+json"]')
    for (var i = 0; i < scripts.length; i++) {
      var data
      try {
        data = JSON.parse(scripts[i].textContent || '')
      } catch {
        continue
      }
      var posting = findPosting(data, 0)
      if (!posting) continue
      var description = String(posting.description || '')
      return {
        title: oneLine(posting.title),
        company: oneLine(name(posting.hiringOrganization)),
        location: oneLine(postingLocation(posting)),
        text: description ? htmlToText(doc, description) : '',
        html: description.slice(0, MAX_HTML),
      }
    }
    return null
  }

  // --- Página ----------------------------------------------------------------------------------

  function meta(doc, property) {
    var el = doc.querySelector('meta[property="' + property + '"], meta[name="' + property + '"]')
    return el ? oneLine(el.getAttribute('content')) : ''
  }

  function siteFor(host) {
    for (var i = 0; i < SITES.length; i++) {
      if (SITES[i].host.test(host)) return SITES[i]
    }
    return null
  }

  function hostOf(url) {
    try {
      return new URL(url).hostname.toLowerCase()
    } catch {
      return ''
    }
  }

  /** La URL sin fragmento y, si aun así es muy larga, sin parámetros (salvo `currentJobId`). */
  function shortUrl(url) {
    try {
      var parsed = new URL(url)
      parsed.hash = ''
      if (parsed.href.length > MAX_URL) {
        var jobId = parsed.searchParams.get('currentJobId')
        parsed.search = jobId ? '?currentJobId=' + encodeURIComponent(jobId) : ''
      }
      return parsed.href.slice(0, MAX_URL)
    } catch {
      return String(url).slice(0, MAX_URL)
    }
  }

  /** Datos de la oferta de `doc` (cuya URL es `url`); `selection`, el texto seleccionado. */
  function run(doc, url, selection) {
    var site = siteFor(hostOf(url))
    var result = { url: shortUrl(url), title: '', company: '', location: '', text: '', html: null, site: null }

    if (site) {
      var description = first(doc, site.description)
      result.site = site.name
      result.title = oneLine(textOf(first(doc, site.title)))
      result.company = oneLine(textOf(first(doc, site.company)))
      // LinkedIn: «Vigo, Galicia, España · hace 2 días · 30 solicitudes».
      result.location = oneLine(textOf(first(doc, site.location)))
      var card = site.card && !(result.title && result.company) ? site.card(doc) : null
      if (card) {
        result.title = result.title || card.title
        result.company = result.company || card.company
        result.location = result.location || card.location
      }
      result.location = result.location.split(' · ')[0].trim()
      if (description) {
        result.text = textWithoutButtons(description)
        result.html = description.outerHTML.slice(0, MAX_HTML)
      }
    }

    var ld = fromJsonLd(doc)
    if (ld) {
      if (!result.site) result.site = 'jsonld'
      result.title = result.title || ld.title
      result.company = result.company || ld.company
      result.location = result.location || ld.location
      if (!result.text && ld.text) {
        result.text = ld.text
        result.html = ld.html
      }
    }

    // Sin empresa no se adivina: el sitio (`og:site_name`) sería el portal, no la empresa.
    if (!result.title) result.title = meta(doc, 'og:title') || oneLine(doc.title)
    // `main` solo en webs sin extractor propio. En un portal conocido cuyo HTML ha cambiado, `main`
    // es la página entera (en LinkedIn, la lista de resultados): mejor no mandar nada y que la app
    // pida seleccionar el texto.
    if (!result.text && !site) {
      var main = doc.querySelector('main, [role="main"], article') || doc.body
      result.text = textOf(main)
      result.html = main ? main.outerHTML.slice(0, MAX_HTML) : null
      if (!result.site) result.site = 'main'
    }

    result.company = result.company.slice(0, MAX_FIELD)
    result.location = result.location.slice(0, MAX_FIELD)
    result.selection = clean(selection || '') || null
    return result
  }

  return { run: run, textOf: textOf }
})()

typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.id
  ? jhExtract.run(document, location.href, String(window.getSelection ? window.getSelection() : ''))
  : null
