import { marked } from 'marked'
import hljs from 'highlight.js'

// Set up marked.js with modern configuration
const markedOptions = {
    breaks: true,
    mangle: false,
    headerIds: false
}

// Set up the renderer with highlight.js integration
const renderer = new marked.Renderer()

// Define custom code block rendering
renderer.code = function (code, language) {
    // Check if code is a token object from marked parser
    if (typeof code === 'object' && code.type === 'code' && 'text' in code) {
        // Use the text property from the token
        code = code.text;
        // If language isn't specified but the token has it, use that
        if (!language && code.lang) {
            language = code.lang;
        }
    } else if (code === null || code === undefined) {
        code = '';
    } else if (typeof code === 'object') {
        // Pretty print other objects
        try {
            code = JSON.stringify(code, null, 2);
        } catch (e) {
            console.error('Failed to stringify object:', e);
            code = String(code);
        }
    } else if (typeof code !== 'string') {
        code = String(code);
    }

    const validLanguage = language && hljs.getLanguage(language) ? language : null
    const highlighted = validLanguage
        ? hljs.highlight(code, { language: validLanguage }).value
        : hljs.highlightAuto(code).value

    return `<pre><code class="hljs ${language || ''}">${highlighted}</code></pre>`
}
// Apply the options and renderer to marked
marked.use(markedOptions, { renderer })

export function renderMarkdown(text) {
    if (!text) return ''

    // If the input is already a parsed token or token array, stringify it back to markdown
    if (typeof text === 'object') {
        if (Array.isArray(text)) {
            // Handle array of tokens
            return text.map(token => {
                if (token.type === 'code') {
                    return `\`\`\`${token.lang || ''}\n${token.text}\n\`\`\``;
                }
                return token.raw || JSON.stringify(token);
            }).join('\n');
        } else if (text.type === 'code') {
            // Handle single code token
            return `<pre><code class="hljs ${text.lang || ''}">${hljs.highlightAuto(text.text).value
                }</code></pre>`;
        }

        // For other objects, try to stringify
        try {
            return marked.parse(JSON.stringify(text, null, 2) || '');
        } catch (e) {
            console.error('Failed to process markdown object:', e);
            return '';
        }
    }

    // Process regular string input
    return marked.parse(text || '');
}

// A reliable function to check if MathJax is ready
export function waitForMathJax() {
    return new Promise((resolve) => {
        // If MathJax is already ready, resolve immediately
        if (window.isMathJaxReady && window.MathJax && window.MathJax.typesetPromise) {
            return resolve()
        }

        // Set up a counter to avoid infinite loops
        let attempts = 0
        const maxAttempts = 30 // Try for 15 seconds (30 * 500ms)

        const checkMathJax = () => {
            attempts++

            // If MathJax is ready or we've reached max attempts, resolve
            if ((window.MathJax && window.MathJax.typesetPromise) || attempts >= maxAttempts) {
                window.isMathJaxReady = true
                return resolve()
            }

            // Otherwise, check again after a delay
            setTimeout(checkMathJax, 500)
        }

        // Start checking
        checkMathJax()
    })
}

// Process LaTeX in the rendered content
export async function processLatex() {
    try {
        // Wait for MathJax to be ready
        await waitForMathJax()

        // Only proceed if we have MathJax
        if (window.MathJax && window.MathJax.typesetPromise) {
            await window.MathJax.typesetPromise()
                .catch((err) => console.error('MathJax typesetting failed:', err))
            console.log('LaTeX processing complete')
        }
    } catch (err) {
        console.error('Error in processLatex:', err)
    }
}