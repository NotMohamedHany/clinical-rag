import { API_URL, USE_MOCK, getToken, mockDelay, request } from './client';
import { findMockAnswer } from './mockData';
import type { ChatRequest, ChatResponse, SourceRef } from '../types';

interface FastApiChatResponse {
  session_id: string;
  answer: string;
  sources: Array<{ source: string; page: number; type?: string }>;
}

export const chatApi = {
  /**
   * Sends a user message + conversation id to the RAG backend and returns
   * the generated answer along with the retrieved sources.
   */
  async sendMessage(payload: ChatRequest): Promise<ChatResponse> {
    if (USE_MOCK) {
      await mockDelay(900 + Math.random() * 600);
      const { answer, sources } = findMockAnswer(payload.message);
      return { answer, sources };
    }
    const res = await request<FastApiChatResponse>('/chat', {
      method: 'POST',
      body: { session_id: payload.conversation_id, message: payload.message },
    });
    const sources: SourceRef[] = (res.sources || []).map((s) => ({
      title: `${s.source} (page ${s.page})`,
      url: '#',
    }));
    return { answer: res.answer, sources };
  },

  /**
   * Stream agent response in real time via SSE events from /chat/stream
   */
  async streamMessage(
    payload: ChatRequest,
    onToken: (token: string) => void,
    onFinal: (answer: string, sources: SourceRef[]) => void,
    onError: (err: string) => void
  ): Promise<void> {
    if (USE_MOCK) {
      const res = await this.sendMessage(payload);
      onFinal(res.answer, res.sources);
      return;
    }

    const token = getToken();
    try {
      const response = await fetch(`${API_URL}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          session_id: payload.conversation_id,
          message: payload.message,
        }),
      });

      if (!response.ok) {
        onError(`Streaming failed (${response.status})`);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) return;

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const blocks = buffer.split('\n\n');
        buffer = blocks.pop() || '';

        for (const block of blocks) {
          const lines = block.split('\n');
          let eventType = '';
          let dataStr = '';

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith('data: ')) {
              dataStr = line.slice(6).trim();
            }
          }

          if (!dataStr) continue;

          try {
            const data = JSON.parse(dataStr);
            if (eventType === 'token' && data.token) {
              onToken(data.token);
            } else if (eventType === 'final') {
              const mappedSources: SourceRef[] = (data.sources || []).map((s: any) => ({
                title: `${s.source} (page ${s.page})`,
                url: '#',
              }));
              onFinal(data.answer || '', mappedSources);
            } else if (eventType === 'error') {
              onError(data.error || 'Stream error');
            }
          } catch {
            /* noop */
          }
        }
      }
    } catch (exc: any) {
      onError(exc?.message || 'Network error during streaming');
    }
  },
};
