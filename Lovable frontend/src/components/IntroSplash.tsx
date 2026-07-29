import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Droplets } from "lucide-react";

const TITLE = "FloodWatch";

/**
 * One-time launch animation: the FloodWatch mark springs in with an expanding
 * ripple, the title reveals letter-by-letter, then the whole overlay fades away
 * to reveal the app. Shows once per browser session.
 */
export function IntroSplash() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    try {
      if (sessionStorage.getItem("fw_intro")) return;
      sessionStorage.setItem("fw_intro", "1");
    } catch {
      /* private mode — just show it */
    }
    setShow(true);
    const t = setTimeout(() => setShow(false), 2400);
    return () => clearTimeout(t);
  }, []);

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          key="intro"
          className="fixed inset-0 z-[9999] flex flex-col items-center justify-center"
          style={{ backgroundColor: "#0a0e16" }}
          initial={{ opacity: 1 }}
          exit={{ opacity: 0, filter: "blur(6px)", transition: { duration: 0.7, ease: "easeInOut" } }}
        >
          {/* expanding ripples */}
          {[0, 0.35].map((delay, i) => (
            <motion.span
              key={i}
              className="absolute rounded-full"
              style={{ border: "1px solid rgba(90,176,240,0.45)" }}
              initial={{ width: 64, height: 64, opacity: 0.6 }}
              animate={{ width: 360, height: 360, opacity: 0 }}
              transition={{ duration: 1.8, ease: "easeOut", delay, repeat: Infinity, repeatDelay: 0.2 }}
            />
          ))}

          {/* logo mark */}
          <motion.div
            className="relative flex h-16 w-16 items-center justify-center rounded-2xl"
            style={{
              background: "linear-gradient(135deg,#3b82c4,#46A758)",
              boxShadow: "0 12px 44px -8px rgba(59,130,196,0.75)",
            }}
            initial={{ scale: 0, rotate: -35, opacity: 0 }}
            animate={{ scale: 1, rotate: 0, opacity: 1 }}
            transition={{ type: "spring", stiffness: 200, damping: 13 }}
          >
            <Droplets className="h-8 w-8 text-white" />
          </motion.div>

          {/* title, letter by letter */}
          <motion.div
            className="mt-6 flex text-4xl font-semibold tracking-tight sm:text-5xl"
            style={{ fontFamily: "Space Grotesk, sans-serif" }}
            initial="hidden"
            animate="show"
            variants={{ show: { transition: { staggerChildren: 0.05, delayChildren: 0.35 } } }}
          >
            {TITLE.split("").map((ch, i) => (
              <motion.span
                key={i}
                className={i < 5 ? "text-white" : "text-white/55"}
                variants={{ hidden: { y: 26, opacity: 0 }, show: { y: 0, opacity: 1 } }}
                transition={{ type: "spring", stiffness: 320, damping: 22 }}
              >
                {ch}
              </motion.span>
            ))}
          </motion.div>

          <motion.div
            className="mt-2 text-sm tracking-wide text-white/45"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 1 }}
          >
            Flash-flood risk · Pakistan
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
