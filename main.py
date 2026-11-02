import os
import threading
import traceback

import yt_dlp
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

try:
    import certifi
    os.environ["SSL_CERT_FILE"] = certifi.where()
except Exception:
    pass

BASE = "/storage/emulated/0"
PLANTILLA = "%(title).60s [%(id.-6:)s].%(ext)s"


class Silencio:
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


def carpeta_trabajo(formato):
    """En el APK: carpeta privada de la app. Fuera: Movies/Music."""
    try:
        from jnius import autoclass
        Act = autoclass("org.kivy.android.PythonActivity")
        ruta = Act.mActivity.getExternalFilesDir(None)
        return ruta.getAbsolutePath(), True
    except Exception:
        sub = "Music" if formato == "audio" else "Movies"
        return f"{BASE}/{sub}", False


def publicar(ruta, formato):
    from jnius import autoclass
    Act = autoclass("org.kivy.android.PythonActivity")
    CV = autoclass("android.content.ContentValues")
    File = autoclass("java.io.File")
    Files = autoclass("java.nio.file.Files")
    ext = os.path.splitext(ruta)[1].lower()
    if formato == "audio":
        tabla = autoclass("android.provider.MediaStore$Audio$Media")
        mime = {".m4a": "audio/mp4", ".webm": "audio/webm",
                ".mp3": "audio/mpeg"}.get(ext, "audio/mp4")
        carpeta = "Music/"
    else:
        tabla = autoclass("android.provider.MediaStore$Video$Media")
        mime = {".webm": "video/webm",
                ".mkv": "video/x-matroska"}.get(ext, "video/mp4")
        carpeta = "Movies/"
    resolver = Act.mActivity.getContentResolver()
    cv = CV()
    cv.put("_display_name", os.path.basename(ruta))
    cv.put("mime_type", mime)
    cv.put("relative_path", carpeta)
    uri = resolver.insert(tabla.EXTERNAL_CONTENT_URI, cv)
    salida = resolver.openOutputStream(uri)
    Files.copy(File(ruta).toPath(), salida)
    salida.close()
    os.remove(ruta)


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


class Pantalla(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", padding=20,
                         spacing=12, **kw)
        self.enlace = TextInput(hint_text="Pega el enlace aquí",
                                multiline=False, size_hint_y=None,
                                height=120)
        self.calidad = Spinner(text="1080",
                               values=("360", "480", "720", "1080"),
                               size_hint_y=None, height=110)
        self.estado = Label(text="Listo", halign="center")
        self.estado.bind(
            size=lambda w, s: setattr(w, "text_size", s))
        b_video = Button(text="Descargar video",
                         size_hint_y=None, height=140)
        b_musica = Button(text="Descargar música",
                          size_hint_y=None, height=140)
        b_video.bind(on_release=lambda *_: self.iniciar("video"))
        b_musica.bind(on_release=lambda *_: self.iniciar("audio"))
        for w in (self.enlace, self.calidad, b_video,
                  b_musica, self.estado):
            self.add_widget(w)

    def poner(self, texto):
        Clock.schedule_once(
            lambda dt: setattr(self.estado, "text", texto))

    def iniciar(self, formato):
        url = self.enlace.text.strip()
        if not url:
            self.poner("Pega un enlace primero")
            return
        self.poner("Descargando...")
        threading.Thread(target=self.bajar, args=(url, formato),
                         daemon=True).start()

    def bajar(self, url, formato):
        def hook(d):
            if d["status"] == "downloading":
                tot = (d.get("total_bytes")
                       or d.get("total_bytes_estimate"))
                if tot:
                    pct = d["downloaded_bytes"] * 100 // tot
                    self.poner(f"Descargando {pct}%")
        try:
            carpeta, privada = carpeta_trabajo(formato)
            op = hacer_opciones(formato, int(self.calidad.text),
                                hook, carpeta)
            with yt_dlp.YoutubeDL(op) as ydl:
                info = ydl.extract_info(url, download=True)
                ruta = info["requested_downloads"][0]["filepath"]
            if privada:
                self.poner("Guardando en la galería...")
                publicar(ruta, formato)
            self.poner("Listo, revisa Movies o Music")
        except Exception:
            self.poner("Error: " + traceback.format_exc()[-400:])


class DescargadorApp(App):
    def build(self):
        try:
            from android.permissions import (
                request_permissions, Permission)
            request_permissions([Permission.READ_EXTERNAL_STORAGE,
                                 Permission.WRITE_EXTERNAL_STORAGE])
        except Exception:
            pass
        return Pantalla()


try:
    DescargadorApp().run()
except Exception:
    with open("/storage/emulated/0/error_app.txt", "w") as f:
        f.write(traceback.format_exc())