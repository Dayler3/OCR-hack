import * as React from "react";
import { Landmark } from "lucide-react";
import { ApiStatus } from "@/components/ApiStatus";
import { DocumentViewer } from "@/components/DocumentViewer";
import { FieldsCard } from "@/components/FieldsCard";
import { UploadZone } from "@/components/UploadZone";
import { VerdictAlert } from "@/components/VerdictAlert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { analyze, getSchemas } from "@/lib/api";
import type { AnalyzeResponse, SchemaInfo } from "@/types";

export default function App() {
  const [schemas, setSchemas] = React.useState<SchemaInfo[]>([]);
  const [file, setFile] = React.useState<File | null>(null);
  const [question, setQuestion] = React.useState("");
  const [docType, setDocType] = React.useState("auto");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<AnalyzeResponse | null>(null);
  const [activeFieldKey, setActiveFieldKey] = React.useState<string | null>(null);
  const [activePage, setActivePage] = React.useState(0);

  React.useEffect(() => {
    getSchemas()
      .then(setSchemas)
      .catch(() => setSchemas([]));
  }, []);

  // hover поля в карточке с bbox переключает страницу скана
  const hoverField = React.useCallback(
    (key: string | null) => {
      setActiveFieldKey(key);
      if (key && result) {
        const field = result.fields.find((f) => f.key === key);
        if (field?.bbox && field.page !== activePage) setActivePage(field.page);
      }
    },
    [result, activePage],
  );

  const submit = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setActivePage(0);
    try {
      const response = await analyze(
        file,
        question,
        docType === "auto" ? null : docType,
      );
      setResult(response);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen">
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <Landmark className="h-5 w-5" />
            </div>
            <div>
              <div className="text-sm font-semibold leading-tight">Цифровой секретарь</div>
              <div className="text-xs text-muted-foreground">онлайн-деканат</div>
            </div>
          </div>
          <ApiStatus />
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">
        <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle>Обращение студента</CardTitle>
              <CardDescription>
                Загрузите скан документа и задайте вопрос — ответ со ссылкой на пункт Положения
              </CardDescription>
            </CardHeader>
            <CardContent>
              <UploadZone
                file={file}
                question={question}
                docType={docType}
                schemas={schemas}
                loading={loading}
                onFileChange={setFile}
                onQuestionChange={setQuestion}
                onDocTypeChange={setDocType}
                onSubmit={submit}
              />
              {error && (
                <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                  {error}
                </div>
              )}
            </CardContent>
          </Card>

          <div className="space-y-4">
            {!result && !loading && (
              <div className="flex h-full min-h-[300px] items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
                Результат проверки появится здесь
              </div>
            )}
            {loading && (
              <div className="flex h-full min-h-[300px] items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
                Идёт распознавание: препроцессинг → OCR → извлечение полей → проверка по Положению…
              </div>
            )}

            {result && (
              <>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="secondary">{result.document_name}</Badge>
                  {result.classifier_confidence != null && (
                    <Badge variant="outline">
                      автоопределение: {Math.round(result.classifier_confidence * 100)}%
                    </Badge>
                  )}
                  {Object.entries(result.timings_ms).map(([k, v]) => (
                    <Badge key={k} variant="outline" className="font-mono text-[10px]">
                      {k}: {v} мс
                    </Badge>
                  ))}
                </div>

                <VerdictAlert verdict={result.verdict} />

                <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
                  <DocumentViewer
                    pages={result.pages}
                    fields={result.fields}
                    activeFieldKey={activeFieldKey}
                    activePage={activePage}
                    onHoverField={hoverField}
                    onActivePageChange={setActivePage}
                  />
                  <FieldsCard
                    documentName={result.document_name}
                    fields={result.fields}
                    activeFieldKey={activeFieldKey}
                    onHoverField={hoverField}
                  />
                </div>
              </>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
