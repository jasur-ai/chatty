import type { JSX } from "react";

interface IconProps {
  size?: number;
  className?: string;
}

function base(props: IconProps, children: JSX.Element, viewBox = "0 0 24 24") {
  return (
    <svg
      width={props.size ?? 20}
      height={props.size ?? 20}
      viewBox={viewBox}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={props.className}
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export const IconSend = (p: IconProps) =>
  base(p, <path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z" />);

export const IconBack = (p: IconProps) => base(p, <path d="M15 18l-6-6 6-6" />);

export const IconSearch = (p: IconProps) =>
  base(p, (
    <>
      <circle cx={11} cy={11} r={7} />
      <path d="m21 21-4.3-4.3" />
    </>
  ));

export const IconPhone = (p: IconProps) =>
  base(p, <path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3 19.5 19.5 0 0 1-6-6 19.8 19.8 0 0 1-3-8.7A2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 2 .7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.2a2 2 0 0 1 2.1-.5c.9.3 1.9.6 2.8.7a2 2 0 0 1 1.7 2z" />);

export const IconLock = (p: IconProps) =>
  base(p, (
    <>
      <rect x={3} y={11} width={18} height={11} rx={2} />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </>
  ));

export const IconCheck = (p: IconProps) => base(p, <path d="M20 6 9 17l-5-5" />);

export const IconCheckDouble = (p: IconProps) =>
  base(p, (
    <>
      <path d="M18 6 7 17l-5-5" />
      <path d="m22 10-7.5 7.5L13 16" />
    </>
  ));

export const IconUser = (p: IconProps) =>
  base(p, (
    <>
      <circle cx={12} cy={8} r={4} />
      <path d="M4 21c0-4 3.6-6 8-6s8 2 8 6" />
    </>
  ));

export const IconGroup = (p: IconProps) =>
  base(p, (
    <>
      <circle cx={9} cy={8} r={3.5} />
      <path d="M2.5 20c0-3.3 3-5 6.5-5s6.5 1.7 6.5 5" />
      <path d="M16 5.5a3.5 3.5 0 0 1 0 7" />
      <path d="M18.5 15.6c1.8.8 3 2 3 4.4" />
    </>
  ));

export const IconMenu = (p: IconProps) =>
  base(p, (
    <>
      <path d="M4 6h16" />
      <path d="M4 12h16" />
      <path d="M4 18h16" />
    </>
  ));

export const IconPlus = (p: IconProps) => base(p, <path d="M12 5v14M5 12h14" />);

export const IconSettings = (p: IconProps) =>
  base(p, (
    <>
      <circle cx={12} cy={12} r={3} />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </>
  ));

export const IconShield = (p: IconProps) =>
  base(p, (
    <>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="m9 12 2 2 4-4" />
    </>
  ));

export const IconEdit = (p: IconProps) =>
  base(p, (
    <>
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.1 2.1 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </>
  ));

export const IconDownload = (p: IconProps) =>
  base(p, (
    <>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <path d="m7 10 5 5 5-5" />
      <path d="M12 15V3" />
    </>
  ));

export const IconMusic = (p: IconProps) =>
  base(p, (
    <>
      <path d="M9 18V5l12-2v13" />
      <circle cx={6} cy={18} r={3} />
      <circle cx={18} cy={16} r={3} />
    </>
  ));

export const IconStar = (p: IconProps) =>
  base(p, <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />);

export const IconMic = (p: IconProps) =>
  base(p, (
    <>
      <rect x={9} y={2} width={6} height={12} rx={3} />
      <path d="M5 10a7 7 0 0 0 14 0" />
      <path d="M12 17v5" />
    </>
  ));

export const IconBot = (p: IconProps) =>
  base(p, (
    <>
      <rect x={4} y={8} width={16} height={12} rx={3} />
      <path d="M12 8V4M8 4h8" />
      <circle cx={9} cy={13} r={1} />
      <circle cx={15} cy={13} r={1} />
    </>
  ));

export const IconCrown = (p: IconProps) =>
  base(p, <path d="M3 8l4 4 5-7 5 7 4-4-1.5 11h-15L3 8z" />);

export const IconImage = (p: IconProps) =>
  base(p, (
    <>
      <rect x={3} y={3} width={18} height={18} rx={2} />
      <circle cx={8.5} cy={8.5} r={1.5} />
      <path d="m21 15-5-5L5 21" />
    </>
  ));

export const IconStory = (p: IconProps) =>
  base(p, (
    <>
      <circle cx={12} cy={12} r={9} />
      <circle cx={12} cy={12} r={3} />
      <path d="M12 3v3M12 18v3M3 12h3M18 12h3" />
    </>
  ));

export const IconTrash = (p: IconProps) =>
  base(p, (
    <>
      <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
    </>
  ));

export const IconHeart = (p: IconProps) =>
  base(p, <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21l7.8-7.6 1-1a5.5 5.5 0 0 0 0-7.8z" />);

export const IconX = (p: IconProps) => base(p, <path d="M18 6 6 18M6 6l12 12" />);

export const IconLogout = (p: IconProps) =>
  base(p, (
    <>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <path d="M16 17l5-5-5-5M21 12H9" />
    </>
  ));

export const IconReply = (p: IconProps) =>
  base(p, (
    <>
      <path d="M9 17l-5-5 5-5" />
      <path d="M20 18v-2a4 4 0 0 0-4-4H4" />
    </>
  ));

export const IconSpinner = (p: IconProps) => (
  <svg
    width={p.size ?? 20}
    height={p.size ?? 20}
    viewBox="0 0 24 24"
    fill="none"
    className={`chatty-spinner ${p.className ?? ""}`}
    aria-hidden="true"
  >
    <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
    <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
  </svg>
);