import { describe, expect, it } from 'vitest'
import { codeName, codeOptions, findCode, knownCodes } from './codes'

describe('idiomas y países por su nombre', () => {
  it('reconoce el nombre en los dos idiomas de la UI, sin tildes ni mayúsculas', () => {
    expect(findCode('language', 'francés', 'es')).toBe('fr')
    expect(findCode('language', 'FRANCES', 'es')).toBe('fr')
    expect(findCode('language', 'French', 'en')).toBe('fr')
    expect(findCode('region', 'Reino Unido', 'es')).toBe('GB')
    expect(findCode('region', 'united kingdom', 'en')).toBe('GB')
    // Escrito en inglés con la UI en español, también.
    expect(findCode('region', 'Germany', 'es')).toBe('DE')
  })

  it('acepta el código, también uno antiguo, y lo guarda en su forma de siempre', () => {
    expect(findCode('language', 'EN', 'es')).toBe('en')
    expect(findCode('region', 'es', 'es')).toBe('ES')
    expect(findCode('region', 'UK', 'en')).toBe('GB')
  })

  it('no inventa: lo que no es un idioma o un país da null', () => {
    expect(findCode('language', 'klingon', 'es')).toBeNull()
    expect(findCode('region', 'Unión Europea', 'es')).toBeNull()
    expect(findCode('region', 'ZZ', 'es')).toBeNull()
    expect(findCode('language', '', 'es')).toBeNull()
  })

  it('nombra los códigos en el idioma de la UI y los ordena por nombre', () => {
    expect(codeName('language', 'de', 'es')).toBe('alemán')
    expect(codeName('region', 'DE', 'en')).toBe('Germany')
    const names = codeOptions('region', 'es').map((o) => o.name)
    expect(names.indexOf('Alemania')).toBeLessThan(names.indexOf('España'))
    expect(knownCodes('region')).not.toContain('UK')
    expect(knownCodes('language')).toContain('eu')
  })
})
