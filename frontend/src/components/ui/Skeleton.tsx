interface SkeletonProps {
  className?: string;
}

/** A shimmering placeholder block. Compose several to mock a loading card. */
export function Skeleton({ className = "" }: SkeletonProps) {
  return <div className={`skeleton rounded-md ${className}`} aria-hidden />;
}
