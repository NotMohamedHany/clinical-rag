import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AuthLayout } from '../components/auth/AuthLayout';
import { PasswordField } from '../components/auth/PasswordField';
import { Button } from '../components/common/Button';
import { useAuth } from '../context/AuthContext';
import { isValidEmail, passwordStrengthError } from '../utils/validators';
import { ApiError } from '../api/client';

interface FormErrors {
  name?: string;
  email?: string;
  password?: string;
  confirm?: string;
}

export function SignUpPage() {
  const { signUp } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [role, setRole] = useState<'patient' | 'doctor'>('patient');
  const [errors, setErrors] = useState<FormErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const validate = () => {
    const next: FormErrors = {};
    if (!name.trim()) next.name = 'Enter your display name.';
    if (!email.trim()) next.email = 'Enter a username.';
    const pwError = passwordStrengthError(password);
    if (pwError) next.password = pwError;
    if (confirm !== password) next.confirm = 'Passwords do not match.';
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (!validate()) return;
    setLoading(true);
    try {
      await signUp(email, password, name.trim(), role);
      navigate('/', { replace: true });
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : 'Unable to create your account. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout>
      <h2>Create your account</h2>
      <p className="auth-sub">Get personalized, source-backed clinical guidelines answers.</p>

      <form className="auth-form" onSubmit={onSubmit} noValidate>
        {formError && <div className="auth-error-banner">{formError}</div>}

        <div className="field">
          <label>Account Role</label>
          <div className="theme-switch-group" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <button
              type="button"
              className={`theme-switch-opt ${role === 'patient' ? 'active' : ''}`}
              onClick={() => setRole('patient')}
            >
              Patient
            </button>
            <button
              type="button"
              className={`theme-switch-opt ${role === 'doctor' ? 'active' : ''}`}
              onClick={() => setRole('doctor')}
            >
              Doctor
            </button>
          </div>
        </div>

        <div className="field">
          <label htmlFor="name">Display name</label>
          <input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Dr. Smith or Jane Doe"
            autoComplete="name"
            className={errors.name ? 'has-error' : ''}
          />
          {errors.name && <span className="field-error">{errors.name}</span>}
        </div>

        <div className="field">
          <label htmlFor="username">Username</label>
          <input
            id="username"
            type="text"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Choose a username"
            autoComplete="username"
            className={errors.email ? 'has-error' : ''}
          />
          {errors.email && <span className="field-error">{errors.email}</span>}
        </div>

        <PasswordField
          label="Password"
          value={password}
          onChange={setPassword}
          error={errors.password}
          autoComplete="new-password"
        />

        <PasswordField
          label="Confirm password"
          value={confirm}
          onChange={setConfirm}
          error={errors.confirm}
          autoComplete="new-password"
        />

        <Button type="submit" block loading={loading}>
          Create account
        </Button>
      </form>

      <div className="auth-foot">
        Already have an account? <Link className="auth-link" to="/sign-in">Sign in</Link>
      </div>
    </AuthLayout>
  );
}
