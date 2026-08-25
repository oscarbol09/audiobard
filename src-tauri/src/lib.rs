pub mod commands;

use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build())
        .manage(crate::commands::sidecar::PythonSidecar::new())
        .invoke_handler(tauri::generate_handler![
            crate::commands::sidecar::start_python_sidecar,
            crate::commands::sidecar::stop_python_sidecar,
            crate::commands::sidecar::check_server_health,
            crate::commands::sidecar::generate_audiobook,
            crate::commands::sidecar::get_generation_progress,
            crate::commands::sidecar::cancel_audiobook,
            crate::commands::sidecar::get_library,
            crate::commands::sidecar::download_book,
            crate::commands::sidecar::select_output_folder,
            crate::commands::sidecar::clear_cache,
            crate::commands::sidecar::delete_book,
        ])
        .setup(|app| {
            // Start the Python sidecar on app launch
            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                // Give the app a moment to fully initialize
                tokio::time::sleep(std::time::Duration::from_millis(500)).await;
                let _ = crate::commands::sidecar::start_python_sidecar(app_handle.clone(), app_handle.state()).await;
            });
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                // Stop the Python sidecar when the window is closed
                let sidecar: tauri::State<'_, crate::commands::sidecar::PythonSidecar> = window.state();
                let _ = tauri::async_runtime::block_on(async {
                    let _ = crate::commands::sidecar::stop_python_sidecar(sidecar).await;
                });
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}