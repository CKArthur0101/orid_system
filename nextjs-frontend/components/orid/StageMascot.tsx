/** 內建 SVG 松鼠小幫手（無背景、可任意縮放） */

function SquirrelSvg({ className, size = 40 }: { className?: string; size?: number }) {
  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      className={className}
      aria-hidden
    >
      <ellipse cx="34" cy="38" rx="16" ry="14" fill="#A67C52" />
      <ellipse cx="34" cy="40" rx="11" ry="9" fill="#F5E6D3" />
      <path d="M14 34 Q6 24 10 14 Q20 22 22 32 Z" fill="#8B5E3C" />
      <path d="M48 20 Q58 12 54 26 Q50 22 48 24 Z" fill="#8B5E3C" />
      <circle cx="28" cy="34" r="2.2" fill="#3D2914" />
      <circle cx="38" cy="34" r="2.2" fill="#3D2914" />
      <ellipse cx="33" cy="38" rx="2" ry="1.2" fill="#C4956A" />
      <path d="M30 41 Q33 44 36 41" stroke="#8B5E3C" strokeWidth="1.2" fill="none" strokeLinecap="round" />
      <ellipse cx="42" cy="48" rx="5" ry="6" fill="#C4956A" />
      <ellipse cx="42" cy="47" rx="3" ry="3.5" fill="#D4A574" />
      <rect x="22" y="42" width="10" height="8" rx="1" fill="#E8D5B7" stroke="#8B5E3C" strokeWidth="0.8" />
      <line x1="24" y1="44" x2="30" y2="44" stroke="#8B5E3C" strokeWidth="0.6" />
      <line x1="24" y1="46" x2="30" y2="46" stroke="#8B5E3C" strokeWidth="0.6" />
    </svg>
  );
}

function SquirrelFaceSvg({ className, size = 32 }: { className?: string; size?: number }) {
  return (
    <svg viewBox="0 0 48 48" width={size} height={size} className={className} aria-hidden>
      <circle cx="24" cy="26" r="14" fill="#A67C52" />
      <ellipse cx="24" cy="28" rx="9" ry="8" fill="#F5E6D3" />
      <path d="M12 18 Q8 10 14 8 Q16 14 14 18 Z" fill="#8B5E3C" />
      <path d="M36 18 Q40 10 34 8 Q32 14 34 18 Z" fill="#8B5E3C" />
      <circle cx="20" cy="25" r="1.8" fill="#3D2914" />
      <circle cx="28" cy="25" r="1.8" fill="#3D2914" />
      <ellipse cx="24" cy="29" rx="1.5" ry="1" fill="#C4956A" />
      <ellipse cx="32" cy="32" rx="3" ry="3.5" fill="#D4A574" />
    </svg>
  );
}

export function OridPartnerMascot({ size = 40, className }: { size?: number; className?: string }) {
  return <SquirrelSvg className={className} size={size} />;
}

export function OridLogo({ size = 34, className }: { size?: number; className?: string }) {
  return <SquirrelFaceSvg className={className} size={size} />;
}
