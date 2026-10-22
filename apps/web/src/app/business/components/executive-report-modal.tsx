"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Download, X } from "lucide-react";
import type { Analytics } from "../types";
import { useI18n } from "@/i18n/context";

interface ExecutiveReportModalProps {
  show: boolean;
  report: { markdown: string; html: string } | null;
  reportPeriod: string;
  analytics: Analytics | null;
  selectedId: number | null;
  onClose: () => void;
}

export function ExecutiveReportModal({ show, report, reportPeriod, analytics, selectedId, onClose }: ExecutiveReportModalProps) {
  const { t } = useI18n();
  if (!show || !report) return null;

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4"
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      >
        <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
        <motion.div
          role="dialog"
          aria-modal="true"
          aria-labelledby="executive-report-title"
          className="relative w-full max-w-3xl max-h-[85vh] bg-card border border-border rounded-3xl shadow-2xl flex flex-col overflow-hidden"
          initial={{ scale: 0.92, y: 30 }} animate={{ scale: 1, y: 0 }}
          exit={{ scale: 0.92, y: 30 }}
          transition={{ type: "spring", stiffness: 400, damping: 34 }}
        >
          <div className="flex items-center justify-between px-6 py-4 border-b border-border shrink-0">
            <div>
              <h2 id="executive-report-title" className="font-bold text-lg">{t("business.report_title")}</h2>
              <p className="text-xs text-muted-foreground capitalize">{t("business.period_" + reportPeriod)} · {analytics?.project_name}</p>
            </div>
            <div className="flex items-center gap-2">
              <a
                href={`data:text/markdown;charset=utf-8,${encodeURIComponent(report.markdown)}`}
                download={`report_${selectedId}_${reportPeriod}.md`}
                className="flex items-center gap-1.5 text-xs font-semibold border border-border px-3 py-1.5 rounded-lg hover:bg-muted transition-colors"
              >
                <Download size={13} /> .MD
              </a>
              <a
                href={`data:text/html;charset=utf-8,${encodeURIComponent(report.html)}`}
                download={`report_${selectedId}_${reportPeriod}.html`}
                className="flex items-center gap-1.5 text-xs font-semibold border border-border px-3 py-1.5 rounded-lg hover:bg-muted transition-colors"
              >
                <Download size={13} /> .HTML
              </a>
              <button
                onClick={() => {
                  const printWin = window.open("", "_blank");
                  if (printWin) {
                    printWin.document.write(`
                      <!DOCTYPE html>
                      <html>
                      <head>
                        <title>Executive Report - ${analytics?.project_name}</title>
                        <style>
                          @media print { @page { margin: 15mm; size: A4; } }
                          body { font-family: sans-serif; padding: 24px; color: #111; }
                        </style>
                      </head>
                      <body onload="window.print();">
                        ${report.html}
                      </body>
                      </html>
                    `);
                    printWin.document.close();
                  }
                }}
                className="flex items-center gap-1.5 text-xs font-semibold border border-primary bg-primary text-primary-foreground px-3 py-1.5 rounded-lg hover:opacity-90 transition-opacity"
              >
                <Download size={13} /> .PDF
              </button>
              <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-muted transition-colors">
                <X size={18} />
              </button>
            </div>
          </div>
          <div className="overflow-y-auto p-6">
            <pre className="text-xs text-muted-foreground whitespace-pre-wrap font-mono leading-relaxed">
              {report.markdown}
            </pre>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
