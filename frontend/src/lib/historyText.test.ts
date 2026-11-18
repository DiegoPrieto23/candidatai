import { describe, expect, it } from 'vitest'
import { byBlock, fieldLabel, valueText, versionSummary, versionWhen, type ItemChange, type Say } from './historyText'

// Devuelve la clave con sus valores; las de campo que «existen», con un nombre.
const KNOWN: Record<string, string> = {
  'history.fields.level': 'Nivel',
  'history.fields.summary': 'Resumen',
  'history.fields.locations_preferred': 'Ubicaciones: cualquier modalidad',
  'levels.F': 'F · fuerte',
  'blocks.skills.title': 'Skills',
  'blocks.experience.title': 'Experiencia',
}
const say: Say = (key, values) => KNOWN[key] ?? (values ? `${key}(${Object.values(values).join('|')})` : key)
const country = (code: string) => `[${code}]`

describe('historyText', () => {
  const now = new Date(2026, 10, 18, 12, 0)

  it('dice cuándo: hoy, ayer, este año y otro año; en una frase, en minúscula', () => {
    const at = (y: number, m: number, d: number) => new Date(y, m, d, 9, 5).toISOString()
    const time = new Intl.DateTimeFormat('es-ES', { hour: '2-digit', minute: '2-digit' }).format(new Date(2026, 0, 1, 9, 5))
    expect(versionWhen(at(2026, 10, 18), say, 'es-ES', { now })).toBe(`history.when.today(${time})`)
    expect(versionWhen(at(2026, 10, 17), say, 'es-ES', { now })).toBe(`history.when.yesterday(${time})`)
    expect(versionWhen(at(2026, 10, 18), say, 'es-ES', { now, inline: true })).toBe(`history.when.todayInline(${time})`)
    expect(versionWhen(at(2026, 10, 12), say, 'es-ES', { now })).toMatch(/^history\.when\.other\(12 nov\|/)
    expect(versionWhen(at(2025, 10, 12), say, 'es-ES', { now })).toMatch(/^history\.when\.other\(12 nov 2025\|/)
  })

  it('nombra cada campo sin claves del YAML', () => {
    expect(fieldLabel(['level'], say, country)).toBe('Nivel')
    expect(fieldLabel(['summary', 'en'], say, country)).toBe('history.inLanguage(Resumen|history.languages.en)')
    expect(fieldLabel(['photo_policy', 'by_country', 'FR'], say, country)).toBe('history.fields.photo_in([FR])')
    expect(fieldLabel(['locations', 'preferred'], say, country)).toBe('Ubicaciones: cualquier modalidad')
    expect(fieldLabel(['algo_nuevo'], say, country)).toBe('Algo nuevo')
  })

  it('lee cada valor como una persona', () => {
    expect(valueText(['nda'], true, say, 'es-ES')).toBe('history.yes')
    expect(valueText(['metrics'], null, say, 'es-ES')).toBe('history.empty')
    expect(valueText(['end'], 'present', say, 'es-ES')).toBe('fields.present')
    expect(valueText(['start'], '2026-03', say, 'es-ES')).toBe('marzo de 2026')
    expect(valueText(['level'], 'F', say, 'es-ES')).toBe('F · fuerte')
    expect(valueText(['level'], 'B2', say, 'es-ES')).toBe('B2')
    expect(valueText(['roles'], ['A', 'B'], say, 'es-ES')).toBe('A, B')
  })

  it('resume una versión por bloques y agrupa sus cambios', () => {
    expect(versionSummary({ first: true, summary: [] }, say)).toBe('history.first')
    expect(versionSummary({ first: false, summary: [] }, say)).toBe('history.noChanges')
    expect(
      versionSummary(
        {
          first: false,
          summary: [
            { block: 'skills', changes: 2 },
            { block: 'private', changes: 1 },
          ],
        },
        say,
      ),
    ).toBe('history.count(Skills|2) · history.privateChanged(history.blocks.private)')
    const change = (block: ItemChange['block'], label: string): ItemChange => ({ block, kind: 'changed', label, fields: [], hidden: false })
    const groups = byBlock([change('experience', 'a'), change('skills', 'b'), change('experience', 'c')])
    expect(groups.map(([block, items]) => [block, items.map((i) => i.label)])).toEqual([
      ['experience', ['a', 'c']],
      ['skills', ['b']],
    ])
  })
})
