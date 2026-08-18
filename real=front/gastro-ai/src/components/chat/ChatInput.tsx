import { useRef, useState, type ChangeEvent, type KeyboardEvent } from 'react';
import { useAutoResizeTextarea } from '../../hooks/useAutoResizeTextarea';
import { IconArrowUp, IconPaperclip, IconX } from '../common/Icons';

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [text, setText] = useState('');
  const [attachment, setAttachment] = useState<File | null>(null);
  const textareaRef = useAutoResizeTextarea(text);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = () => {
    const value = text.trim();
    if (!value || disabled) return;
    onSend(value);
    setText('');
    setAttachment(null);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) setAttachment(file);
  };

  return (
    <div className="composer-wrap">
      <div className="composer">
        <div className="composer-actions-left">
          <button className="btn-icon" onClick={() => fileInputRef.current?.click()} aria-label="Attach file">
            <IconPaperclip size={17} />
          </button>
          <input ref={fileInputRef} type="file" hidden onChange={handleFileChange} />
        </div>

        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about a digestive symptom or condition…"
          rows={1}
          disabled={disabled}
        />

        <div className="composer-actions-right">
          <button className="composer-send" onClick={handleSend} disabled={disabled || !text.trim()} aria-label="Send message">
            <IconArrowUp size={17} />
          </button>
        </div>
      </div>

      {attachment && (
        <div style={{ maxWidth: 760, margin: '8px auto 0', display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, color: 'var(--ink-muted)' }}>
          <IconPaperclip size={13} />
          {attachment.name}
          <button className="btn-icon" style={{ width: 20, height: 20 }} onClick={() => setAttachment(null)}>
            <IconX size={12} />
          </button>
        </div>
      )}

      <div className="composer-hint">Gastro AI can make mistakes. Verify important information with a healthcare professional.</div>
    </div>
  );
}
