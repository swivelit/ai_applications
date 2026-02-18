package com.example.actionexecutor.ui

import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.actionexecutor.data.model.Command
import com.example.actionexecutor.data.repository.CommandRepository
import com.example.actionexecutor.data.repository.DummyCommandRepository
import kotlinx.coroutines.launch

class MainViewModel : ViewModel() {
    private val repository: CommandRepository = DummyCommandRepository()
    
    private val _currentCommand = MutableLiveData<Command?>()
    val currentCommand: LiveData<Command?> = _currentCommand

    private val _statusMessage = MutableLiveData<String>()
    val statusMessage: LiveData<String> = _statusMessage

    fun fetchCommand(type: String) {
        viewModelScope.launch {
            try {
                val command = repository.getCommand(type)
                _currentCommand.value = command
                _statusMessage.value = "Fetched ${command.app} command"
            } catch (e: Exception) {
                _statusMessage.value = "Error: ${e.message}"
            }
        }
    }

    fun clearCommand() {
        _currentCommand.value = null
    }
    
    fun setStatus(message: String) {
        _statusMessage.value = message
    }
}
