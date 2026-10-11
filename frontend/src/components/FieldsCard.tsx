import * as React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { FieldItem } from "@/types";

interface FieldsCardProps {
  documentName: string;
  fields: FieldItem[];
  activeFieldKey: string | null;
  onHoverField: (key: string | null) => void;
}

export const FieldsCard: React.FC<FieldsCardProps> = ({
  documentName,
  fields,
  activeFieldKey,
  onHoverField,
}) => {
  return (
    <Card className="shadow-sm">
      <CardHeader className="py-3 px-4 flex flex-row items-center justify-between border-b !space-y-0">
        <CardTitle className="text-base font-semibold">Карточка реквизитов</CardTitle>
        <Badge className="font-mono text-xs max-w-[220px] truncate" variant="outline">
          {documentName}
        </Badge>
      </CardHeader>
      <CardContent className="p-0">
        <div className="divide-y divide-border text-sm">
          {fields.map((field) => {
            const isMissing = field.value === "не найдено";
            const isActive = activeFieldKey === field.key;

            return (
              <div
                key={field.key}
                onMouseEnter={() => onHoverField(field.key)}
                onMouseLeave={() => onHoverField(null)}
                className={`flex justify-between items-center gap-3 py-2.5 px-4 transition-colors ${
                  field.bbox ? "cursor-pointer" : ""
                } ${isActive ? "bg-muted font-medium" : "hover:bg-muted/40"}`}
              >
                <span className="text-muted-foreground shrink-0">{field.label}</span>
                <span className="text-right min-w-0">
                  {isMissing ? (
                    <Badge
                      className="text-[11px] uppercase tracking-wider font-mono"
                      variant="destructive"
                    >
                      не найдено
                    </Badge>
                  ) : (
                    <span className="font-medium text-foreground break-words">{field.value}</span>
                  )}
                </span>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
};
