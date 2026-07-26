interface MarkdownContentProps {
  content: string;
}

type Block =
  | { type: "paragraph"; text: string }
  | { type: "table"; headers: string[]; rows: string[][] };

function splitTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function isTableDivider(line: string): boolean {
  const cells = splitTableRow(line);
  return (
    cells.length > 1 &&
    cells.every((cell) => /^:?-{3,}:?$/.test(cell.replace(/\s/g, "")))
  );
}

function parseMarkdown(content: string): Block[] {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let paragraph: string[] = [];

  function flushParagraph() {
    if (paragraph.length === 0) return;
    blocks.push({ type: "paragraph", text: paragraph.join("\n").trim() });
    paragraph = [];
  }

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const nextLine = lines[index + 1];

    if (line.includes("|") && nextLine && isTableDivider(nextLine)) {
      flushParagraph();
      const headers = splitTableRow(line);
      const rows: string[][] = [];
      index += 2;

      while (index < lines.length && lines[index].includes("|")) {
        rows.push(splitTableRow(lines[index]));
        index += 1;
      }

      blocks.push({ type: "table", headers, rows });
      index -= 1;
      continue;
    }

    if (line.trim() === "") {
      flushParagraph();
      continue;
    }

    paragraph.push(line);
  }

  flushParagraph();
  return blocks;
}

function InlineMarkdown({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);

  return (
    <>
      {parts.map((part, index) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return (
            <strong key={`${part}-${index}`} className="font-semibold text-white">
              {part.slice(2, -2)}
            </strong>
          );
        }

        return <span key={`${part}-${index}`}>{part}</span>;
      })}
    </>
  );
}

export function MarkdownContent({ content }: MarkdownContentProps) {
  const blocks = parseMarkdown(content);

  return (
    <div className="space-y-5">
      {blocks.map((block, index) => {
        if (block.type === "table") {
          return (
            <div
              key={`table-${index}`}
              className="overflow-x-auto border-y border-white/[0.08]"
            >
              <table className="w-full min-w-[680px] border-collapse text-left text-[15px] leading-7">
                <thead>
                  <tr className="border-b border-white/[0.12]">
                    {block.headers.map((header) => (
                      <th
                        key={header}
                        scope="col"
                        className="px-0 py-3 pr-8 align-top font-semibold text-white last:pr-0"
                      >
                        <InlineMarkdown text={header} />
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.07]">
                  {block.rows.map((row, rowIndex) => (
                    <tr key={`row-${rowIndex}`}>
                      {block.headers.map((header, cellIndex) => (
                        <td
                          key={`${header}-${cellIndex}`}
                          className={`px-0 py-5 pr-8 align-top text-slate-200 last:pr-0 ${
                            cellIndex === 0 ? "font-semibold text-white" : ""
                          }`}
                        >
                          <InlineMarkdown text={row[cellIndex] ?? ""} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }

        return (
          <p
            key={`paragraph-${index}`}
            className="whitespace-pre-wrap break-words text-[15px] leading-7 text-slate-200"
          >
            <InlineMarkdown text={block.text} />
          </p>
        );
      })}
    </div>
  );
}
