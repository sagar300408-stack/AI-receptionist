import { motion } from "motion/react";
import { useEffect, useState } from "react";

interface ComponentBoxProps {
  title: string;
  items?: string[];
  color: string;
  delay?: number;
  size?: "small" | "medium" | "large";
}

function ComponentBox({ title, items, color, delay = 0, size = "medium" }: ComponentBoxProps) {
  const sizeClasses = {
    small: "p-4 min-w-[180px]",
    medium: "p-6 min-w-[220px]",
    large: "p-8 min-w-[280px]"
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay }}
      className={`${sizeClasses[size]} bg-white rounded-xl shadow-lg border-2 ${color} relative`}
    >
      <h3 className="font-semibold text-gray-800 mb-3 text-center">{title}</h3>
      {items && items.length > 0 && (
        <ul className="space-y-2">
          {items.map((item, index) => (
            <motion.li
              key={index}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.4, delay: delay + 0.1 + index * 0.1 }}
              className="text-sm text-gray-600 flex items-center gap-2"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-gradient-to-r from-blue-500 to-purple-500" />
              {item}
            </motion.li>
          ))}
        </ul>
      )}
    </motion.div>
  );
}

interface ArrowProps {
  direction: "right" | "down" | "left";
  delay?: number;
  length?: number;
}

function Arrow({ direction, delay = 0, length = 80 }: ArrowProps) {
  const [showFlow, setShowFlow] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setShowFlow(true), delay * 1000 + 600);
    return () => clearTimeout(timer);
  }, [delay]);

  const paths = {
    right: `M 0,0 L ${length},0`,
    down: `M 0,0 L 0,${length}`,
    left: `M ${length},0 L 0,0`
  };

  const isHorizontal = direction === "right" || direction === "left";
  const size = isHorizontal ? { width: length + 20, height: 40 } : { width: 40, height: length + 20 };

  return (
    <svg {...size} className="overflow-visible">
      <defs>
        <linearGradient id={`gradient-${direction}-${delay}`} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#3b82f6" />
          <stop offset="100%" stopColor="#a855f7" />
        </linearGradient>
        <marker
          id={`arrowhead-${direction}-${delay}`}
          markerWidth="10"
          markerHeight="10"
          refX="9"
          refY="3"
          orient="auto"
        >
          <polygon points="0 0, 10 3, 0 6" fill="url(#gradient-${direction}-${delay})" />
        </marker>
      </defs>

      <motion.path
        d={paths[direction]}
        stroke="url(#gradient-${direction}-${delay})"
        strokeWidth="2"
        fill="none"
        markerEnd={`url(#arrowhead-${direction}-${delay})`}
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 1 }}
        transition={{ duration: 0.8, delay }}
        transform={isHorizontal ? "translate(10, 20)" : "translate(20, 10)"}
      />

      {showFlow && (
        <motion.circle
          r="3"
          fill="#a855f7"
          initial={direction === "right" ? { cx: 10, cy: 20 } : direction === "left" ? { cx: length + 10, cy: 20 } : { cx: 20, cy: 10 }}
          animate={
            direction === "right"
              ? { cx: [10, length + 10], cy: 20 }
              : direction === "left"
              ? { cx: [length + 10, 10], cy: 20 }
              : { cx: 20, cy: [10, length + 10] }
          }
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: "linear"
          }}
        />
      )}
    </svg>
  );
}

