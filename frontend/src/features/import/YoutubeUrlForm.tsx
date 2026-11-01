"use client";

import { useState, type FormEvent } from "react";
import { ArrowRight, Link2 } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { parseYoutubeUrl } from "@/lib/import-validation";

export interface YoutubeUrlFormProps {
  /** Receives a validated, canonical `https://www.youtube.com/watch?v=…` URL. */
  onSubmit: (url: string) => void;
  isSubmitting?: boolean;
  /** Error from the server, shown when the link itself is valid. */
  error?: string | null;
}

export function YoutubeUrlForm({
  onSubmit,
  isSubmitting = false,
  error,
}: YoutubeUrlFormProps) {
  const [value, setValue] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [submittedValue, setSubmittedValue] = useState<string | null>(null);
  // A server error describes the submitted link, so hide it once that changes.
  const visibleError =
    validationError ?? (value === submittedValue ? error : null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const result = parseYoutubeUrl(value);

    if (!result.ok) {
      setValidationError(result.message);
      return;
    }

    setValidationError(null);
    setSubmittedValue(value);
    onSubmit(result.url);
  }

  function handleChange(nextValue: string) {
    setValue(nextValue);
    // Once an error is showing, re-check live so it clears as soon as it's fixed.
    if (validationError) {
      const result = parseYoutubeUrl(nextValue);
      setValidationError(result.ok ? null : result.message);
    }
  }

  function handleBlur() {
    // Don't nag about an empty field the person simply tabbed through.
    if (value.trim()) {
      const result = parseYoutubeUrl(value);
      setValidationError(result.ok ? null : result.message);
    }
  }

  return (
    <form noValidate onSubmit={handleSubmit} className="flex flex-col gap-4">
      <Input
        label="YouTube video link"
        type="url"
        inputMode="url"
        autoComplete="off"
        spellCheck={false}
        placeholder="https://www.youtube.com/watch?v=…"
        icon={<Link2 />}
        value={value}
        onChange={(event) => handleChange(event.target.value)}
        onBlur={handleBlur}
        disabled={isSubmitting}
        hint="Paste a link to a public YouTube video you’re allowed to download."
        error={visibleError}
      />
      <Button
        type="submit"
        size="lg"
        fullWidth
        isLoading={isSubmitting}
        trailingIcon={<ArrowRight />}
      >
        {isSubmitting ? "Importing video…" : "Import video"}
      </Button>
    </form>
  );
}
