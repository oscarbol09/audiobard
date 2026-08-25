//! Sidecar commands for managing the FastAPI Python process.

use std::sync::Mutex;
use std::time::Duration;
use serde::Serialize;
use tauri::{AppHandle, Runtime, State};
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
/// must stay in sync with `GenerationProgress` in
/// `gui/src/stores/generation.ts`.
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

    // Try sidecar binary first; if unavailable (e.g. dev mode), fallback to system python command
    let sidecar_command = match shell.sidecar("python-sidecar") {
        Ok(cmd) => cmd,
        Err(_) => shell
            .command("python")
            .env("PYTHONPATH", "src")
            .args(["-m", "uvicorn", "audiobard.api:app", "--host", "127.0.0.1", "--port", "8000"]),
    };

    // Spawn the sidecar process
    let (mut rx, child) = match sidecar_command.spawn() {
        Ok(res) => res,
        Err(e) => {
            log::warn!("Failed sidecar spawn ({}), trying python command fallback...", e);
            shell
                .command("python")
                .env("PYTHONPATH", "src")
                .args(["-m", "uvicorn", "audiobard.api:app", "--host", "127.0.0.1", "--port", "8000"])
                .spawn()
                .map_err(|err| format!("Failed to spawn Python sidecar: {}", err))?
        }
    };

    // Store the child process for later shutdown
    {
        let mut guard = sidecar.child.lock().map_err(|e| format!("Mutex lock failed: {}", e))?;
        *guard = Some(child);
    }

    // Spawn a task to monitor the sidecar output
    let _app_handle = app.clone();
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

    if let Some(child) = guard.take() {
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
        Ok(response) => {
            if !response.status().is_success() {
                return Ok(false);
            }
            // Also probe /library to verify it is the current AudioBard API app version
            let lib_url = "http://127.0.0.1:8000/library";
            match client.get(lib_url).send().await {
                Ok(res) => Ok(res.status().is_success()),
                Err(_) => Ok(false),
            }
        }
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
    file_base64: String,
    file_name: String,
    locale: String,
    tts_provider: String,
    llm_provider: String,
    llm_model: String,
    session_id: String,
    openrouter_api_key: Option<String>,
    gemini_api_key: Option<String>,
    nim_api_key: Option<String>,
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
        "openrouter_api_key": openrouter_api_key.unwrap_or_default(),
        "gemini_api_key": gemini_api_key.unwrap_or_default(),
        "nim_api_key": nim_api_key.unwrap_or_default(),
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
pub async fn get_generation_progress(session_id: String) -> Result<GenerationProgress, String> {
    let client = reqwest::Client::builder()
        .timeout(PROBE_TIMEOUT)
        .build()
        .map_err(|e| format!("Failed to build HTTP client: {}", e))?;
    let url = "http://127.0.0.1:8000/progress";

    match client.get(url).query(&[("session_id", session_id.as_str())]).send().await {
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

/// Cancel an in-flight generation.
///
/// Posts the session id to FastAPI's `/cancel` endpoint, which
/// sets a flag on the `ProgressStore` entry. The pipeline's next
/// progress emit raises `asyncio.CancelledError` and unwinds.
///
/// Returns `Ok(())` when FastAPI acknowledges (the endpoint is
/// idempotent — unknown or already-finished sessions still return
/// 200). A network failure surfaces as an `Err` so the Vue store can
/// decide whether to retry or treat the cancel as best-effort.
#[tauri::command]
pub async fn cancel_audiobook(session_id: String) -> Result<String, String> {
    let client = reqwest::Client::builder()
        .timeout(PROBE_TIMEOUT)
        .build()
        .map_err(|e| format!("Failed to build HTTP client: {}", e))?;
    let url = "http://127.0.0.1:8000/cancel";

    let payload = serde_json::json!({
        "session_id": session_id,
    });

    let response = client
        .post(url)
        .json(&payload)
        .send()
        .await
        .map_err(|e| format!("Failed to call /cancel: {}", e))?;

    if !response.status().is_success() {
        let err = response.text().await.unwrap_or_default();
        return Err(format!("Cancel failed: {}", err));
    }

    Ok("cancelled".to_string())
}

/// Library book entry returned by the API.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LibraryBook {
    pub id: i64,
    pub title: String,
    pub path: String,
    pub total_paragraphs: i64,
    pub total_words: i64,
    pub dialog_ratio: f64,
    pub created_at: Option<String>,
}

/// Fetch the full library from FastAPI.
#[tauri::command]
pub async fn get_library() -> Result<Vec<LibraryBook>, String> {
    let client = reqwest::Client::builder()
        .timeout(PROBE_TIMEOUT)
        .build()
        .map_err(|e| format!("Failed to build HTTP client: {}", e))?;
    let url = "http://127.0.0.1:8000/library";

    match client.get(url).send().await {
        Ok(response) => {
            if response.status().is_success() {
                let books: Vec<LibraryBook> = response.json().await
                    .map_err(|e| format!("Failed to parse library response: {}", e))?;
                Ok(books)
            } else {
                let err = response.text().await.unwrap_or_default();
                Err(format!("Library request failed: {}", err))
            }
        }
        Err(e) => {
            log::warn!("Library request failed: {}", e);
            Err(format!("Network error: {}", e))
        }
    }
}

/// Download a generated audiobook.
///
/// Returns the local file path so the UI can open it with the system default player.
#[tauri::command]
pub async fn download_book(book_id: i64) -> Result<String, String> {
    let client = reqwest::Client::builder()
        .timeout(PROBE_TIMEOUT)
        .build()
        .map_err(|e| format!("Failed to build HTTP client: {}", e))?;
    let url = format!("http://127.0.0.1:8000/book/{}/path", book_id);

    match client.get(url).send().await {
        Ok(response) => {
            if response.status().is_success() {
                let body: serde_json::Value = response.json().await
                    .map_err(|e| format!("Failed to parse path response: {}", e))?;
                let path = body.get("path")
                    .and_then(|v| v.as_str())
                    .ok_or_else(|| "Missing path field in response".to_string())?;
                Ok(path.to_string())
            } else {
                let err = response.text().await.unwrap_or_default();
                Err(format!("Download path request failed: {}", err))
            }
        }
        Err(e) => {
            log::warn!("Download path request failed: {}", e);
            Err(format!("Network error: {}", e))
        }
    }
}

/// Regenerate a book with previous settings (stub).
#[tauri::command]
pub async fn regenerate_book(book_id: i64, settings: serde_json::Value) -> Result<String, String> {
    let client = reqwest::Client::builder()
        .timeout(GENERATE_TIMEOUT)
        .build()
        .map_err(|e| format!("Failed to build HTTP client: {}", e))?;
    let url = format!("http://127.0.0.1:8000/book/{}/regenerate", book_id);

    match client.post(url).json(&settings).send().await {
        Ok(response) => {
            if response.status().is_success() {
                let result: serde_json::Value = response.json().await
                    .map_err(|e| format!("Failed to parse regenerate response: {}", e))?;
                Ok(result.to_string())
            } else {
                let err = response.text().await.unwrap_or_default();
                Err(format!("Regenerate failed: {}", err))
            }
        }
        Err(e) => {
            log::warn!("Regenerate request failed: {}", e);
            Err(format!("Network error: {}", e))
        }
    }
}

/// Clear cached audio clips and LLM responses via FastAPI backend.
#[tauri::command]
pub async fn clear_cache() -> Result<String, String> {
    let client = reqwest::Client::builder()
        .timeout(PROBE_TIMEOUT)
        .build()
        .map_err(|e| format!("Failed to build HTTP client: {}", e))?;
    let url = "http://127.0.0.1:8000/clear_cache";

    match client.post(url).send().await {
        Ok(response) => {
            if response.status().is_success() {
                Ok("Cache cleared".to_string())
            } else {
                let err = response.text().await.unwrap_or_default();
                Err(format!("Clear cache failed: {}", err))
            }
        }
        Err(e) => {
            log::warn!("Clear cache request failed: {}", e);
            Err(format!("Network error: {}", e))
        }
    }
}

/// Open a native folder-picker dialog and return the selected path.
///
/// Returns `None` when the user cancels without selecting a folder.
/// The blocking dialog call is offloaded to a dedicated thread so it
/// does not block the Tokio async runtime.
#[tauri::command]
pub async fn select_output_folder(app: AppHandle) -> Result<Option<String>, String> {
    use tauri_plugin_dialog::DialogExt;
    let folder = tokio::task::spawn_blocking(move || {
        app.dialog().file().blocking_pick_folder()
    })
    .await
    .map_err(|e| format!("Dialog task panicked: {}", e))?;

    Ok(folder.map(|p| p.to_string()))
}