export default function ArchitectureDiagram() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50 p-8 overflow-auto">
      <div className="max-w-7xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="text-center mb-12"
        >
          <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent mb-2">
            The AI Receptionist System Architecture
          </h1>
          <p className="text-gray-600">Enterprise AI Receptionist Platform Architecture</p>
        </motion.div>

        <div className="relative">
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto_2fr_auto_1fr] gap-8 items-start mb-12">
            <div className="flex flex-col gap-4">
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.6 }}
                className="text-center"
              >
                <h2 className="text-lg font-semibold text-gray-700 mb-4">Customer Channels</h2>
              </motion.div>

              <div className="flex flex-col gap-4">
                <ComponentBox
                  title="Website Chat"
                  color="border-blue-300"
                  delay={0.2}
                  size="small"
                />
                <ComponentBox
                  title="WhatsApp"
                  color="border-green-300"
                  delay={0.3}
                  size="small"
                />
                <ComponentBox
                  title="Voice Calls"
                  color="border-purple-300"
                  delay={0.4}
                  size="small"
                />
                <ComponentBox
                  title="Email"
                  color="border-indigo-300"
                  delay={0.5}
                  size="small"
                />
              </div>
            </div>

            <div className="hidden lg:flex items-center justify-center h-full">
              <Arrow direction="right" delay={0.6} length={60} />
            </div>

            <div className="flex flex-col gap-6">
              <motion.div
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.8, delay: 0.7 }}
                className="p-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl shadow-2xl border-4 border-blue-200"
              >
                <h2 className="text-2xl font-bold text-white text-center mb-6">AI RECEPTIONIST</h2>

                <div className="grid grid-cols-1 gap-3">
                  {[
                    "Conversation Engine",
                    "Intent Detection"
                  ].map((item, index) => (
                    <motion.div
                      key={index}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.5, delay: 0.8 + index * 0.1 }}
                      className="bg-white/95 backdrop-blur-sm rounded-lg p-3 text-sm font-medium text-gray-700 shadow-md"
                    >
                      {item}
                    </motion.div>
                  ))}

                  <div className="relative">
                    <motion.div
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.5, delay: 1.0 }}
                      className="bg-white/95 backdrop-blur-sm rounded-lg p-3 text-sm font-medium text-gray-700 shadow-md"
                    >
                      Lead Qualification
                    </motion.div>
                    <motion.div
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.5, delay: 1.2 }}
                      className="absolute -right-32 top-1/2 -translate-y-1/2 bg-emerald-500 text-white px-3 py-1.5 rounded-md text-xs font-semibold shadow-lg whitespace-nowrap flex items-center gap-2"
                    >
                      <span>→ CRM Sync</span>
                    </motion.div>
                  </div>

                  <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.5, delay: 1.1 }}
                    className="bg-white/95 backdrop-blur-sm rounded-lg p-3 text-sm font-medium text-gray-700 shadow-md"
                  >
                    Appointment Scheduler
                  </motion.div>

                  <div className="relative">
                    <motion.div
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.5, delay: 1.2 }}
                      className="bg-white/95 backdrop-blur-sm rounded-lg p-3 text-sm font-medium text-gray-700 shadow-md"
                    >
                      Human Handoff Manager
                    </motion.div>
                    <motion.div
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.5, delay: 1.4 }}
                      className="absolute -right-40 top-1/2 -translate-y-1/2 bg-indigo-500 text-white px-3 py-1.5 rounded-md text-xs font-semibold shadow-lg whitespace-nowrap flex items-center gap-2"
                    >
                      <span>→ Team Dashboard</span>
                    </motion.div>
                  </div>
                </div>
              </motion.div>

              <div className="flex justify-center">
                <Arrow direction="down" delay={1.3} length={40} />
              </div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 1.4 }}
                className="text-center"
              >
                <h2 className="text-lg font-semibold text-gray-700 mb-4">AI Layer</h2>
              </motion.div>

              <div className="grid grid-cols-2 gap-4">
                <ComponentBox
                  title="AI Reasoning Engine"
                  color="border-purple-400"
                  delay={1.5}
                  size="small"
                />
                <ComponentBox
                  title="Prompt Orchestration"
                  color="border-blue-400"
                  delay={1.6}
                  size="small"
                />
                <ComponentBox
                  title="RAG Pipeline"
                  color="border-indigo-400"
                  delay={1.7}
                  size="small"
                />
                <ComponentBox
                  title="Vector Search"
                  color="border-violet-400"
                  delay={1.8}
                  size="small"
                />
              </div>
            </div>

            <div className="hidden lg:flex items-center justify-center h-full">
              <Arrow direction="left" delay={1.9} length={60} />
            </div>

            <div className="flex flex-col gap-4">
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.6, delay: 2.0 }}
                className="text-center"
              >
                <h2 className="text-lg font-semibold text-gray-700 mb-4">Business Systems</h2>
              </motion.div>

              <div className="flex flex-col gap-4">
                <ComponentBox
                  title="CRM"
                  color="border-blue-300"
                  delay={2.1}
                  size="small"
                />
                <ComponentBox
                  title="Calendar"
                  color="border-purple-300"
                  delay={2.2}
                  size="small"
                />
                <ComponentBox
                  title="Email Platform"
                  color="border-indigo-300"
                  delay={2.3}
                  size="small"
                />
                <ComponentBox
                  title="Internal Team Dashboard"
                  color="border-violet-300"
                  delay={2.4}
                  size="small"
                />
              </div>
            </div>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 2.5 }}
            className="mt-12"
          >
            <h2 className="text-lg font-semibold text-gray-700 mb-6 text-center">Knowledge & Data Layer</h2>

            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
              <ComponentBox
                title="Business Knowledge Base"
                color="border-emerald-300"
                delay={2.6}
                size="small"
              />
              <ComponentBox
                title="FAQs"
                color="border-teal-300"
                delay={2.7}
                size="small"
              />
              <ComponentBox
                title="Services & Pricing"
                color="border-cyan-300"
                delay={2.8}
                size="small"
              />
              <ComponentBox
                title="PostgreSQL"
                color="border-blue-400"
                delay={2.9}
                size="small"
              />
              <ComponentBox
                title="Redis"
                color="border-red-400"
                delay={3.0}
                size="small"
              />
              <ComponentBox
                title="Vector Database"
                color="border-purple-400"
                delay={3.1}
                size="small"
              />
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 1, delay: 3.2 }}
            className="mt-8 text-center text-sm text-gray-500"
          >
            <p>Arrows indicate real-time data flow between system components</p>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
