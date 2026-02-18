package com.example.actionexecutor.data.repository

import com.example.actionexecutor.data.model.Command
import kotlinx.coroutines.delay

class DummyCommandRepository : CommandRepository {
    override suspend fun getCommand(type: String): Command {
        // Simulate network delay
        delay(500)
        
        return when (type) {
            "alarm" -> Command(
                request_id = "req_001",
                app = "clock",
                action = "set_alarm",
                data = mapOf(
                    "time" to "07:30",
                    "label" to "Wake Up Call"
                )
            )
            "notes" -> Command(
                request_id = "req_002",
                app = "notes",
                action = "create_note",
                data = mapOf(
                    "title" to "Shopping List",
                    "content" to "Milk, Bread, Eggs, Coffee"
                )
            )
            else -> throw IllegalArgumentException("Unknown command type: $type")
        }
    }
}
