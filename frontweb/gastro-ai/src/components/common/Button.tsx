import type { ButtonHTMLAttributes, ReactNode } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost';
  block?: boolean;
  loading?: boolean;
  children: ReactNode;
}

export function Button({ variant = 'primary', block, loading, children, className = '', disabled, ...rest }: ButtonProps) {
  const cls = ['btn', `btn-${variant}`, block ? 'btn-block' : '', className].filter(Boolean).join(' ');
  return (
    <button className={cls} disabled={disabled || loading} {...rest}>
      {loading ? <span className="typing-dots"><span /><span /><span /></span> : children}
    </button>
  );
}
