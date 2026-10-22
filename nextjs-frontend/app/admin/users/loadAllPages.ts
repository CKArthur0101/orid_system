export type PagedItems<T> = {
  items: T[];
  total?: number;
};

export async function loadAllPages<T>(
  fetchPage: (page: number, pageSize: number) => Promise<PagedItems<T>>,
  pageSize = 200,
): Promise<T[]> {
  const collected: T[] = [];
  let page = 1;
  let total = Number.POSITIVE_INFINITY;

  while (collected.length < total && page <= 100) {
    const data = await fetchPage(page, pageSize);
    const batch = data.items ?? [];
    if (typeof data.total === "number" && Number.isFinite(data.total)) {
      total = data.total;
    }
    collected.push(...batch);
    if (batch.length === 0 || batch.length < pageSize) break;
    page += 1;
  }

  return collected;
}
