import { loadAllPages } from "@/app/admin/users/loadAllPages";

describe("loadAllPages", () => {
  it("keeps requesting pages until every account is loaded", async () => {
    const pages = [
      { items: ["50801", "50802", "50803"], total: 5 },
      { items: ["50901", "509teacher"], total: 5 },
    ];

    const loaded = await loadAllPages(async (page) => pages[page - 1], 3);

    expect(loaded).toEqual(["50801", "50802", "50803", "50901", "509teacher"]);
  });

  it("stops when a page comes back short", async () => {
    const fetchPage = jest.fn(async (page: number) =>
      page === 1
        ? { items: ["50101", "50102"], total: 99 }
        : { items: ["50901"], total: 99 },
    );

    const loaded = await loadAllPages(fetchPage, 2);

    expect(loaded).toEqual(["50101", "50102", "50901"]);
    expect(fetchPage).toHaveBeenCalledTimes(2);
  });
});
