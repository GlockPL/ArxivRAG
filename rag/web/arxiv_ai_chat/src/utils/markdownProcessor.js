import { marked } from 'marked';
import Prism from 'prismjs';

// Import common languages
import 'prismjs/components/prism-javascript';
import 'prismjs/components/prism-typescript';
import 'prismjs/components/prism-css';
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-bash';
import 'prismjs/components/prism-json';
import 'prismjs/components/prism-markdown';

// Set up marked.js with modern configuration
const markedOptions = {
  breaks: true,         // Convert \n to <br>
  mangle: false,        // Don't escape HTML in output
  headerIds: false,     // Don't add ids to headers
  gfm: true,            // GitHub Flavored Markdown
  smartLists: true,     // Use smarter list behavior
}

// Create custom renderer
const renderer = new marked.Renderer();

// Customize code block rendering to use Prism
// renderer.code = function(code, language) {
//     console.log(`code: ${code}`)
//   // Ensure code is a string
//   if (code === null || code === undefined) {
//     code = '';
//   } else if (typeof code !== 'string') {
//     code = String(code);
//   }

//   // Clean up line breaks
//   code = code.replace(/\\n/g, '\n');
  
//   // Set default language to plaintext if not specified
//   language = language || 'python';
//   console.log(`language: ${language}`)
  
//   let highlighted;
//   try {
//     // Check if Prism has this language
//     if (!Prism.languages[language]) {
//       try {
//         // Try to dynamically load the language
//         require(`prismjs/components/prism-${language}`);
//       } catch (e) {
//         // Fallback to plaintext if language isn't available
//         language = 'plaintext';
//       }
//     }
//     // Apply syntax highlighting with Prism
//     highlighted = Prism.highlight(code, Prism.languages[language] || Prism.languages.plaintext, language);
//     console.log(`highlighted: ${highlighted}`)
//   } catch (e) {
//     // Fallback to escaped plain text if highlighting fails
//     console.error('Error highlighting code:', e);
//     highlighted = escapeHtml(code);
//   }
  
//   // Return the highlighted code in a pre/code block with appropriate class
//   return `<pre><code class="language-${language}">${highlighted}</code></pre>`;
// };

// Helper function to escape HTML for fallback cases
function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

marked.use({
    ...markedOptions,
    hooks: {
      postprocess(html) {
        // Add a callback to apply Prism highlighting after the HTML is generated
        setTimeout(() => Prism.highlightAll(), 0);
        return html;
      }
    }
  });

/**
 * Renders markdown text to HTML using marked with Prism syntax highlighting
 * @param {string|object} text - The markdown text to render
 * @returns {string} The rendered HTML
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
  let processedText = text.replace(/```(.*?)\n([\s\S]*?)```/g, (match, lang, code) => {
    return `\n\`\`\`${lang}\n${code}\n\`\`\`\n`;
  });
  let parsedText = marked.parse(processedText);
  // Parse and return the markdown
  return parsedText
}

/**
 * Reapplies Prism highlighting to any code blocks in the document
 * Call this after dynamically inserting rendered markdown into the DOM
 */
export function rehighlightCode() {
  Prism.highlightAll();
}