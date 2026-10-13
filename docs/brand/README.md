# Marca de CandidatAI

El logo es el **torso de una persona con un sello de verificado en lugar de la cabeza**: un
candidato y la idea de *candid* (honesto, verificado, sin nada inventado), que es lo que distingue
a la app. Plano, sin degradados ni adornos (fase 23.5a, elegido por el usuario entre varias
propuestas).

| Fichero | Para qué |
|---|---|
| `mark.svg` | Isotipo (el símbolo en su cuadrado). La fuente de todos los iconos |
| `mark-mono.svg` | Símbolo solo, de un color (`currentColor`): sellos, marcas de agua, fondos de color |
| `logo.svg` | Isotipo + «CandidatAI» para fondo claro |
| `logo-dark.svg` | Lo mismo para fondo oscuro |

## Colores

| | Hex | Uso |
|---|---|---|
| Verde | `#0F766E` | El cuadrado del isotipo y el «AI» del logotipo en fondo claro |
| Verde claro | `#5EEAD4` | El «AI» en fondo oscuro |
| Tinta | `#18181B` | «Candidat» en fondo claro |
| Blanco | `#FFFFFF` | La figura dentro del cuadrado (la ✓ del sello va en verde) |

## Uso

- **Tamaño mínimo:** 16 px (favicon). Por debajo de 24 px, solo el isotipo, nunca el logotipo.
- **Margen:** al menos un cuarto del lado del isotipo alrededor.
- **Logotipo:** «Candidat» y «AI» en la misma palabra, con el «AI» en verde. Nunca «Candidat AI»
  separado, ni «CandidatAi».
- **No:** degradados, sombras, contornos, girar el símbolo, cambiar sus proporciones o ponerlo sobre
  fotos sin el cuadrado.

## Generar los iconos

Los PNG de la extensión, el favicon, el `apple-touch-icon` y el `.ico` de Windows salen de
`mark.svg` con:

```
cd backend
uv run python ../scripts/build_icons.py
```

El texto del logotipo usa la pila de fuentes del sistema (Geist si está instalada; si no, Segoe
UI o Helvetica). Para una pieza impresa o externa, conviértelo a trazados con un editor de SVG.
