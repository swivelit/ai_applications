package com.example.actionexecutor.execution

import android.content.Context
import android.content.Intent
import android.provider.AlarmClock
import android.widget.Toast
import com.example.actionexecutor.data.model.AlarmData

class AlarmExecutor(private val context: Context) {
    fun execute(data: AlarmData) {
        val timeParts = data.time.split(":")
        if (timeParts.size != 2) {
            Toast.makeText(context, "Invalid time format", Toast.LENGTH_SHORT).show()
            return
        }

        val hour = timeParts[0].toIntOrNull() ?: 0
        val minute = timeParts[1].toIntOrNull() ?: 0

        val intent = Intent(AlarmClock.ACTION_SET_ALARM).apply {
            putExtra(AlarmClock.EXTRA_HOUR, hour)
            putExtra(AlarmClock.EXTRA_MINUTES, minute)
            putExtra(AlarmClock.EXTRA_MESSAGE, data.label)
            putExtra(AlarmClock.EXTRA_SKIP_UI, false)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }

        if (intent.resolveActivity(context.packageManager) != null) {
            context.startActivity(intent)
        } else {
            Toast.makeText(context, "No Alarm app found", Toast.LENGTH_SHORT).show()
        }
    }
}
