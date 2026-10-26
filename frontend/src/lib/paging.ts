/** Las listas largas van de 25 en 25: se ve el final sin tanto desplazamiento. */
export const LIST_PAGE_SIZE = 25

/** La página `page` de una lista que ya está entera en memoria. */
export function pageOf<T>(items: T[], page: number, pageSize = LIST_PAGE_SIZE): T[] {
  return items.slice((page - 1) * pageSize, page * pageSize)
}
