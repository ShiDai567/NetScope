import type { ReactNode } from "react";

/** 统一 HUD 玻璃面板：四角亮标 + 微光顶边 */
export function HudPanel({
  title,
  right,
  children,
  className = "",
  bodyClassName = "",
}: {
  title?: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={`hud-panel flex flex-col ${className}`}>
      <i className="hud-corner hud-corner-tl" aria-hidden />
      <i className="hud-corner hud-corner-tr" aria-hidden />
      <i className="hud-corner hud-corner-bl" aria-hidden />
      <i className="hud-corner hud-corner-br" aria-hidden />

      {title && (
        <header className="flex shrink-0 items-center justify-between border-b border-cyan-400/10 px-3 py-2">
          <h2 className="panel-title">{title}</h2>
          {right}
        </header>
      )}
      <div className={`min-h-0 flex-1 ${bodyClassName}`}>{children}</div>
    </section>
  );
}
