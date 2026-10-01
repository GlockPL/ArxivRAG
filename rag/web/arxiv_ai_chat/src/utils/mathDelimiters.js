// Code spans and fenced code blocks, where backslashes and dollar signs must stay as they are
const CODE = /(```[\s\S]*?```|`[^`\n]*`)/

/**
 * Convert LaTeX delimiters \( ... \) and \[ ... \] to $ ... $ and $$ ... $$.
 * Models often use the backslash forms, which the KaTeX markdown extension does not recognise,
 * and markdown would otherwise unescape them to plain ( and [.
 * Display math is kept on one line, so it also renders inside lists and other blocks.
 * @param {string} text - markdown text
 * @returns {string} markdown with dollar math delimiters
 */
export function normalizeMathDelimiters(text) {
  return text
    .split(CODE)
    .map((part, index) => {
      // Odd parts are the code matched by the capturing split
      if (index % 2 === 1) return part
      return part
        .replace(/\\\[([\s\S]+?)\\\]/g, (match, math) => `$$${math.trim().replace(/\s*\n\s*/g, ' ')}$$`)
        .replace(/\\\(([\s\S]+?)\\\)/g, (match, math) => `$${math.trim()}$`)
    })
    .join('')
}
