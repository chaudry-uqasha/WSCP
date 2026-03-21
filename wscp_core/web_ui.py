def render_index_html(upload_folder, allow_uploads, allow_downloads, allowed_paths):
    UPLOAD_FOLDER = upload_folder
    ALLOW_UPLOADS = allow_uploads
    ALLOW_DOWNLOADS = allow_downloads
    ALLOWED_PATHS = allowed_paths
    return f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <title>WSCP - File Sharing Server</title>
                <link href="https://fonts.googleapis.com/css2?family=Inter:wght@500;700&display=swap" rel="stylesheet">
                <style>
                    * {{
                        margin: 0;
                        padding: 0;
                        box-sizing: border-box;
                    }}

                    :root {{
                        --bg-0: #000000;
                        --bg-1: #080808;
                        --bg-2: #101010;
                        --bg-3: #171717;
                        --line-1: #242424;
                        --line-2: #343434;
                        --text-1: #ffffff;
                        --text-2: #d5d5d5;
                        --text-3: #9b9b9b;
                        --radius-1: 8px;
                        --radius-2: 10px;
                        --btn-h: 34px;
                    }}
                    
                    body {{
                        font-family: 'Inter', sans-serif;
                        background-color: var(--bg-0);
                        color: var(--text-1);
                        display: flex;
                        flex-direction: column;
                        height: 100vh;
                    }}

                    button {{
                        font-family: 'Inter', sans-serif;
                    }}
                    
                    .container {{
                        display: flex;
                        flex: 1;
                        overflow: hidden;
                    }}
                    
                    .sidebar {{
                        width: 280px;
                        background: linear-gradient(180deg, #0d0d0d 0%, #090909 100%);
                        border-right: 1px solid var(--line-1);
                        overflow-y: auto;
                        padding: 20px 15px;
                        font-size: 13px;
                    }}
                    
                    .main-content {{
                        flex: 1;
                        display: flex;
                        flex-direction: column;
                        overflow: hidden;
                        background-color: var(--bg-0);
                    }}
                    
                    .toolbar {{
                        background-color: var(--bg-2);
                        border-bottom: 1px solid var(--line-1);
                        padding: 12px 20px;
                        display: flex;
                        gap: 8px;
                        align-items: center;
                        justify-content: flex-start;
                    }}
                    
                    .toolbar .spacer {{
                        flex: 1;
                    }}
                    
                    .toolbar .bulk-actions {{
                        display: none;
                        gap: 8px;
                    }}
                    
                    .toolbar .bulk-actions.show {{
                        display: flex;
                    }}

                    .toolbar .bulk-management {{
                        display: none;
                        gap: 8px;
                    }}

                    .toolbar .bulk-management.show {{
                        display: flex;
                    }}

                    .toolbar .search-wrap {{
                        display: none;
                        align-items: center;
                        gap: 8px;
                        min-width: 220px;
                        max-width: 420px;
                        flex: 1 1 300px;
                    }}

                    .toolbar .search-wrap.show {{
                        display: flex;
                    }}

                    .toolbar .search-wrap input {{
                        flex: 1;
                        height: var(--btn-h);
                        border-radius: var(--radius-1);
                        border: 1px solid var(--line-2);
                        padding: 0 10px;
                        background: #0f0f0f;
                        color: var(--text-1);
                        font-size: 12px;
                    }}

                    .toolbar .search-wrap input:focus-visible {{
                        outline: 2px solid #9a9a9a;
                        outline-offset: 2px;
                    }}

                    #search-clear {{
                        min-width: 72px;
                    }}

                    .toolbar button,
                    .breadcrumb button,
                    .close-btn,
                    .action-btn,
                    .dialog-content button {{
                        height: var(--btn-h);
                        border-radius: var(--radius-1);
                        border: 1px solid var(--line-2);
                        padding: 0 12px;
                        cursor: pointer;
                        font-size: 12px;
                        font-weight: 600;
                        letter-spacing: 0.04em;
                        transition: all 0.18s ease;
                        display: inline-flex;
                        align-items: center;
                        justify-content: center;
                        gap: 6px;
                    }}

                    .toolbar button,
                    .dialog-content button {{
                        background-color: var(--text-1);
                        color: #050505;
                        border-color: var(--text-1);
                    }}

                    .toolbar button:hover,
                    .dialog-content button:hover {{
                        background-color: #e8e8e8;
                        border-color: #e8e8e8;
                    }}

                    .toolbar button[disabled] {{
                        opacity: 0.4;
                        cursor: not-allowed;
                    }}

                    .breadcrumb button,
                    .close-btn,
                    .action-btn {{
                        background-color: var(--bg-3);
                        color: var(--text-1);
                    }}

                    .breadcrumb button:hover,
                    .close-btn:hover,
                    .action-btn:hover {{
                        background-color: #232323;
                        border-color: #5a5a5a;
                    }}

                    .toolbar button:focus-visible,
                    .breadcrumb button:focus-visible,
                    .close-btn:focus-visible,
                    .action-btn:focus-visible,
                    .dialog-content button:focus-visible {{
                        outline: 2px solid #9a9a9a;
                        outline-offset: 2px;
                    }}

                    #sidebar-toggle {{
                        width: var(--btn-h);
                        padding: 0;
                    }}

                    #bulk-zip,
                    #bulk-download,
                    #bulk-delete,
                    #bulk-move {{
                        min-width: 108px;
                    }}
                    
                    .sidebar.hidden {{
                        display: none;
                    }}

                    .sidebar-backdrop {{
                        display: none;
                    }}
                    
                    .main-content.fullwidth {{
                        width: 100%;
                    }}
                    
                    .breadcrumb {{
                        background-color: #0d0d0d;
                        border-bottom: 1px solid var(--line-1);
                        padding: 12px 20px;
                        display: flex;
                        align-items: center;
                        gap: 8px;
                        font-size: 12px;
                    }}
                    
                    .breadcrumb span {{
                        color: var(--text-3);
                    }}
                    
                    .table-container {{
                        flex: 1;
                        overflow: auto;
                        padding: 18px;
                        background: linear-gradient(180deg, #050505 0%, #000000 100%);
                    }}
                    
                    .file-table {{
                        width: 100%;
                        min-width: 1120px;
                        table-layout: fixed;
                        border-collapse: separate;
                        border-spacing: 0;
                        background-color: #050505;
                        border: 1px solid #1f1f1f;
                        border-radius: var(--radius-2);
                        overflow: hidden;
                    }}
                    
                    .file-table thead {{
                        position: sticky;
                        top: 0;
                        z-index: 10;
                    }}
                    
                    .file-table th {{
                        background-color: #0f0f0f;
                        color: #ffffff;
                        padding: 0 12px;
                        text-align: left;
                        border-bottom: 1px solid #2b2b2b;
                        font-weight: 600;
                        font-size: 11px;
                        letter-spacing: 0.08em;
                        text-transform: uppercase;
                        height: 42px;
                        vertical-align: middle;
                    }}

                    .file-table th.col-size {{
                        text-align: right;
                        padding-right: 22px;
                    }}
                    
                    .file-table td {{
                        padding: 0 12px;
                        border-bottom: 1px solid #191919;
                        color: #d0d0d0;
                        font-size: 12px;
                        height: 48px;
                        line-height: 1;
                        vertical-align: middle;
                    }}
                    
                    .file-table tbody tr {{
                        height: 48px;
                    }}
                    
                    .file-table tbody tr:hover {{
                        background-color: #0b0b0b;
                    }}

                    .file-table tbody tr.folder-row td.col-name {{
                        cursor: pointer;
                    }}
                    
                    .file-table tbody tr:last-child td {{
                        border-bottom: none;
                    }}

                    .col-select {{
                        width: 52px;
                        text-align: center;
                        padding: 0 8px;
                    }}

                    .col-name {{
                        width: 30%;
                    }}

                    .col-size {{
                        width: 14%;
                        text-align: right;
                        padding-right: 22px;
                        color: #b8b8b8;
                        font-variant-numeric: tabular-nums;
                    }}

                    .col-type {{
                        width: 12%;
                        color: #b8b8b8;
                    }}

                    .col-date {{
                        width: 20%;
                        color: #a6a6a6;
                        font-variant-numeric: tabular-nums;
                    }}

                    .col-action {{
                        width: 280px;
                    }}
                    
                    .filename {{
                        color: #ffffff;
                        cursor: pointer;
                        font-weight: 500;
                        white-space: nowrap;
                        overflow: hidden;
                        text-overflow: ellipsis;
                    }}
                    
                    .filename:hover {{
                        color: #f1f1f1;
                    }}
                    
                    .action-slot {{
                        display: flex;
                        align-items: center;
                        justify-content: flex-start;
                        gap: 6px;
                        min-height: 48px;
                    }}
                    
                    .action-btn {{
                        height: 30px;
                        min-width: 78px;
                        padding: 0 12px;
                        font-size: 10px;
                        letter-spacing: 0.04em;
                    }}

                    .action-btn.manage-action {{
                        display: none;
                    }}

                    body.manage-mode .action-btn.manage-action {{
                        display: inline-flex;
                    }}

                    .tree-item.drop-target,
                    tr.drop-target td {{
                        background-color: #1a1a1a !important;
                        border-color: #646464 !important;
                    }}

                    .action-placeholder {{
                        color: #5a5a5a;
                        font-size: 13px;
                        font-weight: 600;
                    }}
                    
                    .tree-item {{
                        margin: 4px 0;
                        color: var(--text-2);
                        padding: 8px 10px;
                        border-radius: var(--radius-1);
                        border: 1px solid transparent;
                        transition: all 0.2s;
                    }}
                    
                    .tree-item.folder {{
                        cursor: pointer;
                        user-select: none;
                    }}
                    
                    .tree-item.folder:hover {{
                        background-color: #171717;
                        border-color: #2f2f2f;
                        color: var(--text-1);
                    }}
                    
                    .tree-item.active {{
                        background-color: #1f1f1f;
                        border-color: #3a3a3a;
                        color: var(--text-1);
                        font-weight: 600;
                    }}
                    
                    .tree-children {{
                        margin-left: 12px;
                        display: none;
                    }}
                    
                    .tree-children.open {{
                        display: block;
                    }}
                    
                    .tree-toggle {{
                        cursor: pointer;
                        color: #7d7d7d;
                        margin-right: 6px;
                        user-select: none;
                        font-weight: bold;
                        display: inline-block;
                        transition: all 0.15s ease;
                    }}
                    
                    .tree-toggle:hover {{
                        transform: scale(1.3);
                        color: #b8b8b8;
                    }}
                    
                    .modal {{
                        display: none;
                        position: fixed;
                        z-index: 1000;
                        left: 0;
                        top: 0;
                        width: 100%;
                        height: 100%;
                        background-color: rgba(0, 0, 0, 0.8);
                    }}
                    
                    .modal.show {{
                        display: flex;
                        align-items: center;
                        justify-content: center;
                    }}
                    
                    .modal-content {{
                        background: linear-gradient(180deg, #121212 0%, #0d0d0d 100%);
                        padding: 18px;
                        border: 1px solid #2d2d2d;
                        border-radius: 12px;
                        width: 85%;
                        height: 85%;
                        display: flex;
                        flex-direction: column;
                        position: relative;
                        box-shadow: 0 10px 40px rgba(0,0,0,0.7);
                    }}
                    
                    .modal-header {{
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        margin-bottom: 15px;
                        border-bottom: 1px solid #2a2a2a;
                        padding-bottom: 12px;
                    }}
                    
                    .modal-header h2 {{
                        color: var(--text-1);
                        font-size: 16px;
                        font-weight: 600;
                    }}
                    
                    .modal-body {{
                        flex: 1;
                        overflow: auto;
                        background-color: #080808;
                        border: 1px solid #1f1f1f;
                        border-radius: var(--radius-1);
                        padding: 12px;
                        font-family: 'Courier New', monospace;
                        font-size: 12px;
                        white-space: pre-wrap;
                        word-wrap: break-word;
                        color: var(--text-1);
                    }}

                    .doc-preview-frame {{
                        width: 100%;
                        height: 100%;
                        min-height: 420px;
                        border: 0;
                        border-radius: 8px;
                        background: #080808;
                    }}

                    .doc-preview-message {{
                        font-family: 'Inter', sans-serif;
                        font-size: 13px;
                        color: var(--text-2);
                        line-height: 1.5;
                        margin-bottom: 12px;
                    }}

                    .doc-preview-actions {{
                        display: flex;
                        gap: 10px;
                        flex-wrap: wrap;
                    }}

                    .sheet-preview-table {{
                        width: 100%;
                        border-collapse: collapse;
                        font-family: 'Inter', sans-serif;
                        font-size: 12px;
                    }}

                    .sheet-preview-table th,
                    .sheet-preview-table td {{
                        border: 1px solid #242424;
                        padding: 6px 8px;
                        text-align: left;
                        vertical-align: top;
                        max-width: 260px;
                        overflow: hidden;
                        text-overflow: ellipsis;
                        white-space: nowrap;
                    }}

                    .sheet-preview-table th {{
                        background: #141414;
                        color: #fafafa;
                        font-weight: 600;
                    }}

                    .image-viewer-body {{
                        flex: 1;
                        display: flex;
                        flex-direction: column;
                        gap: 10px;
                        min-height: 0;
                    }}

                    .image-nav {{
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        gap: 10px;
                    }}

                    .image-nav-btn {{
                        min-width: 44px;
                        height: 34px;
                        border-radius: 8px;
                        border: 1px solid #3a3a3a;
                        background: #151515;
                        color: var(--text-1);
                        cursor: pointer;
                        font-size: 16px;
                    }}

                    .image-nav-btn:disabled {{
                        opacity: 0.45;
                        cursor: not-allowed;
                    }}

                    .image-counter {{
                        min-width: 72px;
                        text-align: center;
                        color: var(--text-3);
                        font-size: 12px;
                    }}

                    .image-preview-wrap {{
                        flex: 1;
                        min-height: 0;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        border: 1px solid #1f1f1f;
                        border-radius: var(--radius-1);
                        background: #080808;
                        overflow: hidden;
                        padding: 10px;
                    }}

                    .image-preview {{
                        max-width: 100%;
                        max-height: 100%;
                        object-fit: contain;
                    }}

                    .video-viewer-body {{
                        flex: 1;
                        display: flex;
                        flex-direction: column;
                        gap: 10px;
                        min-height: 0;
                    }}

                    .video-nav {{
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        gap: 10px;
                    }}

                    .video-nav-btn {{
                        min-width: 44px;
                        height: 34px;
                        border-radius: 8px;
                        border: 1px solid #3a3a3a;
                        background: #151515;
                        color: var(--text-1);
                        cursor: pointer;
                        font-size: 16px;
                    }}

                    .video-nav-btn:disabled {{
                        opacity: 0.45;
                        cursor: not-allowed;
                    }}

                    .video-counter {{
                        min-width: 72px;
                        text-align: center;
                        color: var(--text-3);
                        font-size: 12px;
                    }}

                    .video-preview-wrap {{
                        flex: 1;
                        min-height: 0;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        border: 1px solid #1f1f1f;
                        border-radius: var(--radius-1);
                        background: #080808;
                        overflow: hidden;
                        padding: 10px;
                    }}

                    .video-preview {{
                        max-width: 100%;
                        max-height: 100%;
                        width: 100%;
                        background: #000;
                    }}

                    .audio-player-body {{
                        flex: 1;
                        display: flex;
                        flex-direction: column;
                        gap: 12px;
                        min-height: 0;
                    }}

                    .audio-nav {{
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        gap: 10px;
                    }}

                    .audio-nav-btn {{
                        min-width: 44px;
                        height: 34px;
                        border-radius: 8px;
                        border: 1px solid #3a3a3a;
                        background: #151515;
                        color: var(--text-1);
                        cursor: pointer;
                        font-size: 16px;
                    }}

                    .audio-nav-btn:disabled {{
                        opacity: 0.45;
                        cursor: not-allowed;
                    }}

                    .audio-counter {{
                        min-width: 72px;
                        text-align: center;
                        color: var(--text-3);
                        font-size: 12px;
                    }}

                    .audio-preview-wrap {{
                        border: 1px solid #1f1f1f;
                        border-radius: var(--radius-1);
                        background: #080808;
                        padding: 18px 14px;
                    }}

                    .audio-preview {{
                        width: 100%;
                    }}
                    
                    .row-checkbox {{
                        width: 20px;
                        height: 20px;
                        cursor: pointer;
                        accent-color: #24d061;
                    }}
                    
                    .custom-dialog {{
                        position: fixed;
                        top: 0;
                        left: 0;
                        width: 100%;
                        height: 100%;
                        background-color: rgba(0, 0, 0, 0.78);
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        z-index: 1000;
                    }}
                    
                    .dialog-content {{
                        background: linear-gradient(180deg, #1a1a1a 0%, #121212 100%);
                        border: 1px solid #3a3a3a;
                        border-radius: 12px;
                        padding: 24px 28px;
                        max-width: 420px;
                        width: calc(100% - 28px);
                        text-align: center;
                        color: var(--text-1);
                        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6);
                    }}
                    
                    .dialog-content p {{
                        margin: 0 0 24px 0;
                        font-size: 13px;
                        line-height: 1.5;
                        color: #dddddd;
                    }}

                    .dialog-title {{
                        font-size: 15px;
                        font-weight: 700;
                        margin-bottom: 10px;
                        color: var(--text-1);
                    }}

                    .dialog-subtitle {{
                        font-size: 12px;
                        color: var(--text-3);
                        margin-bottom: 14px;
                    }}

                    .dialog-row {{
                        display: flex;
                        align-items: center;
                        justify-content: space-between;
                        gap: 12px;
                        margin: 10px 0;
                    }}

                    .dialog-row input[type="checkbox"] {{
                        width: 16px;
                        height: 16px;
                        accent-color: #ffffff;
                    }}

                    .dialog-row label {{
                        font-size: 12px;
                        color: var(--text-2);
                        display: flex;
                        align-items: center;
                        gap: 8px;
                    }}

                    .dialog-content input[type="file"] {{
                        width: 100%;
                        margin: 8px 0 14px;
                        color: var(--text-2);
                        font-size: 12px;
                    }}

                    .dialog-actions {{
                        display: flex;
                        justify-content: flex-end;
                        gap: 10px;
                        margin-top: 14px;
                    }}

                    .dialog-actions .ghost-btn {{
                        background: var(--bg-3);
                        color: var(--text-1);
                        border: 1px solid var(--line-2);
                    }}

                    .move-tree {{
                        width: 100%;
                        max-height: 240px;
                        overflow: auto;
                        border: 1px solid #3a3a3a;
                        border-radius: 8px;
                        background: #0f0f0f;
                        text-align: left;
                        padding: 6px 0;
                    }}

                    .move-tree-item {{
                        display: flex;
                        align-items: center;
                        gap: 8px;
                        height: 30px;
                        padding-right: 10px;
                        border-left: 2px solid transparent;
                        color: var(--text-2);
                        cursor: pointer;
                    }}

                    .move-tree-item:hover {{
                        background: #171717;
                        color: var(--text-1);
                    }}

                    .move-tree-item.selected {{
                        background: #1f1f1f;
                        border-left-color: #7a7a7a;
                        color: var(--text-1);
                    }}

                    .move-tree-toggle {{
                        width: 14px;
                        text-align: center;
                        color: #7d7d7d;
                        font-size: 11px;
                        user-select: none;
                        flex: 0 0 14px;
                        display: inline-block;
                        transition: all 0.15s ease;
                        cursor: pointer;
                    }}
                    
                    .move-tree-toggle:hover {{
                        transform: scale(1.3);
                        color: #b8b8b8;
                    }}

                    .move-tree-label {{
                        font-size: 12px;
                        white-space: nowrap;
                        overflow: hidden;
                        text-overflow: ellipsis;
                    }}

                    .move-tree-children {{
                        display: none;
                    }}

                    .move-tree-children.open {{
                        display: block;
                    }}

                    .progress-wrap {{
                        width: 100%;
                        height: 10px;
                        border-radius: 999px;
                        border: 1px solid #303030;
                        background: #090909;
                        overflow: hidden;
                        margin: 12px 0 10px;
                    }}

                    .progress-fill {{
                        height: 100%;
                        width: 0%;
                        background: linear-gradient(90deg, #f4f4f4 0%, #bdbdbd 100%);
                        transition: width 0.18s ease;
                    }}

                    .progress-meta {{
                        display: flex;
                        justify-content: space-between;
                        font-size: 11px;
                        color: var(--text-3);
                        margin-bottom: 8px;
                    }}

                    .dialog-result {{
                        margin-top: 10px;
                        font-size: 12px;
                        color: var(--text-2);
                        word-break: break-all;
                    }}

                    .drop-overlay {{
                        position: fixed;
                        inset: 0;
                        z-index: 1100;
                        display: none;
                        align-items: center;
                        justify-content: center;
                        background: rgba(0, 0, 0, 0.72);
                    }}

                    .drop-overlay.show {{
                        display: flex;
                    }}

                    .drop-panel {{
                        width: min(560px, calc(100% - 28px));
                        border: 1px dashed #6a6a6a;
                        border-radius: 12px;
                        background: linear-gradient(180deg, #141414 0%, #0e0e0e 100%);
                        padding: 26px;
                        text-align: center;
                        color: var(--text-2);
                        font-size: 13px;
                    }}
                    .mode-badge {{
                        margin-left: 8px;
                        font-size: 11px;
                        color: #0a0a0a;
                        background: #d8d8d8;
                        border: 1px solid #d8d8d8;
                        border-radius: 999px;
                        padding: 5px 10px;
                        font-weight: 700;
                        letter-spacing: 0.04em;
                        text-transform: uppercase;
                    }}

                    .toast-host {{
                        position: fixed;
                        right: 16px;
                        bottom: 16px;
                        z-index: 1200;
                        display: flex;
                        flex-direction: column;
                        gap: 8px;
                        pointer-events: none;
                    }}

                    .toast {{
                        min-width: 220px;
                        max-width: 340px;
                        padding: 10px 12px;
                        border-radius: 10px;
                        border: 1px solid #3a3a3a;
                        background: #111111;
                        color: #f3f3f3;
                        font-size: 12px;
                        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.35);
                        opacity: 0;
                        transform: translateY(6px);
                        transition: opacity 0.16s ease, transform 0.16s ease;
                    }}

                    .toast.show {{
                        opacity: 1;
                        transform: translateY(0);
                    }}

                    .toast.success {{
                        border-color: #4c7f4c;
                    }}

                    @media (max-width: 1024px) {{
                        #sidebar-toggle {{
                            position: fixed;
                            top: 10px;
                            left: 10px;
                            z-index: 1205;
                            width: 40px;
                            height: 40px;
                        }}

                        .sidebar.mobile-open + .sidebar-backdrop + .main-content #sidebar-toggle {{
                            left: calc(min(84vw, 320px) - 50px);
                        }}

                        .sidebar {{
                            position: fixed;
                            left: 0;
                            top: 0;
                            bottom: 0;
                            width: min(84vw, 320px);
                            max-width: 320px;
                            transform: translateX(-105%);
                            transition: transform 0.2s ease;
                            z-index: 1150;
                        }}

                        .sidebar.mobile-open {{
                            transform: translateX(0);
                        }}

                        .sidebar.hidden {{
                            display: block !important;
                        }}

                        .sidebar-backdrop {{
                            position: fixed;
                            inset: 0;
                            background: rgba(0, 0, 0, 0.35);
                            z-index: 1140;
                        }}

                        .sidebar-backdrop.show {{
                            display: block;
                        }}

                        .main-content {{
                            width: 100%;
                            min-width: 0;
                        }}

                        .main-content.fullwidth {{
                            width: 100%;
                        }}

                        .col-action {{
                            width: 240px;
                        }}

                        .toolbar {{
                            padding-left: 58px;
                            gap: 8px;
                            flex-wrap: wrap;
                        }}
                    }}

                    @media (max-width: 768px) {{
                        body {{
                            overflow-x: hidden;
                        }}

                        .container {{
                            height: 100vh;
                            height: 100dvh;
                        }}

                        .toolbar {{
                            padding: 10px 10px 10px 58px;
                            gap: 8px;
                            flex-wrap: wrap;
                            align-items: stretch;
                        }}

                        .toolbar .spacer {{
                            display: none;
                        }}

                        .toolbar > button,
                        .bulk-actions button,
                        .bulk-management button {{
                            min-height: 40px;
                            padding: 0 10px;
                            font-size: 11px;
                        }}

                        .toolbar .search-wrap.show {{
                            order: 100;
                            width: 100%;
                            max-width: none;
                        }}

                        .mode-badge {{
                            order: 99;
                            margin-left: 0;
                            margin-top: 2px;
                        }}

                        .breadcrumb {{
                            padding: 8px 10px;
                            overflow-x: auto;
                            white-space: nowrap;
                            -webkit-overflow-scrolling: touch;
                        }}

                        .table-container {{
                            padding: 8px;
                            overflow-x: hidden;
                        }}

                        .file-table {{
                            min-width: 0;
                            border-collapse: separate;
                            border-spacing: 0 10px;
                            background: transparent;
                            border: 0;
                        }}

                        .file-table thead {{
                            display: none;
                        }}

                        .file-table,
                        .file-table tbody,
                        .file-table tr,
                        .file-table td {{
                            display: block;
                            width: 100%;
                        }}

                        .file-table tr {{
                            background: #0f0f0f;
                            border: 1px solid #222;
                            border-radius: 10px;
                            padding: 8px;
                            margin: 0;
                        }}

                        .file-table td {{
                            border: 0;
                            padding: 5px 8px;
                            display: flex;
                            justify-content: space-between;
                            align-items: center;
                            gap: 10px;
                        }}

                        .file-table td::before {{
                            content: attr(data-label);
                            font-size: 10px;
                            color: var(--text-3);
                            text-transform: uppercase;
                            letter-spacing: 0.04em;
                            flex: 0 0 74px;
                        }}

                        .file-table td.col-name {{
                            display: block;
                            font-size: 14px;
                            font-weight: 600;
                        }}

                        .file-table td.col-name::before {{
                            content: attr(data-label);
                            display: block;
                            margin-bottom: 3px;
                        }}

                        .file-table td.col-select {{
                            display: flex;
                            justify-content: flex-start;
                        }}

                        .file-table td.col-select::before {{
                            flex: 0 0 74px;
                        }}

                        .row-checkbox {{
                            width: 24px;
                            height: 24px;
                        }}

                        .col-action {{
                            width: 100%;
                            min-width: 0;
                        }}

                        .action-slot {{
                            justify-content: flex-start;
                            flex-wrap: wrap;
                        }}

                        .action-btn {{
                            min-width: 72px;
                            height: 36px;
                            font-size: 10px;
                        }}

                        .modal-content {{
                            width: calc(100% - 16px);
                            height: min(88vh, 760px);
                            height: min(88dvh, 760px);
                            padding: 12px;
                        }}

                        .dialog-content {{
                            width: calc(100% - 16px);
                            padding: 16px;
                        }}

                        .image-nav-btn,
                        .video-nav-btn,
                        .audio-nav-btn,
                        .close-btn {{
                            min-width: 42px;
                            height: 42px;
                        }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="sidebar hidden" id="sidebar"></div>
                    <div class="sidebar-backdrop" id="sidebar-backdrop"></div>
                    <div class="main-content">
                        <div class="toolbar">
                            <button id="sidebar-toggle" aria-label="Toggle sidebar">⇆</button>
                            <button id="upload-btn">Upload</button>
                            <button id="mkdir-btn">New Folder</button>
                            <button id="manage-btn">Manage</button>
                            <button id="search-toggle">Search</button>
                            <div class="search-wrap" id="search-wrap">
                                <input id="search-input" type="text" placeholder="Search files in current folder" aria-label="Search files" />
                                <button id="search-clear">Clear</button>
                            </div>
                            {"<span class='mode-badge'>Download Only</span>" if (not ALLOW_UPLOADS) else ("<span class='mode-badge'>Upload Only</span>" if (ALLOW_UPLOADS and not ALLOW_DOWNLOADS) else ("<span class='mode-badge'>Restricted Downloads</span>" if bool(ALLOWED_PATHS) else ""))}
                            <div class="spacer"></div>
                            <div class="bulk-actions" id="bulk-actions">
                                <button id="bulk-zip">Zip</button>
                                <button id="bulk-download">Download</button>
                            </div>
                            <div class="bulk-management" id="bulk-management">
                                <button id="bulk-delete">Delete Selected</button>
                                <button id="bulk-move">Move Selected</button>
                            </div>
                        </div>
                        <div class="breadcrumb" id="breadcrumb"></div>
                        <div class="table-container">
                            <table class="file-table">
                                <thead>
                                    <tr>
                                        <th class="col-select"></th>
                                        <th class="col-name">File Name</th>
                                        <th class="col-size">Size</th>
                                        <th class="col-type">Type</th>
                                        <th class="col-date">Date</th>
                                        <th class="col-action">Action</th>
                                    </tr>
                                </thead>
                                <tbody id="file-table"></tbody>
                            </table>
                        </div>
                    </div>
                </div>
                
                <div class="modal" id="file-modal">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h2 id="modal-title">File Viewer</h2>
                            <button class="close-btn" id="file-close-btn">✕</button>
                        </div>
                        <div class="modal-body" id="modal-body"></div>
                    </div>
                </div>

                <div class="modal" id="image-modal">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h2 id="image-modal-title">Image Viewer</h2>
                            <button class="close-btn" id="image-close-btn">✕</button>
                        </div>
                        <div class="image-viewer-body">
                            <div class="image-nav">
                                <button class="image-nav-btn" id="image-prev-btn" aria-label="Previous image">&#x2039;</button>
                                <span class="image-counter" id="image-counter">0 / 0</span>
                                <button class="image-nav-btn" id="image-next-btn" aria-label="Next image">&#x203A;</button>
                            </div>
                            <div class="image-preview-wrap">
                                <img class="image-preview" id="image-preview" alt="Image preview" />
                            </div>
                        </div>
                    </div>
                </div>

                <div class="modal" id="video-modal">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h2 id="video-modal-title">Video Player</h2>
                            <button class="close-btn" id="video-close-btn">✕</button>
                        </div>
                        <div class="video-viewer-body">
                            <div class="video-nav">
                                <button class="video-nav-btn" id="video-prev-btn" aria-label="Previous video">&#x2039;</button>
                                <span class="video-counter" id="video-counter">0 / 0</span>
                                <button class="video-nav-btn" id="video-next-btn" aria-label="Next video">&#x203A;</button>
                            </div>
                            <div class="video-preview-wrap">
                                <video class="video-preview" id="video-preview" controls></video>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="modal" id="audio-modal">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h2 id="audio-modal-title">Audio Player</h2>
                            <button class="close-btn" id="audio-close-btn">✕</button>
                        </div>
                        <div class="audio-player-body">
                            <div class="audio-nav">
                                <button class="audio-nav-btn" id="audio-prev-btn" aria-label="Previous audio">&#x2039;</button>
                                <span class="audio-counter" id="audio-counter">0 / 0</span>
                                <button class="audio-nav-btn" id="audio-next-btn" aria-label="Next audio">&#x203A;</button>
                            </div>
                            <div class="audio-preview-wrap">
                                <audio class="audio-preview" id="audio-preview" controls></audio>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="drop-overlay" id="drop-overlay">
                    <div class="drop-panel">Drop files here to upload</div>
                </div>

                <div class="toast-host" id="toast-host"></div>
                
                <script>
                    let currentPath = "{UPLOAD_FOLDER}";
                    const uploadsEnabled = {str(ALLOW_UPLOADS).lower()};
                    const downloadsEnabled = {str(ALLOW_DOWNLOADS).lower()};
                    const modal = document.getElementById('file-modal');
                    const modalTitle = document.getElementById('modal-title');
                    const modalBody = document.getElementById('modal-body');
                    const imageModal = document.getElementById('image-modal');
                    const imageModalTitle = document.getElementById('image-modal-title');
                    const imagePreview = document.getElementById('image-preview');
                    const imagePrevBtn = document.getElementById('image-prev-btn');
                    const imageNextBtn = document.getElementById('image-next-btn');
                    const imageCounter = document.getElementById('image-counter');
                    const videoModal = document.getElementById('video-modal');
                    const videoModalTitle = document.getElementById('video-modal-title');
                    const videoPreview = document.getElementById('video-preview');
                    const videoPrevBtn = document.getElementById('video-prev-btn');
                    const videoNextBtn = document.getElementById('video-next-btn');
                    const videoCounter = document.getElementById('video-counter');
                    const sidebarBackdrop = document.getElementById('sidebar-backdrop');
                    const audioModal = document.getElementById('audio-modal');
                    const audioModalTitle = document.getElementById('audio-modal-title');
                    const audioPreview = document.getElementById('audio-preview');
                    const audioPrevBtn = document.getElementById('audio-prev-btn');
                    const audioNextBtn = document.getElementById('audio-next-btn');
                    const audioCounter = document.getElementById('audio-counter');
                    const dropOverlay = document.getElementById('drop-overlay');
                    const toastHost = document.getElementById('toast-host');
                    const searchToggleBtn = document.getElementById('search-toggle');
                    const searchWrap = document.getElementById('search-wrap');
                    const searchInput = document.getElementById('search-input');
                    const searchClearBtn = document.getElementById('search-clear');
                    let itemMap = new Map();
                    let currentFolderItems = [];
                    let searchQuery = '';
                    let selectedItems = new Set();
                    let dragCounter = 0;
                    let manageMode = false;
                    let imageFilesInCurrentFolder = [];
                    let activeImageIndex = -1;
                    let videoFilesInCurrentFolder = [];
                    let activeVideoIndex = -1;
                    let audioFilesInCurrentFolder = [];
                    let activeAudioIndex = -1;
                    const INTERNAL_MOVE_MIME = 'application/x-wscp-items';

                    function ensureWriteEnabled() {{
                        if (!uploadsEnabled) {{
                            showDialog('Uploads are disabled in this mode.');
                            return false;
                        }}
                        return true;
                    }}

                    function isMobileViewport() {{
                        return window.matchMedia('(max-width: 1024px)').matches;
                    }}

                    function updateSidebarToggleIcon() {{
                        const sidebar = document.getElementById('sidebar');
                        const toggleBtn = document.getElementById('sidebar-toggle');
                        if (!sidebar || !toggleBtn) return;
                        if (isMobileViewport()) {{
                            toggleBtn.textContent = sidebar.classList.contains('mobile-open') ? '✕' : '☰';
                            return;
                        }}
                        toggleBtn.textContent = sidebar.classList.contains('hidden') ? '☰' : '⇆';
                    }}

                    function closeMobileSidebar() {{
                        if (!isMobileViewport()) return;
                        const sidebar = document.getElementById('sidebar');
                        if (!sidebar) return;
                        sidebar.classList.remove('mobile-open');
                        if (sidebarBackdrop) sidebarBackdrop.classList.remove('show');
                        updateSidebarToggleIcon();
                    }}

                    function applyResponsiveLayout(initial = false) {{
                        const sidebar = document.getElementById('sidebar');
                        const mainContent = document.querySelector('.main-content');
                        if (!sidebar || !mainContent) return;

                        if (isMobileViewport()) {{
                            sidebar.classList.remove('hidden');
                            mainContent.classList.add('fullwidth');
                            if (initial) sidebar.classList.remove('mobile-open');
                            if (sidebarBackdrop) sidebarBackdrop.classList.remove('show');
                        }} else {{
                            sidebar.classList.remove('mobile-open');
                            if (sidebarBackdrop) sidebarBackdrop.classList.remove('show');
                            if (initial) {{
                                sidebar.classList.remove('hidden');
                                mainContent.classList.remove('fullwidth');
                            }}
                        }}

                        updateSidebarToggleIcon();
                    }}

                    function setManageMode(enabled) {{
                        manageMode = !!enabled;
                        document.body.classList.toggle('manage-mode', manageMode);
                        const btn = document.getElementById('manage-btn');
                        if (btn) btn.textContent = manageMode ? 'Done' : 'Manage';
                        updateBulkActions();
                    }}

                    function showToast(message, kind = 'success') {{
                        if (!toastHost) return;
                        const toast = document.createElement('div');
                        toast.className = 'toast ' + kind;
                        toast.textContent = message;
                        toastHost.appendChild(toast);
                        requestAnimationFrame(() => toast.classList.add('show'));
                        setTimeout(() => {{
                            toast.classList.remove('show');
                            setTimeout(() => toast.remove(), 180);
                        }}, 1700);
                    }}

                    function clearSelection() {{
                        selectedItems.clear();
                        document.querySelectorAll('.row-checkbox').forEach(cb => {{
                            cb.checked = false;
                        }});
                        updateBulkActions();
                    }}

                    function isInternalMoveDrag(event) {{
                        const types = Array.from(event.dataTransfer?.types || []);
                        return types.includes(INTERNAL_MOVE_MIME);
                    }}

                    function isExternalFilesDrag(event) {{
                        const types = Array.from(event.dataTransfer?.types || []);
                        return types.includes('Files');
                    }}

                    function getDraggedInternalPaths(event) {{
                        try {{
                            const raw = event.dataTransfer?.getData(INTERNAL_MOVE_MIME) || '[]';
                            const paths = JSON.parse(raw);
                            if (!Array.isArray(paths)) return [];
                            return Array.from(new Set(paths.filter(Boolean)));
                        }} catch (_) {{
                            return [];
                        }}
                    }}

                    function getSelectedOrSinglePaths(primaryPath) {{
                        if (selectedItems.has(primaryPath) && selectedItems.size > 0) {{
                            return Array.from(selectedItems);
                        }}
                        return [primaryPath];
                    }}

                    async function postJson(url, payload) {{
                        const res = await fetch(url, {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: JSON.stringify(payload),
                        }});
                        const data = await res.json();
                        if (!res.ok) throw new Error(data.error || 'Operation failed');
                        return data;
                    }}

                    function createDialogContainer(title, subtitle = '') {{
                        const dialogDiv = document.createElement('div');
                        dialogDiv.className = 'custom-dialog';

                        const content = document.createElement('div');
                        content.className = 'dialog-content';

                        const h = document.createElement('div');
                        h.className = 'dialog-title';
                        h.textContent = title;
                        content.appendChild(h);

                        if (subtitle) {{
                            const sub = document.createElement('div');
                            sub.className = 'dialog-subtitle';
                            sub.textContent = subtitle;
                            content.appendChild(sub);
                        }}

                        dialogDiv.appendChild(content);
                        document.body.appendChild(dialogDiv);
                        return {{ dialogDiv, content }};
                    }}

                    function showDialog(message) {{
                        const ui = createDialogContainer('Notice', '');
                        const p = document.createElement('p');
                        p.textContent = message;
                        ui.content.appendChild(p);

                        const actions = document.createElement('div');
                        actions.className = 'dialog-actions';
                        const btn = document.createElement('button');
                        btn.textContent = 'OK';
                        btn.onclick = function() {{ ui.dialogDiv.remove(); }};
                        actions.appendChild(btn);
                        ui.content.appendChild(actions);
                    }}

                    function createProgressDialog(title, subtitle = '') {{
                        const ui = createDialogContainer(title, subtitle);

                        const status = document.createElement('div');
                        status.className = 'dialog-subtitle';
                        status.textContent = 'Preparing...';
                        ui.content.appendChild(status);

                        const wrap = document.createElement('div');
                        wrap.className = 'progress-wrap';
                        const fill = document.createElement('div');
                        fill.className = 'progress-fill';
                        wrap.appendChild(fill);
                        ui.content.appendChild(wrap);

                        const meta = document.createElement('div');
                        meta.className = 'progress-meta';
                        const pct = document.createElement('span');
                        pct.textContent = '0%';
                        const speed = document.createElement('span');
                        speed.textContent = '';
                        meta.appendChild(pct);
                        meta.appendChild(speed);
                        ui.content.appendChild(meta);

                        const result = document.createElement('div');
                        result.className = 'dialog-result';
                        ui.content.appendChild(result);

                        const actions = document.createElement('div');
                        actions.className = 'dialog-actions';
                        const closeBtn = document.createElement('button');
                        closeBtn.className = 'ghost-btn';
                        closeBtn.textContent = 'Close';
                        closeBtn.onclick = function() {{ ui.dialogDiv.remove(); }};
                        actions.appendChild(closeBtn);
                        ui.content.appendChild(actions);

                        return {{
                            setStatus: (msg) => status.textContent = msg,
                            setProgress: (percent) => {{
                                const p = Math.max(0, Math.min(100, Math.round(percent || 0)));
                                fill.style.width = p + '%';
                                pct.textContent = p + '%';
                            }},
                            setSpeed: (msg) => speed.textContent = msg || '',
                            setResult: (msg) => result.textContent = msg || '',
                            close: () => ui.dialogDiv.remove(),
                        }};
                    }}

                    function formatSpeed(bytesPerSecond) {{
                        if (!bytesPerSecond || bytesPerSecond <= 0) return '';
                        return formatSize(bytesPerSecond) + '/s';
                    }}

                    async function createTask(kind) {{
                        const res = await fetch('/task/new?kind=' + encodeURIComponent(kind));
                        if (!res.ok) throw new Error('Failed to create task');
                        const payload = await res.json();
                        return payload.task_id;
                    }}

                    async function getTask(taskId) {{
                        const res = await fetch('/progress?task_id=' + encodeURIComponent(taskId));
                        if (!res.ok) throw new Error('Progress unavailable');
                        return await res.json();
                    }}

                    async function waitForTaskCompletion(taskId, progressUi) {{
                        const started = Date.now();
                        while (Date.now() - started < 120000) {{
                            const task = await getTask(taskId);
                            if (progressUi) {{
                                progressUi.setProgress(task.percent || 0);
                                progressUi.setStatus(task.message || task.phase || 'Working...');
                                progressUi.setSpeed(formatSpeed(task.speed_bps));
                            }}
                            if (task.status === 'done') return task;
                            if (task.status === 'error') throw new Error(task.error || 'Task failed');
                            await new Promise(resolve => setTimeout(resolve, 350));
                        }}
                        throw new Error('Operation timeout');
                    }}

                    function xhrUpload(url, file, onProgress) {{
                        return new Promise((resolve, reject) => {{
                            const xhr = new XMLHttpRequest();
                            xhr.open('POST', url, true);
                            xhr.onload = function() {{
                                if (xhr.status >= 200 && xhr.status < 300) resolve(xhr.responseText);
                                else reject(new Error('Upload failed (' + xhr.status + ')'));
                            }};
                            xhr.onerror = function() {{ reject(new Error('Upload failed')); }};
                            xhr.upload.onprogress = function(event) {{
                                if (event.lengthComputable && onProgress) onProgress(event.loaded, event.total);
                            }};
                            xhr.send(file);
                        }});
                    }}

                    function xhrDownloadBlob(url, method, body, onProgress) {{
                        return new Promise((resolve, reject) => {{
                            const xhr = new XMLHttpRequest();
                            xhr.open(method, url, true);
                            xhr.responseType = 'blob';
                            xhr.onload = function() {{
                                if (xhr.status >= 200 && xhr.status < 300) resolve(xhr.response);
                                else reject(new Error('Download failed (' + xhr.status + ')'));
                            }};
                            xhr.onerror = function() {{ reject(new Error('Download failed')); }};
                            xhr.onprogress = function(event) {{
                                if (event.lengthComputable && onProgress) onProgress(event.loaded, event.total);
                            }};
                            if (body) {{
                                xhr.setRequestHeader('Content-Type', 'application/json');
                                xhr.send(body);
                            }} else {{
                                xhr.send();
                            }}
                        }});
                    }}

                    function saveBlob(blob, fileName) {{
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = fileName;
                        document.body.appendChild(a);
                        a.click();
                        a.remove();
                        setTimeout(() => URL.revokeObjectURL(url), 1500);
                    }}

                    function openUploadDialog() {{
                        if (!ensureWriteEnabled()) return;
                        const ui = createDialogContainer('Upload Files', 'Upload to: ' + currentPath);

                        const fileInput = document.createElement('input');
                        fileInput.type = 'file';
                        fileInput.multiple = true;
                        ui.content.appendChild(fileInput);

                        const options = document.createElement('div');
                        options.className = 'dialog-row';
                        const hashLabel = document.createElement('label');
                        const hashCheck = document.createElement('input');
                        hashCheck.type = 'checkbox';
                        hashLabel.appendChild(hashCheck);
                        hashLabel.appendChild(document.createTextNode('Calculate SHA-256 after upload'));
                        options.appendChild(hashLabel);
                        ui.content.appendChild(options);

                        const actions = document.createElement('div');
                        actions.className = 'dialog-actions';
                        const cancelBtn = document.createElement('button');
                        cancelBtn.className = 'ghost-btn';
                        cancelBtn.textContent = 'Cancel';
                        cancelBtn.onclick = function() {{ ui.dialogDiv.remove(); }};
                        const startBtn = document.createElement('button');
                        startBtn.textContent = 'Start Upload';
                        startBtn.onclick = async function() {{
                            const files = Array.from(fileInput.files || []);
                            if (files.length === 0) {{
                                showDialog('Select at least one file.');
                                return;
                            }}
                            ui.dialogDiv.remove();
                            await uploadFilesBatch(files, hashCheck.checked);
                        }};
                        actions.appendChild(cancelBtn);
                        actions.appendChild(startBtn);
                        ui.content.appendChild(actions);
                    }}

                    async function uploadSingleFile(file, withHash, autoCloseOnSuccess = false) {{
                        const taskId = await createTask('upload');
                        const progress = createProgressDialog('Uploading', file.name);
                        try {{
                            const uploadUrl = '/upload-raw?task_id=' + encodeURIComponent(taskId) +
                                '&path=' + encodeURIComponent(currentPath) +
                                '&filename=' + encodeURIComponent(file.name) +
                                '&hash=' + (withHash ? '1' : '0');

                            const responseText = await xhrUpload(uploadUrl, file, (loaded, total) => {{
                                progress.setProgress((loaded / Math.max(total, 1)) * 100);
                                progress.setStatus('Uploading...');
                            }});

                            const task = await waitForTaskCompletion(taskId, progress);
                            const response = JSON.parse(responseText);
                            const resultText = task.hash_sha256 ? 'SHA-256: ' + task.hash_sha256 : 'Upload complete';
                            progress.setStatus('Completed');
                            progress.setProgress(100);
                            progress.setResult(resultText + ' | Saved as: ' + response.name);
                            if (autoCloseOnSuccess) {{
                                setTimeout(() => progress.close(), 450);
                            }}
                        }} catch (e) {{
                            progress.setStatus('Failed');
                            progress.setResult(e.message);
                        }}
                    }}

                    async function uploadFilesBatch(files, withHash = false) {{
                        if (!ensureWriteEnabled()) return;
                        if (!files || files.length === 0) return;
                        if (files.length === 1) {{
                            await uploadSingleFile(files[0], withHash, false);
                            await loadFolderContents(currentPath);
                            await loadFolderTree();
                            return;
                        }}

                        const progress = createProgressDialog('Uploading Files', files.length + ' file(s)');
                        let successCount = 0;
                        const failed = [];

                        for (let i = 0; i < files.length; i += 1) {{
                            const file = files[i];
                            const taskId = await createTask('upload');
                            progress.setProgress(0);
                            progress.setStatus('Uploading (' + (i + 1) + '/' + files.length + '): ' + file.name);
                            progress.setResult('');

                            try {{
                                const uploadUrl = '/upload-raw?task_id=' + encodeURIComponent(taskId) +
                                    '&path=' + encodeURIComponent(currentPath) +
                                    '&filename=' + encodeURIComponent(file.name) +
                                    '&hash=' + (withHash ? '1' : '0');

                                await xhrUpload(uploadUrl, file, (loaded, total) => {{
                                    progress.setProgress((loaded / Math.max(total, 1)) * 100);
                                    progress.setStatus('Uploading (' + (i + 1) + '/' + files.length + '): ' + file.name);
                                }});

                                await waitForTaskCompletion(taskId, {{
                                    setProgress: (p) => progress.setProgress(p),
                                    setStatus: (msg) => progress.setStatus('Processing (' + (i + 1) + '/' + files.length + '): ' + file.name + (msg ? ' - ' + msg : '')),
                                    setSpeed: (msg) => progress.setSpeed(msg),
                                }});

                                successCount += 1;
                            }} catch (e) {{
                                failed.push(file.name + ': ' + e.message);
                            }}
                        }}

                        progress.setSpeed('');
                        progress.setProgress(100);
                        if (failed.length === 0) {{
                            progress.setStatus('Completed');
                            progress.setResult('Uploaded ' + successCount + ' file(s) successfully.');
                        }} else {{
                            progress.setStatus('Completed with errors');
                            const preview = failed.slice(0, 3).join(' | ');
                            const more = failed.length > 3 ? ' | +' + (failed.length - 3) + ' more error(s)' : '';
                            progress.setResult('Uploaded ' + successCount + '/' + files.length + ' file(s). ' + preview + more);
                        }}

                        await loadFolderContents(currentPath);
                        await loadFolderTree();
                    }}

                    function openMkdirDialog() {{
                        if (!ensureWriteEnabled()) return;
                        const ui = createDialogContainer('Create Folder', 'Location: ' + currentPath);

                        const input = document.createElement('input');
                        input.type = 'text';
                        input.placeholder = 'Folder name';
                        input.style.width = '100%';
                        input.style.height = '34px';
                        input.style.padding = '0 10px';
                        input.style.borderRadius = '8px';
                        input.style.border = '1px solid #3a3a3a';
                        input.style.background = '#0f0f0f';
                        input.style.color = '#ffffff';
                        ui.content.appendChild(input);

                        const actions = document.createElement('div');
                        actions.className = 'dialog-actions';
                        const cancelBtn = document.createElement('button');
                        cancelBtn.className = 'ghost-btn';
                        cancelBtn.textContent = 'Cancel';
                        cancelBtn.onclick = function() {{ ui.dialogDiv.remove(); }};
                        const createBtn = document.createElement('button');
                        createBtn.textContent = 'Create';
                        createBtn.onclick = async function() {{
                            const name = (input.value || '').trim();
                            if (!name) {{
                                showDialog('Enter a folder name.');
                                return;
                            }}
                            try {{
                                const res = await fetch('/mkdir', {{
                                    method: 'POST',
                                    headers: {{ 'Content-Type': 'application/json' }},
                                    body: JSON.stringify({{ path: currentPath, name }}),
                                }});
                                const data = await res.json();
                                if (!res.ok) throw new Error(data.error || 'Failed to create folder');
                                ui.dialogDiv.remove();
                                await loadFolderContents(currentPath);
                                await loadFolderTree();
                            }} catch (e) {{
                                showDialog(e.message);
                            }}
                        }};
                        actions.appendChild(cancelBtn);
                        actions.appendChild(createBtn);
                        ui.content.appendChild(actions);
                        input.focus();
                    }}

                    function flattenFolderTree(node, depth = 0, acc = []) {{
                        const children = node.children || [];
                        acc.push({{
                            path: node.path,
                            name: node.name,
                            depth,
                            hasChildren: children.length > 0,
                            fullPath: node.path,
                        }});
                        children.forEach(child => flattenFolderTree(child, depth + 1, acc));
                        return acc;
                    }}

                    async function openRenameDialog(itemPath, itemName) {{
                        if (!ensureWriteEnabled()) return;
                        const ui = createDialogContainer('Rename', 'From: ' + itemName);

                        const input = document.createElement('input');
                        input.type = 'text';
                        input.value = itemName;
                        input.style.width = '100%';
                        input.style.height = '34px';
                        input.style.padding = '0 10px';
                        input.style.borderRadius = '8px';
                        input.style.border = '1px solid #3a3a3a';
                        input.style.background = '#0f0f0f';
                        input.style.color = '#ffffff';
                        ui.content.appendChild(input);

                        const actions = document.createElement('div');
                        actions.className = 'dialog-actions';
                        const cancelBtn = document.createElement('button');
                        cancelBtn.className = 'ghost-btn';
                        cancelBtn.textContent = 'Cancel';
                        cancelBtn.onclick = function() {{ ui.dialogDiv.remove(); }};

                        const renameBtn = document.createElement('button');
                        renameBtn.textContent = 'Rename';
                        renameBtn.onclick = async function() {{
                            const newName = (input.value || '').trim();
                            if (!newName) {{
                                showDialog('Enter a new name.');
                                return;
                            }}
                            try {{
                                await postJson('/rename', {{ path: itemPath, new_name: newName }});
                                ui.dialogDiv.remove();
                                clearSelection();
                                await loadFolderContents(currentPath);
                                await loadFolderTree();
                                showToast('Renamed successfully');
                            }} catch (e) {{
                                showDialog(e.message);
                            }}
                        }};

                        actions.appendChild(cancelBtn);
                        actions.appendChild(renameBtn);
                        ui.content.appendChild(actions);
                        input.focus();
                        input.select();
                    }}

                    async function runBulkDelete(paths) {{
                        const taskId = await createTask('bulk-delete');
                        const progress = createProgressDialog('Deleting', paths.length + ' item(s)');
                        progress.setStatus('Deleting...');

                        try {{
                            const waitPromise = waitForTaskCompletion(taskId, progress);
                            const res = await postJson('/bulk-delete?task_id=' + encodeURIComponent(taskId), {{ paths }});
                            await waitPromise;
                            progress.setStatus('Completed');
                            progress.setProgress(100);
                            progress.setResult('Deleted ' + (res.deleted || paths.length) + ' item(s)');
                        }} catch (e) {{
                            progress.setStatus('Failed');
                            progress.setResult(e.message);
                            throw e;
                        }}
                    }}

                    async function openDeleteConfirmDialog(paths, titleText) {{
                        if (!ensureWriteEnabled()) return;
                        const list = Array.isArray(paths) ? paths : [paths];
                        const ui = createDialogContainer('Delete Permanently', titleText || (list.length + ' item(s) selected'));

                        const msg = document.createElement('p');
                        msg.textContent = list.length === 1
                            ? 'This will permanently delete the selected item.'
                            : 'This will permanently delete ' + list.length + ' selected items.';
                        ui.content.appendChild(msg);

                        const confirmLabel = document.createElement('label');
                        confirmLabel.style.display = 'flex';
                        confirmLabel.style.alignItems = 'center';
                        confirmLabel.style.gap = '8px';
                        confirmLabel.style.marginTop = '12px';
                        const confirmCheck = document.createElement('input');
                        confirmCheck.type = 'checkbox';
                        confirmLabel.appendChild(confirmCheck);
                        confirmLabel.appendChild(document.createTextNode('I understand this cannot be undone'));
                        ui.content.appendChild(confirmLabel);

                        const actions = document.createElement('div');
                        actions.className = 'dialog-actions';
                        const cancelBtn = document.createElement('button');
                        cancelBtn.className = 'ghost-btn';
                        cancelBtn.textContent = 'Cancel';
                        cancelBtn.onclick = function() {{ ui.dialogDiv.remove(); }};

                        const deleteBtn = document.createElement('button');
                        deleteBtn.textContent = 'Delete';
                        deleteBtn.onclick = async function() {{
                            if (!confirmCheck.checked) {{
                                showDialog('Please confirm permanent deletion.');
                                return;
                            }}
                            try {{
                                if (list.length === 1) {{
                                    await postJson('/delete', {{ path: list[0] }});
                                }} else {{
                                    await runBulkDelete(list);
                                }}
                                ui.dialogDiv.remove();
                                clearSelection();
                                await loadFolderContents(currentPath);
                                await loadFolderTree();
                                showToast('Deleted successfully');
                            }} catch (e) {{
                                showDialog(e.message);
                            }}
                        }};

                        actions.appendChild(cancelBtn);
                        actions.appendChild(deleteBtn);
                        ui.content.appendChild(actions);
                    }}

                    async function runBulkMove(paths, destinationPath) {{
                        const taskId = await createTask('bulk-move');
                        const progress = createProgressDialog('Moving', paths.length + ' item(s)');
                        progress.setStatus('Moving...');

                        try {{
                            const waitPromise = waitForTaskCompletion(taskId, progress);
                            const res = await postJson('/bulk-move?task_id=' + encodeURIComponent(taskId), {{
                                paths,
                                destination: destinationPath,
                            }});
                            await waitPromise;
                            progress.setStatus('Completed');
                            progress.setProgress(100);
                            progress.setResult('Moved ' + (res.moved || paths.length) + ' item(s)');
                        }} catch (e) {{
                            progress.setStatus('Failed');
                            progress.setResult(e.message);
                            throw e;
                        }}
                    }}

                    async function executeMove(paths, destinationPath) {{
                        if (paths.length === 1) {{
                            await postJson('/move', {{ path: paths[0], destination: destinationPath }});
                            return;
                        }}
                        await runBulkMove(paths, destinationPath);
                    }}

                    async function openMoveDialog(paths, titleText) {{
                        if (!ensureWriteEnabled()) return;
                        const list = Array.isArray(paths) ? paths : [paths];

                        let tree;
                        try {{
                            const res = await fetch('/folder-tree');
                            if (!res.ok) throw new Error('Failed to load folders');
                            tree = await res.json();
                        }} catch (e) {{
                            showDialog(e.message);
                            return;
                        }}

                        const ui = createDialogContainer('Move To Folder', titleText || (list.length + ' item(s) selected'));

                        const treeWrap = document.createElement('div');
                        treeWrap.className = 'move-tree';
                        ui.content.appendChild(treeWrap);

                        const targetHint = document.createElement('div');
                        targetHint.className = 'dialog-subtitle';
                        targetHint.style.marginTop = '10px';
                        targetHint.style.textAlign = 'left';

                        let selectedDestination = currentPath || tree.path;
                        let selectedRow = null;

                        const updateTargetHint = function(path) {{
                            if (!path) return;
                            selectedDestination = path;
                            targetHint.textContent = 'Target: ' + path;
                        }};

                        const isOpenByDefault = function(path) {{
                            return currentPath === path || currentPath.startsWith(path + '/');
                        }};

                        const renderMoveNode = function(node, depth, mountPoint) {{
                            const hasChildren = Array.isArray(node.children) && node.children.length > 0;

                            const row = document.createElement('div');
                            row.className = 'move-tree-item';
                            row.style.paddingLeft = (10 + (depth * 14)) + 'px';
                            row.dataset.path = node.path;
                            row.title = node.path;

                            const toggle = document.createElement('span');
                            toggle.className = 'move-tree-toggle';
                            toggle.textContent = hasChildren ? '>' : '-';
                            row.appendChild(toggle);

                            const label = document.createElement('span');
                            label.className = 'move-tree-label';
                            label.textContent = node.name + (hasChildren ? ' +' : '');
                            row.appendChild(label);

                            row.addEventListener('mouseenter', () => {{
                                targetHint.textContent = 'Target: ' + node.path;
                            }});

                            row.addEventListener('click', () => {{
                                if (selectedRow) selectedRow.classList.remove('selected');
                                selectedRow = row;
                                selectedRow.classList.add('selected');
                                updateTargetHint(node.path);
                            }});

                            mountPoint.appendChild(row);

                            const childWrap = document.createElement('div');
                            childWrap.className = 'move-tree-children';
                            mountPoint.appendChild(childWrap);

                            if (hasChildren) {{
                                if (isOpenByDefault(node.path)) {{
                                    childWrap.classList.add('open');
                                    toggle.textContent = 'v';
                                }}

                                toggle.addEventListener('click', (event) => {{
                                    event.stopPropagation();
                                    childWrap.classList.toggle('open');
                                    toggle.textContent = childWrap.classList.contains('open') ? 'v' : '>';
                                }});

                                node.children.forEach((child) => renderMoveNode(child, depth + 1, childWrap));
                            }}

                            if (node.path === selectedDestination) {{
                                row.classList.add('selected');
                                selectedRow = row;
                                updateTargetHint(node.path);
                            }}
                        }};

                        renderMoveNode(tree, 0, treeWrap);
                        updateTargetHint(selectedDestination);
                        ui.content.appendChild(targetHint);

                        const actions = document.createElement('div');
                        actions.className = 'dialog-actions';
                        const cancelBtn = document.createElement('button');
                        cancelBtn.className = 'ghost-btn';
                        cancelBtn.textContent = 'Cancel';
                        cancelBtn.onclick = function() {{ ui.dialogDiv.remove(); }};

                        const moveBtn = document.createElement('button');
                        moveBtn.textContent = 'Move';
                        moveBtn.onclick = async function() {{
                            const destinationPath = selectedDestination;
                            if (!destinationPath) {{
                                showDialog('Choose a destination folder.');
                                return;
                            }}
                            try {{
                                await executeMove(list, destinationPath);
                                ui.dialogDiv.remove();
                                clearSelection();
                                await loadFolderContents(currentPath);
                                await loadFolderTree();
                                showToast('Moved successfully');
                            }} catch (e) {{
                                showDialog(e.message);
                            }}
                        }};

                        actions.appendChild(cancelBtn);
                        actions.appendChild(moveBtn);
                        ui.content.appendChild(actions);
                    }}

                    function openDownloadDialog(filePath, fileName) {{
                        const ui = createDialogContainer('Download File', fileName);
                        const options = document.createElement('div');
                        options.className = 'dialog-row';
                        const hashLabel = document.createElement('label');
                        const hashCheck = document.createElement('input');
                        hashCheck.type = 'checkbox';
                        hashLabel.appendChild(hashCheck);
                        hashLabel.appendChild(document.createTextNode('Calculate SHA-256 while downloading'));
                        options.appendChild(hashLabel);
                        ui.content.appendChild(options);

                        const actions = document.createElement('div');
                        actions.className = 'dialog-actions';
                        const cancelBtn = document.createElement('button');
                        cancelBtn.className = 'ghost-btn';
                        cancelBtn.textContent = 'Cancel';
                        cancelBtn.onclick = function() {{ ui.dialogDiv.remove(); }};
                        const startBtn = document.createElement('button');
                        startBtn.textContent = 'Download';
                        startBtn.onclick = async function() {{
                            ui.dialogDiv.remove();
                            await startFileDownload(filePath, fileName, hashCheck.checked);
                        }};
                        actions.appendChild(cancelBtn);
                        actions.appendChild(startBtn);
                        ui.content.appendChild(actions);
                    }}

                    async function startFileDownload(filePath, fileName, withHash) {{
                        const taskId = await createTask('download');

                        const a = document.createElement('a');
                        a.href = '/download?path=' + encodeURIComponent(filePath) +
                            '&task_id=' + encodeURIComponent(taskId) +
                            '&hash=' + (withHash ? '1' : '0');
                        a.download = fileName;
                        document.body.appendChild(a);
                        a.click();
                        a.remove();

                        if (!withHash) return;

                        const progress = createProgressDialog('Downloading', fileName);
                        try {{
                            progress.setStatus('Downloading...');
                            const task = await waitForTaskCompletion(taskId, progress);
                            progress.setStatus('Completed');
                            progress.setProgress(100);
                            progress.setResult(task.hash_sha256 ? 'SHA-256: ' + task.hash_sha256 : 'Hash unavailable');
                        }} catch (e) {{
                            progress.setStatus('Failed');
                            progress.setResult(e.message);
                        }}
                    }}

                    async function startZipDownload(paths, archiveName) {{
                        const taskId = await createTask('zip');
                        const progress = createProgressDialog('Preparing ZIP', archiveName);
                        try {{
                            const blob = await xhrDownloadBlob(
                                '/zip-download?task_id=' + encodeURIComponent(taskId),
                                'POST',
                                JSON.stringify({{ paths: paths, archive_name: archiveName }}),
                                (loaded, total) => {{
                                    progress.setStatus('Downloading ZIP...');
                                    if (total > 0) progress.setProgress((loaded / total) * 100);
                                }}
                            );
                            saveBlob(blob, archiveName);
                            await waitForTaskCompletion(taskId, progress);
                            progress.setStatus('Completed');
                            progress.setProgress(100);
                            progress.setResult('ZIP download complete');
                        }} catch (e) {{
                            progress.setStatus('Failed');
                            progress.setResult(e.message);
                        }}
                    }}
                    
                    async function loadFolderTree() {{
                        try {{
                            const res = await fetch('/folder-tree');
                            const tree = await res.json();
                            const sidebar = document.getElementById('sidebar');
                            sidebar.innerHTML = '';
                            renderTree(tree, sidebar);
                        }} catch (e) {{
                            console.error('Error loading folder tree:', e);
                        }}
                    }}
                    
                    function renderTree(node, container, depth = 0) {{
                        const div = document.createElement('div');
                        div.className = 'tree-item folder';
                        div.style.marginLeft = (depth * 15) + 'px';
                        
                        let html = '<span class="tree-toggle">+ </span>';
                        html += '📁 ' + node.name;
                        
                        div.innerHTML = html;
                        div.dataset.path = node.path;
                        
                        const toggle = div.querySelector('.tree-toggle');
                        const childrenDiv = document.createElement('div');
                        childrenDiv.className = 'tree-children';
                        
                        if (node.children.length === 0) {{
                            toggle.style.visibility = 'hidden';
                        }}
                        
                        toggle.addEventListener('click', (e) => {{
                            e.stopPropagation();
                            childrenDiv.classList.toggle('open');
                            toggle.textContent = childrenDiv.classList.contains('open') ? '- ' : '+ ';
                        }});
                        
                        div.addEventListener('click', () => {{
                            loadFolderContents(node.path);
                            updateBreadcrumb(node.path);
                            closeMobileSidebar();
                        }});

                        if (uploadsEnabled) {{
                            div.addEventListener('dragover', (e) => {{
                                if (!isInternalMoveDrag(e)) return;
                                e.preventDefault();
                                e.dataTransfer.dropEffect = 'move';
                                div.classList.add('drop-target');
                            }});

                            div.addEventListener('dragleave', () => {{
                                div.classList.remove('drop-target');
                            }});

                            div.addEventListener('drop', async (e) => {{
                                if (!isInternalMoveDrag(e)) return;
                                e.preventDefault();
                                div.classList.remove('drop-target');
                                const paths = getDraggedInternalPaths(e);
                                if (paths.length === 0) return;
                                try {{
                                    await executeMove(paths, node.path);
                                    clearSelection();
                                    await loadFolderContents(currentPath);
                                    await loadFolderTree();
                                    showToast('Moved successfully');
                                }} catch (err) {{
                                    showDialog(err.message);
                                }}
                            }});
                        }}
                        
                        node.children.forEach(child => {{
                            renderTree(child, childrenDiv, depth + 1);
                        }});
                        
                        container.appendChild(div);
                        container.appendChild(childrenDiv);
                    }}
                    
                    async function loadFolderContents(path) {{
                        currentPath = path;
                        try {{
                            const res = await fetch('/files-metadata?path=' + encodeURIComponent(path));
                            if (!res.ok) throw new Error('Failed to open folder');
                            const items = await res.json();
                            currentFolderItems = Array.isArray(items) ? items : [];
                            applySearchFilter();
                        }} catch (e) {{
                            console.error('Error loading folder contents:', e);
                        }}
                    }}

                    function applySearchFilter() {{
                        const query = (searchInput?.value || '').trim().toLowerCase();
                        searchQuery = query;
                        selectedItems.clear();

                        if (!query) {{
                            renderTable(currentFolderItems);
                            return;
                        }}

                        const filtered = currentFolderItems.filter(item => {{
                            const name = String(item.name || '').toLowerCase();
                            const path = String(item.path || '').toLowerCase();
                            return name.includes(query) || path.includes(query);
                        }});
                        renderTable(filtered);
                    }}

                    function toggleSearchBar(forceOpen = null) {{
                        const shouldOpen = forceOpen === null ? !searchWrap.classList.contains('show') : !!forceOpen;
                        searchWrap.classList.toggle('show', shouldOpen);

                        if (shouldOpen) {{
                            searchInput.focus();
                            searchInput.select();
                            return;
                        }}

                        searchInput.value = '';
                        searchQuery = '';
                        applySearchFilter();
                    }}
                    
                    function renderTable(items) {{
                        const tbody = document.getElementById('file-table');
                        tbody.innerHTML = '';
                        itemMap = new Map();
                        imageFilesInCurrentFolder = items
                            .filter(item => !item.is_dir && (!!item.is_image || isImageFilename(item.name)))
                            .map(item => ({{ path: item.path, name: item.name }}));
                        videoFilesInCurrentFolder = items
                            .filter(item => !item.is_dir && (!!item.is_video || isVideoFilename(item.name)))
                            .map(item => ({{ path: item.path, name: item.name }}));
                        audioFilesInCurrentFolder = items
                            .filter(item => !item.is_dir && (!!item.is_audio || isAudioFilename(item.name)))
                            .map(item => ({{ path: item.path, name: item.name }}));
                        
                        items.forEach(item => {{
                            itemMap.set(item.path, item);
                            const row = document.createElement('tr');
                            const ext = item.name.substring(item.name.lastIndexOf('.')).toLowerCase();
                            const isTextFile = !!item.is_text;
                            const isImageFile = !!item.is_image || isImageFilename(item.name);
                            const isVideoFile = !!item.is_video || isVideoFilename(item.name);
                            const isAudioFile = !!item.is_audio || isAudioFilename(item.name);
                            const isPdfFile = !!item.is_pdf || isPdfFilename(item.name);
                            
                            let filename = item.name;
                            if (item.is_dir) filename += '/';
                            
                            let sizeStr = '';
                            if (!item.is_dir) {{
                                sizeStr = formatSize(item.size);
                            }}
                            
                            let typeStr = item.is_dir ? 'Folder' : ext || 'File';
                            
                            // Checkbox cell
                            const checkboxCell = document.createElement('td');
                            checkboxCell.className = 'col-select';
                            checkboxCell.dataset.label = 'Select';
                            const checkbox = document.createElement('input');
                            checkbox.type = 'checkbox';
                            checkbox.className = 'row-checkbox';
                            checkbox.dataset.path = item.path;
                            checkbox.addEventListener('change', updateBulkActions);
                            checkboxCell.appendChild(checkbox);
                            row.appendChild(checkboxCell);
                            
                            // Filename cell
                            const filenameCell = document.createElement('td');
                            filenameCell.className = 'filename col-name';
                            filenameCell.dataset.label = 'Name';
                            filenameCell.textContent = filename;
                            filenameCell.dataset.path = item.path;
                            filenameCell.dataset.isdir = item.is_dir;
                            if (item.is_dir) row.classList.add('folder-row');
                            row.appendChild(filenameCell);
                            
                            const sizeCell = document.createElement('td');
                            sizeCell.className = 'col-size';
                            sizeCell.dataset.label = 'Size';
                            sizeCell.textContent = sizeStr;
                            row.appendChild(sizeCell);
                            
                            const typeCell = document.createElement('td');
                            typeCell.className = 'col-type';
                            typeCell.dataset.label = 'Type';
                            typeCell.textContent = typeStr;
                            row.appendChild(typeCell);
                            
                            const dateCell = document.createElement('td');
                            dateCell.className = 'col-date';
                            dateCell.dataset.label = 'Date';
                            dateCell.textContent = item.date;
                            row.appendChild(dateCell);
                            
                            const actionCell = document.createElement('td');
                            actionCell.className = 'col-action';
                            actionCell.dataset.label = 'Actions';
                            const actionSlot = document.createElement('div');
                            actionSlot.className = 'action-slot';
                            
                            if (downloadsEnabled) {{
                                if (item.is_dir) {{
                                    const zipBtn = document.createElement('button');
                                    zipBtn.className = 'action-btn zip';
                                    zipBtn.textContent = 'ZIP';
                                    zipBtn.dataset.path = item.path;
                                    zipBtn.dataset.name = item.name;
                                    actionSlot.appendChild(zipBtn);
                                }} else {{
                                    const downloadBtn = document.createElement('button');
                                    downloadBtn.className = 'action-btn download';
                                    downloadBtn.textContent = 'DOWNLOAD';
                                    downloadBtn.dataset.file = item.path;
                                    downloadBtn.dataset.name = item.name;
                                    actionSlot.appendChild(downloadBtn);

                                    if (isTextFile) {{
                                        const viewBtn = document.createElement('button');
                                        viewBtn.className = 'action-btn view';
                                        viewBtn.textContent = 'VIEW';
                                        viewBtn.dataset.file = item.path;
                                        viewBtn.dataset.name = item.name;
                                        actionSlot.appendChild(viewBtn);
                                    }}

                                    if (isImageFile) {{
                                        const imageViewBtn = document.createElement('button');
                                        imageViewBtn.className = 'action-btn image-view';
                                        imageViewBtn.textContent = 'VIEW';
                                        imageViewBtn.dataset.file = item.path;
                                        imageViewBtn.dataset.name = item.name;
                                        actionSlot.appendChild(imageViewBtn);
                                    }}

                                    if (isVideoFile) {{
                                        const videoPlayBtn = document.createElement('button');
                                        videoPlayBtn.className = 'action-btn video-play';
                                        videoPlayBtn.textContent = 'PLAY';
                                        videoPlayBtn.dataset.file = item.path;
                                        videoPlayBtn.dataset.name = item.name;
                                        actionSlot.appendChild(videoPlayBtn);
                                    }}

                                    if (isAudioFile) {{
                                        const audioPlayBtn = document.createElement('button');
                                        audioPlayBtn.className = 'action-btn audio-play';
                                        audioPlayBtn.textContent = 'PLAY';
                                        audioPlayBtn.dataset.file = item.path;
                                        audioPlayBtn.dataset.name = item.name;
                                        actionSlot.appendChild(audioPlayBtn);
                                    }}

                                    if (isPdfFile) {{
                                        const pdfViewBtn = document.createElement('button');
                                        pdfViewBtn.className = 'action-btn pdf-view';
                                        pdfViewBtn.textContent = 'VIEW';
                                        pdfViewBtn.dataset.file = item.path;
                                        pdfViewBtn.dataset.name = item.name;
                                        actionSlot.appendChild(pdfViewBtn);
                                    }}
                                }}
                            }}

                            if (uploadsEnabled) {{
                                const renameBtn = document.createElement('button');
                                renameBtn.className = 'action-btn manage-action rename';
                                renameBtn.textContent = 'RENAME';
                                renameBtn.dataset.path = item.path;
                                renameBtn.dataset.name = item.name;
                                actionSlot.appendChild(renameBtn);
                            }}
                            
                            actionCell.appendChild(actionSlot);
                            row.appendChild(actionCell);

                            if (uploadsEnabled) {{
                                row.draggable = true;
                                row.addEventListener('dragstart', (e) => {{
                                    const dragPaths = getSelectedOrSinglePaths(item.path);
                                    e.dataTransfer.setData(INTERNAL_MOVE_MIME, JSON.stringify(dragPaths));
                                    e.dataTransfer.effectAllowed = 'move';
                                }});

                                row.addEventListener('dragend', () => {{
                                    document.querySelectorAll('.drop-target').forEach(el => el.classList.remove('drop-target'));
                                }});
                            }}

                            if (item.is_dir) {{
                                row.addEventListener('click', function(e) {{
                                    if (e.target.closest('button') || e.target.closest('input')) return;
                                    loadFolderContents(item.path);
                                    updateBreadcrumb(item.path);
                                }});

                                if (uploadsEnabled) {{
                                    row.addEventListener('dragover', (e) => {{
                                        if (!isInternalMoveDrag(e)) return;
                                        e.preventDefault();
                                        e.dataTransfer.dropEffect = 'move';
                                        row.classList.add('drop-target');
                                    }});

                                    row.addEventListener('dragleave', () => {{
                                        row.classList.remove('drop-target');
                                    }});

                                    row.addEventListener('drop', async (e) => {{
                                        if (!isInternalMoveDrag(e)) return;
                                        e.preventDefault();
                                        row.classList.remove('drop-target');
                                        const dragPaths = getDraggedInternalPaths(e);
                                        if (dragPaths.length === 0) return;
                                        try {{
                                            await executeMove(dragPaths, item.path);
                                            clearSelection();
                                            await loadFolderContents(currentPath);
                                            await loadFolderTree();
                                            showToast('Moved successfully');
                                        }} catch (err) {{
                                            showDialog(err.message);
                                        }}
                                    }});
                                }}
                            }}

                            tbody.appendChild(row);
                        }});

                        if (items.length === 0) {{
                            const emptyRow = document.createElement('tr');
                            const emptyCell = document.createElement('td');
                            emptyCell.colSpan = 6;
                            emptyCell.style.padding = '18px 12px';
                            emptyCell.style.color = '#a0a0a0';
                            emptyCell.textContent = searchQuery
                                ? 'No results for "' + searchQuery + '" in this folder.'
                                : 'No files found in this folder.';
                            emptyRow.appendChild(emptyCell);
                            tbody.appendChild(emptyRow);
                        }}
                        
                        // Attach event listeners
                        document.querySelectorAll('.filename').forEach(el => {{
                            el.addEventListener('click', function() {{
                                const path = this.dataset.path;
                                const isDir = this.dataset.isdir === 'true' || this.dataset.isdir === true;
                                if (isDir && path) {{
                                    loadFolderContents(path);
                                    updateBreadcrumb(path);
                                    closeMobileSidebar();
                                }}
                            }});
                        }});
                        
                        document.querySelectorAll('.view').forEach(el => {{
                            el.addEventListener('click', function() {{
                                const filePath = this.dataset.file;
                                const fileName = this.dataset.name;
                                viewFile(filePath, fileName);
                            }});
                        }});

                        document.querySelectorAll('.image-view').forEach(el => {{
                            el.addEventListener('click', function() {{
                                const filePath = this.dataset.file;
                                const fileName = this.dataset.name;
                                openImageViewer(filePath, fileName);
                            }});
                        }});

                        document.querySelectorAll('.video-play').forEach(el => {{
                            el.addEventListener('click', function() {{
                                const filePath = this.dataset.file;
                                const fileName = this.dataset.name;
                                openVideoPlayer(filePath, fileName);
                            }});
                        }});

                        document.querySelectorAll('.audio-play').forEach(el => {{
                            el.addEventListener('click', function() {{
                                const filePath = this.dataset.file;
                                const fileName = this.dataset.name;
                                openAudioPlayer(filePath, fileName);
                            }});
                        }});

                        document.querySelectorAll('.pdf-view').forEach(el => {{
                            el.addEventListener('click', function() {{
                                const filePath = this.dataset.file;
                                const fileName = this.dataset.name;
                                openPdfViewer(filePath, fileName);
                            }});
                        }});
                        
                        document.querySelectorAll('.zip').forEach(el => {{
                            el.addEventListener('click', function() {{
                                const folderPath = this.dataset.path;
                                const folderName = this.dataset.name;
                                startZipDownload([folderPath], folderName + '.zip');
                            }});
                        }});

                        document.querySelectorAll('.download').forEach(el => {{
                            el.addEventListener('click', function() {{
                                openDownloadDialog(this.dataset.file, this.dataset.name);
                            }});
                        }});

                        document.querySelectorAll('.rename').forEach(el => {{
                            el.addEventListener('click', function() {{
                                openRenameDialog(this.dataset.path, this.dataset.name);
                            }});
                        }});
                    }}
                    
                    function formatSize(bytes) {{
                        if (bytes === 0) return '0 B';
                        const k = 1024;
                        const sizes = ['B', 'KB', 'MB', 'GB'];
                        const i = Math.floor(Math.log(bytes) / Math.log(k));
                        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
                    }}

                    function isImageFilename(name) {{
                        return /\\.(jpg|jpeg|png)$/i.test(name || '');
                    }}

                    function isVideoFilename(name) {{
                        return /\\.(mp4|webm|ogg)$/i.test(name || '');
                    }}

                    function isAudioFilename(name) {{
                        return /\\.(mp3|wav|ogg|aac)$/i.test(name || '');
                    }}

                    function isPdfFilename(name) {{
                        return /\\.pdf$/i.test(name || '');
                    }}

                    function isWordFilename(name) {{
                        return /\\.docx$/i.test(name || '');
                    }}

                    function isSheetFilename(name) {{
                        return /\\.(xlsx|xls|csv)$/i.test(name || '');
                    }}

                    function closeFileViewer() {{
                        modal.classList.remove('show');
                        modalBody.textContent = '';
                        modalBody.innerHTML = '';
                    }}

                    function openModalWithTitle(title) {{
                        modalTitle.textContent = title;
                        modalBody.textContent = '';
                        modalBody.innerHTML = '';
                        modal.classList.add('show');
                    }}

                    function openPdfViewer(filePath, fileName) {{
                        if (!downloadsEnabled) return;
                        openModalWithTitle('PDF Viewer - ' + fileName);
                        const frame = document.createElement('iframe');
                        frame.className = 'doc-preview-frame';
                        frame.src = '/pdf?path=' + encodeURIComponent(filePath);
                        frame.setAttribute('title', 'PDF preview');
                        modalBody.appendChild(frame);
                    }}

                    async function openWordViewer(filePath, fileName) {{
                        if (!downloadsEnabled) return;
                        openModalWithTitle('Word Viewer - ' + fileName);

                        try {{
                            const res = await fetch('/docx?path=' + encodeURIComponent(filePath));
                            if (!res.ok) throw new Error('Preview unavailable');
                            const blob = await res.blob();
                            const sizeText = formatSize(blob.size || 0);

                            const message = document.createElement('div');
                            message.className = 'doc-preview-message';
                            message.textContent = 'Document stream is ready (' + sizeText + '). Rich DOCX rendering will be enabled in the next implementation step.';
                            modalBody.appendChild(message);

                            const actions = document.createElement('div');
                            actions.className = 'doc-preview-actions';
                            const downloadBtn = document.createElement('button');
                            downloadBtn.className = 'action-btn';
                            downloadBtn.textContent = 'DOWNLOAD';
                            downloadBtn.addEventListener('click', function() {{
                                openDownloadDialog(filePath, fileName);
                            }});
                            actions.appendChild(downloadBtn);
                            modalBody.appendChild(actions);
                        }} catch (e) {{
                            showDialog('Error loading document: ' + e.message);
                            closeFileViewer();
                        }}
                    }}

                    function parseCsvLine(line) {{
                        const out = [];
                        let current = '';
                        let inQuotes = false;

                        for (let i = 0; i < line.length; i += 1) {{
                            const ch = line[i];
                            if (ch === '"') {{
                                if (inQuotes && line[i + 1] === '"') {{
                                    current += '"';
                                    i += 1;
                                }} else {{
                                    inQuotes = !inQuotes;
                                }}
                            }} else if (ch === ',' && !inQuotes) {{
                                out.push(current);
                                current = '';
                            }} else {{
                                current += ch;
                            }}
                        }}
                        out.push(current);
                        return out;
                    }}

                    function renderCsvPreview(csvText) {{
                        const lines = (csvText || '').split(/\\r?\\n/).filter(Boolean).slice(0, 200);
                        if (!lines.length) {{
                            modalBody.textContent = 'Empty CSV file.';
                            return;
                        }}

                        const rows = lines.map(parseCsvLine);
                        const maxCols = Math.min(20, Math.max(...rows.map(r => r.length), 0));
                        const table = document.createElement('table');
                        table.className = 'sheet-preview-table';

                        const thead = document.createElement('thead');
                        const headRow = document.createElement('tr');
                        for (let i = 0; i < maxCols; i += 1) {{
                            const th = document.createElement('th');
                            th.textContent = 'Col ' + (i + 1);
                            headRow.appendChild(th);
                        }}
                        thead.appendChild(headRow);
                        table.appendChild(thead);

                        const tbody = document.createElement('tbody');
                        rows.forEach(row => {{
                            const tr = document.createElement('tr');
                            for (let i = 0; i < maxCols; i += 1) {{
                                const td = document.createElement('td');
                                td.textContent = row[i] || '';
                                tr.appendChild(td);
                            }}
                            tbody.appendChild(tr);
                        }});

                        table.appendChild(tbody);
                        modalBody.appendChild(table);
                    }}

                    async function openSheetViewer(filePath, fileName) {{
                        if (!downloadsEnabled) return;
                        openModalWithTitle('Sheet Viewer - ' + fileName);

                        try {{
                            const res = await fetch('/sheet?path=' + encodeURIComponent(filePath));
                            if (!res.ok) throw new Error('Preview unavailable');

                            const contentType = (res.headers.get('Content-Type') || '').toLowerCase();
                            if (contentType.includes('csv') || /\\.csv$/i.test(fileName || '')) {{
                                const csvText = await res.text();
                                renderCsvPreview(csvText);
                                return;
                            }}

                            const blob = await res.blob();
                            const message = document.createElement('div');
                            message.className = 'doc-preview-message';
                            message.textContent = 'Spreadsheet stream is ready (' + formatSize(blob.size || 0) + '). XLSX/XLS grid rendering will be enabled in the next implementation step.';
                            modalBody.appendChild(message);

                            const actions = document.createElement('div');
                            actions.className = 'doc-preview-actions';
                            const downloadBtn = document.createElement('button');
                            downloadBtn.className = 'action-btn';
                            downloadBtn.textContent = 'DOWNLOAD';
                            downloadBtn.addEventListener('click', function() {{
                                openDownloadDialog(filePath, fileName);
                            }});
                            actions.appendChild(downloadBtn);
                            modalBody.appendChild(actions);
                        }} catch (e) {{
                            showDialog('Error loading sheet: ' + e.message);
                            closeFileViewer();
                        }}
                    }}

                    function closeImageViewer() {{
                        imageModal.classList.remove('show');
                        imagePreview.removeAttribute('src');
                        activeImageIndex = -1;
                    }}

                    function renderActiveImage() {{
                        if (activeImageIndex < 0 || activeImageIndex >= imageFilesInCurrentFolder.length) return;
                        const active = imageFilesInCurrentFolder[activeImageIndex];
                        imageModalTitle.textContent = '🖼 ' + active.name;
                        imageCounter.textContent = (activeImageIndex + 1) + ' / ' + imageFilesInCurrentFolder.length;
                        imagePreview.src = '/image?path=' + encodeURIComponent(active.path);
                        imagePrevBtn.disabled = activeImageIndex === 0;
                        imageNextBtn.disabled = activeImageIndex === imageFilesInCurrentFolder.length - 1;
                    }}

                    function openImageViewer(filePath, fileName) {{
                        if (!downloadsEnabled) return;
                        if (!imageFilesInCurrentFolder.length) {{
                            showDialog('No images found in this folder.');
                            return;
                        }}

                        const index = imageFilesInCurrentFolder.findIndex(file => file.path === filePath);
                        if (index >= 0) {{
                            activeImageIndex = index;
                        }} else {{
                            imageFilesInCurrentFolder.push({{ path: filePath, name: fileName }});
                            activeImageIndex = imageFilesInCurrentFolder.length - 1;
                        }}

                        renderActiveImage();
                        imageModal.classList.add('show');
                    }}

                    function navigateImage(delta) {{
                        if (!imageModal.classList.contains('show')) return;
                        const nextIndex = activeImageIndex + delta;
                        if (nextIndex < 0 || nextIndex >= imageFilesInCurrentFolder.length) return;
                        activeImageIndex = nextIndex;
                        renderActiveImage();
                    }}

                    function closeVideoPlayer() {{
                        videoModal.classList.remove('show');
                        videoPreview.pause();
                        videoPreview.removeAttribute('src');
                        videoPreview.load();
                        activeVideoIndex = -1;
                    }}

                    function renderActiveVideo() {{
                        if (activeVideoIndex < 0 || activeVideoIndex >= videoFilesInCurrentFolder.length) return;
                        const active = videoFilesInCurrentFolder[activeVideoIndex];
                        videoModalTitle.textContent = '▶ ' + active.name;
                        videoCounter.textContent = (activeVideoIndex + 1) + ' / ' + videoFilesInCurrentFolder.length;
                        videoPreview.src = '/video?path=' + encodeURIComponent(active.path);
                        videoPrevBtn.disabled = activeVideoIndex === 0;
                        videoNextBtn.disabled = activeVideoIndex === videoFilesInCurrentFolder.length - 1;
                    }}

                    function openVideoPlayer(filePath, fileName) {{
                        if (!downloadsEnabled) return;
                        if (!videoFilesInCurrentFolder.length) {{
                            showDialog('No videos found in this folder.');
                            return;
                        }}

                        const index = videoFilesInCurrentFolder.findIndex(file => file.path === filePath);
                        if (index >= 0) {{
                            activeVideoIndex = index;
                        }} else {{
                            videoFilesInCurrentFolder.push({{ path: filePath, name: fileName }});
                            activeVideoIndex = videoFilesInCurrentFolder.length - 1;
                        }}

                        renderActiveVideo();
                        videoModal.classList.add('show');
                    }}

                    function navigateVideo(delta) {{
                        if (!videoModal.classList.contains('show')) return;
                        const nextIndex = activeVideoIndex + delta;
                        if (nextIndex < 0 || nextIndex >= videoFilesInCurrentFolder.length) return;
                        activeVideoIndex = nextIndex;
                        renderActiveVideo();
                    }}

                    function closeAudioPlayer() {{
                        audioModal.classList.remove('show');
                        audioPreview.pause();
                        audioPreview.removeAttribute('src');
                        audioPreview.load();
                        activeAudioIndex = -1;
                    }}

                    function renderActiveAudio() {{
                        if (activeAudioIndex < 0 || activeAudioIndex >= audioFilesInCurrentFolder.length) return;
                        const active = audioFilesInCurrentFolder[activeAudioIndex];
                        audioModalTitle.textContent = '♪ ' + active.name;
                        audioCounter.textContent = (activeAudioIndex + 1) + ' / ' + audioFilesInCurrentFolder.length;
                        audioPreview.src = '/audio?path=' + encodeURIComponent(active.path);
                        audioPrevBtn.disabled = activeAudioIndex === 0;
                        audioNextBtn.disabled = activeAudioIndex === audioFilesInCurrentFolder.length - 1;
                    }}

                    function openAudioPlayer(filePath, fileName) {{
                        if (!downloadsEnabled) return;
                        if (!audioFilesInCurrentFolder.length) {{
                            showDialog('No audio files found in this folder.');
                            return;
                        }}

                        const index = audioFilesInCurrentFolder.findIndex(file => file.path === filePath);
                        if (index >= 0) {{
                            activeAudioIndex = index;
                        }} else {{
                            audioFilesInCurrentFolder.push({{ path: filePath, name: fileName }});
                            activeAudioIndex = audioFilesInCurrentFolder.length - 1;
                        }}

                        renderActiveAudio();
                        audioModal.classList.add('show');
                    }}

                    function navigateAudio(delta) {{
                        if (!audioModal.classList.contains('show')) return;
                        const nextIndex = activeAudioIndex + delta;
                        if (nextIndex < 0 || nextIndex >= audioFilesInCurrentFolder.length) return;
                        activeAudioIndex = nextIndex;
                        renderActiveAudio();
                    }}
                    
                    async function viewFile(filePath, fileName) {{
                        try {{
                            const res = await fetch('/view?path=' + encodeURIComponent(filePath));
                            if (!res.ok) {{
                                const msg = await res.text();
                                throw new Error(msg || 'Preview unavailable');
                            }}
                            const content = await res.text();
                            modalTitle.textContent = '📄 ' + fileName;
                            modalBody.textContent = content;
                            modal.classList.add('show');
                        }} catch (e) {{
                            showDialog('Error loading file: ' + e.message);
                        }}
                    }}
                    
                    function updateBulkActions() {{
                        selectedItems.clear();
                        document.querySelectorAll('.row-checkbox:checked').forEach(checkbox => {{
                            selectedItems.add(checkbox.dataset.path);
                        }});
                        
                        const bulkActionsDiv = document.getElementById('bulk-actions');
                        if (selectedItems.size > 0 && downloadsEnabled) {{
                            bulkActionsDiv.classList.add('show');
                        }} else {{
                            bulkActionsDiv.classList.remove('show');
                        }}

                        const bulkManagementDiv = document.getElementById('bulk-management');
                        if (selectedItems.size > 0 && uploadsEnabled && manageMode) {{
                            bulkManagementDiv.classList.add('show');
                        }} else {{
                            bulkManagementDiv.classList.remove('show');
                        }}
                    }}
                    
                    document.getElementById('bulk-zip').addEventListener('click', function() {{
                        if (selectedItems.size === 0) return;
                        const selected = Array.from(selectedItems);
                        if (selected.length === 1) {{
                            const one = itemMap.get(selected[0]);
                            if (one) {{
                                const rawName = one.name || 'archive';
                                const baseName = one.is_dir ? rawName : (rawName.replace(/\\.[^/.]+$/, '') || rawName);
                                startZipDownload(selected, baseName + '.zip');
                                return;
                            }}
                        }}
                        startZipDownload(selected, 'selected-items.zip');
                    }});
                    
                    document.getElementById('bulk-download').addEventListener('click', async function() {{
                        if (selectedItems.size === 0) return;
                        const selected = Array.from(selectedItems);
                        if (selected.length === 1) {{
                            const one = itemMap.get(selected[0]);
                            if (one && !one.is_dir) {{
                                openDownloadDialog(one.path, one.name);
                                return;
                            }}
                            if (one) {{
                                const rawName = one.name || 'archive';
                                const baseName = one.is_dir ? rawName : (rawName.replace(/\\.[^/.]+$/, '') || rawName);
                                startZipDownload(selected, baseName + '.zip');
                                return;
                            }}
                        }}
                        startZipDownload(selected, 'bulk-download.zip');
                    }});

                    document.getElementById('upload-btn').addEventListener('click', function() {{
                        openUploadDialog();
                    }});

                    document.getElementById('mkdir-btn').addEventListener('click', function() {{
                        openMkdirDialog();
                    }});

                    document.getElementById('manage-btn').addEventListener('click', function() {{
                        if (!uploadsEnabled) return;
                        setManageMode(!manageMode);
                    }});

                    searchToggleBtn.addEventListener('click', function() {{
                        toggleSearchBar();
                    }});

                    searchClearBtn.addEventListener('click', function() {{
                        searchInput.value = '';
                        searchQuery = '';
                        applySearchFilter();
                        searchInput.focus();
                    }});

                    searchInput.addEventListener('input', function() {{
                        applySearchFilter();
                    }});

                    searchInput.addEventListener('keydown', function(e) {{
                        if (e.key !== 'Escape') return;
                        e.preventDefault();
                        toggleSearchBar(false);
                    }});

                    document.getElementById('bulk-delete').addEventListener('click', function() {{
                        if (selectedItems.size === 0) return;
                        const paths = Array.from(selectedItems);
                        openDeleteConfirmDialog(paths, paths.length + ' item(s) selected');
                    }});

                    document.getElementById('bulk-move').addEventListener('click', function() {{
                        if (selectedItems.size === 0) return;
                        const paths = Array.from(selectedItems);
                        openMoveDialog(paths, paths.length + ' item(s) selected');
                    }});

                    document.getElementById('file-close-btn').addEventListener('click', function() {{
                        closeFileViewer();
                    }});

                    modal.addEventListener('click', function(e) {{
                        if (e.target === modal) closeFileViewer();
                    }});

                    imagePrevBtn.addEventListener('click', function() {{
                        navigateImage(-1);
                    }});

                    imageNextBtn.addEventListener('click', function() {{
                        navigateImage(1);
                    }});

                    document.getElementById('image-close-btn').addEventListener('click', function() {{
                        closeImageViewer();
                    }});

                    imageModal.addEventListener('click', function(e) {{
                        if (e.target === imageModal) closeImageViewer();
                    }});

                    videoPrevBtn.addEventListener('click', function() {{
                        navigateVideo(-1);
                    }});

                    videoNextBtn.addEventListener('click', function() {{
                        navigateVideo(1);
                    }});

                    document.getElementById('video-close-btn').addEventListener('click', function() {{
                        closeVideoPlayer();
                    }});

                    videoModal.addEventListener('click', function(e) {{
                        if (e.target === videoModal) closeVideoPlayer();
                    }});

                    audioPrevBtn.addEventListener('click', function() {{
                        navigateAudio(-1);
                    }});

                    audioNextBtn.addEventListener('click', function() {{
                        navigateAudio(1);
                    }});

                    document.getElementById('audio-close-btn').addEventListener('click', function() {{
                        closeAudioPlayer();
                    }});

                    audioModal.addEventListener('click', function(e) {{
                        if (e.target === audioModal) closeAudioPlayer();
                    }});

                    document.addEventListener('keydown', function(e) {{
                        if (imageModal.classList.contains('show')) {{
                            if (e.key === 'ArrowLeft') {{
                                e.preventDefault();
                                navigateImage(-1);
                            }} else if (e.key === 'ArrowRight') {{
                                e.preventDefault();
                                navigateImage(1);
                            }} else if (e.key === 'Escape') {{
                                e.preventDefault();
                                closeImageViewer();
                            }}
                            return;
                        }}
                        if (videoModal.classList.contains('show')) {{
                            if (e.key === 'ArrowLeft') {{
                                e.preventDefault();
                                navigateVideo(-1);
                            }} else if (e.key === 'ArrowRight') {{
                                e.preventDefault();
                                navigateVideo(1);
                            }} else if (e.key === 'Escape') {{
                                e.preventDefault();
                                closeVideoPlayer();
                            }}
                            return;
                        }}
                        if (modal.classList.contains('show') && e.key === 'Escape') {{
                            e.preventDefault();
                            closeFileViewer();
                            return;
                        }}
                        if (!audioModal.classList.contains('show')) return;
                        if (e.key === 'ArrowLeft') {{
                            e.preventDefault();
                            navigateAudio(-1);
                        }} else if (e.key === 'ArrowRight') {{
                            e.preventDefault();
                            navigateAudio(1);
                        }} else if (e.key === 'Escape') {{
                            e.preventDefault();
                            closeAudioPlayer();
                        }}
                    }});
                    
                    function updateBreadcrumb(path) {{
                        // Remove the base upload folder path to get relative parts
                        const basePath = path.replace(/\\\\/g, '/');
                        const parts = basePath.split('/').filter(p => p && p !== 'shared_files');
                        
                        const breadcrumbDiv = document.getElementById('breadcrumb');
                        breadcrumbDiv.innerHTML = '';
                        
                        // Root button
                        const rootBtn = document.createElement('button');
                        rootBtn.textContent = '🌲';
                        rootBtn.addEventListener('click', function() {{
                            loadFolderContents('{UPLOAD_FOLDER}');
                            updateBreadcrumb('{UPLOAD_FOLDER}');
                        }});
                        breadcrumbDiv.appendChild(rootBtn);
                        
                        let currentPath = '{UPLOAD_FOLDER}';
                        parts.forEach((part) => {{
                            const sep = document.createElement('span');
                            sep.textContent = ' / ';
                            breadcrumbDiv.appendChild(sep);
                            
                            currentPath = currentPath + '/' + part;
                            const btn = document.createElement('button');
                            btn.textContent = part;
                            btn.addEventListener('click', (function(path) {{
                                return function() {{
                                    loadFolderContents(path);
                                    updateBreadcrumb(path);
                                }};
                            }})(currentPath));
                            breadcrumbDiv.appendChild(btn);
                        }});
                    }}
                    
                    // Sidebar toggle
                    document.getElementById('sidebar-toggle').addEventListener('click', () => {{
                        const sidebar = document.getElementById('sidebar');
                        const mainContent = document.querySelector('.main-content');
                        if (isMobileViewport()) {{
                            sidebar.classList.remove('hidden');
                            mainContent.classList.add('fullwidth');
                            sidebar.classList.toggle('mobile-open');
                            if (sidebarBackdrop) {{
                                sidebarBackdrop.classList.toggle('show', sidebar.classList.contains('mobile-open'));
                            }}
                            updateSidebarToggleIcon();
                            return;
                        }}

                        sidebar.classList.toggle('hidden');
                        mainContent.classList.toggle('fullwidth');
                        updateSidebarToggleIcon();
                    }});

                    if (sidebarBackdrop) {{
                        sidebarBackdrop.addEventListener('click', () => {{
                            closeMobileSidebar();
                        }});
                    }}

                    window.addEventListener('resize', () => {{
                        applyResponsiveLayout(false);
                    }});

                    document.addEventListener('dragenter', (e) => {{
                        if (!uploadsEnabled) return;
                        if (!isExternalFilesDrag(e)) return;
                        e.preventDefault();
                        dragCounter += 1;
                        dropOverlay.classList.add('show');
                    }});

                    document.addEventListener('dragover', (e) => {{
                        if (!uploadsEnabled) return;
                        if (!isExternalFilesDrag(e)) return;
                        e.preventDefault();
                    }});

                    document.addEventListener('dragleave', (e) => {{
                        if (!uploadsEnabled) return;
                        if (!isExternalFilesDrag(e)) return;
                        e.preventDefault();
                        dragCounter = Math.max(0, dragCounter - 1);
                        if (dragCounter === 0) dropOverlay.classList.remove('show');
                    }});

                    document.addEventListener('drop', async (e) => {{
                        if (!uploadsEnabled) return;
                        if (!isExternalFilesDrag(e)) return;
                        e.preventDefault();
                        dragCounter = 0;
                        dropOverlay.classList.remove('show');
                        if (!ensureWriteEnabled()) return;
                        const files = Array.from(e.dataTransfer?.files || []);
                        if (files.length === 0) return;
                        await uploadFilesBatch(files, false);
                    }});

                    if (!uploadsEnabled) {{
                        const uploadBtn = document.getElementById('upload-btn');
                        const mkdirBtn = document.getElementById('mkdir-btn');
                        const manageBtn = document.getElementById('manage-btn');
                        const bulkManagement = document.getElementById('bulk-management');
                        uploadBtn.style.display = 'none';
                        mkdirBtn.style.display = 'none';
                        manageBtn.style.display = 'none';
                        bulkManagement.style.display = 'none';
                    }}

                    if (!downloadsEnabled) {{
                        const bulkActions = document.getElementById('bulk-actions');
                        bulkActions.style.display = 'none';
                    }}

                    if (uploadsEnabled) {{
                        setManageMode(false);
                    }}
                    
                    applyResponsiveLayout(true);

                    // Load on page load
                    if (document.readyState === 'loading') {{
                        window.addEventListener('load', () => {{
                            loadFolderTree();
                            loadFolderContents('{UPLOAD_FOLDER}');
                            updateBreadcrumb('{UPLOAD_FOLDER}');
                        }});
                    }} else {{
                        // DOMContentLoaded already fired
                        loadFolderTree();
                        loadFolderContents('{UPLOAD_FOLDER}');
                        updateBreadcrumb('{UPLOAD_FOLDER}');
                    }}
                </script>
            </body>
            </html>
            """
