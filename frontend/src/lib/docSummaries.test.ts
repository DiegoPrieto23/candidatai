import { describe, expect, it } from 'vitest'
import { cvSummary, letterSummary, type Say } from './docSummaries'

// Devuelve la clave con sus valores, para ver qué se dice sin depender de los textos.
const say: Say = (key, values) => (values ? `${key}(${Object.values(values).join('|')})` : key)
const names = { template: (id: string) => id.toUpperCase(), region: (code: string) => `[${code}]` }

describe('docSummaries', () => {
  it('resume el CV: plantilla, páginas, foto con sus excepciones, indicaciones y lo que evitar', () => {
    expect(cvSummary({ photo_policy: { default: true } }, say, names)).toBe('cv.templateAuto · cv.photoOn')
    expect(
      cvSummary(
        {
          default_template: 'clasica',
          max_pages: 2,
          photo_policy: { default: true, by_country: { US: false, GB: false, ES: true } },
          instructions: 'Destaca los datos',
          avoid: ['a', 'b'],
        },
        say,
        names,
      ),
    ).toBe('cv.template(CLASICA) · cv.pages(2) · cv.photoExcept(cv.photoOn|[US], [GB]) · cv.instructions · cv.avoid(2)')
    expect(cvSummary({ photo_policy: { default: false }, instructions: '   ' }, say, names)).toBe('cv.templateAuto · cv.photoOff')
    // Valores raros del YAML: lo que no es sí o no, no cuenta como excepción.
    expect(cvSummary({ photo_policy: { default: true, by_country: { US: null, FR: 'no', XX: false } } }, say, names)).toBe(
      'cv.templateAuto · cv.photoExcept(cv.photoOn|[XX])',
    )
  })

  it('resume la carta y dice si no hay nada elegido', () => {
    expect(letterSummary(null, say, 'es')).toBe('letter.none')
    expect(letterSummary({ sign_off: { es: '  ' } }, say, 'es')).toBe('letter.none')
    expect(
      letterSummary({ tone: 'cercano', max_words: 300, default_format: 'pdf', sign_off: { es: 'Un saludo', en: 'Best' } }, say, 'en'),
    ).toBe('letter.tone(cercano) · letter.words(300) · letter.pdf · letter.signOff(Best)')
    expect(letterSummary({ sign_off: { es: 'Un saludo' }, instructions: 'x', avoid: ['y'] }, say, 'en')).toBe(
      'letter.signOff(Un saludo) · letter.instructions · letter.avoid(1)',
    )
  })
})
