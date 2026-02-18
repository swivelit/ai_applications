# Android Action Execution Prototype

A clean, modular Android Kotlin project designed to receive structured JSON commands and execute system actions (Alarm / Notes). Built with scalability in mind to allow easy upgrades for AI/NLP integration.

## 🏗 Architecture Design

This project follows **Clean Architecture** principles to separate concerns and ensure the execution logic remains independent of the data source.

### Layers:
- **UI Layer (`ui/`)**: Activities and ViewModels. Handles user interaction and observes state.
- **ViewModel Layer (`ui/MainViewModel`)**: Bridge between UI and Repository. Orchestrates data flow using Coroutines.
- **Command Repository (`data/repository/`)**: Abstracts the data source. Currently uses `DummyCommandRepository` for prototyping.
- **Execution Engine (`execution/`)**: Contains specific executors (`AlarmExecutor`, `NotesExecutor`) and a central `CommandExecutor` for routing.

## 🔄 Execution Flow Diagram

```text
User Interaction
      ↓
 [MainActivity] (Button Click)
      ↓
 [MainViewModel] (Fetch Command)
      ↓
 [CommandRepository] (Get JSON/Model)
      ↓
 [MainActivity] (Click Execute)
      ↓
 [CommandExecutor] (Route Action)
      ↓
[Specific Executor] (Alarm/Notes Intent)
      ↓
  [External App] (User Action)
      ↓
  [Back Button]
      ↓
 [MainActivity] (onResume Detection)
      ↓
  [Success Notification] (Snackbar)
```

## 🚀 How to Run

1.  **Open in Android Studio**:
    - Select "Open an existing project" and navigate to this folder.
2.  **Run on Device/Emulator**:
    - Ensure your device is running API 24 (Nougat) or higher.
3.  **Use the Prototype**:
    - Click **"Fetch Alarm Command"** or **"Fetch Notes Command"** to load a dummy command.
    - Click **"Execute Command"** to launch the system action.
    - After the external app opens, press the **Back button** to return.
    - Observe the "Task completed successfully" Snackbar.

## 🔮 Future Integration Guide

This architecture is built for easy replacement of the backend logic:

### 1. Retrofit Integration
To connect to a real API (like FastAPI), add the Retrofit dependency and create an `ApiCommandRepository` implementing the `CommandRepository` interface.

### 2. Python FastAPI Backend
The backend can handle complex logic like NLP or LLM processing to convert natural language queries into the structured JSON format already supported by this app.

### 3. AI Plugin System
New actions can be added by:
1. Creating a new `DataModel`.
2. Implementing a new `Executor`.
3. Updating `CommandExecutor` to route the new `app` type.

---
Built with ❤️ for AI-ready Android development.
