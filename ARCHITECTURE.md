# Video Tutor - System Architecture

This document outlines the high-level architecture, component interactions, and codebase structure of the Video Tutor application.

## High-Level Architecture Diagram

```mermaid
graph TD
    subgraph Client [Frontend (Browser)]
        UI[User Interface]
        UploadPage[Upload / YouTube Input]
        WatchInterface[Watch & Chat Interface]
        QuizUI[Quiz UI]
        
        UI --> UploadPage
        UI --> WatchInterface
        WatchInterface --> QuizUI
    end

    subgraph Server [Backend (Flask Framework)]
        App[app.py - Routing & Auth]
        Models[models.py - DB Schema]
        Processing[processing.py - BG Tasks]
        RAG[rag.py - AI Logic]
        Utils[utils.py - Helpers]
        
        UploadPage -- "POST /upload" --> App
        WatchInterface -- "POST /video/<id>/qa" --> App
        QuizUI -- "GET /video/<id>/quiz" --> App
    end

    subgraph Data & External Services
        DB[(PostgreSQL/Supabase DB)]
        Storage[(Supabase Storage)]
        Gemini[Google Gemini API]
        YouTube[YouTube (yt-dlp)]
    end

    App <--> Models
    Models <--> DB
    App -- "Save File" --> Utils
    Utils -- "Upload/Download" --> Storage
    Utils -- "Download Video" --> YouTube
    App -- "Trigger" --> Processing
    Processing -- "Upload to Gemini" --> Gemini
    App <--> RAG
    RAG -- "Generate Content & Quizzes" --> Gemini
```

## Component Breakdown

### 1. The Frontend (Client)
The frontend is built using standard HTML, CSS (Tailwind via CDN for rapid styling), and Vanilla JavaScript. It communicates with the backend via RESTful APIs and standard form submissions.
*   **Templates (`frontend/templates/`):** Contains the Jinja2 templates (`base.html`, `index.html`, `login.html`, `watch.html`) that are rendered by Flask.
*   **Static Assets (`frontend/static/`):** Contains custom CSS, JavaScript logic for the chat and quiz interfaces, and images.

### 2. The Backend Engine (Flask)
The core logic resides in a Python Flask application.
*   **`backend/app.py`:** The entry point. It defines all the web routes, handles user authentication (Flask-Login), manages sessions, and orchestrates the flow of data between the frontend and background processes.
*   **`backend/models.py`:** Defines the SQLAlchemy ORM models. Currently, we have `User` (for authentication) and `Video` (for metadata, storage links, and processing status).
*   **`backend/extensions.py`:** Initializes the `db` (SQLAlchemy) and `login_manager` objects to avoid circular imports.

### 3. Asynchronous Processing Pipeline
Processing a video with Gemini takes time, so it must be done asynchronously so the web UI doesn't freeze.
*   **`backend/processing.py`:** Contains the `process_video` function. When a user uploads a video, `app.py` spawns a new Python Thread running this function. It handles downloading the file from storage, uploading it to the Gemini API, waiting for Gemini to finish processing, and extracting the initial transcript/summary.

### 4. Artificial Intelligence Integration
*   **`backend/rag.py`:** The "brain" of the app. It connects to the `google-genai` SDK.
    *   **`ask_question()`:** Takes the user's prompt and the stored Gemini File URI to perform multimodal Q&A.
    *   **`generate_quiz()`:** Prompts Gemini to generate a structured JSON output of multiple-choice questions based on the specific video context.
*   **`backend/utils.py`:** Contains `generate_with_retry`, a crucial wrapper around Gemini API calls that handles `429 Rate Limit` errors by implementing exponential backoff.

### 5. Storage and Database
*   **Relational Database (PostgreSQL via Supabase):** Stores user credentials securely, video metadata, and tracks the processing `status` of videos.
*   **Object Storage (Supabase Storage):** Acts as an S3-compatible bucket. Hosted videos are stored here to keep the server lightweight. `utils.py` handles the generation of presigned URLs so the frontend HTML5 video player can load the videos securely.

## Code Flow Example: Uploading a YouTube Video
1.  User enters a link on the UI and submits.
2.  `app.py` intercepts the request. It uses `utils.download_youtube_video` (which utilizes `yt-dlp` using mobile spoofing) to grab the `.mp4`.
3.  The file is pushed to **Supabase Storage**.
4.  A new `Video` record is created in **PostgreSQL** with a `status` of `"pending"`.
5.  A background thread calls `process_video` in `processing.py`.
6.  The UI redirects the user to the dashboard, showing the video as "Processing".
7.  The background thread retrieves the file from Supabase, pushes it to the **Gemini API** via the Generative File API, and asks for a transcript.
8.  Once complete, the database `status` updates to `"completed"`.
9.  The user clicks on the video, taking them to the Watch interface where they can now chat with the video via `rag.py`.
