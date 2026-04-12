// components/animations/MaskReveal.jsx
'use client';

import { motion } from "motion/react"

/**
 * A reusable component that reveals its children with a "mask wipe"
 * animation as it scrolls into view.
 */
const MaskReveal = ({ children }) => {
  return (
    // This is the MASK. It clips its children.
    <div style={{ overflow: 'hidden', width: '100%' }}>
      
      {/* This is the CONTENT. It animates "up" from below. */}
      <motion.div
        // Define the animation "variants"
        variants={{
          hidden: { y: '100%', opacity: 0.5 }, // Start 100% (its full height) below
          visible: { y: '0%', opacity: 1 },    // Animate to its original position
        }}
        
        // Initial state is "hidden"
        initial="hidden"
        
        // Animate to "visible" when it's in the viewport
        whileInView="visible"
        
        // --- This is the key for a "premium" feel ---
        
        // 1. viewport={{ once: true }}
        //    This ensures the animation only plays ONCE when it scrolls into view,
        //    not every single time it enters/leaves the screen.
        viewport={{ once: true }}
        
        // 2. transition={{ ... }}
        //    A custom duration and ease makes it feel smooth and intentional.
        //    This ease curve is a "quint" ease-out.
        transition={{
          duration: 0.1,
          ease: [0.22, 1, 0.36, 1], 
        }}
      >
        {children}
      </motion.div>
    </div>
  );
};

export default MaskReveal;