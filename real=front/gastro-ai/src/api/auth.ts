import { ApiError, USE_MOCK, mockDelay, request, setToken } from './client';
import type { AuthResponse, User } from '../types';

const USERS_KEY = 'gastro_ai_mock_users';
const SESSION_KEY = 'gastro_ai_mock_session';

interface StoredUser extends User {
  password: string;
}

function readUsers(): StoredUser[] {
  try {
    return JSON.parse(localStorage.getItem(USERS_KEY) || '[]');
  } catch {
    return [];
  }
}

function writeUsers(users: StoredUser[]) {
  localStorage.setItem(USERS_KEY, JSON.stringify(users));
}

function toPublicUser(u: StoredUser): User {
  const { password: _password, ...rest } = u;
  return rest;
}

interface FastApiLoginResponse {
  token: string;
  username: string;
  role: string;
  name: string;
}

interface FastApiProfileResponse {
  username: string;
  role: string;
  name: string;
}

export const authApi = {
  async signUp(email: string, password: string, name: string, role = 'patient'): Promise<AuthResponse> {
    if (USE_MOCK) {
      await mockDelay(700);
      const users = readUsers();
      if (users.some((u) => u.email.toLowerCase() === email.toLowerCase())) {
        throw new ApiError('An account with this email already exists.', 409);
      }
      const user: StoredUser = {
        id: crypto.randomUUID(),
        email,
        password,
        name,
        createdAt: new Date().toISOString(),
      };
      users.push(user);
      writeUsers(users);
      const token = `mock-${user.id}`;
      setToken(token);
      localStorage.setItem(SESSION_KEY, user.id);
      return { user: toPublicUser(user), token };
    }
    const res = await request<FastApiLoginResponse>('/auth/signup', {
      method: 'POST',
      body: { username: email, password, name, role },
    });
    setToken(res.token);
    const user: User = {
      id: res.username,
      email: res.username,
      name: res.name || res.username,
      role: res.role,
      createdAt: new Date().toISOString(),
    };
    return { token: res.token, user };
  },

  async signIn(email: string, password: string): Promise<AuthResponse> {
    if (USE_MOCK) {
      await mockDelay(700);
      const users = readUsers();
      const user = users.find((u) => u.email.toLowerCase() === email.toLowerCase());
      if (!user || user.password !== password) {
        throw new ApiError('Incorrect email or password.', 401);
      }
      const token = `mock-${user.id}`;
      setToken(token);
      localStorage.setItem(SESSION_KEY, user.id);
      return { user: toPublicUser(user), token };
    }
    const res = await request<FastApiLoginResponse>('/auth/login', {
      method: 'POST',
      body: { username: email, password },
    });
    setToken(res.token);
    const user: User = {
      id: res.username,
      email: res.username,
      name: res.name || res.username,
      role: res.role,
      createdAt: new Date().toISOString(),
    };
    return { token: res.token, user };
  },

  async requestPasswordReset(email: string): Promise<{ message: string }> {
    if (USE_MOCK) {
      await mockDelay(600);
      return { message: `If an account exists for ${email}, a reset link has been sent.` };
    }
    return { message: `Reset link request sent for ${email}.` };
  },

  async me(): Promise<User | null> {
    if (USE_MOCK) {
      await mockDelay(200);
      const id = localStorage.getItem(SESSION_KEY);
      if (!id) return null;
      const user = readUsers().find((u) => u.id === id);
      return user ? toPublicUser(user) : null;
    }
    try {
      const res = await request<FastApiProfileResponse>('/auth/me');
      return {
        id: res.username,
        email: res.username,
        name: res.name || res.username,
        role: res.role,
        createdAt: new Date().toISOString(),
      };
    } catch {
      return null;
    }
  },

  async signOut(): Promise<void> {
    if (USE_MOCK) {
      localStorage.removeItem(SESSION_KEY);
      setToken(null);
      return;
    }
    try {
      await request('/auth/logout', { method: 'POST' });
    } catch {
      /* noop */
    }
    setToken(null);
  },
};
