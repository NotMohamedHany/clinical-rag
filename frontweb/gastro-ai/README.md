# Medica — Clinical Guidelines Assistant

A premium, production-ready frontend for an AI medical chat assistant focused on
stomach and digestive system conditions. Built with React + TypeScript + Vite,
structured to plug directly into a RAG backend (FastAPI/Flask).

## Getting started

```bash
npm install
cp .env.example .env
npm run dev
```

The app opens at `http://localhost:5173`.

By default `VITE_USE_MOCK_API=true`, so the app runs entirely on an in-memory /
localStorage-backed mock service — no backend required. Create an account with
any email/password to try it out immediately.

### Connecting a real backend

1. Set `VITE_API_URL` to your backend's base URL (e.g. `http://localhost:8000`).
2. Set `VITE_USE_MOCK_API=false`.
3. Implement these endpoints (see `src/api/*.ts` for exact request/response shapes):
   - `POST /api/auth/signup`, `POST /api/auth/signin`, `POST /api/auth/forgot-password`, `GET /api/user/me`
   - `POST /api/chat` — accepts `{ message, conversation_id }`, returns `{ answer, sources }`
   - `GET/POST/PUT/PATCH/DELETE /api/conversations`
   - `POST /api/voice/speak`, `POST /api/voice/transcribe` (optional — the app
     uses the browser's Web Speech API by default and only calls these if you
     want server-side TTS/STT)
   - `GET/PUT /api/user/preferences`, `PUT /api/user/profile`

The frontend never hardcodes medical answers — `/api/chat` is expected to be
backed by a retrieval-augmented generation pipeline, and every AI response
renders whatever `sources` the backend returns underneath the message.

## Project structure

```
src/
  api/          # Centralized service layer (auth, chat, conversations, voice, user) + mock fallbacks
  components/
    auth/       # Sign in / sign up building blocks
    chat/       # Welcome screen, message list/bubble, composer, sources panel
    common/     # Buttons, icons, markdown renderer, toasts, modals
    layout/     # Sidebar, top bar, protected route, app shell
    voice/      # Voice orb + full-screen voice conversation mode
  context/      # Auth, theme, chat, layout, toast, voice-settings providers
  hooks/        # useSpeechRecognition, useSpeechSynthesis, useAutoResizeTextarea, useOutsideClick
  pages/        # Routed pages (SignIn, SignUp, Chat, Settings, NotFound)
  styles/       # Design tokens (CSS variables) + global stylesheet
  types/        # Shared TypeScript types
  utils/        # Markdown parser, date formatting, validators, constants
```

## Notable implementation details

- **Auth**: full sign up / sign in flow with show/hide password, validation,
  loading states, "remember me", forgot-password UI, and protected routing
  that redirects unauthenticated users to `/sign-in`.
- **Chat**: streaming-style AI responses, markdown + code-block rendering with
  copy buttons, regenerate, like/dislike, per-message text-to-speech, and a
  "Sources" panel rendered directly from the RAG backend's response.
- **Voice input**: browser `SpeechRecognition` wrapped in `useSpeechRecognition`,
  with a clear listening state and editable transcript before sending.
- **Voice output**: browser `SpeechSynthesis` wrapped in `useSpeechSynthesis`,
  with global rate/voice controls in Settings, plus a dedicated full-screen
  **Voice Conversation Mode** with an animated orb reflecting listening /
  thinking / speaking state.
- **Theming**: light/dark/system, implemented with CSS variables and a
  `data-theme` attribute, transitioning smoothly.
- **Responsive**: sidebar becomes a mobile drawer under 900px; touch-friendly
  controls throughout.
- **Safety**: a persistent, non-intrusive medical disclaimer on the welcome
  screen; the assistant never claims to be a doctor or offers a certain
  diagnosis by design (enforced at the backend/prompt level — the frontend
  only renders what it's given).

## Environment variables

See `.env.example`. `VITE_API_URL` points at your backend; `VITE_USE_MOCK_API`
forces the local mock service even if a backend URL is set, which is useful
for frontend-only demos.
