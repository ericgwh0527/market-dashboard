/**
 * Tiny, safe Markdown for the AI brief. Supports only what the prompt asks for:
 * paragraphs, **bold**, *italic*, and "-"/"*" bullet lists.
 *
 * Why not a full Markdown library? The brief is written by an AI from news
 * headlines, and a crafted headline could make it emit [links](javascript:…)
 * or tracking images. Here all text is escaped first, and links/images/HTML
 * are never produced.
 */
import { esc } from "../core/dom.js";

const inline = (s) =>
  esc(s)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*(?!\s)(.+?)\*(?!\*)/g, "$1<em>$2</em>");

export function renderSafeMarkdown(text) {
  const out = [];
  let list = null, para = [];
  const flushPara = () => { if (para.length) { out.push(`<p>${para.map(inline).join("<br>")}</p>`); para = []; } };
  const flushList = () => { if (list) { out.push(`<ul>${list.map((li) => `<li>${inline(li)}</li>`).join("")}</ul>`); list = null; } };

  for (const raw of String(text ?? "").split(/\r?\n/)) {
    const line = raw.trimEnd();
    const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
    if (bullet) { flushPara(); (list ??= []).push(bullet[1]); continue; }
    if (!line.trim()) { flushPara(); flushList(); continue; }
    flushList();
    para.push(line.replace(/^#+\s*/, ""));   // headings become plain paragraphs
  }
  flushPara(); flushList();
  return out.join("");
}
