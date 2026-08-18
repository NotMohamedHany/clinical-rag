import type { ReactNode } from 'react';
import { useLayout } from '../../context/LayoutContext';
import { IconMenu } from '../common/Icons';

interface TopBarProps {
  title: string;
  badge?: string;
  right?: ReactNode;
}

export function TopBar({ title, badge, right }: TopBarProps) {
  const { openMobileSidebar } = useLayout();
  return (
    <div className="topbar">
      <div className="topbar-left">
        <button className="btn-icon mobile-only" onClick={openMobileSidebar} aria-label="Open menu">
          <IconMenu size={19} />
        </button>
        <span className="topbar-title">{title}</span>
        {badge && <span className="topbar-badge">{badge}</span>}
      </div>
      <div className="topbar-right">{right}</div>
    </div>
  );
}
