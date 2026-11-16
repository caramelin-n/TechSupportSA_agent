import { MAX_FILES } from "../chat/constants";

/** Chips de los adjuntos ya subidos, pendientes de enviar con el mensaje. */
export default function AttachmentChips({ attachments, onRemove, disabled }) {
  if (attachments.length === 0) return null;

  return (
    <ul className="flex flex-wrap gap-2 px-4 pb-2">
      {attachments.map((adjunto) => (
        <li
          key={adjunto.id}
          className="flex items-center gap-2 rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-xs text-gray-700"
        >
          <span className="max-w-[14rem] truncate" title={adjunto.filename}>
            {adjunto.filename}
          </span>
          <span className="text-gray-400">{adjunto.kind}</span>
          <button
            type="button"
            onClick={() => onRemove(adjunto.id)}
            disabled={disabled}
            aria-label={`Quitar ${adjunto.filename}`}
            className="text-gray-400 transition hover:text-gray-700 disabled:opacity-50"
          >
            ×
          </button>
        </li>
      ))}
      <li className="self-center text-xs text-gray-400">
        {attachments.length}/{MAX_FILES}
      </li>
    </ul>
  );
}
