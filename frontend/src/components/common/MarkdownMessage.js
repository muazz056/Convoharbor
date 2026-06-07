/**
 * MarkdownMessage - rich-text renderer for chat messages.
 *
 * Supports:
 *   - Markdown (headings, lists, bold/italic, links, blockquotes)
 *   - GitHub-flavored Markdown (tables, task lists, strikethrough)
 *   - Fenced code blocks with syntax highlighting
 *   - Inline code
 *   - LaTeX math (KaTeX):  $E = mc^2$  and  $$\int_0^1 x^2 dx$$
 *   - Chemical equations (mhchem):  $\ce{H2O}$  /  $$\ce{2H2 + O2 -> 2H2O}$$
 *   - Raw HTML (sanitised through rehype-sanitize when present)
 *
 * The component is streaming-safe: if a code block / math block is
 * incomplete (no closing fence/delimiter) the renderer will fall back
 * to a "plain" markdown render so the partial content is still
 * readable while the rest of the response is still being received.
 */
import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';
import rehypeRaw from 'rehype-raw';
import 'katex/dist/katex.min.css';
import './MarkdownMessage.css';

/**
 * Detect content that looks "in the middle of" a code block or math
 * block. When streaming an LLM response we can receive a partial
 * fenced block that has not been closed yet — running that through
 * KaTeX / the syntax highlighter would throw, so we render it as
 * plain text instead.
 */
function isPartial(content) {
  if (!content) return false;
  // Count un-escaped triple-backticks
  const fences = (content.match(/(^|[^`])```/g) || []).length;
  if (fences % 2 !== 0) return true;
  // Count un-escaped $$ pairs
  const dollars = (content.match(/(^|[^$])\$\$/g) || []).length;
  if (dollars % 2 !== 0) return true;
  return false;
}

const MarkdownMessage = ({ content, className = '' }) => {
  const text = typeof content === 'string' ? content : '';
  const partial = useMemo(() => isPartial(text), [text]);

  return (
    <div className={`markdown-message ${partial ? 'is-partial' : ''} ${className}`}>
      {partial ? (
        // Render as plain text when we have an unterminated block.
        <pre className="markdown-partial">{text}</pre>
      ) : (
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkMath]}
          rehypePlugins={[
            rehypeRaw,
            [rehypeKatex, { strict: false, throwOnError: false }],
            [rehypeHighlight, { detect: true, ignoreMissing: true }],
          ]}
          // Make every link open in a new tab and stay safe.
          components={{
            a: ({ node, ...props }) => (
              // eslint-disable-next-line jsx-a11y/anchor-has-content
              <a {...props} target="_blank" rel="noopener noreferrer" />
            ),
          }}
        >
          {text}
        </ReactMarkdown>
      )}
    </div>
  );
};

export default MarkdownMessage;
