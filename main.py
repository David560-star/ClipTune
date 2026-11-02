import os
import re
import threading
import traceback

import yt_dlp
from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import ListProperty, NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.widget import Widget

try:
    import certifi
    os.environ["SSL_CERT_FILE"] = certifi.where()
except Exception:
    pass

BASE = "/storage/emulated/0"
PLANTILLA = "%(title).60s [%(id.-6:)s].%(ext)s"

# Colores con buen contraste (texto claro sobre fondo oscuro)
FONDO = (0.07, 0.08, 0.11, 1)
TEXTO = (0.95, 0.96, 0.98, 1)
TEXTO_SUAVE = (0.78, 0.80, 0.86, 1)
AZUL = (0.11, 0.37, 0.82, 1)
VERDE = (0.05, 0.48, 0.35, 1)
GRIS = (0.24, 0.27, 0.35, 1)
OK = (0.45, 0.90, 0.60, 1)
ERROR = (1.0, 0.55, 0.55, 1)

Window.clearcolor = FONDO


class Boton(Button):
    fondo = ListProperty(AZUL)


class Barra(Widget):
    progreso = NumericProperty(0)


Builder.load_string('''
#:import dp kivy.metrics.dp

<Boton>:
    background_normal: ''
    background_down: ''
    background_color: 0, 0, 0, 0
    color: 1, 1, 1, 1
    bold: True
    font_size: '18sp'
    size_hint_y: None
    height: dp(60)
    canvas.before:
        Color:
            rgba: self.fondo if self.state == 'normal' else [self.fondo[0] * .7, self.fondo[1] * .7, self.fondo[2] * .7, 1]
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(14)]

<Barra>:
    size_hint_y: None
    height: dp(10)
    canvas:
        Color:
            rgba: 0.24, 0.27, 0.35, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(5)]
        Color:
            rgba: 0.40, 0.70, 1, 1
        RoundedRectangle:
            pos: self.pos
            size: self.width * self.progreso / 100., self.height
            radius: [dp(5)]
''')


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


def extraer_enlace(texto):
    """Saca el primer enlace de un texto compartido."""
    m = re.search(r"https?://\S+", texto or "")
    return m.group(0) if m else ""


KV_PANTALLA = '''
<Pantalla>:
    orientation: 'vertical'
    padding: dp(20)
    spacing: dp(14)

    Label:
        text: 'MusicDL'
        font_size: '30sp'
        bold: True
        color: 0.95, 0.96, 0.98, 1
        size_hint_y: None
        height: dp(48)
        halign: 'left'
        text_size: self.size

    Label:
        text: 'Comparte un enlace a esta app o pégalo aquí'
        font_size: '15sp'
        color: 0.78, 0.80, 0.86, 1
        size_hint_y: None
        height: dp(24)
        halign: 'left'
        text_size: self.size

    BoxLayout:
        size_hint_y: None
        height: dp(56)
        spacing: dp(10)
        TextInput:
            id: enlace
            hint_text: 'Pega el enlace aquí'
            multiline: False
            font_size: '17sp'
            padding: [dp(14), dp(16), dp(14), dp(10)]
            background_normal: ''
            background_active: ''
            background_color: 0.15, 0.17, 0.23, 1
            foreground_color: 0.95, 0.96, 0.98, 1
            hint_text_color: 0.70, 0.73, 0.80, 1
            cursor_color: 0.40, 0.70, 1, 1
        Boton:
            text: 'Pegar'
            size_hint_x: None
            width: dp(90)
            height: dp(56)
            fondo: 0.24, 0.27, 0.35, 1
            on_release: root.pegar()

    BoxLayout:
        size_hint_y: None
        height: dp(50)
        spacing: dp(10)
        Label:
            text: 'Calidad del video'
            font_size: '16sp'
            color: 0.95, 0.96, 0.98, 1
            halign: 'left'
            valign: 'middle'
            text_size: self.size
        Spinner:
            id: calidad
            text: '1080'
            values: ('360', '480', '720', '1080')
            size_hint_x: None
            width: dp(110)
            font_size: '17sp'
            bold: True
            background_normal: ''
            background_color: 0.24, 0.27, 0.35, 1
            color: 1, 1, 1, 1

    Boton:
        id: b_video
        text: 'Descargar video'
        fondo: 0.11, 0.37, 0.82, 1
        on_release: root.iniciar('video')

    Boton:
        id: b_musica
        text: 'Descargar música'
        fondo: 0.05, 0.48, 0.35, 1
        on_release: root.iniciar('audio')

    Barra:
        id: barra

    Label:
        id: estado
        text: 'Listo'
        font_size: '16sp'
        color: 0.78, 0.80, 0.86, 1
        halign: 'center'
        valign: 'top'
        text_size: self.size
'''
Builder.load_string(KV_PANTALLA)


