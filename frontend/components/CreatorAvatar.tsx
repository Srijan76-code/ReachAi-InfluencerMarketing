"use client";

import { useEffect, useRef, useState } from "react";

/** A creator's profile photo in the same box the initial used to fill. Falls back to the initial when
 *  there's no photo (older results) or it fails to load. `className` is the box's existing classes. */
export function CreatorAvatar({
  name,
  src,
  className,
  textClassName = "",
}: {
  name: string;
  src?: string | null;
  className: string;
  textClassName?: string;
}) {
  const [failed, setFailed] = useState(false);
  const img = useRef<HTMLImageElement>(null);
  // A photo can fail before React attaches onError (server-rendered page): check once mounted too.
  useEffect(() => {
    setFailed(false);
    const el = img.current;
    if (el && el.complete && el.naturalWidth === 0) setFailed(true);
  }, [src]);
  const initial = (name || "?").trim().charAt(0).toUpperCase() || "?";
  const showPhoto = Boolean(src) && !failed;
  return (
    <div className={`${className} overflow-hidden`}>
      {showPhoto ? (
        // eslint-disable-next-line @next/next/no-img-element -- remote platform photo; next/image would need every CDN host configured
        <img
          ref={img}
          src={src as string}
          alt={name}
          width={48}
          height={48}
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          className="h-full w-full object-cover"
          onError={() => setFailed(true)}
        />
      ) : (
        <span className={textClassName}>{initial}</span>
      )}
    </div>
  );
}
