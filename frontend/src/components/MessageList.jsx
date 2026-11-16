import MessageBubble from "./MessageBubble";

/**
 * Historial de la conversación. Con la conversación vacía muestra sugerencias.
 */
export default function MessageList({ messages, sending, suggestions, onSuggestion }) {
  if (messages.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 px-4 py-10 text-center">
        <div>
          <p className="text-base font-medium text-gray-800">
            Contame qué problema tenés
          </p>
          <p className="mt-1 text-sm text-gray-500">
            Podés escribir en lenguaje natural o adjuntar una captura, un TXT o un
            LOG.
          </p>
        </div>
        <div className="flex flex-col gap-2">
          {suggestions.map((texto) => (
            <button
              key={texto}
              type="button"
              onClick={() => onSuggestion(texto)}
              className="rounded-md border border-gray-200 bg-white px-3 py-2 text-left text-sm text-gray-700 transition hover:bg-gray-50"
            >
              {texto}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div
      role="log"
      aria-live="polite"
      aria-label="Conversación"
      className="flex-1 space-y-3 overflow-y-auto px-4 py-4"
    >
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}

      {sending && (
        <div className="flex justify-start">
          <div className="rounded-lg border border-dashed border-gray-300 bg-white px-4 py-3 text-sm text-gray-500">
            El agente está escribiendo…
          </div>
        </div>
      )}
    </div>
  );
}
