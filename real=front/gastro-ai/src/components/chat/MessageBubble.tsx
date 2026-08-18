import { useState } from 'react';
import type { ChatMessage } from '../../types';
import { formatTime } from '../../utils/formatDate';
import { MarkdownRenderer } from '../common/MarkdownRenderer';
import { SourcesPanel } from './SourcesPanel';
import {
  IconCheck,
  IconCopy,
  IconRefresh,
  IconStethoscope,
  IconThumbsDown,
  IconThumbsUp,
} from '../common/Icons';
import { useAuth } from '../../context/AuthContext';

interface MessageBubbleProps {
  message: ChatMessage;
  isStreaming: boolean;
  onRegenerate: (id: string) => void;
  onToggleLike: (id: string) => void;
  onToggleDislike: (id: string) => void;
}

export function MessageBubble({ message, isStreaming, onRegenerate, onToggleLike, onToggleDislike }: MessageBubbleProps) {
  const { user } = useAuth();
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  return (
    <div className={`msg-row ${isUser ? 'user' : 'ai'}`}>
      <div className={`avatar ${isUser ? 'avatar-user' : 'avatar-ai'}`}>
        {isUser ? (user?.name || 'U').slice(0, 1).toUpperCase() : <IconStethoscope size={15} />}
      </div>
      <div className="msg-col">
        <div className="msg-bubble">
          {message.pending && !message.content ? (
            <span className="typing-dots"><span /><span /><span /></span>
          ) : (
            <>
              <MarkdownRenderer content={message.content} />
              {isStreaming && <span className="cursor-blink" />}
            </>
          )}
        </div>

        {!isUser && !message.pending && message.sources && <SourcesPanel sources={message.sources} />}

        <div className="msg-meta">
          <span>{formatTime(message.createdAt)}</span>
        </div>

        {!message.pending && (
          <div className="msg-actions">
            <button className="btn-icon" onClick={handleCopy} aria-label="Copy">
              {copied ? <IconCheck size={14} /> : <IconCopy size={14} />}
            </button>
            {!isUser && (
              <>
                <button className="btn-icon" onClick={() => onRegenerate(message.id)} aria-label="Regenerate">
                  <IconRefresh size={14} />
                </button>
                <button
                  className={`btn-icon ${message.liked ? 'liked' : ''}`}
                  onClick={() => onToggleLike(message.id)}
                  aria-label="Like"
                >
                  <IconThumbsUp size={14} />
                </button>
                <button
                  className={`btn-icon ${message.disliked ? 'disliked' : ''}`}
                  onClick={() => onToggleDislike(message.id)}
                  aria-label="Dislike"
                >
                  <IconThumbsDown size={14} />
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
