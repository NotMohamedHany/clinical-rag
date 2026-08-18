import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useChat } from '../../context/ChatContext';
import { useLayout } from '../../context/LayoutContext';
import { useOutsideClick } from '../../hooks/useOutsideClick';
import { formatRelativeDate } from '../../utils/formatDate';
import { APP_NAME } from '../../utils/constants';
import {
  IconLogOut,
  IconMessageSquare,
  IconPanelLeft,
  IconPlus,
  IconSearch,
  IconSettings,
  IconStethoscope,
  IconTrash,
  IconX,
} from '../common/Icons';
import { ConfirmModal } from '../common/ConfirmModal';

export function Sidebar() {
  const { user, signOut } = useAuth();
  const {
    filteredConversations,
    activeId,
    selectConversation,
    startNewConversation,
    deleteConversation,
    searchQuery,
    setSearchQuery,
    isLoadingConversations,
  } = useChat();
  const { sidebarCollapsed, toggleSidebarCollapsed, mobileSidebarOpen, closeMobileSidebar } = useLayout();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  useOutsideClick(menuRef, () => setMenuOpen(false), menuOpen);

  const handleSelect = (id: string) => {
    selectConversation(id);
    closeMobileSidebar();
  };

  const handleNewChat = () => {
    startNewConversation();
    navigate('/');
    closeMobileSidebar();
  };

  return (
    <>
      <aside className="sidebar">
        <div className="sidebar-top">
          <div className="sidebar-brand">
            <div className="sidebar-brand-mark"><IconStethoscope size={16} /></div>
            <span>{APP_NAME}</span>
          </div>
          <button className="btn-icon sidebar-collapse-btn" onClick={toggleSidebarCollapsed} aria-label="Toggle sidebar">
            <IconPanelLeft size={18} />
          </button>
          <button className="btn-icon mobile-only" onClick={closeMobileSidebar} aria-label="Close menu">
            <IconX size={18} />
          </button>
        </div>

        <button className="btn btn-secondary sidebar-new-chat" onClick={handleNewChat}>
          <IconPlus size={16} />
          <span>New chat</span>
        </button>

        <div className="sidebar-search">
          <IconSearch size={15} />
          <input
            placeholder="Search conversations"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div className="sidebar-label">Recent</div>
        <div className="sidebar-history">
          {isLoadingConversations && <div className="sidebar-empty">Loading…</div>}
          {!isLoadingConversations && filteredConversations.length === 0 && (
            <div className="sidebar-empty">
              {searchQuery ? 'No matching conversations.' : 'No conversations yet — start one above.'}
            </div>
          )}
          {filteredConversations.map((c) => (
            <div
              key={c.id}
              className={`convo-item ${c.id === activeId ? 'active' : ''}`}
              onClick={() => handleSelect(c.id)}
            >
              <IconMessageSquare size={15} />
              <div className="convo-item-text">
                <span className="convo-title">{c.title}</span>
                <span className="convo-date">{formatRelativeDate(c.updatedAt)}</span>
              </div>
              <button
                className="convo-delete"
                onClick={(e) => {
                  e.stopPropagation();
                  setPendingDelete(c.id);
                }}
                aria-label="Delete conversation"
              >
                <IconTrash size={14} />
              </button>
            </div>
          ))}
        </div>

        <div className="sidebar-bottom" ref={menuRef}>
          {menuOpen && (
            <>
              <button className="sidebar-nav-btn" onClick={() => { navigate('/settings'); setMenuOpen(false); closeMobileSidebar(); }}>
                <IconSettings size={16} /> <span>Settings</span>
              </button>
              <button className="sidebar-nav-btn" onClick={() => signOut()}>
                <IconLogOut size={16} /> <span>Log out</span>
              </button>
            </>
          )}
          <div className="sidebar-user" onClick={() => setMenuOpen((v) => !v)}>
            <div className="avatar avatar-user">{(user?.name || 'U').slice(0, 1).toUpperCase()}</div>
            <div className="sidebar-user-meta">
              <div className="sidebar-user-name">{user?.name}</div>
              <div className="sidebar-user-email">{user?.email}</div>
            </div>
          </div>
        </div>
      </aside>

      {mobileSidebarOpen && <div className="sidebar-backdrop" onClick={closeMobileSidebar} />}

      {pendingDelete && (
        <ConfirmModal
          title="Delete conversation?"
          description="This will permanently remove this conversation and its messages."
          onCancel={() => setPendingDelete(null)}
          onConfirm={() => {
            deleteConversation(pendingDelete);
            setPendingDelete(null);
          }}
        />
      )}
    </>
  );
}
