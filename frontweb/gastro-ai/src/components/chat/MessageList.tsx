import { useEffect, useRef } from 'react';
import type { ChatMessage } from '../../types';
import { MessageBubble } from './MessageBubble';
import { useChat } from '../../context/ChatContext';

interface MessageListProps {
  messages: ChatMessage[];
}

export function MessageList({ messages }: MessageListProps) {
  const { streamingMessageId, regenerate, toggleLike, toggleDislike } = useChat();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length, messages[messages.length - 1]?.content]);

  return (
    <div className="chat-inner">
      {messages.map((m) => (
        <MessageBubble
          key={m.id}
          message={m}
          isStreaming={streamingMessageId === m.id}
          onRegenerate={regenerate}
          onToggleLike={toggleLike}
          onToggleDislike={toggleDislike}
        />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
