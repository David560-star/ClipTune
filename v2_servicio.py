"""Servicio de Android: descarga en segundo plano con notificación."""
import os
import time
import traceback

from jnius import autoclass, cast

from descarga import descargar, leer_config

PythonService = autoclass("org.kivy.android.PythonService")
servicio = PythonService.mService
Context = autoclass("android.content.Context")
VERSION = autoclass("android.os.Build$VERSION")
NotifBuilder = autoclass("android.app.Notification$Builder")
Drawable = autoclass("android.R$drawable")
String = autoclass("java.lang.String")

CANAL = "musicdl_descargas"
ID_PROGRESO = 7101
_contador = [7200]


def cs(texto):
    return cast("java.lang.CharSequence", String(str(texto)))


def gestor():
    return cast("android.app.NotificationManager",
                servicio.getSystemService(Context.NOTIFICATION_SERVICE))


def crear_canal():
    if VERSION.SDK_INT >= 26:
        Canal = autoclass("android.app.NotificationChannel")
        gestor().createNotificationChannel(
            Canal(CANAL, cs("Descargas"), 2))  # 2 = importancia baja


def construir(titulo, texto, pct=None, en_curso=True):
    if VERSION.SDK_INT >= 26:
        b = NotifBuilder(servicio, CANAL)
    else:
        b = NotifBuilder(servicio)
    b.setContentTitle(cs(titulo))
    b.setContentText(cs(texto))
    b.setOnlyAlertOnce(True)
    if en_curso:
        b.setSmallIcon(Drawable.stat_sys_download)
        b.setOngoing(True)
        if pct is None:
            b.setProgress(0, 0, True)
        else:
            b.setProgress(100, int(pct), False)
    else:
        b.setSmallIcon(Drawable.stat_sys_download_done)
        b.setAutoCancel(True)
        try:
            estilo = autoclass("android.app.Notification$BigTextStyle")()
            estilo.bigText(cs(texto))
            b.setStyle(estilo)
        except Exception:
            pass
    return b.build()


def actualizar(titulo, texto, pct=None):
    servicio.startForeground(ID_PROGRESO, construir(titulo, texto, pct))


def avisar_final(titulo, texto):
    _contador[0] += 1
    gestor().notify(_contador[0],
                    construir(titulo, texto, en_curso=False))


def tomar_lote(cola, proc):
    """Lee las descargas pedidas desde la ventana de compartir."""
    if os.path.exists(cola) and not os.path.exists(proc):
        try:
            os.replace(cola, proc)
        except OSError:
            return []
    if not os.path.exists(proc):
        return []
    try:
        with open(proc, encoding="utf-8") as f:
            return [l.strip() for l in f if "|" in l]
    finally:
        try:
            os.remove(proc)
        except OSError:
            pass


def procesar(linea):
    formato, url = linea.split("|", 1)
    etiqueta = "música" if formato == "audio" else "video"
    cfg = leer_config()
    ultimo = [0.0]

    def al_progreso(p):
        ahora = time.time()
        if ahora - ultimo[0] > 0.8 or p >= 100:
            ultimo[0] = ahora
            actualizar(f"Descargando {etiqueta}", f"{p}%", p)

    def al_estado(texto):
        actualizar(f"Descargando {etiqueta}", texto)

    try:
        actualizar(f"Descargando {etiqueta}", "Iniciando...")
        relativa, completa = descargar(
            url, formato, cfg.get("destino", "Automática"),
            cfg.get("sub", ""), cfg.get("calidad", "1080"),
            al_progreso, al_estado)
        avisar_final("Descarga lista ✔", completa)
    except Exception as e:
        avisar_final("No se pudo descargar", str(e)[-200:])


def main():
    try:
        crear_canal()
        servicio.startForeground(ID_PROGRESO,
                                 construir("MusicDL", "Preparando..."))
        base = servicio.getFilesDir().getAbsolutePath()
        cola = os.path.join(base, "cola.txt")
        proc = cola + ".proc"
        vacios = 0
        while vacios < 2:
            lineas = tomar_lote(cola, proc)
            if not lineas:
                vacios += 1
                time.sleep(1)
                continue
            vacios = 0
            for linea in lineas:
                procesar(linea)
    except Exception:
        try:
            avisar_final("MusicDL: error en el servicio",
                         traceback.format_exc()[-300:])
        except Exception:
            pass
    finally:
        try:
            servicio.stopForeground(True)
        except Exception:
            pass
        try:
            servicio.stopSelf()
        except Exception:
            pass


if __name__ == "__main__":
    main()
