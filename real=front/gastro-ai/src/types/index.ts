export interface User {
  id: string;
  email: string;
  name: string;
  role?: string;
  avatarColor?: string;
  createdAt: string;
}

export interface AuthResponse {
  user: User;
  token: string;
}

export type MessageRole = 'user' | 'ai';

export interface SourceRef {
  title: string;
  url: string;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  createdAt: string;
  sources?: SourceRef[];
  liked?: boolean;
  disliked?: boolean;
  pending?: boolean;
}

export interface Conversation {
  id: string;
  title: string;
  updatedAt: string;
  createdAt: string;
  messages: ChatMessage[];
}

export interface ChatRequest {
  message: string;
  conversation_id: string;
}

export interface ChatResponse {
  answer: string;
  sources: SourceRef[];
  tools_used_count?: number;
  tools_used?: string[];
}

export type ThemeMode = 'light' | 'dark' | 'system';

export interface NotificationSettings {
  productUpdates: boolean;
  chatSummaries: boolean;
}

export interface ToastItem {
  id: string;
  type: 'info' | 'error' | 'success';
  message: string;
}
