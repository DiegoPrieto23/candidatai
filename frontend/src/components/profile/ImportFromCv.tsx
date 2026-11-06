/** «Importar información desde un CV», en «Mi perfil» con perfil: subir un CV y que tu agente traiga
 * a tu perfil lo que le falte. Es lo mismo que «Crear mi perfil desde mi CV» (`StartFromCv`), pero
 * sobre un perfil que ya existe: no cambia ni borra nada sin preguntar. No tiene que ver con
 * «Subir nueva plantilla» (Plantillas), que usa un CV solo como ejemplo de diseño. */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { FileArrowUpIcon } from '@phosphor-icons/react'
import { useSourceDocuments } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { UploadCv } from '@/components/profile/StartFromCv'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'

export function ImportFromCv() {
  const { t } = useTranslation('profile', { keyPrefix: 'import' })
  const { t: tAgent } = useTranslation('agent')
  const [open, setOpen] = useState(false)
  const latest = useSourceDocuments('cv').data?.[0]
  return (
    <>
      <Button type="button" variant="outline" size="sm" onClick={() => setOpen(true)}>
        <FileArrowUpIcon />
        {t('button')}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('title')}</DialogTitle>
            <DialogDescription>{t('intro')}</DialogDescription>
          </DialogHeader>
          <ol className="grid gap-5 text-sm">
            <li className="space-y-3">
              <p className="font-medium">{t('stepUpload')}</p>
              <UploadCv />
            </li>
            <li className="space-y-3">
              <p className="font-medium">{t('stepAgent')}</p>
              <AgentButton action="import-profile-from-cv" primary={Boolean(latest)}>
                {tAgent('actions.import-profile-from-cv')}
              </AgentButton>
            </li>
          </ol>
        </DialogContent>
      </Dialog>
    </>
  )
}
