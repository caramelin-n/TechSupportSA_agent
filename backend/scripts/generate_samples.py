"""Genera los archivos ficticios de data/samples/ de forma determinista.

Uso: python scripts/generate_samples.py
Requiere: Pillow (ver requirements.txt). Sin foto de equipo: decisión del proyecto
omitirla; las capturas son sintéticas y 100% ficticias.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "data" / "samples"

INFO_LINES = [
    "INFO  Consulta ejecutada en {table} (filas={n})",
    "INFO  Health check ok: servicio de facturación v2.3.1",
    "INFO  Sesión iniciada usuario=demo_{i} origen=oficina",
    "INFO  Cache refrescada entradas={n}",
    "INFO  Heartbeat servicio interno ok",
    "INFO  Lectura de configuración desde /etc/demo/app.conf",
]
ERROR_BLOCK = [
    "ERROR Connection timeout after 30s (host=db-prod-01, port=5432)",
    "WARN  Reintentando conexión (1/3)",
    "ERROR Connection timeout after 30s (host=db-prod-01, port=5432)",
    "FATAL No se pudo establecer conexión. Cerrando aplicación.",
]


def _window(title: str, lines: list[str], accent=(220, 60, 60)) -> Image.Image:
    """Ventana sintética tipo captura de pantalla (ficticia)."""
    img = Image.new("RGB", (1280, 720), (245, 245, 245))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 1280, 48], fill=(30, 30, 40))
    d.text((16, 14), title, fill=(255, 255, 255))
    d.rectangle([80, 120, 1200, 120 + 56 * len(lines)], fill=(255, 255, 255), outline=(180, 180, 180))
    for i, line in enumerate(lines):
        y = 140 + i * 56
        d.text((110, y), line, fill=accent if i == 0 else (30, 30, 30))
    d.text((110, 640), "Captura sintética ficticia - TechSupport S.A.", fill=(120, 120, 120))
    return img


def screenshot_acceso_denegado() -> None:
    img = _window("Error - Accesos y permisos", ["Error 0x80070005: acceso denegado", "No tiene permisos para abrir esta carpeta."])
    img.save(SAMPLES / "captura_acceso_denegado.png")


def screenshot_navegador() -> None:
    img = _window("Navegador - Sin conexión", ["No se puede acceder a este sitio", "Compruebe su conexión a Internet e inténtelo de nuevo."])
    img.save(SAMPLES / "captura_navegador.png")


def screenshot_borrosa() -> None:
    img = _window("VPN - Conectando", ["Conectando a VPN...", "Error (ilegible en esta captura)"])
    img.filter(ImageFilter.GaussianBlur(radius=14)).save(SAMPLES / "captura_borrosa.png")


def app_facturacion_log() -> None:
    lines: list[str] = []
    lines.append("2026-10-12 08:59:58 INFO  Iniciando servicio de facturación v2.3.1")
    lines.append("2026-10-12 09:00:01 INFO  Conectando a base de datos db-prod-01")
    # 300 líneas INFO con bloques de error en posiciones fijas y deterministas.
    for i in range(300):
        minute = i // 60
        sec = (i % 60)
        stamp = f"2026-10-12 09:{minute:02d}:{sec:02d}"
        if i in (60, 150, 240):
            for err in ERROR_BLOCK:
                lines.append(f"{stamp} {err}")
            continue
        template = INFO_LINES[i % len(INFO_LINES)]
        lines.append(f"{stamp} " + template.format(table="copias", n=100 + i, i=i))
    (SAMPLES / "app_facturacion.log").write_text("\n".join(lines) + "\n", encoding="utf-8")


def log_ambiguo() -> None:
    lines = []
    for i in range(120):
        lines.append(f"2026-10-21 14:{i // 60:02d}:{i % 60:02d} " + INFO_LINES[i % len(INFO_LINES)].format(table="copias", n=50 + i, i=i))
        if i == 60:
            lines.append("2026-10-21 14:30:00 WARN  Respuesta lenta sin detalle adicional")
    (SAMPLES / "log_ambiguo.log").write_text("\n".join(lines) + "\n", encoding="utf-8")


def reporte_txt() -> None:
    text = (
        "Hola, desde ayer me pasa que cuando quiero imprimir el PDF del reporte\n"
        "la impresora del 2do piso no responde. Probé reiniciar y nada.\n"
        "Ya le avisé a Carla y a ella le pasa lo mismo.\n"
    )
    (SAMPLES / "reporte_impresora.txt").write_text(text, encoding="utf-8")


def main() -> None:
    SAMPLES.mkdir(parents=True, exist_ok=True)
    screenshot_acceso_denegado()
    screenshot_navegador()
    screenshot_borrosa()
    app_facturacion_log()
    log_ambiguo()
    reporte_txt()
    print(f"Samples generados en {SAMPLES}")


if __name__ == "__main__":
    main()
