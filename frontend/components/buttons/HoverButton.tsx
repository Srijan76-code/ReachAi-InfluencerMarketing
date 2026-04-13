"use client"
import React, { useRef, useState, type MouseEventHandler, type ReactNode } from 'react';

type HoverButtonProps = {
  children?: ReactNode;
  onClick?: MouseEventHandler<HTMLButtonElement>;
  className?: string;
  disabled?: boolean;
  glowColor?: string;
  backgroundColor?: string;
  textColor?: string;
  hoverTextColor?: string;
} & React.ButtonHTMLAttributes<HTMLButtonElement>;

const HoverButton = ({ 
  children, 
  onClick, 
  className = '', 
  disabled = false,
  glowColor = 'white',
  backgroundColor = 'transparent',
  textColor = '#ffffff',
  hoverTextColor = 'black',
  ...props
}: HoverButtonProps) => {
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const [glowPosition, setGlowPosition] = useState({ x: 50, y: 50 });
  const [isHovered, setIsHovered] = useState(false);

  const handleMouseMove: MouseEventHandler = (e) => {
    if (buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      const ex = (e as React.MouseEvent<HTMLButtonElement>).clientX;
      const ey = (e as React.MouseEvent<HTMLButtonElement>).clientY;
      const x = ex - rect.left;
      const y = ey - rect.top;
      setGlowPosition({ x, y });
    }
  };

  const handleMouseEnter = () => {
    setIsHovered(true);
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
  };

  return (
    <button
      {...props}
      ref={buttonRef}
      onClick={onClick}
      disabled={disabled}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={`
        relative inline-block px-4 py-1.5 border border-neutral-900 
        cursor-pointer overflow-hidden transition-colors duration-300 
        rounded-lg z-10 text-sm font-medium
        ${disabled ? 'opacity-80 cursor-not-allowed' : ''}
        ${className}
      `}
      style={{
        backgroundColor: backgroundColor,
        color: isHovered ? hoverTextColor : textColor,
      }}>
      <div
        className={`
          absolute w-[200px] h-[200px] rounded-full opacity-90 pointer-events-none 
          transition-transform duration-400 ease-out -translate-x-1/2 -translate-y-1/2
          ${isHovered ? 'scale-120' : 'scale-0'}
        `}
        style={{
          left: `${glowPosition.x}px`,
          top: `${glowPosition.y}px`,
          background: `radial-gradient(circle, ${glowColor} 10%, transparent 70%)`,
          zIndex: 0,
        }} />
      <span className="relative z-10">{children}</span>
    </button>
  );
};

export { HoverButton };