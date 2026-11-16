/** Constantes de la pantalla de chat. */

export const MAX_FILES = 5;
export const MAX_FILE_MB = 5;

export const ACCEPTED_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp", ".txt", ".log"];
export const ACCEPT_ATTR = ACCEPTED_EXTENSIONS.join(",");

export const CONVERSATION_KEY = "techsupport.conversation";

export const SUGGESTIONS = [
  "La impresora del 2do piso no responde",
  "Mostrame mis tickets abiertos",
  "¿Cuántos tickets hay por estado?",
];

/** Extensión en minúsculas, con el punto. */
export function extensionOf(name) {
  const dot = name.lastIndexOf(".");
  return dot === -1 ? "" : name.slice(dot).toLowerCase();
}

/** Valida cantidad, tamaño y tipo. Devuelve un mensaje de error o null. */
export function validateFiles(files, alreadyAttached = 0) {
  if (files.length === 0) return null;

  if (alreadyAttached + files.length > MAX_FILES) {
    return `Podés adjuntar hasta ${MAX_FILES} archivos por mensaje.`;
  }

  for (const file of files) {
    if (!ACCEPTED_EXTENSIONS.includes(extensionOf(file.name))) {
      return `Formato no admitido: "${file.name}". Se aceptan PNG, JPG, WEBP, TXT o LOG.`;
    }
    if (file.size > MAX_FILE_MB * 1024 * 1024) {
      return `"${file.name}" supera el máximo de ${MAX_FILE_MB} MB.`;
    }
    if (file.size === 0) {
      return `"${file.name}" está vacío.`;
    }
  }

  return null;
}
