export function isValidEmail(username: string): boolean {
  return username.trim().length >= 2;
}

export function passwordStrengthError(password: string): string | null {
  if (password.length < 8) return 'Password must be at least 8 characters.';
  if (!/[A-Z]/.test(password)) return 'Include at least one uppercase letter.';
  if (!/[0-9]/.test(password)) return 'Include at least one number.';
  return null;
}
