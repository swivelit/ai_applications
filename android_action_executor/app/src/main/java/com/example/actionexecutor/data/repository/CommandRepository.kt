package com.example.actionexecutor.data.repository

import com.example.actionexecutor.data.model.Command

interface CommandRepository {
    suspend fun getCommand(type: String): Command
}
