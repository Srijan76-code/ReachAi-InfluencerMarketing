"use client";

import { motion } from "motion/react";

/** Switching campaign tabs (Brief, Creators, Outreach): the new tab's content fades in with a slight rise. */
export default function Template({ children }: { children: React.ReactNode }) {
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2, ease: [0.2, 0.8, 0.2, 1] }}>
      {children}
    </motion.div>
  );
}
