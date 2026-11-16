/** Burbuja de un mensaje de la conversación. */
export default function MessageBubble({ message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={
          isUser
            ? "max-w-[85%] rounded-lg bg-gray-900 px-4 py-3 text-sm text-white"
            : "max-w-[85%] rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm text-gray-800"
        }
      >
        <p className="whitespace-pre-wrap break-words">{message.text}</p>

        {message.attachments?.length > 0 && (
          <ul className="mt-2 space-y-1">
            {message.attachments.map((adjunto, i) => (
              <li
                key={`${adjunto.filename}-${i}`}
                className={`text-xs ${isUser ? "text-gray-300" : "text-gray-500"}`}
              >
                Adjunto: {adjunto.filename} ({adjunto.kind})
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
