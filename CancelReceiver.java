package org.ClipTune;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import java.io.File;

/** Recibe el toque en "Cancelar" de la notificación. */
public class CancelReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        try {
            new File(context.getFilesDir(), "cancelar.flag").createNewFile();
        } catch (Exception e) {
            // nada que hacer
        }
    }
}
