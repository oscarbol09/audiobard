//! Sidecar commands for managing the FastAPI Python process.

use std::process::{Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;
use serde::Serialize;
use tauri::{AppHandle, Manager, Runtime, State};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

/// Timeout for short-lived health and progress probes.
///
/// Five seconds is generous for a localhost request; longer means the
/// UI is hung waiting for a stuck sidecar.
const PROBE_TIMEOUT: Duration = Duration::from_secs(5);

/// Timeout for the full generation request.
///
/// Audiobooks for long public-domain texts can take more than half an
/// hour to render end-to-end; a one-hour ceiling lets the network call
/// fail loudly if the pipeline wedges instead of blocking the IPC.
const GENERATE_TIMEOUT: Duration = Duration::from_secs(3600);

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

/// Structured progress update returned by `get_generation_progress`.
///
/// Serialised as JSON and consumed by the Vue store, so the field names
/// must stay in sync with `GenerationProgress` in `gui/src/types.ts`.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GenerationProgress {
    pub stage: String,
    pub percent: u8,
    pub message: String,
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
    let client = reqwest::Client::builder()
        .timeout(PROBE_TIMEOUT)
        .build()
        .map_err(|e| format!("Failed to build HTTP client: {}", e))?;
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
///
/// Returns a JSON string with `{ "session_id": "...", "output_path": "..." }`
/// so the Vue store can keep polling progress for the same session even
/// after the request resolves.
#[tauri::command]
pub async fn generate_audiobook(
    app: AppHandle,
    file_base64: String,
    file_name: String,
    locale: String,
    tts_provider: String,
    llm_provider: String,
    llm_model: String,
    session_id: String,
) -> Result<String, String> {
    let client = reqwest::Client::builder()
        .timeout(GENERATE_TIMEOUT)
        .build()
        .map_err(|e| format!("Failed to build HTTP client: {}", e))?;
    let url = "http://127.0.0.1:8000/generate";

    let payload = serde_json::json!({
        "file_base64": file_base64,
        "file_name": file_name,
        "locale": locale,
        "tts_provider": tts_provider,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "session_id": session_id,
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

    // Return the full response so the caller can recover session_id and
    // output_path from a single round trip.
    let result: serde_json::Value = response.json().await
        .map_err(|e| format!("Failed to parse response: {}", e))?;

    serde_json::to_string(&result)
        .map_err(|e| format!("Failed to serialise response: {}", e))
}

/// Poll generation progress for *session_id* from FastAPI.
///
/// Returns a structured `GenerationProgress` so the UI can render stage
/// labels and human-readable messages without an extra JSON parse step.
#[tauri::command]
pub async fn get_generation_progress(
    app: AppHandle,
    session_id: String,
) -> Result<GenerationProgress, String> {
    let client = reqwest::Client::builder()
        .timeout(PROBE_TIMEOUT)
        .build()
        .map_err(|e| format!("Failed to build HTTP client: {}", e))?;
    let url = "http://127.0.0.1:8000/progress";

    match client.get(&url).query(&[("session_id", session_id.as_str())]).send().await {
        Ok(response) => {
            if response.status().is_success() {
                let result: serde_json::Value = response.json().await
                    .map_err(|e| format!("Failed to parse progress response: {}", e))?;
                Ok(GenerationProgress {
                    stage: result.get("stage")
                        .and_then(|v| v.as_str())
                        .unwrap_or("idle")
                        .to_string(),
                    percent: result.get("percent")
                        .and_then(|v| v.as_u64())
                        .map(|v| v.min(100) as u8)
                        .unwrap_or(0),
                    message: result.get("message")
                        .and_then(|v| v.as_str())
                        .unwrap_or("")
                        .to_string(),
                })
            } else {
                Ok(GenerationProgress { stage: "idle".into(), percent: 0, message: String::new() })
            }
        }
        Err(e) => {
            log::warn!("Progress check failed: {}", e);
            Ok(GenerationProgress { stage: "idle".into(), percent: 0, message: String::new() })
        }
    }
}