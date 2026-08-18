import { Link } from 'react-router-dom';
import { Button } from '../components/common/Button';

export function NotFoundPage() {
  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 14 }}>
      <h1 style={{ fontSize: 22 }}>Page not found</h1>
      <p style={{ color: 'var(--ink-muted)' }}>The page you're looking for doesn't exist.</p>
      <Link to="/">
        <Button>Back to chat</Button>
      </Link>
    </div>
  );
}
