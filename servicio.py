"""Servicio de Android: descarga en segundo plano con notificación."""
import os
import time
import traceback

from jnius import autoclass, cast

from descarga import (Cancelado, descargar, escribir_estado, hay_cancelar,
                      leer_config, quitar_cancelar, version_ytdlp)

PythonService = autoclass("org.kivy.android.PythonService")
servicio = PythonService.mService
Context = autoclass("android.content.Context")
VERSION = autoclass("android.os.Build$VERSION")
NotifBuilder = autoclass("android.app.Notification$Builder")
Drawable = autoclass("android.R$drawable")
String = autoclass("java.lang.String")
Intent = autoclass("android.content.Intent")
Uri = autoclass("android.net.Uri")
PendingIntent = autoclass("android.app.PendingIntent")

CANAL = "musicdl_descargas"
ID_PROGRESO = 7101
_contador = [7200]
FLAGS_PI = 67108864 | 134217728  # IMMUTABLE | UPDATE_CURRENT


def siguiente():
    _contador[0] += 1
    return _contador[0]


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


def pi_abrir_app():
    i = servicio.getPackageManager().getLaunchIntentForPackage(
        servicio.getPackageName())
    return PendingIntent.getActivity(servicio, siguiente(), i, FLAGS_PI)


def pi_ver(uri, mime):
    i = Intent("android.intent.action.VIEW")
    i.setDataAndType(Uri.parse(uri), mime)
    i.addFlags(1 | 268435456)  # permiso de lectura | nueva tarea
    return PendingIntent.getActivity(servicio, siguiente(), i, FLAGS_PI)


def pi_cancelar():
    i = Intent()
    i.setClassName(servicio.getPackageName(),
                   servicio.getPackageName() + ".CancelReceiver")
    return PendingIntent.getBroadcast(servicio, 1, i, FLAGS_PI)


def construir(titulo, texto, pct=None, en_curso=True, uri=None, mime=None):
    if VERSION.SDK_INT >= 26:
        b = NotifBuilder(servicio, CANAL)
    else:
        b = NotifBuilder(servicio)
    b.setContentTitle(cs(titulo))
    b.setContentText(cs(texto))
    b.setOnlyAlertOnce(True)
    try:  # al tocarla: abre el archivo (si se puede) o la app
        if uri:
            b.setContentIntent(pi_ver(uri, mime or "*/*"))
        else:
            b.setContentIntent(pi_abrir_app())
    except Exception:
        pass
    if en_curso:
        b.setSmallIcon(Drawable.stat_sys_download)
        b.setOngoing(True)
        if pct is None:
            b.setProgress(0, 0, True)
        else:
            b.setProgress(100, int(pct), False)
        try:  # botón Cancelar
            b.addAction(Drawable.ic_menu_close_clear_cancel,
                        cs("Cancelar"), pi_cancelar())
        except Exception:
            pass
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


def avisar_final(titulo, texto, uri=None, mime=None):
    gestor().notify(siguiente(),
                    construir(titulo, texto, en_curso=False,
                              uri=uri, mime=mime))


def tomar_lote(cola, proc):
    """Lee las descargas pedidas (ventana de compartir o la app)."""
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
    titulo = f"Descargando {etiqueta}"
    cfg = leer_config()
    ultimo = [0.0]
    quitar_cancelar()  # limpia un cancelar viejo

    def estado(texto, pct=None):
        actualizar(titulo, texto, pct)
        escribir_estado("progreso", texto, pct)

    def al_progreso(p):
        ahora = time.time()
        if ahora - ultimo[0] > 0.8 or p >= 100:
            ultimo[0] = ahora
            estado(f"Descargando {p}%", p)

    try:
        estado("Iniciando...")
        r = descargar(url, formato, cfg.get("destino", "Automática"),
                      cfg.get("sub", ""), cfg.get("calidad", "1080"),
                      al_progreso, estado, hay_cancelar)
        escribir_estado("ok", "", 100, r["ruta"], r["relativa"])
        avisar_final("Descarga lista ✔", r["ruta"], r.get("uri"),
                     r.get("mime"))
    except Cancelado:
        quitar_cancelar()
        escribir_estado("cancelado")
        avisar_final("Descarga cancelada", "")
    except Exception as e:
        detalle = str(e)[-250:]
        escribir_estado("error", detalle + f"\n(yt-dlp {version_ytdlp()})")
        avisar_final("No se pudo descargar", detalle[-200:])


def main():
    try:
        crear_canal()
        servicio.startForeground(ID_PROGRESO,
                                 construir("ClipTune", "Preparando..."))
        escribir_estado("progreso", "Preparando...")
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
        detalle = traceback.format_exc()[-300:]
        escribir_estado("error", detalle)
        try:
            avisar_final("ClipTune: error en el servicio", detalle)
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
