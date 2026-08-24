//! Sidecar commands for managing the FastAPI Python process.

use std::process::{Command, Stdio};
use std::sync::Mutex;
use tauri::{AppHandle, Manager, Runtime, State};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

/// Managed state for the Python sidecar process.
pub struct PythonSidecar {
    child: Mutex<Option<CommandChild>>,
}

impl PythonSidecar {
    pub fn new() -> Self {
        Self {
            child: Mutex::new(None),
        }
    }
}

/// Start the FastAPI Python sidecar process.
#[tauri::command]
pub async fn start_python_sidecar<R: Runtime>(
    app: AppHandle<R>,
    sidecar: State<'_, PythonSidecar>,
) -> Result<String, String> {
    let shell = app.shell();

    // Determine the Python script path relative to the app
    let sidecar_command = shell
        .sidecar("python-sidecar")
        .map_err(|e| format!("Failed to create sidecar command: {}", e))?;

    // Spawn the sidecar process
    let (mut rx, child) = sidecar_command
        .spawn()
        .map_err(|e| format!("Failed to spawn Python sidecar: {}", e))?;

    // Store the child process for later shutdown
    {
        let mut guard = sidecar.child.lock().map_err(|e| format!("Mutex lock failed: {}", e))?;
        *guard = Some(child);
    }

    // Spawn a task to monitor the sidecar output
    let app_handle = app.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    log::info!("[Python sidecar stdout] {}", String::from_utf8_lossy(&line));
                    // Check if the server is ready
                    if String::from_utf8_lossy(&line).contains("Uvicorn running on") {
                        log::info!("FastAPI server is ready");
                    }
                }
                CommandEvent::Stderr(line) => {
                    log::error!("[Python sidecar stderr] {}", String::from_utf8_lossy(&line));
                }
                CommandEvent::Error(err) => {
                    log::error!("[Python sidecar error] {}", err);
                }
                CommandEvent::Terminated(payload) => {
                    log::info!("Python sidecar terminated with code: {:?}", payload.code);
                }
                _ => {}
            }
        }
    });

    Ok("Python sidecar started".to_string())
}

/// Stop the FastAPI Python sidecar process.
#[tauri::command]
pub async fn stop_python_sidecar(sidecar: State<'_, PythonSidecar>) -> Result<String, String> {
    let mut guard = sidecar.child.lock().map_err(|e| format!("Mutex lock failed: {}", e))?;

    if let Some(mut child) = guard.take() {
        child.kill().map_err(|e| format!("Failed to kill Python sidecar: {}", e))?;
        log::info!("Python sidecar stopped");
        Ok("Python sidecar stopped".to_string())
    } else {
        Ok("Python sidecar was not running".to_string())
    }
}

/// Check if the FastAPI server is healthy.
#[tauri::command]
pub async fn check_server_health() -> Result<bool, String> {
    let client = reqwest::Client::new();
    let url = "http://127.0.0.1:8000/health";

    match client.get(url).send().await {
        Ok(response) => Ok(response.status().is_success()),
        Err(e) => {
            log::warn!("Health check failed: {}", e);
            Ok(false)
        }
    }
}