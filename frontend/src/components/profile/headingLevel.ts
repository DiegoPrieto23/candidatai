import { createContext } from 'react'

/** El nivel del título de cada bloque: 2 en «Mi perfil»; 3 donde van dentro de una sección con su `h2`. */
export const BlockHeadingLevel = createContext<2 | 3>(2)
