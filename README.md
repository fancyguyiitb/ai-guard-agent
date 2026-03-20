# AI Room Guard System

Python security assistant that activates by voice, watches a room through a webcam, and escalates alerts when unknown faces are repeatedly detected.

## What Is Implemented

- Voice activation with `SpeechRecognition` + Whisper (`openai-whisper`)
- Face recognition against locally stored embeddings (`data/embeddings.pkl`)
- 3-stage spoken escalation flow via `pyttsx3`
- Stage 3 evidence capture (snapshot) + SMTP email alert with attachment
- Trusted-person override that terminates active escalation and returns to monitoring flow
- Event logging to console and `data/logs/events.log`

## Current Runtime Flow

1. System starts in `OFF`.
2. ASR loop listens for activation phrases:
   - `guard my room`
   - `guard the room`
   - `guard this room`
   - `start guard`
   - `start guarding`
   - `guarding my room`
3. On activation, state switches to `GUARD`; webcam recognition loop starts.
4. If an unknown face is detected 2+ times within 4 seconds, escalation starts.
5. Escalation timeline:
   - Stage 1 message, then wait
   - Stage 2 message, then wait
   - Stage 3 message, snapshot capture, email notification, then reset to `OFF`
6. If a trusted person appears during escalation, escalation is terminated early.

Notes:
- `INTERACT` and `ALARM` states exist in `src/state_manager.py` but are not used by the current main flow.
- Face checks run at approximately 1-second intervals in the recognition loop.

## Repository Layout

```text
ai-guard-agent/
├── src/
│   ├── main.py
│   ├── asr_worker.py
│   ├── face_recog.py
│   ├── tts.py
│   ├── email_notifier.py
│   ├── snapshot_capture.py
│   ├── state_manager.py
│   └── utils/
│       ├── config.py
│       └── logger.py
├── scripts/
│   ├── enroll_face.py
│   └── test_activation_from_file.py
├── data/
│   └── embeddings.pkl
├── requirements.txt
├── .gitignore
└── README.md
```

## Setup

### 1) Create environment

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2) Configure email (optional but recommended)

Create `.env` in repo root:

```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your-email@example.com
SENDER_PASSWORD=your-app-password
RECIPIENT_EMAILS=you@example.com,team@example.com
```

If email is not configured, Stage 3 still runs, but sending the alert email may fail.

### 3) Enroll trusted faces

```powershell
python scripts/enroll_face.py --name "Your Name" --count 30
```

This captures images and appends embeddings into `data/embeddings.pkl`.

## Run

```powershell
# Full flow (voice activation -> guard mode)
python src/main.py

# Skip ASR and enter guard mode directly
python src/main.py --direct-guard

# Camera verification only
python src/main.py --camera-test
```

## Configuration Surface

Runtime constants live in `src/utils/config.py`, including:
- ASR model and phrase window (`WHISPER_MODEL`, `PHRASE_TIME_LIMIT`)
- activation phrase list
- face match threshold (`FACE_MATCH_THRESHOLD`)
- webcam index (`WEBCAM_INDEX`)
- default enrollment image count

Email credentials and recipients are read from `.env` by `src/email_notifier.py`.

## Testing In This Repo

There is no formal `tests/` suite in the current repository. Available checks are:

- `python src/main.py --camera-test`
- `python src/main.py --direct-guard`
- `python scripts/test_activation_from_file.py <path-to-audio-file>`

## Resume-Friendly Project Summary

If you want to describe this project on a resume:

- Built a real-time room monitoring agent in Python using Whisper ASR, OpenCV/face-recognition, and pyttsx3.
- Implemented an escalation pipeline (multi-stage spoken alerts, snapshot evidence capture, SMTP notifications).
- Added trusted-identity override logic, local embedding management, and persistent event logging.
