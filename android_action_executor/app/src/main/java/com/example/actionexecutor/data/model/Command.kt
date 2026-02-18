package com.example.actionexecutor.data.model

data class Command(
    val request_id: String,
    val app: String,
    val action: String,
    val data: Map<String, Any>
)
