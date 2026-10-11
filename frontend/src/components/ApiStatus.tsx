import * as React from "react";
import { CircleCheck, CircleX } from "lucide-react";
import { getHealth } from "@/lib/api";
import type { HealthInfo } from "@/types";

/** Индикатор доступности бэкенда и OCR-движка (опрос /api/health). */
export const ApiStatus: React.FC = () => {
  const [health, setHealth] = React.useState<HealthInfo | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let alive = true;
    const poll = () =>
      getHealth()
        .then((h) => alive && (setHealth(h), setError(null)))
        .catch((e) => alive && setError(String(e.message ?? e)));
    poll();
    const id = setInterval(poll, 15000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  if (error) {
    return (
      <div className="inline-flex items-center gap-1.5 text-xs text-red-600">
        <CircleX className="h-4 w-4" /> Бэкенд недоступен ({error})
      </div>
    );
  }
  if (!health) return null;

  const ocrReady = health.ocr_engine !== null && !health.ocr_engine.includes("недоступен");
  return (
    <div className="inline-flex items-center gap-3 text-xs text-muted-foreground">
      <span className="inline-flex items-center gap-1.5">
        <CircleCheck className="h-4 w-4 text-emerald-600" />
        API: {health.schemas_loaded} типа документов
      </span>
      <span className="inline-flex items-center gap-1.5">
        {ocrReady ? (
          <>
            <CircleCheck className="h-4 w-4 text-emerald-600" />
            OCR: {health.ocr_engine}
          </>
        ) : (
          <>
            <CircleX className="h-4 w-4 text-amber-600" />
            OCR {health.ocr_engine}
          </>
        )}
      </span>
    </div>
  );
};
