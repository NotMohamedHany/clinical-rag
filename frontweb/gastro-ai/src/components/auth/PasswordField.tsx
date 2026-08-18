import { useId, useState } from 'react';
import { IconEye, IconEyeOff } from '../common/Icons';

interface PasswordFieldProps {
  label: string;
  value: string;
  onChange: (v: string) => void;
  error?: string | null;
  autoComplete?: string;
  placeholder?: string;
}

export function PasswordField({ label, value, onChange, error, autoComplete, placeholder }: PasswordFieldProps) {
  const [visible, setVisible] = useState(false);
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <div className="field-input-wrap">
        <input
          id={id}
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete={autoComplete}
          placeholder={placeholder || '••••••••'}
          className={error ? 'has-error' : ''}
          style={{ paddingRight: 40 }}
        />
        <button
          type="button"
          className="field-toggle"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? 'Hide password' : 'Show password'}
        >
          {visible ? <IconEyeOff size={17} /> : <IconEye size={17} />}
        </button>
      </div>
      {error && <span className="field-error">{error}</span>}
    </div>
  );
}
