import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { AuthLayout } from '../components/auth/AuthLayout';
import { PasswordField } from '../components/auth/PasswordField';
import { Button } from '../components/common/Button';
import { useAuth } from '../context/AuthContext';
import { isValidEmail } from '../utils/validators';
import { ApiError } from '../api/client';
import { authApi } from '../api/auth';

export function SignInPage() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(true);
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [resetSent, setResetSent] = useState(false);

  const from = (location.state as { from?: string })?.from || '/';

  const validate = () => {
    const next: typeof errors = {};
    if (!email.trim()) next.email = 'Enter a valid username.';
    if (!password) next.password = 'Password is required.';
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (!validate()) return;
    setLoading(true);
    try {
      await signIn(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : 'Unable to sign in. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout>
      <h2>Welcome back</h2>
      <p className="auth-sub">Sign in to continue your conversation about clinical guidelines.</p>

      <form className="auth-form" onSubmit={onSubmit} noValidate>
        {formError && <div className="auth-error-banner">{formError}</div>}

        <div className="field">
          <label htmlFor="username">Username</label>
          <input
            id="username"
            type="text"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="e.g. doctor or patient"
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
          autoComplete="current-password"
        />

        <div className="auth-row-between">
          <label className="auth-check">
            <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
            Remember me
          </label>
        </div>

        <Button type="submit" block loading={loading}>
          Sign in
        </Button>
      </form>

      <div className="auth-foot">
        Don&apos;t have an account? <Link className="auth-link" to="/sign-up">Create one</Link>
      </div>
    </AuthLayout>
  );
}
