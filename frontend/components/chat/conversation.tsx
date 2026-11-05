"use client";

import type { ComponentProps } from "react";
import { ArrowDown } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";
import { cn } from "@/lib/utils";

/** A scrolling chat that sticks to the newest message (adapted from Vercel AI Elements' Conversation). */
export const Conversation = ({ className, ...props }: ComponentProps<typeof StickToBottom>) => (
  <StickToBottom className={cn("relative flex-1 min-h-0 overflow-y-hidden", className)} initial="instant" resize="smooth" role="log" {...props} />
);

export const ConversationContent = ({ className, ...props }: ComponentProps<typeof StickToBottom.Content>) => (
  <StickToBottom.Content className={cn("flex flex-col px-5 md:px-8 py-6", className)} {...props} />
);

/** "Jump to latest", shown only when you've scrolled up. */
export function ConversationScrollButton({ className }: { className?: string }) {
  const { isAtBottom, scrollToBottom } = useStickToBottomContext();
  return (
    <AnimatePresence>
      {!isAtBottom && (
        <motion.button
          type="button"
          onClick={() => scrollToBottom()}
          aria-label="Jump to the latest message"
          initial={{ opacity: 0, y: 8, scale: 0.9 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 8, scale: 0.9 }}
          transition={{ type: "spring", stiffness: 500, damping: 30 }}
          className={cn(
            "absolute bottom-3 left-1/2 -translate-x-1/2 h-8 w-8 rounded-full flex items-center justify-center",
            "border border-zinc-200 dark:border-zinc-800 bg-white/90 dark:bg-[#121314]/90 backdrop-blur text-zinc-600 dark:text-zinc-300 shadow-sm",
            className,
          )}
        >
          <ArrowDown size={14} />
        </motion.button>
      )}
    </AnimatePresence>
  );
}
