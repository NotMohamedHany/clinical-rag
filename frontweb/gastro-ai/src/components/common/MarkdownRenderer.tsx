import { Fragment, useState } from 'react';
import { parseInline, parseMarkdown } from '../../utils/markdown';
import { IconCheck, IconCopy } from './Icons';

function Inline({ text }: { text: string }) {
  const tokens = parseInline(text);
  return (
    <>
      {tokens.map((t, i) => {
        if (t.bold) return <strong key={i}>{t.text}</strong>;
        if (t.code) return <code key={i}>{t.text}</code>;
        if (t.italic) return <em key={i}>{t.text}</em>;
        return <Fragment key={i}>{t.text}</Fragment>;
      })}
    </>
  );
}

function CodeBlock({ lang, code }: { lang: string; code: string }) {
  const [copied, setCopied] = useState(false);
  const onCopy = () => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };
  return (
    <div className="code-block">
      <div className="code-block-head">
        <span>{lang || 'code'}</span>
        <button className="copy-mini" onClick={onCopy}>
          {copied ? <IconCheck size={13} /> : <IconCopy size={13} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre><code>{code}</code></pre>
    </div>
  );
}

export function MarkdownRenderer({ content }: { content: string }) {
  const blocks = parseMarkdown(content);
  return (
    <div className="markdown-body">
      {blocks.map((block, i) => {
        if (block.type === 'heading') {
          const Tag = (`h${block.level}` as unknown) as 'h2' | 'h3' | 'h4';
          return (
            <Tag key={i} style={{ marginTop: i === 0 ? 0 : 14, marginBottom: 6, fontSize: block.level === 2 ? 17 : 15 }}>
              <Inline text={block.text} />
            </Tag>
          );
        }
        if (block.type === 'paragraph') {
          return (
            <p key={i}>
              <Inline text={block.text} />
            </p>
          );
        }
        if (block.type === 'list') {
          const ListTag = block.ordered ? 'ol' : 'ul';
          return (
            <ListTag key={i}>
              {block.items.map((item, j) => (
                <li key={j}>
                  <Inline text={item} />
                </li>
              ))}
            </ListTag>
          );
        }
        if (block.type === 'code') {
          return <CodeBlock key={i} lang={block.lang} code={block.code} />;
        }
        if (block.type === 'table') {
          return (
            <table key={i} style={{ width: '100%', borderCollapse: 'collapse', margin: '10px 0', fontSize: 13 }}>
              <thead>
                <tr>
                  {block.headers.map((h, hi) => (
                    <th key={hi} style={{ textAlign: 'left', borderBottom: '1px solid var(--border)', padding: '6px 8px', color: 'var(--ink-muted)' }}>
                      <Inline text={h} />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {block.rows.map((row, ri) => (
                  <tr key={ri}>
                    {row.map((cell, ci) => (
                      <td key={ci} style={{ borderBottom: '1px solid var(--border)', padding: '6px 8px' }}>
                        <Inline text={cell} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          );
        }
        return null;
      })}
    </div>
  );
}
