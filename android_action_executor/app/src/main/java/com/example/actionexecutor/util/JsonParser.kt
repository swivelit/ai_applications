package com.example.actionexecutor.util

import com.example.actionexecutor.data.model.Command

/**
 * Utility for parsing JSON into Command models.
 * Currently simplified as this prototype uses a Map-based approach in the Dummy Repository.
 * Future versions will use Gson/Moshi here for real API integration.
 */
object JsonParser {
    fun parseJsonToCommand(json: String): Command {
        // Placeholder implementation
        // For now, the dummy repository creates the objects directly
        return Command("", "", "", emptyMap())
    }
}
