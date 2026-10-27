import { studentHeaderName, studentHelloLine } from "@/lib/student-display-name";

describe("teacher demo display name", () => {
  const demo = { display_name: "鄒欣潔老師體驗", email: "501demo" };
  const student = { display_name: "王小明", email: "50101" };

  it("addresses the experience account as a teacher", () => {
    expect(studentHeaderName(demo)).toBe("鄒欣潔 老師");
    expect(studentHelloLine(demo)).toBe("哈囉，鄒欣潔 老師！");
  });

  it("keeps real students as classmates", () => {
    expect(studentHeaderName(student)).toBe("王小明 同學");
    expect(studentHelloLine(student)).toBe("哈囉，王小明同學！");
  });
});
