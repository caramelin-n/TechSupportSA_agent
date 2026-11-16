import Composer from "../components/Composer";
import MessageList from "../components/MessageList";
import PendingActions from "../components/PendingActions";
import { SUGGESTIONS } from "../chat/constants";
import { useChat } from "../chat/useChat";

/** Pantalla principal: conversación con el agente de soporte. */
export default function ChatPage() {
  const chat = useChat();

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold text-gray-900">Asistente de soporte</h2>
        <p className="mt-1 text-sm text-gray-500">
          Describí el problema o adjuntá una captura, un TXT o un LOG. El agente
          crea y consulta tickets, siempre con tu confirmación.
        </p>
      </div>

      <div className="flex h-[calc(100vh-13rem)] min-h-[420px] flex-col overflow-hidden rounded-lg border border-gray-200 bg-gray-50">
        <MessageList
          messages={chat.messages}
          sending={chat.sending}
          suggestions={SUGGESTIONS}
          onSuggestion={chat.send}
        />

        {chat.pending.length > 0 && (
          <PendingActions
            actions={chat.pending}
            disabled={chat.sending}
            onApprove={() => chat.resolve("approve")}
            onReject={(reason) => chat.resolve("reject", reason)}
          />
        )}

        {chat.error && (
          <div
            role="alert"
            className="mx-4 mb-3 flex items-start justify-between gap-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700"
          >
            <span>{chat.error}</span>
            <button
              type="button"
              onClick={chat.dismissError}
              aria-label="Cerrar aviso"
              className="text-red-500 transition hover:text-red-800"
            >
              ×
            </button>
          </div>
        )}

        <Composer
          onSend={chat.send}
          onAddFiles={chat.addFiles}
          attachments={chat.attachments}
          onRemoveAttachment={chat.removeAttachment}
          disabled={chat.pending.length > 0}
          uploading={chat.uploading}
        />
      </div>
    </section>
  );
}
