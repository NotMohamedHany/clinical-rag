import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { chatApi } from '../api/chat';
import { conversationsApi } from '../api/conversations';
import { useAuth } from './AuthContext';
import type { ChatMessage, Conversation } from '../types';

interface ChatContextValue {
  conversations: Conversation[];
  filteredConversations: Conversation[];
  activeConversation: Conversation | null;
  activeId: string | null;
  isLoadingConversations: boolean;
  isSending: boolean;
  streamingMessageId: string | null;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  selectConversation: (id: string) => void;
  startNewConversation: () => void;
  deleteConversation: (id: string) => Promise<void>;
  renameConversation: (id: string, title: string) => Promise<void>;
  clearConversation: (id: string) => void;
  sendMessage: (text: string) => Promise<void>;
  regenerate: (messageId: string) => Promise<void>;
  toggleLike: (messageId: string) => void;
  toggleDislike: (messageId: string) => void;
}

const ChatContext = createContext<ChatContextValue | undefined>(undefined);

function titleFromMessage(text: string): string {
  const trimmed = text.trim().replace(/\s+/g, ' ');
  return trimmed.length > 46 ? `${trimmed.slice(0, 46)}…` : trimmed || 'New conversation';
}

export function ChatProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [isLoadingConversations, setIsLoadingConversations] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const streamTimer = useRef<number | null>(null);

  useEffect(() => {
    if (!user) {
      setConversations([]);
      setActiveId(null);
      setIsLoadingConversations(false);
      return;
    }
    setIsLoadingConversations(true);
    conversationsApi.list(user.id).then((list) => {
      setConversations(list);
      setIsLoadingConversations(false);
    });
  }, [user]);

  const persist = useCallback(
    (convo: Conversation) => {
      if (!user) return;
      conversationsApi.update(user.id, convo);
    },
    [user]
  );

  const updateConversation = useCallback(
    (id: string, updater: (c: Conversation) => Conversation) => {
      setConversations((prev) => {
        const next = prev.map((c) => (c.id === id ? updater(c) : c));
        const updated = next.find((c) => c.id === id);
        if (updated) persist(updated);
        return next;
      });
    },
    [persist]
  );

  const selectConversation = useCallback((id: string) => setActiveId(id), []);

  const startNewConversation = useCallback(() => {
    setActiveId(null);
  }, []);

  const ensureActiveConversation = useCallback(
    async (firstMessageText: string): Promise<Conversation> => {
      if (activeId) {
        const existing = conversations.find((c) => c.id === activeId);
        if (existing) return existing;
      }
      if (!user) throw new Error('Not authenticated');
      const created = await conversationsApi.create(user.id, titleFromMessage(firstMessageText));
      setConversations((prev) => [created, ...prev]);
      setActiveId(created.id);
      return created;
    },
    [activeId, conversations, user]
  );

  const deleteConversation = useCallback(
    async (id: string) => {
      if (!user) return;
      await conversationsApi.remove(user.id, id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeId === id) setActiveId(null);
    },
    [user, activeId]
  );

  const renameConversation = useCallback(
    async (id: string, title: string) => {
      if (!user) return;
      await conversationsApi.rename(user.id, id, title);
      setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, title } : c)));
    },
    [user]
  );

  const clearConversation = useCallback(
    (id: string) => {
      updateConversation(id, (c) => ({ ...c, messages: [] }));
    },
    [updateConversation]
  );

  const streamAnswer = useCallback(
    (conversationId: string, messageId: string, fullText: string) => {
      return new Promise<void>((resolve) => {
        setStreamingMessageId(messageId);
        let index = 0;
        const chunkSize = Math.max(2, Math.round(fullText.length / 90));

        const tick = () => {
          index = Math.min(fullText.length, index + chunkSize);
          const partial = fullText.slice(0, index);
          updateConversation(conversationId, (c) => ({
            ...c,
            messages: c.messages.map((m) => (m.id === messageId ? { ...m, content: partial } : m)),
          }));
          if (index < fullText.length) {
            streamTimer.current = window.setTimeout(tick, 18);
          } else {
            setStreamingMessageId(null);
            resolve();
          }
        };
        tick();
      });
    },
    [updateConversation]
  );

  const runAssistantTurn = useCallback(
    async (conversationId: string, userText: string) => {
      const aiMessageId = crypto.randomUUID();
      const placeholder: ChatMessage = {
        id: aiMessageId,
        role: 'ai',
        content: '',
        createdAt: new Date().toISOString(),
        pending: true,
      };
      updateConversation(conversationId, (c) => ({ ...c, messages: [...c.messages, placeholder] }));
      setIsSending(true);
      try {
        const res = await chatApi.sendMessage({ message: userText, conversation_id: conversationId });
        updateConversation(conversationId, (c) => ({
          ...c,
          messages: c.messages.map((m) =>
            m.id === aiMessageId ? { ...m, pending: false, sources: res.sources } : m
          ),
        }));
        await streamAnswer(conversationId, aiMessageId, res.answer);
      } catch {
        updateConversation(conversationId, (c) => ({
          ...c,
          messages: c.messages.map((m) =>
            m.id === aiMessageId
              ? {
                  ...m,
                  pending: false,
                  content:
                    "Something went wrong reaching the assistant. Please check your connection and try again.",
                }
              : m
          ),
        }));
      } finally {
        setIsSending(false);
      }
    },
    [streamAnswer, updateConversation]
  );

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      const convo = await ensureActiveConversation(trimmed);
      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'user',
        content: trimmed,
        createdAt: new Date().toISOString(),
      };
      updateConversation(convo.id, (c) => ({ ...c, messages: [...c.messages, userMessage] }));
      await runAssistantTurn(convo.id, trimmed);
    },
    [ensureActiveConversation, runAssistantTurn, updateConversation]
  );

  const regenerate = useCallback(
    async (messageId: string) => {
      if (!activeId) return;
      const convo = conversations.find((c) => c.id === activeId);
      if (!convo) return;
      const idx = convo.messages.findIndex((m) => m.id === messageId);
      if (idx < 0) return;
      const priorUser = [...convo.messages.slice(0, idx)].reverse().find((m) => m.role === 'user');
      if (!priorUser) return;
      updateConversation(activeId, (c) => ({
        ...c,
        messages: c.messages.filter((m) => m.id !== messageId),
      }));
      await runAssistantTurn(activeId, priorUser.content);
    },
    [activeId, conversations, runAssistantTurn, updateConversation]
  );

  const toggleLike = useCallback(
    (messageId: string) => {
      if (!activeId) return;
      updateConversation(activeId, (c) => ({
        ...c,
        messages: c.messages.map((m) =>
          m.id === messageId ? { ...m, liked: !m.liked, disliked: false } : m
        ),
      }));
    },
    [activeId, updateConversation]
  );

  const toggleDislike = useCallback(
    (messageId: string) => {
      if (!activeId) return;
      updateConversation(activeId, (c) => ({
        ...c,
        messages: c.messages.map((m) =>
          m.id === messageId ? { ...m, disliked: !m.disliked, liked: false } : m
        ),
      }));
    },
    [activeId, updateConversation]
  );

  const activeConversation = useMemo(
    () => conversations.find((c) => c.id === activeId) || null,
    [conversations, activeId]
  );

  const filteredConversations = useMemo(() => {
    if (!searchQuery.trim()) return conversations;
    const q = searchQuery.toLowerCase();
    return conversations.filter((c) => c.title.toLowerCase().includes(q));
  }, [conversations, searchQuery]);

  const value: ChatContextValue = {
    conversations,
    filteredConversations,
    activeConversation,
    activeId,
    isLoadingConversations,
    isSending,
    streamingMessageId,
    searchQuery,
    setSearchQuery,
    selectConversation,
    startNewConversation,
    deleteConversation,
    renameConversation,
    clearConversation,
    sendMessage,
    regenerate,
    toggleLike,
    toggleDislike,
  };

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error('useChat must be used within ChatProvider');
  return ctx;
}
