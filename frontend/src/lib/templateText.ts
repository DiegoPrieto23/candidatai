import { useTranslation } from 'react-i18next'

type Template = { id: string; origin: string }

/**
 * Nombre y descripción de una plantilla en el idioma de la UI. Las integradas (`origin: builtin`)
 * tienen un `id` estable y su texto traducido en `templates.builtinText`; las tuyas salen tal como
 * las llamaste, aunque compartan `id` con una integrada.
 */
export function useTemplateText() {
  const { t, i18n } = useTranslation('templates')
  const known = (template: Template) =>
    template.origin === 'builtin' && i18n.exists(`templates:builtinText.${template.id}.name`)
  return {
    name: (template: Template & { name: string }) =>
      known(template) ? t(`builtinText.${template.id}.name` as never) : template.name,
    description: (template: Template & { description: string }) =>
      known(template) ? t(`builtinText.${template.id}.description` as never) : template.description,
  }
}
