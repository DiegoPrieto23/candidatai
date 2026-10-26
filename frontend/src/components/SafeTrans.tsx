import type { ComponentProps } from 'react'
import { Trans } from 'react-i18next'

/**
 * `Trans` para textos con `values` que vienen de fuera (el servidor, una web, una oferta). `Trans`
 * interpola antes de leer las etiquetas del texto y la app no escapa (`escapeValue: false`, React
 * ya lo hace): un valor con `<strong>` se tomaría por marcado. Aquí se escapan los valores al
 * interpolar y se desescapan al pintar, así que se ven tal cual, como texto (fase 23.6).
 */
type Props = Omit<ComponentProps<typeof Trans>, 'i18nKey'> & { i18nKey: string }

export function SafeTrans({ i18nKey, ...props }: Props) {
  // La clave la comprueba el `t` que se pasa (con su espacio de nombres y prefijo).
  return (
    <Trans shouldUnescape tOptions={{ interpolation: { escapeValue: true } }} i18nKey={i18nKey as never} {...props} />
  )
}
