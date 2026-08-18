import type { SVGProps } from 'react';

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function base(children: React.ReactNode, { size = 18, ...props }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      {children}
    </svg>
  );
}

export const IconSearch = (p: IconProps) => base(<><circle cx="11" cy="11" r="7" /><path d="m20 20-3.2-3.2" /></>, p);
export const IconPlus = (p: IconProps) => base(<><path d="M12 5v14M5 12h14" /></>, p);
export const IconTrash = (p: IconProps) => base(<><path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2m2 0-.7 12.1A2 2 0 0 1 15.3 21H8.7a2 2 0 0 1-2-1.9L6 7" /></>, p);
export const IconSettings = (p: IconProps) => base(<><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.9 2.9l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.9-2.9l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.6-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.9-2.9l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.6V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.9 2.9l-.1.1a1.7 1.7 0 0 0-.3 1.9V9c.1.7.5 1.3 1 1.6.4.2.8.3 1.3.3H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1.1z" /></>, p);
export const IconLogOut = (p: IconProps) => base(<><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="M16 17l5-5-5-5" /><path d="M21 12H9" /></>, p);
export const IconMenu = (p: IconProps) => base(<><path d="M4 6h16M4 12h16M4 18h16" /></>, p);
export const IconPanelLeft = (p: IconProps) => base(<><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M9 4v16" /></>, p);
export const IconSend = (p: IconProps) => base(<><path d="m22 2-7 20-4-9-9-4z" /><path d="M22 2 11 13" /></>, p);
export const IconArrowUp = (p: IconProps) => base(<><path d="M12 19V5M5 12l7-7 7 7" /></>, p);
export const IconMic = (p: IconProps) => base(<><rect x="9" y="2" width="6" height="12" rx="3" /><path d="M5 10a7 7 0 0 0 14 0" /><path d="M12 19v3M9 22h6" /></>, p);
export const IconPaperclip = (p: IconProps) => base(<><path d="M21.4 11.6 12.3 20.7a5 5 0 0 1-7.1-7.1l8.5-8.5a3.3 3.3 0 0 1 4.7 4.7L9.9 18.3a1.7 1.7 0 0 1-2.4-2.4l7.5-7.5" /></>, p);
export const IconPhone = (p: IconProps) => base(<><path d="M14 9a5 5 0 0 1 5 5M14 5a9 9 0 0 1 9 9" /><rect x="3" y="3" width="7" height="7" rx="2" opacity="0" /><path d="M9.5 13.5a13.5 13.5 0 0 0 5 5l1.6-1.9a1.5 1.5 0 0 1 1.8-.4c1 .4 2 .7 3.1.8a1.5 1.5 0 0 1 1.3 1.5v2.9a1.5 1.5 0 0 1-1.6 1.5A18.5 18.5 0 0 1 3.5 5.1 1.5 1.5 0 0 1 5 3.5h3a1.5 1.5 0 0 1 1.5 1.3c.1 1.1.4 2.1.8 3.1a1.5 1.5 0 0 1-.4 1.8L8 11.3" /></>, p);
export const IconCopy = (p: IconProps) => base(<><rect x="9" y="9" width="12" height="12" rx="2" /><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1" /></>, p);
export const IconRefresh = (p: IconProps) => base(<><path d="M21 12a9 9 0 1 1-2.6-6.3" /><path d="M21 3v6h-6" /></>, p);
export const IconThumbsUp = (p: IconProps) => base(<><path d="M7 10v11H4a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1h3zm0 0 4.5-7a2 2 0 0 1 3.6 1.2L14 9h5.3a2 2 0 0 1 2 2.3l-1.3 8A2 2 0 0 1 18 21H9a2 2 0 0 1-2-2" /></>, p);
export const IconThumbsDown = (p: IconProps) => base(<><path d="M17 14V3h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-3zm0 0-4.5 7a2 2 0 0 1-3.6-1.2L10 15H4.7a2 2 0 0 1-2-2.3l1.3-8A2 2 0 0 1 6 3h9a2 2 0 0 1 2 2" /></>, p);
export const IconVolume = (p: IconProps) => base(<><path d="M11 5 6 9H3v6h3l5 4z" /><path d="M16 8a5 5 0 0 1 0 8M19 5a9 9 0 0 1 0 14" /></>, p);
export const IconVolumeMute = (p: IconProps) => base(<><path d="M11 5 6 9H3v6h3l5 4z" /><path d="m17 9 4 6m0-6-4 6" /></>, p);
export const IconPause = (p: IconProps) => base(<><rect x="6" y="4" width="4" height="16" rx="1" /><rect x="14" y="4" width="4" height="16" rx="1" /></>, p);
export const IconPlay = (p: IconProps) => base(<><path d="M6 4l14 8-14 8z" /></>, p);
export const IconX = (p: IconProps) => base(<><path d="M18 6 6 18M6 6l12 12" /></>, p);
export const IconSun = (p: IconProps) => base(<><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>, p);
export const IconMoon = (p: IconProps) => base(<><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z" /></>, p);
export const IconMonitor = (p: IconProps) => base(<><rect x="3" y="4" width="18" height="12" rx="2" /><path d="M8 20h8M12 16v4" /></>, p);
export const IconCheck = (p: IconProps) => base(<><path d="m5 12 5 5L20 7" /></>, p);
export const IconAlert = (p: IconProps) => base(<><path d="M12 9v4M12 17h.01" /><path d="M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" /></>, p);
export const IconInfo = (p: IconProps) => base(<><circle cx="12" cy="12" r="10" /><path d="M12 16v-5M12 8h.01" /></>, p);
export const IconChevronDown = (p: IconProps) => base(<><path d="m6 9 6 6 6-6" /></>, p);
export const IconEye = (p: IconProps) => base(<><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" /></>, p);
export const IconEyeOff = (p: IconProps) => base(<><path d="M3 3l18 18" /><path d="M10.6 5.1A10.6 10.6 0 0 1 12 5c6.5 0 10 7 10 7a13.2 13.2 0 0 1-3.1 4M6.6 6.6C4 8.3 2 12 2 12s3.5 7 10 7c1.4 0 2.6-.3 3.7-.8" /><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" /></>, p);
export const IconStethoscope = (p: IconProps) => base(<><path d="M6 3v6a4 4 0 0 0 8 0V3" /><path d="M10 15a6 6 0 0 0 6 6 6 6 0 0 0 6-6v-2" /><circle cx="20" cy="6" r="2" /></>, p);
export const IconMessageSquare = (p: IconProps) => base(<><path d="M21 15a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></>, p);
export const IconUser = (p: IconProps) => base(<><circle cx="12" cy="8" r="4" /><path d="M4 21v-1a8 8 0 0 1 16 0v1" /></>, p);
export const IconBell = (p: IconProps) => base(<><path d="M6 8a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6" /><path d="M9.7 21a2.3 2.3 0 0 0 4.6 0" /></>, p);
export const IconMoreVertical = (p: IconProps) => base(<><circle cx="12" cy="5" r="1.2" /><circle cx="12" cy="12" r="1.2" /><circle cx="12" cy="19" r="1.2" /></>, p);
export const IconLink = (p: IconProps) => base(<><path d="M10 13a5 5 0 0 0 7 0l2-2a5 5 0 0 0-7-7l-1 1" /><path d="M14 11a5 5 0 0 0-7 0l-2 2a5 5 0 0 0 7 7l1-1" /></>, p);
export const IconInbox = (p: IconProps) => base(<><path d="M22 12h-6l-2 3h-4l-2-3H2" /><path d="M5.5 5h13l3.5 7v7a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-7z" /></>, p);
