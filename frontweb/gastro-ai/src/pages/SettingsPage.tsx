import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { TopBar } from '../components/layout/TopBar';
import { Avatar } from '../components/common/Avatar';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { useToast } from '../context/ToastContext';
import { IconMonitor, IconMoon, IconSun } from '../components/common/Icons';

export function SettingsPage() {
  const { user, signOut } = useAuth();
  const { mode, setMode } = useTheme();
  const { push } = useToast();
  const navigate = useNavigate();

  const [notifications, setNotifications] = useState({
    productUpdates: true,
    chatSummaries: true,
  });

  const handleSignOut = async () => {
    await signOut();
    navigate('/sign-in', { replace: true });
  };

  return (
    <>
      <TopBar title="Settings" />

      <div className="chat-scroll">
        <div className="settings-container">
          <div className="settings-card">
            <h3>Profile</h3>
            <p className="settings-card-sub">Your account details and role.</p>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <Avatar name={user?.name || 'User'} size="lg" />
              <div>
                <div style={{ fontWeight: 700, fontSize: 16 }}>{user?.name}</div>
                <div style={{ fontSize: 13, color: 'var(--ink-muted)' }}>Username: {user?.id}</div>
                {user?.role && (
                  <div style={{ fontSize: 12, color: 'var(--brand-strong)', textTransform: 'capitalize', marginTop: 4, fontWeight: 600 }}>
                    Role: {user.role}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="settings-card">
            <h3>Appearance</h3>
            <p className="settings-card-sub">Choose how Gastro AI looks on your device.</p>
            <div className="theme-switch-group">
              <button
                className={`theme-switch-opt ${mode === 'light' ? 'active' : ''}`}
                onClick={() => setMode('light')}
              >
                <IconSun size={15} /> Light
              </button>
              <button
                className={`theme-switch-opt ${mode === 'dark' ? 'active' : ''}`}
                onClick={() => setMode('dark')}
              >
                <IconMoon size={15} /> Dark
              </button>
              <button
                className={`theme-switch-opt ${mode === 'system' ? 'active' : ''}`}
                onClick={() => setMode('system')}
              >
                <IconMonitor size={15} /> System
              </button>
            </div>
          </div>

          <div className="settings-card">
            <h3>Notifications</h3>
            <p className="settings-card-sub">Choose what Gastro AI can notify you about.</p>
            <div className="settings-row">
              <div>
                <div className="settings-row-label">Product updates</div>
                <div className="settings-row-desc">New features and improvements.</div>
              </div>
              <button
                className={`toggle ${notifications.productUpdates ? 'on' : ''}`}
                onClick={() => setNotifications((prev) => ({ ...prev, productUpdates: !prev.productUpdates }))}
              >
                <span className="toggle-knob" />
              </button>
            </div>
            <div className="settings-row">
              <div>
                <div className="settings-row-label">Chat summaries</div>
                <div className="settings-row-desc">Weekly digest of your conversations.</div>
              </div>
              <button
                className={`toggle ${notifications.chatSummaries ? 'on' : ''}`}
                onClick={() => setNotifications((prev) => ({ ...prev, chatSummaries: !prev.chatSummaries }))}
              >
                <span className="toggle-knob" />
              </button>
            </div>
          </div>

          <div className="settings-card danger-zone">
            <h3>Account Session</h3>
            <p className="settings-card-sub">Sign out of your active session on this device.</p>
            <div>
              <button className="btn btn-secondary" onClick={handleSignOut}>
                Sign out
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