class Pantalla(BoxLayout):
    ocupado = False

    def pegar(self):
        try:
            texto = Clipboard.paste() or ""
        except Exception:
            texto = ""
        enlace = extraer_enlace(texto) or texto.strip()
        if enlace:
            self.ids.enlace.text = enlace
            self.mostrar("Enlace pegado. Elige video o música.")
        else:
            self.mostrar("No hay nada copiado todavía.", ERROR)

    def recibir_enlace(self, texto):
        """Se llama cuando se comparte un enlace hacia la app."""
        enlace = extraer_enlace(texto)
        if enlace:
            self.ids.enlace.text = enlace
            self.mostrar("Enlace recibido. Elige video o música.", OK)
        else:
            self.mostrar("Lo compartido no tiene un enlace.", ERROR)

    def mostrar(self, texto, color=TEXTO_SUAVE, progreso=None):
        def _ui(dt):
            self.ids.estado.text = texto
            self.ids.estado.color = color
            if progreso is not None:
                self.ids.barra.progreso = progreso
        Clock.schedule_once(_ui)

    def poner_ocupado(self, valor):
        self.ocupado = valor

    def iniciar(self, formato):
        if self.ocupado:
            return
        url = extraer_enlace(self.ids.enlace.text) \
            or self.ids.enlace.text.strip()
        if not url:
            self.mostrar("Pega o comparte un enlace primero.", ERROR)
            return
        self.ocupado = True
        self.mostrar("Descargando...", TEXTO_SUAVE, 0)
        threading.Thread(target=self.bajar, args=(url, formato),
                         daemon=True).start()

    def bajar(self, url, formato):
        def hook(d):
            if d["status"] == "downloading":
                tot = (d.get("total_bytes")
                       or d.get("total_bytes_estimate"))
                if tot:
                    pct = d["downloaded_bytes"] * 100 // tot
                    self.mostrar(f"Descargando {pct}%",
                                 TEXTO_SUAVE, pct)
        try:
            carpeta, privada = carpeta_trabajo(formato)
            op = hacer_opciones(formato, int(self.ids.calidad.text),
                                hook, carpeta)
            with yt_dlp.YoutubeDL(op) as ydl:
                info = ydl.extract_info(url, download=True)
                ruta = info["requested_downloads"][0]["filepath"]
            if privada:
                self.mostrar("Guardando en la galería...",
                             TEXTO_SUAVE, 100)
                publicar(ruta, formato)
            carpeta_final = "Music" if formato == "audio" else "Movies"
            self.mostrar(f"Listo ✔ Guardado en {carpeta_final}",
                         OK, 100)
        except Exception:
            self.mostrar("No se pudo descargar:\n"
                         + traceback.format_exc()[-300:], ERROR, 0)
        finally:
            self.ocupado = False


class DescargadorApp(App):
    ultimo = ""

    def build(self):
        try:
            from android.permissions import (
                request_permissions, Permission)
            request_permissions([Permission.READ_EXTERNAL_STORAGE,
                                 Permission.WRITE_EXTERNAL_STORAGE])
        except Exception:
            pass
        self.pantalla = Pantalla()
        return self.pantalla

    def on_start(self):
        # Recibir enlaces compartidos desde otras apps (Android)
        try:
            from android import activity
            from jnius import autoclass
            activity.bind(on_new_intent=self.nuevo_intent)
            Act = autoclass("org.kivy.android.PythonActivity")
            self.nuevo_intent(Act.mActivity.getIntent())
        except Exception:
            pass

    def nuevo_intent(self, intent):
        try:
            if intent is None:
                return
            if intent.getAction() != "android.intent.action.SEND":
                return
            texto = intent.getStringExtra("android.intent.extra.TEXT")
            if texto and texto != self.ultimo:
                self.ultimo = texto
                Clock.schedule_once(
                    lambda dt: self.pantalla.recibir_enlace(texto))
        except Exception:
            pass


try:
    DescargadorApp().run()
except Exception:
    with open("/storage/emulated/0/error_app.txt", "w") as f:
        f.write(traceback.format_exc())
