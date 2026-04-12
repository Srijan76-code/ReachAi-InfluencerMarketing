import { Variants } from 'motion/react';

// This file just defines and exports the animation rules.
// No 'use client' needed.

/**
 * Variants for the "staggered" container.
 * It will orchestrate the children's animations.
 */
export const staggerContainerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      // This is the "stagger"
      // It will apply a 0.1s delay between each child's animation.
      staggerChildren: 0.1, 
    },
  },
};

/**
 * Variants for the "fade & rise" items (the children).
 */
export const staggerItemVariants: Variants = {
  // Start 20px down and invisible
  hidden: { y: -20, opacity: 0 },
  // Animate to original position and fully visible
  visible: {
    y: 0,
    opacity: 1,
    transition: {
      // Use a "spring" for a premium, bouncy feel
      type: 'spring',
      stiffness: 35,
      damping: 25,
    },
  },
};

export const staggerItemVariants2: Variants = {
  // Start 20px down and invisible
  hidden: { y: -80, opacity: 0 },
  // Animate to original position and fully visible
  visible: {
    y: 0,
    opacity: 1,
    transition: {
      // Use a "spring" for a premium, bouncy feel
      type: 'spring',
      stiffness: 40,
      damping: 50,
    },
  },
};

/**
 * NEW: ITEM VARIANTS (Fade & Slide from Left)
 */
export const staggerItemFadeSlideIn: Variants = {
  // Start 20px to the left and invisible
  hidden: { x: -20, opacity: 0 }, 
  // Animate to original position and fully visible
  visible: {
    x: 0,
    opacity: 1,
    transition: {
      type: 'spring',
      stiffness: 100,
      damping: 10,
    },
  },
};

/**
 * NEW: ITEM VARIANTS (Fade & Slide from Right)
 */
export const staggerItemFadeSlideInRight: Variants = {
  // Start 20px to the right and invisible
  hidden: { x: 20, opacity: 0 },
  // Animate to original position and fully visible
  visible: {
    x: 0,
    opacity: 1,
    transition: {
      type: 'spring',
      stiffness: 100,
      damping: 10,
    },
  },
};