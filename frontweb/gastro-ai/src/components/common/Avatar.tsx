interface AvatarProps {
  name: string;
  size?: 'sm' | 'lg';
}

export function Avatar({ name, size = 'sm' }: AvatarProps) {
  const initials = name
    .split(' ')
    .map((p) => p[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
  return (
    <div className={size === 'lg' ? 'profile-avatar-lg' : 'avatar avatar-user'}>{initials || 'U'}</div>
  );
}
