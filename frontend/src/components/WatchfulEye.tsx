import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion, useSpring } from "framer-motion";

export type EyeMode = "idle" | "email" | "password" | "peek";
export type EyeStatus = "none" | "error" | "success" | "loading";

interface Props {
  mode: EyeMode;
  status: EyeStatus;
  /** Longitud del texto del correo: la mirada sigue al cursor de escritura. */
  caret: number;
}

const CX = 120;
const CY = 70;
const MAX_X = 44;
const MAX_Y = 16;
// Punto de control del párpado superior (curva cuadrática) por estado.
const LID = { open: -14, peek: 40, closed: 154 } as const;

const eyePath = (u: number) => `M14 70 Q120 ${u} 226 70 Q120 154 14 70 Z`;
const lidPath = (u: number) => `M14 70 Q120 ${u} 226 70`;
const TICKS = Array.from({ length: 24 }, (_, i) => (i / 24) * Math.PI * 2);

/**
 * Ojo vigilante del inicio de sesión.
 * - Sigue al puntero en reposo y al texto mientras escribes el correo.
 * - Se cierra al escribir la contraseña; se entreabre si la muestras.
 * - Parpadea de forma irregular, niega con la cabeza ante un error y dilata la pupila al entrar.
 * El iris es un dial de medición: guiño al carácter analítico del proyecto.
 */
export function WatchfulEye({ mode, status, caret }: Props) {
  const reduce = useReducedMotion() ?? false;
  const svgRef = useRef<SVGSVGElement>(null);
  const [blink, setBlink] = useState(false);
  const spring = { stiffness: 220, damping: 22, mass: 0.6 };
  const x = useSpring(0, spring);
  const y = useSpring(0, spring);

  // Seguimiento del puntero (solo en reposo).
  useEffect(() => {
    if (mode !== "idle") return;
    const onMove = (e: PointerEvent) => {
      const box = svgRef.current?.getBoundingClientRect();
      if (!box) return;
      const dx = e.clientX - (box.left + box.width / 2);
      const dy = e.clientY - (box.top + box.height / 2);
      const dist = Math.hypot(dx, dy) || 1;
      const reach = Math.min(1, dist / 260);
      x.set((dx / dist) * MAX_X * reach);
      y.set((dy / dist) * MAX_Y * reach);
    };
    window.addEventListener("pointermove", onMove);
    return () => window.removeEventListener("pointermove", onMove);
  }, [mode, x, y]);

  // Mirada hacia el campo de correo, recorriéndolo conforme se escribe.
  useEffect(() => {
    if (mode === "email") {
      const ratio = Math.min(caret / 30, 1);
      x.set(-MAX_X * 0.85 + ratio * MAX_X * 1.7);
      y.set(MAX_Y * 0.9);
    } else if (mode === "peek") {
      x.set(MAX_X * 0.35);
      y.set(MAX_Y);
    } else if (mode === "password") {
      x.set(0);
      y.set(MAX_Y * 0.6);
    }
  }, [mode, caret, x, y]);

  // Parpadeo irregular.
  useEffect(() => {
    if (reduce) return;
    let timer: number;
    const schedule = () => {
      timer = window.setTimeout(() => {
        setBlink(true);
        window.setTimeout(() => setBlink(false), 140);
        schedule();
      }, 2800 + Math.random() * 3600);
    };
    schedule();
    return () => window.clearTimeout(timer);
  }, [reduce]);

  const closed = mode === "password" || (blink && (mode === "idle" || mode === "email"));
  const u = closed ? LID.closed : mode === "peek" ? LID.peek : LID.open;
  const lidTransition = blink ? { duration: 0.07 } : { type: "spring" as const, stiffness: 260, damping: 26 };
  const pupil = status === "success" ? 1.45 : status === "loading" ? 0.8 : 1;

  return (
    <motion.svg
      ref={svgRef}
      viewBox="0 0 240 140"
      className="h-auto w-[220px] select-none"
      aria-hidden="true"
      animate={status === "error" && !reduce ? { x: [0, -10, 9, -6, 4, 0] } : { x: 0 }}
      transition={{ duration: 0.45, ease: "easeOut" }}
    >
      <defs>
        <clipPath id="eye-clip">
          <motion.path initial={false} animate={{ d: eyePath(u) }} transition={lidTransition} />
        </clipPath>
      </defs>

      {/* Esclerótica */}
      <motion.path
        initial={false}
        animate={{ d: eyePath(u) }}
        transition={lidTransition}
        fill="rgb(var(--panel))"
      />

      <g clipPath="url(#eye-clip)">
        <motion.g style={{ x, y }}>
          <circle cx={CX} cy={CY} r={33} fill="rgb(var(--brand) / 0.10)" />
          <circle cx={CX} cy={CY} r={33} fill="none" stroke="rgb(var(--brand))" strokeWidth={1.6} />
          <circle cx={CX} cy={CY} r={23} fill="none" stroke="rgb(var(--brand) / 0.55)" strokeWidth={0.8} />
          <motion.g
            animate={reduce ? undefined : { rotate: 360 }}
            transition={{ duration: 60, repeat: Infinity, ease: "linear" }}
          >
            {TICKS.map((a, i) => (
              <line
                key={i}
                x1={CX + Math.cos(a) * 26}
                y1={CY + Math.sin(a) * 26}
                x2={CX + Math.cos(a) * (i % 6 === 0 ? 31 : 29)}
                y2={CY + Math.sin(a) * (i % 6 === 0 ? 31 : 29)}
                stroke="rgb(var(--brand) / 0.7)"
                strokeWidth={i % 6 === 0 ? 1.4 : 0.8}
              />
            ))}
          </motion.g>
          <motion.circle
            cx={CX}
            cy={CY}
            r={12}
            fill="rgb(var(--ink))"
            animate={{ scale: pupil }}
            transition={{ type: "spring", stiffness: 200, damping: 14 }}
          />
          <circle cx={CX + 5} cy={CY - 5} r={3.4} fill="rgb(var(--panel))" opacity={0.9} />
        </motion.g>
      </g>

      {/* Contorno: párpado superior (animado) e inferior */}
      <motion.path
        initial={false}
        animate={{ d: lidPath(u) }}
        transition={lidTransition}
        fill="none"
        stroke="rgb(var(--ink))"
        strokeWidth={2.6}
        strokeLinecap="round"
      />
      <path d="M14 70 Q120 154 226 70" fill="none" stroke="rgb(var(--ink) / 0.55)" strokeWidth={1.4} strokeLinecap="round" />
    </motion.svg>
  );
}
