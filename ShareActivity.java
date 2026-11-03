package org.musicdl.musicdl2;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.os.Bundle;
import android.widget.Toast;

import java.io.File;
import java.io.FileWriter;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Ventanita que aparece al compartir un enlace a ClipTune. */
public class ShareActivity extends Activity {

    private String url = "";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        Intent intent = getIntent();
        String texto = (intent == null) ? null
                : intent.getStringExtra(Intent.EXTRA_TEXT);
        if (texto == null) {
            finish();
            return;
        }
        Matcher m = Pattern.compile("https?://\\S+").matcher(texto);
        if (!m.find()) {
            Toast.makeText(this, "No encontré un enlace",
                    Toast.LENGTH_SHORT).show();
            finish();
            return;
        }
        url = m.group();

        String corto = url.length() > 70 ? url.substring(0, 70) + "…" : url;

        AlertDialog.Builder b = new AlertDialog.Builder(
                this, android.R.style.Theme_DeviceDefault_Dialog_Alert);
        b.setTitle("ClipTune");
        b.setMessage(corto);
        b.setPositiveButton("Video", new DialogInterface.OnClickListener() {
            public void onClick(DialogInterface d, int w) {
                iniciar("video");
            }
        });
        b.setNegativeButton("Música", new DialogInterface.OnClickListener() {
            public void onClick(DialogInterface d, int w) {
                iniciar("audio");
            }
        });
        b.setNeutralButton("Cancelar", new DialogInterface.OnClickListener() {
            public void onClick(DialogInterface d, int w) {
                finish();
            }
        });
        b.setOnCancelListener(new DialogInterface.OnCancelListener() {
            public void onCancel(DialogInterface d) {
                finish();
            }
        });
        b.show();
    }

    private void iniciar(String formato) {
        try {
            File f = new File(getFilesDir(), "cola.txt");
            FileWriter w = new FileWriter(f, true);
            w.write(formato + "|" + url + "\n");
            w.close();
            arrancarServicio();
            Toast.makeText(this, "Descargando en segundo plano",
                    Toast.LENGTH_SHORT).show();
        } catch (Exception e) {
            Toast.makeText(this, "Error: " + e, Toast.LENGTH_LONG).show();
        }
        finish();
    }

    /** Arranca el servicio de Python (clase generada por p4a). */
    private void arrancarServicio() throws Exception {
        Class<?> c = Class.forName(getPackageName() + ".ServiceDescargas");
        try {
            c.getMethod("start", Context.class, String.class)
                    .invoke(null, this, "");
        } catch (NoSuchMethodException e) {
            c.getMethod("start", Context.class, String.class, String.class,
                    String.class, String.class)
                    .invoke(null, this, "icon", "ClipTune", "Descargando", "");
        }
    }
}
