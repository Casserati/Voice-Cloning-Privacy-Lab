# Voice Biometrics Lab – Speaker Verification vs. Voice Cloning

Group project for the module **Privacy & Technology (HSLU, HS26)**.
Topic: *Spracherkennung & Voice Cloning – Stimmbiometrie als Authentifizierung und ihre Angreifbarkeit.*

This repository contains a small, local voice login system and the scripts we use to attack it.
The goal is to show how well (or how badly) voice biometrics protects an account when an attacker
can record or clone the victim's voice.

> **Scenario:** A bank's telephone hotline authenticates customers by their voice and a spoken
> passphrase. We build a simplified version of such a system and test it against replay attacks
> and AI-generated voice clones.

---

## Contents

- [How it works](#how-it-works)
- [Repository structure](#repository-structure)
- [Requirements](#requirements)
- [Setup (Windows)](#setup-windows)
- [Preparing audio files](#preparing-audio-files)
- [Usage](#usage)
- [Thresholds](#thresholds)
- [Speech recognition engines](#speech-recognition-engines)
- [Log file](#log-file)
- [Experiment plan](#experiment-plan)
- [Troubleshooting](#troubleshooting)
- [Ethics and privacy](#ethics-and-privacy)
- [Credits](#credits)

---

## How it works

A login attempt passes two independent checks. Access is only granted if **both** succeed.

| Check | Question | Tool |
|---|---|---|
| Passphrase | *What* was said? | Whisper (speech-to-text) |
| Voice | *Who* said it? | SpeechBrain ECAPA-TDNN (speaker verification) |

**Voice check.** SpeechBrain turns each recording into a "voice fingerprint" (a speaker embedding)
and compares the fingerprint of the test recording with the one of a reference recording of the
real person. The result is a similarity score. If the score is at or above the voice threshold,
the voice is accepted. The model is text-independent: it only checks voice characteristics,
not the words.

**Passphrase check.** Whisper converts the test recording into text. Both the recognized text and
the expected passphrase are normalized (lowercase, umlauts → ae/oe/ue, ß → ss, accents and
punctuation removed) and compared letter by letter. If they match to at least 85 %, the
passphrase is accepted.

**What the system does *not* check:** whether a live human is speaking. A replayed recording or a
good AI clone looks the same to the system as the real person. Demonstrating this weakness is the
point of the lab.

```
recording ──► Whisper ──────► text ──► compare with passphrase ──┐
    │                                                            ├──► GRANTED / DENIED ──► access_log.csv
    └───────► SpeechBrain ──► score ──► compare with threshold ──┘
                   ▲
       reference recording (enrollment)
```

---

## Repository structure

```
.
├── compare.py          # voice check only: compares two recordings
├── login.py            # full login: passphrase check + voice check + logging
├── requirements.txt    # Python packages
├── .gitignore          # keeps recordings, models and logs out of Git
└── README.md
```

Recordings, downloaded models and the log file are created locally and are **not** part of the
repository (see [Ethics and privacy](#ethics-and-privacy)).

---

## Requirements

- Windows, macOS or Linux (tested on Windows 11)
- Python **3.11 or 3.12**
- [ffmpeg](https://ffmpeg.org/) for converting audio files
- About 6 GB free disk space for the models
- 16 GB RAM recommended if you use the Swiss German model

No graphics card is needed. Everything runs on the CPU.

---

## Setup (Windows)

Run these commands in the **Command Prompt (cmd)** inside the project folder.

1. Check which Python versions are installed:
   ```
   py -0
   ```
   If neither 3.11 nor 3.12 is listed, install one, e.g. `winget install Python.Python.3.12`,
   then open a new terminal.

2. Install ffmpeg (once):
   ```
   winget install ffmpeg
   ```

3. Create and activate a virtual environment:
   ```
   py -3.12 -m venv .venv
   .venv\Scripts\activate
   ```
   The prompt should now start with `(.venv)`. Activate the environment again in every new
   terminal window.

4. Install the packages:
   ```
   python -m pip install -r requirements.txt
   ```

On the first run, the models are downloaded automatically from Hugging Face:

| Model | Size | Used for |
|---|---|---|
| `speechbrain/spkrec-ecapa-voxceleb` | ~80 MB | voice check |
| Whisper `medium` (faster-whisper) | ~1.5 GB | passphrase check (default) |
| `Flix-AI/flix-swissgerman-full` | ~3 GB | passphrase check, Swiss German (optional) |

---

## Preparing audio files

The scripts expect **WAV** files. Convert other formats (e.g. MP3 from a cloning tool, or a
WhatsApp voice message) with ffmpeg:

```
ffmpeg -i input.mp3 -ac 1 -ar 16000 output.wav
```

This produces mono audio at 16 kHz, which works best for both models.

Recommended naming scheme, so results stay traceable:

```
<person>_real_<n>.wav          e.g. anna_real_1.wav, anna_real_2.wav
<person>_clone_<length>.wav    e.g. anna_clone_30s.wav, anna_clone_5min.wav
<person>_replay_<n>.wav        e.g. anna_replay_1.wav
```

**Important:** use a reference recording that was **not** uploaded to the cloning tool. Comparing
a clone with its own training audio makes the clone look better than it really is.

---

## Usage

### Voice check only – `compare.py`

```
python compare.py <reference.wav> <test.wav> [threshold]
```

Example:

```
python compare.py anna_real_1.wav anna_clone_30s.wav 0.35
```

Output:

```
Reference:   anna_real_1.wav
Test:        anna_clone_30s.wav
Score:       0.52   (threshold 0.35)
Similarity:  52 %
Decision:    ACCEPTED - same person
```

### Full login – `login.py`

```
python login.py <reference.wav> <test.wav> "<passphrase>" [voice_threshold] [--asr medium|swiss]
```

Examples:

```
python login.py anna_real_1.wav anna_clone_30s.wav "Meine Stimme ist mein Passwort"
python login.py anna_real_1.wav anna_clone_30s.wav "Meine Stimme ist mein Passwort" 0.35 --asr swiss
```

Output:

```
Passphrase:       Meine Stimme ist mein Passwort
Recognized text:  Meine Stimme ist mein Passwort.   [medium]
Text match:       100 %  -> OK
Voice score:      0.52 (threshold 0.35)  -> OK
RESULT:           ACCESS GRANTED
```

Put the passphrase in quotes, because it contains spaces. Write it in **Standard German**, even if
it is spoken in Swiss German (see [Speech recognition engines](#speech-recognition-engines)).

---

## Thresholds

### Voice threshold (default 0.25)

The score is a **similarity**, not a probability. A similarity of 52 % does *not* mean "52 % chance
it is the same person". Unrelated voices typically score around 0, while recordings of the same
person on clean audio usually score clearly higher.

The default of 0.25 is SpeechBrain's standard value for this model, roughly the point where false
acceptances and false rejections are equally frequent on the VoxCeleb benchmark. A real operator
chooses the threshold based on risk. For our experiments we test three levels:

| Level | Target false acceptance rate | Threshold |
|---|---|---|
| Default | about 1 in 100 | 0.25 |
| "Standard bank" (NIST SP 800-63-3) | 1 in 1,000 | ~0.35 |
| "Strict bank" (NIST SP 800-63-4) | 1 in 10,000 | ~0.45 |

The values 0.35 and 0.45 are **our own literature-based estimates**, not published figures. With
only a few group members we cannot measure such low error rates ourselves.

Pass a different threshold as an argument, or change `VOICE_THRESHOLD` / `THRESHOLD` at the top of
the scripts.

### Text threshold (default 0.85)

Set by `TEXT_THRESHOLD` in `login.py`. The recognized text must match the passphrase to at least
85 % after normalization. This tolerates small recognition errors but rejects different
sentences:

| Spoken | Match | Result |
|---|---|---|
| "Meine Stimme ist mein Passwort." | 100 % | OK |
| "Meine Stimme ist dein Passwort!" | 97 % | OK |
| "Ich hätte gern eine Pizza" | 25 % | WRONG |

A higher value is stricter but rejects real users more often when Whisper mishears a word.

---

## Speech recognition engines

| Engine | Flag | Model | Speed on CPU |
|---|---|---|---|
| Whisper medium | `--asr medium` (default) | `medium` via faster-whisper | a few seconds per clip |
| Swiss German | `--asr swiss` | `Flix-AI/flix-swissgerman-full` (Whisper large-v3 fine-tuned on Swiss German) | ~30 s or more per clip |

**Both engines output Standard German.** Swiss German has no standardized spelling, so speech
recognition for Swiss German always transcribes *and* translates in one step. As a consequence:

- The passphrase must be stored in Standard German.
- The translation can vary (word order, tense), which lowers the text match even if the right
  sentence was spoken.
- Choose a short passphrase that translates almost word for word, e.g.
  *"Mini Stimm isch mis Passwort"* → *"Meine Stimme ist mein Passwort"*.
- Avoid past tense and numbers (Whisper writes "3" or "drei" inconsistently).

The Swiss German model needs about 6–7 GB of RAM while running. Close large programs before using
it.

---

## Log file

Every attempt of `login.py` is appended to `access_log.csv` (semicolon-separated):

| Column | Content |
|---|---|
| `timestamp` | date and time of the attempt |
| `reference` / `test` | file names used |
| `passphrase` | expected passphrase |
| `asr_engine` | `medium` or `swiss` |
| `recognized_text` | what the speech recognition understood |
| `text_similarity` | text match (0–1) |
| `voice_score` | SpeechBrain similarity score |
| `voice_threshold` | threshold used |
| `result` | `GRANTED` or `DENIED` |

Don't keep the file open in Excel while running tests. Windows locks it and the attempt is not
logged. To view it during testing, use `type access_log.csv` or Notepad.

---

## Experiment plan

| Phase | Test | Expected outcome |
|---|---|---|
| 1. Normal operation | Real person vs. own reference; other members vs. reference | Real person accepted, others rejected (baseline) |
| 2. Replay | Recording of the passphrase played back via smartphone | Accepted – the system has no liveness check |
| 3. Voice cloning | Clones trained on 30 s, 1 min, 2 min, 5 min, 10 min of audio; 5 clips per length | How much audio does an attacker need? |
| 4. Countermeasure | Random challenge sentence instead of a fixed passphrase | Replay fails; a clone can still generate the new sentence |
| 5. Listening test | Classmates guess which recordings are real | Does the clone fool humans as well as the machine? |

Each clone is tested at the three voice thresholds (0.25 / 0.35 / 0.45).

To keep results comparable:

- Cut all training lengths from the **same** recording session, so audio length is the only
  variable.
- Use the same microphone, room and passphrase for all tests.
- Keep the cloning tool's settings (speed, stability, similarity) identical for all clones.
- Note tool, plan, model version and date for every clone.

---

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `No suitable Python runtime found` | Requested Python version not installed | Run `py -0`, use an installed version (3.11/3.12) or install one |
| `ModuleNotFoundError: No module named 'speechbrain'` | Environment not active or packages missing | `.venv\Scripts\activate`, then `python -m pip install -r requirements.txt` |
| Warnings about symlinks / `HF_TOKEN` | Windows does not allow symlinks without admin rights; no Hugging Face account | Harmless, can be ignored. Hide with `set HF_HUB_DISABLE_SYMLINKS_WARNING=1` |
| Error about symlinks when loading SpeechBrain | Same cause | Already handled in the scripts (`LocalStrategy.COPY`) |
| `PermissionError: ... access_log.csv` | Log file is open in Excel or being synced by OneDrive | Close Excel, wait a few seconds, repeat the attempt |
| Wrong transcription of Swiss German | Whisper translates dialect into Standard German | Use a simple passphrase, try `--asr swiss` |
| Very slow with `--asr swiss` | Large model on CPU | Expected. Use `medium` for bulk tests, `swiss` for comparisons |

---

## Ethics and privacy

Voice recordings are **biometric data** and count as particularly sensitive personal data under
the Swiss revDSG and the EU GDPR (Art. 9). A voice cannot be changed like a password once it has
leaked. For this project we follow these rules:

- **Consent:** we only clone voices of group members who have explicitly agreed.
- **No real systems:** all attacks run against our own local prototype, never against real bank
  or company systems.
- **No recordings in Git:** `.gitignore` excludes all audio files, models and logs. Recordings are
  stored only in our private group folder.
- **Third-party providers:** uploading voice samples to a web cloning tool hands biometric data to
  that provider. We document which tool was used and delete all cloned voices, recordings and
  accounts after the project.

---

## Credits

- [SpeechBrain](https://speechbrain.github.io/) – speaker verification model
  `speechbrain/spkrec-ecapa-voxceleb` (ECAPA-TDNN trained on VoxCeleb)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) – efficient implementation of
  OpenAI Whisper
- [Flix-AI/flix-swissgerman-full](https://huggingface.co/Flix-AI/flix-swissgerman-full) – Whisper
  large-v3 fine-tuned for Swiss German (Apache 2.0)
- Web-based voice cloning tools used for the attacks (e.g. Cartesia, ElevenLabs)

Parts of the code were created with the help of AI tools (declared in the project documentation).

**Team:** _add names here_
