"""Lógica de descarga compartida por la app y por el servicio."""
import json
import os
import re
import shutil

import yt_dlp
import yt_dlp.version

try:
    import certifi
    os.environ["SSL_CERT_FILE"] = certifi.where()
except Exception:
    pass

BASE = "/storage/emulated/0"

# Clientes de YouTube a probar en orden (None = el predeterminado)
CLIENTES_YT = [None, ["web_embedded"], ["visionos"], ["tv"],
               ["android"], ["ios"]]
PLANTILLA = "%(title).60s [%(id.-6:)s].%(ext)s"


class Cancelado(Exception):
    pass


class Silencio:
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


def version_ytdlp():
    try:
        return yt_dlp.version.__version__
    except Exception:
        return "?"


def contexto():
    """Contexto de Android: el servicio si estamos en él, si no la app."""
    from jnius import autoclass
    ctx = autoclass("org.kivy.android.PythonService").mService
    if ctx is None:
        ctx = autoclass("org.kivy.android.PythonActivity").mActivity
    return ctx


def ruta_config():
    try:
        base = contexto().getFilesDir().getAbsolutePath()
    except Exception:
        base = os.getcwd()
    return os.path.join(base, "musicdl_config.json")


def leer_config():
    c = {"destino": "Automática", "calidad": "1080", "sub": ""}
    try:
        with open(ruta_config(), encoding="utf-8") as f:
            c.update(json.load(f))
    except Exception:
        pass
    return c


def carpeta_trabajo(formato):
    """En el APK: carpeta privada de la app. Fuera: Movies/Music."""
    try:
        ruta = contexto().getExternalFilesDir(None)
        return ruta.getAbsolutePath(), True
    except Exception:
        sub = "Music" if formato == "audio" else "Movies"
        return f"{BASE}/{sub}", False


def limpiar_sub(sub):
    """Deja solo letras, números, espacios, guiones y guion bajo."""
    sub = re.sub(r"[^\w\- ]", "", sub or "").strip()
    return sub[:40]


def carpeta_destino(formato, destino, sub):
    """Ruta relativa pública. Automática: Music (audio) / Movies (video)."""
    if destino == "Descargas":
        base = "Download"
    else:
        base = "Music" if formato == "audio" else "Movies"
    sub = limpiar_sub(sub)
    return base + "/" + (sub + "/" if sub else "")


def limpiar_parciales(carpeta):
    """Borra los restos de una descarga cancelada."""
    try:
        for f in os.listdir(carpeta):
            if f.endswith((".part", ".ytdl", ".temp")) or ".part-Frag" in f:
                os.remove(os.path.join(carpeta, f))
    except Exception:
        pass


def publicar(ruta, formato, relativa):
    from jnius import autoclass
    ctx = contexto()
    sdk = autoclass("android.os.Build$VERSION").SDK_INT
    if sdk < 29:
        # Android 9 o menor: se mueve directo a la carpeta pública
        destino = f"{BASE}/{relativa}"
        os.makedirs(destino, exist_ok=True)
        final = os.path.join(destino, os.path.basename(ruta))
        shutil.move(ruta, final)
        try:
            Scan = autoclass("android.media.MediaScannerConnection")
            Scan.scanFile(ctx, [final], None, None)
        except Exception:
            pass
        return final
    CV = autoclass("android.content.ContentValues")
    File = autoclass("java.io.File")
    Files = autoclass("java.nio.file.Files")
    ext = os.path.splitext(ruta)[1].lower()
    if formato == "audio":
        tabla = autoclass("android.provider.MediaStore$Audio$Media")
        mime = {".m4a": "audio/mp4", ".webm": "audio/webm",
                ".mp3": "audio/mpeg"}.get(ext, "audio/mp4")
    else:
        tabla = autoclass("android.provider.MediaStore$Video$Media")
        mime = {".webm": "video/webm",
                ".mkv": "video/x-matroska"}.get(ext, "video/mp4")
    if relativa.startswith("Download"):
        tabla = autoclass("android.provider.MediaStore$Downloads")
    resolver = ctx.getContentResolver()
    cv = CV()
    cv.put("_display_name", os.path.basename(ruta))
    cv.put("mime_type", mime)
    cv.put("relative_path", relativa)
    uri = resolver.insert(tabla.EXTERNAL_CONTENT_URI, cv)
    salida = resolver.openOutputStream(uri)
    Files.copy(File(ruta).toPath(), salida)
    salida.close()
    # Android puede cambiar el nombre si ya existía uno igual
    nombre = os.path.basename(ruta)
    try:
        cur = resolver.query(uri, None, None, None, None)
        if cur is not None:
            if cur.moveToFirst():
                idx = cur.getColumnIndex("_display_name")
                if idx >= 0:
                    nombre = cur.getString(idx)
            cur.close()
    except Exception:
        pass
    os.remove(ruta)
    return f"{BASE}/{relativa}{nombre}"


def hacer_opciones(formato, calidad, hook, carpeta):
    op = {"noplaylist": True, "overwrites": True,
          "logger": Silencio(), "noprogress": True,
          "progress_hooks": [hook],
          "outtmpl": f"{carpeta}/{PLANTILLA}"}
    if formato == "audio":
        op["format"] = "bestaudio[ext=m4a]/bestaudio"
    else:
        op["format"] = "best"
        op["format_sort"] = [f"res:{calidad}", "vcodec:h264"]
    return op


def extraer_enlace(texto):
    """Saca el primer enlace de un texto compartido."""
    m = re.search(r"https?://\S+", texto or "")
    return m.group(0) if m else ""


def descargar(url, formato, destino, sub, calidad,
              al_progreso=None, al_estado=None, cancelado=None):
    """Descarga y guarda. Devuelve (carpeta_relativa, ruta_completa).

    Lanza Cancelado si cancelado() devuelve True.
    """
    cancelado = cancelado or (lambda: False)
    carpeta = None

    def hook(d):
        if cancelado():
            raise Cancelado()
        if d.get("status") == "downloading" and al_progreso:
            tot = d.get("total_bytes") or d.get("total_bytes_estimate")
            if tot:
                al_progreso(int(d["downloaded_bytes"] * 100 // tot))

    try:
        carpeta, privada = carpeta_trabajo(formato)
        # Para YouTube se prueban varios "clientes" hasta que uno
        # entregue formatos descargables.
        intentos = CLIENTES_YT if "youtu" in url else [None]
        ruta = None
        ultimo_error = ""
        for n, cliente in enumerate(intentos, 1):
            if cancelado():
                raise Cancelado()
            if n > 1 and al_estado:
                al_estado(f"Probando otro método ({n}/{len(intentos)})...")
            op = hacer_opciones(formato, int(calidad), hook, carpeta)
            if cliente:
                op["extractor_args"] = {
                    "youtube": {"player_client": cliente}}
            try:
                with yt_dlp.YoutubeDL(op) as ydl:
                    info = ydl.extract_info(url, download=True)
                    ruta = info["requested_downloads"][0]["filepath"]
                break
            except Exception as e:
                if cancelado():
                    raise Cancelado()
                ultimo_error = str(e)
        if not ruta:
            raise RuntimeError(ultimo_error or "sin resultado")
        relativa = carpeta_destino(formato, destino, sub)
        completa = ruta
        if privada:
            if al_estado:
                al_estado("Guardando en la galería...")
            completa = publicar(ruta, formato, relativa)
        return relativa, completa
    except Cancelado:
        if carpeta:
            limpiar_parciales(carpeta)
        raise
