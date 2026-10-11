import * as React from "react";
import { CheckCircle2, AlertTriangle, HelpCircle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import type { Verdict } from "@/types";

const CONFIGS = {
  OK: {
    title: "Документ в порядке",
    icon: CheckCircle2,
    alertClass: "border-emerald-500/40 text-emerald-800 bg-emerald-500/10",
  },
  MISSING_FIELDS: {
    title: "Не хватает обязательных данных",
    icon: AlertTriangle,
    alertClass: "border-amber-500/40 text-amber-800 bg-amber-500/10",
  },
  NO_INFO: {
    title: "Информация отсутствует",
    icon: HelpCircle,
    alertClass: "border-slate-500/40 text-slate-800 bg-slate-500/10",
  },
} as const;

export const VerdictAlert: React.FC<{ verdict: Verdict }> = ({ verdict }) => {
  const current = CONFIGS[verdict.status];
  const Icon = current.icon;

  return (
    <Alert className={`${current.alertClass} shadow-sm`}>
      <Icon className="h-5 w-5 shrink-0" />
      <div className="ml-1">
        <AlertTitle className="text-sm font-semibold">{current.title}</AlertTitle>
        <AlertDescription className="mt-1 text-sm leading-relaxed opacity-95">
          {verdict.text}
        </AlertDescription>
        {verdict.rule_source && (
          <div className="mt-2 text-xs font-mono font-medium opacity-80">
            Основание: {verdict.rule_source}
          </div>
        )}
      </div>
    </Alert>
  );
};
