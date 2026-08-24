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

/// Generate audiobook via FastAPI.
#[tauri::command]
pub async fn generate_audiobook(
    app: AppHandle,
    file_base64: String,
    file_name: String,
    book_title: String,
    locale: String,
    tts_provider: String,
    llm_provider: String,
    llm_model: String,
) -> Result<String, String> {
    let client = reqwest::Client::new();
    let url = "http://127.0.0.1:8000/generate";

    let payload = serde_json::json!({
        "file_base64": file_base64,
        "file_name": file_name,
        "book_title": book_title,
        "locale": locale,
        "tts_provider": tts_provider,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
    });

    let response = client
        .post(url)
        .json(&payload)
        .send()
        .await
        .map_err(|e| format!("Failed to call /generate: {}", e))?;

    if !response.status().is_success() {
        let err = response.text().await.unwrap_or_default();
        return Err(format!("Generation failed: {}", err));
    }

    // Return the output path from the response
    let result: serde_json::Value = response.json().await
        .map_err(|e| format!("Failed to parse response: {}", e))?;

    result.get("output_path")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
        .ok_or_else(|| "No output_path in response".to_string())
}

/// Poll generation progress from FastAPI.
#[tauri::command]
pub async fn get_generation_progress(app: AppHandle) -> Result<u8, String> {
    let client = reqwest::Client::new();
    let url = "http://127.0.0.1:8000/progress";

    match client.get(url).send().await {
        Ok(response) => {
            if response.status().is_success() {
                let result: serde_json::Value = response.json().await
                    .map_err(|e| format!("Failed to parse progress response: {}", e))?;
                Ok(result.get("progress")
                    .and_then(|v| v.as_u64())
                    .map(|v| v as u8)
                    .unwrap_or(0))
            } else {
                Ok(0)
            }
        }
        Err(e) => {
            log::warn!("Progress check failed: {}", e);
            Ok(0)
        }
    }
}