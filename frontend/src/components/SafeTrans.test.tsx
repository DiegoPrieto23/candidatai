import { render } from '@testing-library/react'
import { useTranslation } from 'react-i18next'
import { describe, expect, it } from 'vitest'
import { SafeTrans } from '@/components/SafeTrans'

function Hint({ file }: { file: string }) {
  const { t } = useTranslation('network', { keyPrefix: 'import' })
  return (
    <p>
      <SafeTrans t={t} i18nKey="hint" values={{ file }} components={{ code: <code /> }} />
    </p>
  )
}

describe('SafeTrans', () => {
  it('pinta como texto un valor con etiquetas, sin convertirlas en marcado', () => {
    const { container } = render(<Hint file={'x</code><strong>fake</strong> & <b>y</b>'} />)
    expect(container.querySelector('strong')).toBeNull()
    expect(container.querySelectorAll('code')).toHaveLength(1)
    expect(container.querySelector('code')).toHaveTextContent('data/x</code><strong>fake</strong> & <b>y</b>')
  })
})
