// components/animations/StaggerFadeRise.jsx
'use client';

import { motion } from "motion/react"
// Import the container variants we just defined
import { staggerContainerVariants } from './variants';

/**
 * This component is the *container* and *trigger* for the stagger.
 * It animates when it scrolls into view.
 *
 * Its children *must* be `motion` components (e.g., <motion.h1>)
 * and use the `staggerItemVariants` to work.
 */
export const StaggerFadeRise = ({ children, className }) => {
  return (
    <motion.div
      // Pass any custom styles
      className={className}
      
      // Use our exported variants
      variants={staggerContainerVariants}
      
      // Start in the "hidden" state
      initial="hidden"
      
      // Animate to "visible" when it enters the viewport
      whileInView="visible"
      
      // Only run this animation once
      viewport={{ once: true }}
    >
      {children}
    </motion.div>
  );
};

