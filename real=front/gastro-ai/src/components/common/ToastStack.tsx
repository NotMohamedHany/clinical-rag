import { useToast } from '../../context/ToastContext';
import { IconAlert, IconCheck, IconInfo, IconX } from './Icons';

export function ToastStack() {
  const { toasts, dismiss } = useToast();
  if (toasts.length === 0) return null;
  return (
    <div className="toast-stack">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.type}`}>
          <span className={`toast-icon ${t.type}`}>
            {t.type === 'error' && <IconAlert size={16} />}
            {t.type === 'success' && <IconCheck size={16} />}
            {t.type === 'info' && <IconInfo size={16} />}
          </span>
          <span style={{ flex: 1 }}>{t.message}</span>
          <button className="btn-icon" style={{ width: 24, height: 24 }} onClick={() => dismiss(t.id)}>
            <IconX size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
