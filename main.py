import json
import os
import threading
import time
import traceback

from kivy.app import App
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import ListProperty, NumericProperty
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.widget import Widget

from descarga import (Cancelado, agregar_a_cola, arrancar_servicio,
                      borrar_estado, descargar, extraer_enlace,
                      leer_estado, pedir_cancelar, quitar_cancelar,
                      ruta_config, vaciar_cola, version_ytdlp)

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

# Color de fondo de la pantalla de entrada. Debe ser igual al fondo de tu
# icon.png (blanco = (1, 1, 1, 1)). Si tu PNG es transparente, usa FONDO.
SPLASH_FONDO = (1, 1, 1, 1)


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
    opacity: .45 if self.disabled else 1
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

    BoxLayout:
        size_hint_y: None
        height: dp(50)
        spacing: dp(10)
        Label:
            text: 'Guardar en'
            font_size: '16sp'
            color: 0.95, 0.96, 0.98, 1
            halign: 'left'
            valign: 'middle'
            text_size: self.size
        Spinner:
            id: destino
            text: 'Automática'
            values: ('Automática', 'Descargas')
            size_hint_x: None
            width: dp(150)
            font_size: '17sp'
            bold: True
            background_normal: ''
            background_color: 0.24, 0.27, 0.35, 1
            color: 1, 1, 1, 1

    TextInput:
        id: subcarpeta
        hint_text: 'Subcarpeta (opcional)'
        multiline: False
        size_hint_y: None
        height: dp(50)
        font_size: '16sp'
        padding: [dp(14), dp(14), dp(14), dp(8)]
        background_normal: ''
        background_active: ''
        background_color: 0.15, 0.17, 0.23, 1
        foreground_color: 0.95, 0.96, 0.98, 1
        hint_text_color: 0.70, 0.73, 0.80, 1
        cursor_color: 0.40, 0.70, 1, 1

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

    Boton:
        id: b_cancelar
        text: 'Cancelar descarga'
        fondo: 0.62, 0.13, 0.13, 1
        height: dp(50)
        disabled: True
        on_release: root.cancelar_descarga()

    Barra:
        id: barra

    BoxLayout:
        orientation: 'vertical'
        spacing: dp(6)
        Label:
            id: estado
            text: 'Listo'
            font_size: '16sp'
            color: 0.78, 0.80, 0.86, 1
            halign: 'center'
            size_hint_y: None
            height: self.texture_size[1]
            text_size: self.width, None
        Label:
            id: ruta
            text: ''
            font_size: '12sp'
            color: 0.70, 0.73, 0.80, 1
            halign: 'center'
            size_hint_y: None
            height: self.texture_size[1]
            text_size: self.width, None
        Widget:
