import { useState } from 'react';
import { useChat } from '../context/ChatContext';
import { TopBar } from '../components/layout/TopBar';
import { WelcomeScreen } from '../components/chat/WelcomeScreen';
import { MessageList } from '../components/chat/MessageList';
import { ChatInput } from '../components/chat/ChatInput';
import { ConfirmModal } from '../components/common/ConfirmModal';
import { IconTrash } from '../components/common/Icons';

export function ChatPage() {
  const { activeConversation, sendMessage, isSending, clearConversation, activeId } = useChat();
  const [clearConfirmOpen, setClearConfirmOpen] = useState(false);

  const hasMessages = !!activeConversation && activeConversation.messages.length > 0;

  return (
    <>
      <TopBar
        title={activeConversation ? activeConversation.title : 'New chat'}
        badge="Digestive Health"
        right={
          hasMessages ? (
            <button className="btn-icon" onClick={() => setClearConfirmOpen(true)} aria-label="Clear conversation">
              <IconTrash size={17} />
            </button>
          ) : null
        }
      />

      <div className="chat-scroll">
        {hasMessages ? (
          <MessageList messages={activeConversation!.messages} />
        ) : (
          <WelcomeScreen onPick={(q) => sendMessage(q)} />
        )}
      </div>

      <ChatInput onSend={sendMessage} disabled={isSending} />

      {clearConfirmOpen && activeId && (
        <ConfirmModal
          title="Clear this conversation?"
          description="All messages in this conversation will be removed. This can't be undone."
          confirmLabel="Clear"
          onCancel={() => setClearConfirmOpen(false)}
          onConfirm={() => {
            clearConversation(activeId);
            setClearConfirmOpen(false);
          }}
        />
      )}
    </>
  );
}
