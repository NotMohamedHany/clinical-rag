import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { useLayout } from '../../context/LayoutContext';

export function AppLayout() {
  const { sidebarCollapsed, mobileSidebarOpen } = useLayout();
  const cls = [
    'app-shell',
    sidebarCollapsed ? 'sidebar-collapsed' : '',
    mobileSidebarOpen ? 'mobile-sidebar-open' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={cls}>
      <Sidebar />
      <div className="main-col">
        <Outlet />
      </div>
    </div>
  );
}
