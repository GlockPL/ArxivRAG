import { marked } from 'marked';
import markedKatex from 'marked-katex-extension';
import { markedHighlight } from 'marked-highlight';
import DOMPurify from 'dompurify';
import Prism from 'prismjs';
import 'katex/dist/katex.min.css';
import 'prismjs/themes/prism-tomorrow.css';

// Import common languages
import 'prismjs/components/prism-javascript';
import 'prismjs/components/prism-typescript';
import 'prismjs/components/prism-css';
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-bash';
import 'prismjs/components/prism-json';
import 'prismjs/components/prism-markdown';

marked.use({
  breaks: true,         // Convert \n to <br>
  gfm: true,            // GitHub Flavored Markdown
});

// Highlight code blocks while rendering, so streamed messages need no extra pass over the DOM
marked.use(markedHighlight({
  langPrefix: 'language-',
  highlight(code, lang) {
    const grammar = Prism.languages[lang];
    return grammar ? Prism.highlight(code, grammar, lang) : code;
  }
}));

// Render $...$ and $$...$$ with KaTeX while parsing, so math in streamed messages needs no later typesetting
marked.use(markedKatex({ throwOnError: false, nonStandard: true }));

/**
 * Renders markdown text to sanitized HTML using marked with KaTeX math and Prism syntax highlighting
 * @param {string|object} text - The markdown text to render
 * @returns {string} The rendered HTML, safe to use with v-html
 */
export function renderMarkdown(text) {
  // Handle empty input
  if (!text) return '';
  // Handle non-string input
  if (typeof text !== 'string') {
    try {
      // Try to convert objects to string representation
      text = JSON.stringify(text, null, 2);
    } catch (e) {
      console.error('Failed to process markdown object:', e);
      text = String(text);
    }
  }

  // Pre-process code blocks to ensure proper formatting
  const processedText = text.replace(/```(.*?)\n([\s\S]*?)```/g, (match, lang, code) => {
    return `\n\`\`\`${lang}\n${code}\n\`\`\`\n`;
  });
  // Model output can contain text from retrieved documents, so it must never reach v-html unsanitized
  return DOMPurify.sanitize(marked.parse(processedText));
}
