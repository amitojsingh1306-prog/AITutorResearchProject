import { useState } from "react";

interface MarkdownContentProps {
  content: string;
}

type Block =
  | { type: "paragraph"; text: string }
  | { type: "code"; text: string; language: string }
  | { type: "heading"; text: string }
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

    const fence = /^ {0,3}(`{3,}|~{3,})\s*([\w+#.-]*)[^\n]*$/.exec(line);
    if (fence) {
      flushParagraph();
      const marker = fence[1][0];
      const size = fence[1].length;
      const code: string[] = [];
      index += 1;
      // An unfinished block is still rendered while the response streams.
      while (index < lines.length) {
        const closing = /^ {0,3}(`{3,}|~{3,})\s*$/.exec(lines[index]);
        if (closing && closing[1][0] === marker && closing[1].length >= size) break;
        code.push(lines[index]);
        index += 1;
      }
      blocks.push({ type: "code", text: code.join("\n"), language: fence[2].toLowerCase() });
      continue;
    }

    const heading = /^ {0,3}#{1,6}\s+(.+)$/.exec(line);
    if (heading) {
      flushParagraph();
      blocks.push({ type: "heading", text: heading[1] });
      continue;
    }

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
  const parts = text.split(/(`[^`\n]+`|\*\*[^*]+\*\*)/g);

  return (
    <>
      {parts.map((part, index) => {
        if (part.startsWith("`") && part.endsWith("`")) {
          return <code key={`inline-${index}`} className="rounded bg-white/[0.08] px-1.5 py-0.5 font-mono text-[0.9em] text-violet-200">{part.slice(1, -1)}</code>;
        }
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

function CodePanel({ text, language }: { text: string; language: string }) {
  const [status, setStatus] = useState<"idle" | "copied" | "failed">("idle");
  const labels: Record<string, string> = {
    py: "Python", python: "Python", sql: "SQL", bash: "Bash", sh: "Shell",
    shell: "Shell", zsh: "Zsh", js: "JavaScript", javascript: "JavaScript",
    ts: "TypeScript", typescript: "TypeScript", json: "JSON", cpp: "C++",
    c: "C", java: "Java", html: "HTML", css: "CSS", text: "Text",
  };
  const label = labels[language] ?? (language || "Code");
  async function copyCode() {
    try {
      await navigator.clipboard.writeText(text);
      setStatus("copied");
    } catch {
      setStatus("failed");
    }
  }
  return (
    <section aria-label={`${label} code block`} className="min-w-0 overflow-hidden rounded-2xl border border-white/10 bg-[#252525] shadow-sm">
      <div className="flex items-center justify-between gap-3 px-4 py-3 text-sm text-slate-200">
        <span className="flex min-w-0 items-center gap-2 font-medium"><span aria-hidden="true" className="font-mono text-lg">&lt;/&gt;</span><span className="truncate">{label}</span></span>
        <button type="button" aria-label={`Copy ${label} code`} onClick={() => void copyCode()}
          className="flex shrink-0 items-center gap-1.5 rounded-md px-2 py-1 text-xs text-slate-300 transition hover:bg-white/10 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet-300">
          <svg aria-hidden="true" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><rect x="8" y="3" width="12" height="14" rx="3"/><path d="M16 17v2a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h2"/></svg>
          {status === "copied" ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="m-0 overflow-x-auto px-4 pb-5 pt-1 font-mono text-[13px] leading-6 text-violet-200 sm:text-sm"><code className={language ? `language-${language}` : undefined}>{text}</code></pre>
      <span role="status" className={status === "failed" ? "block px-4 pb-3 text-xs text-amber-200" : "sr-only"}>
        {status === "failed" ? "Could not copy. Select the code and copy it manually." : status === "copied" ? "Code copied to clipboard." : ""}
      </span>
    </section>
  );
}

export function MarkdownContent({ content }: MarkdownContentProps) {
  const blocks = parseMarkdown(content);

  return (
    <div className="space-y-5">
      {blocks.map((block, index) => {
        if (block.type === "code") return <CodePanel key={`code-${index}`} text={block.text} language={block.language} />;
        if (block.type === "heading") return <h3 key={`heading-${index}`} className="text-base font-semibold text-white"><InlineMarkdown text={block.text} /></h3>;
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
