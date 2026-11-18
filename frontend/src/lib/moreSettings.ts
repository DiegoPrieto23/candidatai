/**
 * «Más ajustes» de «Buscar ofertas», sin React: qué claves de `preferences` cambia, cómo se leen del
 * perfil, cómo quedan al restablecer y cuántos grupos tienen algo puesto (el número del botón).
 */
import {
  CONTRACT_TYPES,
  type ContractType,
  type EmployerKind,
  type EmploymentType,
  type ExcludeSignal,
  type Preferences,
} from '@/components/profile/types'

export interface MoreDraft {
  min_years_required: number | null
  max_years_required: number | null
  languages_for_work: string[]
  discard_title_keywords: string[]
  contract_types: ContractType[]
  employment_types: EmploymentType[]
  excluded_employer_kinds: EmployerKind[]
  exclude_signals: ExcludeSignal[]
}

/**
 * `exclude_signals: [fixed_term]` es lo mismo que no aceptar `fixed_term`: se enseña como «Temporal»
 * sin marcar y, al guardar, queda escrito solo en `contract_types`.
 */
export function readMore(prefs: Preferences): MoreDraft {
  const signals = prefs.exclude_signals ?? []
  const accepted = prefs.contract_types ?? []
  const contract_types = signals.includes('fixed_term')
    ? (accepted.length ? accepted : [...CONTRACT_TYPES]).filter((c) => c !== 'fixed_term')
    : accepted
  return {
    min_years_required: prefs.min_years_required ?? null,
    max_years_required: prefs.max_years_required ?? null,
    languages_for_work: prefs.languages_for_work ?? [],
    discard_title_keywords: prefs.discard_title_keywords ?? [],
    contract_types,
    employment_types: prefs.employment_types ?? [],
    excluded_employer_kinds: prefs.excluded_employer_kinds ?? [],
    exclude_signals: signals.filter((s) => s !== 'fixed_term'),
  }
}

/** Sin ningún filtro de estos (las señales que la pantalla no enseña se quedan como estaban). */
export function clearedMore(draft: MoreDraft): MoreDraft {
  return {
    min_years_required: null,
    max_years_required: null,
    languages_for_work: [],
    discard_title_keywords: [],
    contract_types: [],
    employment_types: [],
    excluded_employer_kinds: [],
    exclude_signals: draft.exclude_signals.filter((s) => s !== 'employer_hidden'),
  }
}

export type MoreGroup = 'experience' | 'languages' | 'contract' | 'discard'

/** Los grupos que tienen algo puesto (el sueldo mínimo cuenta en «Experiencia y sueldo»). */
export function activeGroups(draft: MoreDraft, salary: number | null): Set<MoreGroup> {
  const on = new Set<MoreGroup>()
  if (draft.min_years_required != null || draft.max_years_required != null || salary != null) on.add('experience')
  if (draft.languages_for_work.length > 0) on.add('languages')
  if (draft.contract_types.length > 0 || draft.employment_types.length > 0) on.add('contract')
  if (draft.discard_title_keywords.length > 0 || draft.excluded_employer_kinds.length > 0 || draft.exclude_signals.includes('employer_hidden')) {
    on.add('discard')
  }
  return on
}

/** Cuántos grupos de «Más ajustes» tienen algo puesto: el número del botón. */
export function countMore(prefs: Preferences, salary: number | null): number {
  return activeGroups(readMore(prefs), salary).size
}
