import { useCallback, useState } from "react";
import { decide as apiDecide, sendMessage, uploadFiles } from "../api/chat";
import { CONVERSATION_KEY, validateFiles } from "./constants";

let seq = 0;

function nextId() {
  seq += 1;
  return `m-${Date.now()}-${seq}`;
}

function readConversation() {
  try {
    return window.sessionStorage.getItem(CONVERSATION_KEY);
  } catch {
    return null;
  }
}

function saveConversation(id) {
  try {
    if (id) window.sessionStorage.setItem(CONVERSATION_KEY, id);
  } catch {
    /* sessionStorage bloqueado: la conversación no persiste */
  }
}

function assistantMessage(text) {
  return { id: nextId(), role: "assistant", text };
}

/**
 * Estado de la conversación con el agente.
 *
 * `pending` no vacío significa que hay acciones esperando confirmación: el
 * backend rechaza mensajes nuevos (409) hasta resolverlas, así que la UI debe
 * bloquear el composer.
 */
export function useChat() {
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(readConversation);
  const [pending, setPending] = useState([]);
  const [attachments, setAttachments] = useState([]);
  const [sending, setSending] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);

  const busy = sending || uploading;
  const blocked = pending.length > 0 || busy;

  const send = useCallback(
    async (text) => {
      const message = text.trim();
      if (!message || blocked) return;

      const uploadIds = attachments.map((a) => a.id);
      const userMessage = {
        id: nextId(),
        role: "user",
        text: message,
        attachments: attachments.map((a) => ({ filename: a.filename, kind: a.kind })),
      };

      setError(null);
      setMessages((prev) => [...prev, userMessage]);
      setSending(true);
      try {
        const data = await sendMessage({ message, conversationId, uploadIds });
        if (!conversationId && data?.conversation_id) {
          setConversationId(data.conversation_id);
          saveConversation(data.conversation_id);
        }
        setMessages((prev) => [...prev, assistantMessage(data?.reply ?? "")]);
        setPending(data?.pending_actions ?? []);
        setAttachments([]);
      } catch (exc) {
        // Revertir el mensaje optimista: el envío no llegó a completarse.
        setMessages((prev) => prev.filter((m) => m.id !== userMessage.id));
        setError(exc.message ?? "No se pudo enviar el mensaje.");
      } finally {
        setSending(false);
      }
    },
    [attachments, blocked, conversationId],
  );

  const resolve = useCallback(
    async (decision, reason) => {
      if (!conversationId || busy) return;

      setError(null);
      setSending(true);
      try {
        const data = await apiDecide(conversationId, decision, reason);
        setMessages((prev) => [...prev, assistantMessage(data?.reply ?? "")]);
        setPending(data?.pending_actions ?? []);
        if (data?.conversation_id) {
          setConversationId(data.conversation_id);
          saveConversation(data.conversation_id);
        }
      } catch (exc) {
        setError(exc.message ?? "No se pudo resolver la acción.");
      } finally {
        setSending(false);
      }
    },
    [busy, conversationId],
  );

  const addFiles = useCallback(
    async (fileList) => {
      const files = Array.from(fileList ?? []);
      if (files.length === 0) return;

      const validation = validateFiles(files, attachments.length);
      if (validation) {
        setError(validation);
        return;
      }

      setError(null);
      setUploading(true);
      try {
        const uploaded = await uploadFiles(files);
        setAttachments((prev) => [...prev, ...uploaded]);
      } catch (exc) {
        setError(exc.message ?? "No se pudieron subir los adjuntos.");
      } finally {
        setUploading(false);
      }
    },
    [attachments.length],
  );

  const removeAttachment = useCallback((id) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  }, []);

  const dismissError = useCallback(() => setError(null), []);

  return {
    messages,
    conversationId,
    pending,
    attachments,
    sending,
    uploading,
    error,
    blocked,
    send,
    resolve,
    addFiles,
    removeAttachment,
    dismissError,
  };
}
