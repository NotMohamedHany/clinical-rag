import { USE_MOCK, mockDelay, request } from './client';
import type { Conversation, ChatMessage } from '../types';

const STORE_KEY = 'gastro_ai_mock_conversations';

interface FastApiSessionInfo {
  session_id: string;
  message_count: number;
  created_at: string;
  last_active: string;
  role: string;
}

interface FastApiSessionList {
  total: number;
  sessions: FastApiSessionInfo[];
}

interface FastApiSessionHistory {
  session_id: string;
  messages: Array<{ role: string; content: string }>;
}

function readStore(): Record<string, Conversation[]> {
  try {
    return JSON.parse(localStorage.getItem(STORE_KEY) || '{}');
  } catch {
    return {};
  }
}

function writeStore(store: Record<string, Conversation[]>) {
  localStorage.setItem(STORE_KEY, JSON.stringify(store));
}

export const conversationsApi = {
  async list(userId: string): Promise<Conversation[]> {
    if (USE_MOCK) {
      await mockDelay(250);
      const store = readStore();
      return (store[userId] || []).sort(
        (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
      );
    }
    try {
      const res = await request<FastApiSessionList>('/chat/sessions');
      const sessions = res.sessions || [];

      const conversations = await Promise.all(
        sessions.map(async (s) => {
          let messages: ChatMessage[] = [];
          try {
            const histRes = await request<FastApiSessionHistory>(`/chat/sessions/${s.session_id}/history`);
            messages = (histRes.messages || []).map((m) => ({
              id: crypto.randomUUID(),
              role: m.role === 'assistant' ? 'ai' : 'user',
              content: m.content,
              createdAt: s.created_at || new Date().toISOString(),
            }));
          } catch {
            /* noop */
          }

          const firstUserMsg = messages.find((m) => m.role === 'user');
          const title = firstUserMsg
            ? (firstUserMsg.content.slice(0, 40) + (firstUserMsg.content.length > 40 ? '…' : ''))
            : `Session ${s.session_id.slice(0, 8)}`;

          return {
            id: s.session_id,
            title,
            updatedAt: s.last_active,
            createdAt: s.created_at,
            messages,
          };
        })
      );

      return conversations.sort(
        (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
      );
    } catch (err) {
      console.error('Failed to fetch user sessions:', err);
      return [];
    }
  },

  async getHistory(session_id: string): Promise<ChatMessage[]> {
    if (USE_MOCK) {
      return [];
    }
    try {
      const res = await request<FastApiSessionHistory>(`/chat/sessions/${session_id}/history`);
      return (res.messages || []).map((m) => ({
        id: crypto.randomUUID(),
        role: m.role === 'assistant' ? 'ai' : 'user',
        content: m.content,
        createdAt: new Date().toISOString(),
      }));
    } catch {
      return [];
    }
  },

  async create(userId: string, title = 'New conversation'): Promise<Conversation> {
    const newId = crypto.randomUUID().slice(0, 8);
    if (USE_MOCK) {
      await mockDelay(150);
      const store = readStore();
      const list = store[userId] || [];
      const convo: Conversation = {
        id: newId,
        title,
        messages: [],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };
      store[userId] = [convo, ...list];
      writeStore(store);
      return convo;
    }
    return {
      id: newId,
      title,
      messages: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
  },

  async update(userId: string, conversation: Conversation): Promise<Conversation> {
    if (USE_MOCK) {
      await mockDelay(80);
      const store = readStore();
      const list = store[userId] || [];
      const idx = list.findIndex((c) => c.id === conversation.id);
      const updated = { ...conversation, updatedAt: new Date().toISOString() };
      if (idx >= 0) list[idx] = updated;
      else list.unshift(updated);
      store[userId] = list;
      writeStore(store);
      return updated;
    }
    return conversation;
  },

  async rename(userId: string, id: string, title: string): Promise<void> {
    if (USE_MOCK) {
      await mockDelay(120);
      const store = readStore();
      const list = store[userId] || [];
      const idx = list.findIndex((c) => c.id === id);
      if (idx >= 0) {
        list[idx] = { ...list[idx], title, updatedAt: new Date().toISOString() };
        store[userId] = list;
        writeStore(store);
      }
    }
  },

  async remove(userId: string, id: string): Promise<void> {
    if (USE_MOCK) {
      await mockDelay(120);
      const store = readStore();
      store[userId] = (store[userId] || []).filter((c) => c.id !== id);
      writeStore(store);
      return;
    }
    try {
      await request(`/chat/sessions/${id}`, { method: 'DELETE' });
    } catch {
      /* noop */
    }
  },
};