'''
Builder.load_string(KV_PANTALLA)


class Splash(FloatLayout):
    """Pantalla de entrada con el logo animado."""

    def __init__(self, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            Color(*SPLASH_FONDO)
            self.rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._actualizar, size=self._actualizar)
        self.logo = Image(source="icon.png", size_hint=(None, None),
                          size=(dp(180), dp(180)),
                          pos_hint={"center_x": .5, "center_y": .5},
                          opacity=0)
        self.add_widget(self.logo)

    def _actualizar(self, *_):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def animar(self, al_terminar):
        # Solo se anima la opacidad (muy liviano) y se espera un instante
        # para que la app termine de cargar antes de empezar.
        def empezar(dt):
            entrada = Animation(opacity=1, duration=0.4)
            pausa = Animation(duration=0.4)
            salida = Animation(opacity=0, duration=0.3)
            entrada.bind(on_complete=lambda *_: pausa.start(self.logo))
            pausa.bind(on_complete=lambda *_: salida.start(self))
            salida.bind(on_complete=lambda *_: al_terminar())
            entrada.start(self.logo)
        Clock.schedule_once(empezar, 0.3)


class Pantalla(BoxLayout):
    ocupado = False
    cancelado = False
    modo_servicio = False   # descarga pedida desde esta pantalla
    en_hilo = False         # plan B: descarga dentro de la app
    t0 = time.time()        # cuándo abrió la app
    t_pedido = 0.0
    ultimo_t = 0.0

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

    def mostrar(self, texto, color=TEXTO_SUAVE, progreso=None, ruta=""):
        def _ui(dt):
            self.ids.estado.text = texto
            self.ids.ruta.text = ruta
            self.ids.estado.color = color
            if progreso is not None:
                self.ids.barra.progreso = progreso
        Clock.schedule_once(_ui)

    def poner_ocupado(self, valor):
        self.ocupado = valor

        def _ui(dt):
            self.ids.b_cancelar.disabled = not valor
            self.ids.b_video.disabled = valor
            self.ids.b_musica.disabled = valor
        Clock.schedule_once(_ui)

    def cancelar_descarga(self):
        if not self.ocupado:
            return
        if self.en_hilo:
            self.cancelado = True
        else:
            pedir_cancelar()
        self.mostrar("Cancelando...", TEXTO_SUAVE)

    def sondear(self, dt):
        """Lee lo que reporta el servicio y lo muestra en pantalla."""
        e = leer_estado()
        ahora = time.time()
        if not e or e.get("t", 0) < self.t_pedido:
            if self.modo_servicio and ahora - self.t_pedido > 25:
                self.modo_servicio = False
                self.poner_ocupado(False)
                self.mostrar("No se pudo iniciar la descarga en "
                             "segundo plano.", ERROR, 0)
            return
        t = e["t"]
        tipo = e.get("tipo")
        if tipo == "progreso":
            if ahora - t > 180:      # el servicio dejó de responder
                if self.modo_servicio:
                    self.modo_servicio = False
                    self.poner_ocupado(False)
                    self.mostrar("La descarga dejó de responder.",
                                 ERROR, 0)
                return
            if not self.ocupado:
                self.poner_ocupado(True)
            if t != self.ultimo_t:
                self.ultimo_t = t
                self.mostrar(e.get("texto", ""), TEXTO_SUAVE,
                             e.get("pct") or 0)
        elif tipo in ("ok", "error", "cancelado") \
                and t != self.ultimo_t \
                and (t >= self.t0 or self.modo_servicio):
            self.ultimo_t = t
            self.modo_servicio = False
            self.poner_ocupado(False)
            if tipo == "ok":
                rel = e.get("relativa", "").rstrip("/")
                self.mostrar(f"Listo ✔ Guardado en {rel}", OK, 100,
                             ruta=e.get("ruta", ""))
            elif tipo == "error":
                self.mostrar("No se pudo descargar:\n"
                             + e.get("texto", ""), ERROR, 0)
            else:
                self.mostrar("Descarga cancelada", TEXTO_SUAVE, 0)

    def _ruta_config(self):
        return ruta_config()

    def cargar_config(self):
        try:
            with open(self._ruta_config()) as f:
                c = json.load(f)
            if c.get("destino") in self.ids.destino.values:
                self.ids.destino.text = c["destino"]
            if c.get("calidad") in self.ids.calidad.values:
                self.ids.calidad.text = c["calidad"]
            self.ids.subcarpeta.text = c.get("sub", "")
        except Exception:
            pass

    def guardar_config(self):
        try:
            with open(self._ruta_config(), "w") as f:
                json.dump({"destino": self.ids.destino.text,
                           "calidad": self.ids.calidad.text,
                           "sub": self.ids.subcarpeta.text}, f)
        except Exception:
            pass

    def iniciar(self, formato):
        if self.ocupado:
            return
        url = extraer_enlace(self.ids.enlace.text) \
            or self.ids.enlace.text.strip()
        if not url:
            self.mostrar("Pega o comparte un enlace primero.", ERROR)
            return
        self.cancelado = False
        self.guardar_config()
        self.poner_ocupado(True)
        self.mostrar("Iniciando...", TEXTO_SUAVE, 0)
        try:
            quitar_cancelar()
            self.t_pedido = time.time()
            borrar_estado()
            agregar_a_cola(formato, url)
            arrancar_servicio()
            self.modo_servicio = True
            self.en_hilo = False
        except Exception:
            # Plan B: descargar dentro de la app
            vaciar_cola()
            self.modo_servicio = False
            self.en_hilo = True
            threading.Thread(
                target=self.bajar,
                args=(url, formato, self.ids.destino.text,
                      self.ids.subcarpeta.text,
                      int(self.ids.calidad.text)),
                daemon=True).start()

    def bajar(self, url, formato, destino, sub, calidad):
        try:
            r = descargar(
                url, formato, destino, sub, calidad,
                al_progreso=lambda p: self.mostrar(
                    f"Descargando {p}%", TEXTO_SUAVE, p),
                al_estado=lambda t: self.mostrar(t, TEXTO_SUAVE, 0),
                cancelado=lambda: self.cancelado)
            self.mostrar(
                f"Listo ✔ Guardado en {r['relativa'].rstrip('/')}",
                OK, 100, ruta=r["ruta"])
        except Cancelado:
            self.mostrar("Descarga cancelada", TEXTO_SUAVE, 0)
        except Exception as e:
            self.mostrar("No se pudo descargar:\n" + str(e)[-250:]
                         + f"\n(yt-dlp {version_ytdlp()})", ERROR, 0)
        finally:
            self.en_hilo = False
            self.poner_ocupado(False)


class DescargadorApp(App):

    def build(self):
        try:
            from android.permissions import (
                request_permissions, Permission)
            request_permissions([
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
                "android.permission.POST_NOTIFICATIONS"])
        except Exception:
            pass
        self.pantalla = Pantalla()
        self.raiz = FloatLayout()
        self.raiz.add_widget(self.pantalla)
        self.splash = Splash()
        self.raiz.add_widget(self.splash)
        return self.raiz

    def quitar_splash(self):
        self.raiz.remove_widget(self.splash)

    def on_start(self):
        self.splash.animar(self.quitar_splash)
        self.pantalla.cargar_config()
        Clock.schedule_interval(self.pantalla.sondear, 0.8)


try:
    DescargadorApp().run()
except Exception:
    with open("/storage/emulated/0/error_app.txt", "w") as f:
        f.write(traceback.format_exc())
