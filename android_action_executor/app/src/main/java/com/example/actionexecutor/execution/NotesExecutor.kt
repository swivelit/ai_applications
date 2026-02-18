package com.example.actionexecutor.execution

import android.content.Context
import android.widget.Toast
import com.example.actionexecutor.data.model.NotesData

class NotesExecutor(private val context: Context) {
    fun execute(data: NotesData) {
        // Prototype version: Show Toast and simulate creation
        val message = "Note Created:\nTitle: ${data.title}\nContent: ${data.content}"
        Toast.makeText(context, message, Toast.LENGTH_LONG).show()
        
        // In a real app, this might send an intent to a notes app or save to a DB
        println("Logging Note: $message")
    }
}
