import { useEditableProfile, usePlatforms } from '@/api/queries'

/** Los primeros pasos que faltan en Inicio (perfil y dónde buscar); `null` mientras no se sabe. */
export function useFirstStepsLeft(): number | null {
  const profile = useEditableProfile()
  const platforms = usePlatforms()
  if (!profile.isSuccess || !platforms.isSuccess) return null
  return Number(!profile.data.exists) + Number(platforms.data.sources.length === 0)
}
