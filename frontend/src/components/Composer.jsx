import { useRef, useState } from "react";
import { ACCEPT_ATTR, MAX_FILES } from "../chat/constants";
import AttachmentChips from "./AttachmentChips";

/**
 * Entrada del chat: texto + adjuntos + enviar.
 *
 * Enter envía; Shift+Enter agrega un salto de línea.
 */
export default function Composer({
  onSend,
  onAddFiles,
  attachments,
  onRemoveAttachment,
  disabled,
  uploading,
}) {
  const [text, setText] = useState("");
  const fileRef = useRef(null);

  const canSend = !disabled && !uploading && text.trim().length > 0;

  function submit() {
    if (!canSend) return;
    onSend(text);
    setText("");
  }

  function onKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  function onFiles(event) {
    const files = event.target.files;
    if (files?.length) onAddFiles(files);
    // Permite volver a elegir el mismo archivo.
    event.target.value = "";
  }

  return (
    <div className="border-t border-gray-200 bg-white">
      <AttachmentChips
        attachments={attachments}
        onRemove={onRemoveAttachment}
        disabled={disabled || uploading}
      />

      <div className="flex items-end gap-2 px-4 py-3">
        <div className="flex-1">
          <label htmlFor="chat-message" className="sr-only">
            Mensaje
          </label>
          <textarea
            id="chat-message"
            rows={2}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKeyDown}
            disabled={disabled || uploading}
            placeholder={
              disabled
                ? "Resolvé la acción pendiente para seguir escribiendo…"
                : "Escribí tu mensaje…"
            }
            className="w-full resize-none rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-800 focus:border-gray-400 focus:outline-none disabled:bg-gray-50 disabled:text-gray-400"
          />
        </div>

        <div className="flex items-center gap-2">
          <input
            ref={fileRef}
            type="file"
            multiple
            accept={ACCEPT_ATTR}
            onChange={onFiles}
            className="sr-only"
            aria-label="Adjuntar archivos"
          />
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={disabled || uploading || attachments.length >= MAX_FILES}
            className="rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 transition hover:bg-gray-100 disabled:opacity-50"
          >
            {uploading ? "Subiendo…" : "Adjuntar"}
          </button>

          <button
            type="button"
            onClick={submit}
            disabled={!canSend}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-gray-700 disabled:opacity-50"
          >
            Enviar
          </button>
        </div>
      </div>
    </div>
  );
}
