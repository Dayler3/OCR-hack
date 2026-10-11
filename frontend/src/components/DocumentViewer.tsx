import * as React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { FieldItem, PageInfo } from "@/types";

interface DocumentViewerProps {
  pages: PageInfo[];
  fields: FieldItem[];
  activeFieldKey: string | null;
  activePage: number;
  /** hover по прямоугольнику на скане (бонус: интерактивная подсветка) */
  onHoverField?: (key: string | null) => void;
  onActivePageChange?: (page: number) => void;
}

export const DocumentViewer: React.FC<DocumentViewerProps> = ({
  pages,
  fields,
  activeFieldKey,
  activePage,
  onHoverField,
  onActivePageChange,
}) => {
  const page = pages[activePage];
  if (!page || !page.image_b64) {
    return (
      <div className="rounded-lg border border-dashed p-10 text-center text-sm text-muted-foreground">
        {pages.length ? "Изображения страниц отключены" : "Документ не загружен"}
      </div>
    );
  }

  const src = `data:image/png;base64,${page.image_b64}`;

  return (
    <div className="space-y-2">
      <div className="relative w-full overflow-hidden rounded-lg border bg-slate-900/5 shadow-inner">
        <img
          src={src}
          alt={`Страница ${activePage + 1}`}
          className="w-full h-auto block select-none pointer-events-none"
        />
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none"
          viewBox={`0 0 ${page.width} ${page.height}`}
        >
          {fields.map((field) => {
            if (!field.bbox || field.value === "не найдено" || field.page !== activePage) return null;
            const [x1, y1, x2, y2] = field.bbox;
            const isActive = activeFieldKey === field.key;

            return (
              <rect
                key={field.key}
                x={x1}
                y={y1}
                width={x2 - x1}
                height={y2 - y1}
                className={`pointer-events-auto cursor-pointer transition-all duration-200 ${
                  isActive
                    ? "fill-primary/30 stroke-primary stroke-[3px]"
                    : "fill-blue-500/15 stroke-blue-500/60 stroke-[1.5px] hover:fill-blue-500/30"
                }`}
                onMouseEnter={() => onHoverField?.(field.key)}
                onMouseLeave={() => onHoverField?.(null)}
              />
            );
          })}
        </svg>
      </div>

      {pages.length > 1 && (
        <div className="flex items-center justify-center gap-3 text-sm text-muted-foreground">
          <button
            className="inline-flex items-center rounded-md border px-2 py-1 hover:bg-muted disabled:opacity-40"
            disabled={activePage === 0}
            onClick={() => onActivePageChange?.(activePage - 1)}
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          Страница {activePage + 1} из {pages.length}
          <button
            className="inline-flex items-center rounded-md border px-2 py-1 hover:bg-muted disabled:opacity-40"
            disabled={activePage === pages.length - 1}
            onClick={() => onActivePageChange?.(activePage + 1)}
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
};
