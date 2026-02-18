package com.example.actionexecutor.execution

import android.content.Context
import com.example.actionexecutor.data.model.AlarmData
import com.example.actionexecutor.data.model.Command
import com.example.actionexecutor.data.model.NotesData

class CommandExecutor(private val context: Context) {
    private val alarmExecutor = AlarmExecutor(context)
    private val notesExecutor = NotesExecutor(context)

    fun execute(command: Command) {
        when (command.app) {
            "clock" -> {
                val alarmData = AlarmData(
                    time = command.data["time"] as? String ?: "00:00",
                    label = command.data["label"] as? String ?: "Alarm"
                )
                alarmExecutor.execute(alarmData)
            }
            "notes" -> {
                val notesData = NotesData(
                    title = command.data["title"] as? String ?: "Untitled",
                    content = command.data["content"] as? String ?: ""
                )
                notesExecutor.execute(notesData)
            }
            else -> {
                // Handle unknown app
            }
        }
    }
}
