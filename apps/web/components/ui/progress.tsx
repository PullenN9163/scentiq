export function Progress({ value, label }: { value: number; label: string }) {
  const safeValue = Math.max(0, Math.min(100, value));
  return (
    <div className="progress-wrap">
      <div className="progress" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={safeValue}>
        <span className="progress__fill" style={{ width: `${safeValue}%` }} />
      </div>
    </div>
  );
}
