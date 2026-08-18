import { USE_MOCK, mockDelay, request } from './client';
import type { NotificationSettings, User } from '../types';

const PREFS_KEY = 'gastro_ai_mock_prefs';

interface UserPrefs {
  notifications: NotificationSettings;
}

const DEFAULT_PREFS: UserPrefs = {
  notifications: { productUpdates: true, chatSummaries: false },
};

function readAllPrefs(): Record<string, UserPrefs> {
  try {
    return JSON.parse(localStorage.getItem(PREFS_KEY) || '{}');
  } catch {
    return {};
  }
}

export const userApi = {
  async getPreferences(userId: string): Promise<UserPrefs> {
    if (USE_MOCK) {
      await mockDelay(100);
      const all = readAllPrefs();
      return all[userId] || DEFAULT_PREFS;
    }
    return request<UserPrefs>('/api/user/preferences');
  },

  async savePreferences(userId: string, prefs: UserPrefs): Promise<void> {
    if (USE_MOCK) {
      await mockDelay(100);
      const all = readAllPrefs();
      all[userId] = prefs;
      localStorage.setItem(PREFS_KEY, JSON.stringify(all));
      return;
    }
    await request('/api/user/preferences', { method: 'PUT', body: prefs });
  },

  async updateProfile(_userId: string, updates: Partial<User>): Promise<void> {
    if (USE_MOCK) {
      await mockDelay(300);
      return;
    }
    await request('/api/user/profile', { method: 'PUT', body: updates });
  },
};
