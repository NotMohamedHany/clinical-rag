import type { ReactNode } from 'react';
import { IconStethoscope } from '../common/Icons';
import { APP_NAME } from '../../utils/constants';

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="auth-shell">
      <div className="auth-visual">
        <div className="auth-visual-brand">
          <IconStethoscope size={22} />
          <span>{APP_NAME}</span>
        </div>
        <div className="auth-visual-copy">
          <h1>Clear, sourced answers about digestive health.</h1>
          <p>
            Ask about gastritis, GERD, H. pylori, IBS, and more. Every answer is grounded in
            retrieved medical sources — reviewed for accuracy, never guessed.
          </p>
        </div>
        <div className="auth-visual-foot">
          Educational information only — not a substitute for professional medical care.
        </div>
      </div>
      <div className="auth-panel">
        <div className="auth-card">{children}</div>
      </div>
    </div>
  );
}
