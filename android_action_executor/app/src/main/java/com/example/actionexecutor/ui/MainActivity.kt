package com.example.actionexecutor.ui

import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import com.example.actionexecutor.R
import com.example.actionexecutor.execution.CommandExecutor
import com.google.android.material.snackbar.Snackbar

class MainActivity : AppCompatActivity() {

    private val viewModel: MainViewModel by viewModels()
    private lateinit var commandExecutor: CommandExecutor
    private var actionLaunched = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        commandExecutor = CommandExecutor(this)

        val btnFetchAlarm = findViewById<Button>(R.id.btnFetchAlarm)
        val btnFetchNotes = findViewById<Button>(R.id.btnFetchNotes)
        val btnExecute = findViewById<Button>(R.id.btnExecute)
        val tvStatus = findViewById<TextView>(R.id.tvStatus)

        btnFetchAlarm.setOnClickListener {
            viewModel.fetchCommand("alarm")
        }

        btnFetchNotes.setOnClickListener {
            viewModel.fetchCommand("notes")
        }

        btnExecute.setOnClickListener {
            val command = viewModel.currentCommand.value
            if (command != null) {
                actionLaunched = true
                commandExecutor.execute(command)
            } else {
                viewModel.setStatus("No command to execute. Fetch one first!")
            }
        }

        viewModel.statusMessage.observe(this) { message ->
            tvStatus.text = message
        }
        
        viewModel.currentCommand.observe(this) { command ->
            btnExecute.isEnabled = command != null
        }
    }

    override fun onResume() {
        super.onResume()
        if (actionLaunched) {
            actionLaunched = false
            showSuccessNotification()
        }
    }

    private fun showSuccessNotification() {
        val rootLayout = findViewById<android.view.View>(android.R.id.content)
        Snackbar.make(rootLayout, "Task completed successfully", Snackbar.LENGTH_LONG).show()
        viewModel.setStatus("Task completed successfully")
        viewModel.clearCommand()
    }
}
