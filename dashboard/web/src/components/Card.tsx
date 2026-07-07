export function Card({ label, value, tone }: {
  label: string;
  value: string;
  tone?: "good" | "bad" | "small";
}) {
  return (
    <div className="card">
      <span className="label">{label}</span>
      <span className={`value ${tone ?? ""}`}>{value}</span>
    </div>
  );
}

export function Cards({ children }: { children: React.ReactNode }) {
  return <div className="cards">{children}</div>;
}
