/* eslint-disable react-refresh/only-export-components */

import React from "react";


function Card({
  className = "",
  children,
  ...props
}) {
  return (
    <div
      className={`
        rounded-xl
        border
        bg-card
        text-card-foreground
        shadow-sm
        ${className}
      `}
      {...props}
    >
      {children}
    </div>
  );
}


export { Card };