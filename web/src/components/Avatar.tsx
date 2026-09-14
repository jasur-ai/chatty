import { useState } from "react";

const COLORS = [
  "#e17076",
  "#7bc862",
  "#64a1f4",
  "#ee7aae",
  "#faa774",
  "#65b9c4",
  "#d391f0",
  "#9ad0f5",
];

function colorFor(name: string): string {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return COLORS[h % COLORS.length];
}

function initialsOf(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("");
}

export function Avatar({ name, photo, size = 54 }: { name: string; photo?: string | null; size?: number }) {
  const [failed, setFailed] = useState(false);

  if (photo && !failed) {
    return (
      <img
        src={photo}
        alt={name}
        width={size}
        height={size}
        onError={() => setFailed(true)}
        style={{ width: size, height: size, borderRadius: "50%", objectFit: "cover", flexShrink: 0 }}
      />
    );
  }
  const initials = initialsOf(name);
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        background: colorFor(name || "?"),
        color: "#fff",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: size * 0.42,
        fontWeight: 600,
        flexShrink: 0,
        userSelect: "none",
      }}
    >
      {initials || "?"}
    </div>
  );
}