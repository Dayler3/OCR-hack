import * as React from "react";
import { FileUp, Loader2, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { SchemaInfo } from "@/types";

interface UploadZoneProps {
  file: File | null;
  question: string;
  docType: string; // "auto" | ключ схемы
  schemas: SchemaInfo[];
  loading: boolean;
  onFileChange: (file: File | null) => void;
  onQuestionChange: (q: string) => void;
  onDocTypeChange: (t: string) => void;
  onSubmit: () => void;
}

export const UploadZone: React.FC<UploadZoneProps> = ({
  file, question, docType, schemas, loading,
  onFileChange, onQuestionChange, onDocTypeChange, onSubmit,
}) => {
  const [dragOver, setDragOver] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const pickFile = (f: File | undefined | null) => {
    if (f && /\.(jpe?g|png|pdf)$/i.test(f.name)) onFileChange(f);
  };

  return (
    <div className="space-y-3">
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          pickFile(e.dataTransfer.files?.[0]);
        }}
        className={`flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-8 text-center cursor-pointer transition-colors ${
          dragOver ? "border-primary bg-primary/5" : "border-border hover:bg-muted/40"
        }`}
      >
        <FileUp className="h-8 w-8 text-muted-foreground" />
        <div className="text-sm font-medium">
          {file ? file.name : "Перетащите скан или нажмите для выбора"}
        </div>
        <div className="text-xs text-muted-foreground">JPG, PNG или PDF</div>
        <input
          ref={inputRef}
          type="file"
          accept=".jpg,.jpeg,.png,.pdf"
          className="hidden"
          onChange={(e) => pickFile(e.target.files?.[0])}
        />
      </div>

      <div>
        <label className="text-xs font-medium text-muted-foreground">Тип документа</label>
        <Select
          className="mt-1"
          value={docType}
          onChange={(e) => onDocTypeChange(e.target.value)}
          disabled={loading}
        >
          <option value="auto">Определить автоматически</option>
          {schemas.map((s) => (
            <option key={s.key} value={s.key}>{s.name}</option>
          ))}
        </Select>
      </div>

      <div>
        <label className="text-xs font-medium text-muted-foreground">Вопрос студента</label>
        <Textarea
          className="mt-1"
          placeholder="Например: всё ли в порядке с моей справкой об обучении?"
          value={question}
          onChange={(e) => onQuestionChange(e.target.value)}
          disabled={loading}
        />
      </div>

      <Button className="w-full" onClick={onSubmit} disabled={loading || !file}>
        {loading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Распознаём документ… OCR на CPU может занять до минуты
          </>
        ) : (
          <>
            <Send className="h-4 w-4" />
            Проверить документ
          </>
        )}
      </Button>
    </div>
  );
};
