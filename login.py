"""Voice login: checks WHAT was said (speech recognition) and WHO said it (SpeechBrain).

Usage:
    python login.py <reference.wav> <test.wav> "<passphrase>" [voice_threshold] [--asr medium|swiss]

Examples:
    python login.py lorena_echt.wav lorena_klon.wav "Meine Stimme ist mein Passwort"
    python login.py lorena_echt.wav lorena_klon.wav "Meine Stimme ist mein Passwort" 0.35 --asr swiss

Speech recognition engines (--asr):
    medium  Whisper "medium" via faster-whisper (default, faster)
    swiss   Flix-AI/flix-swissgerman-full, a Whisper large-v3 fine-tuned on Swiss German
            (needs: python -m pip install transformers accelerate; slow on CPU)

Both engines output Standard German text. Every attempt is appended to access_log.csv.
"""
import argparse
import csv
import os
import re
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher

import soundfile as sf
import torch
import torchaudio
from speechbrain.inference.speaker import SpeakerRecognition
from speechbrain.utils.fetching import LocalStrategy

VOICE_THRESHOLD = 0.25  # SpeechBrain default; pass a different value as 4th argument
TEXT_THRESHOLD = 0.85   # how closely the spoken text must match the passphrase (0..1)
LOG_FILE = "access_log.csv"
SWISS_MODEL = "Flix-AI/flix-swissgerman-full"

UMLAUTS = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}


def normalize(text):
    """Make texts comparable: lowercase, umlauts -> ae/oe/ue, ß -> ss,
    accents removed (é -> e), punctuation and extra spaces removed."""
    text = unicodedata.normalize("NFC", text.lower())  # unify how ä etc. are encoded
    for char, replacement in UMLAUTS.items():
        text = text.replace(char, replacement)
    text = unicodedata.normalize("NFKD", text)          # split é into e + accent
    text = "".join(c for c in text if not unicodedata.combining(c))  # drop accents
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return " ".join(text.split())


def load_16k_mono(path):
    """Read the WAV file as 16 kHz mono (avoids PyAV version conflicts)."""
    data, sample_rate = sf.read(path, dtype="float32", always_2d=True)
    audio = torch.from_numpy(data.mean(axis=1))
    if sample_rate != 16000:
        audio = torchaudio.functional.resample(audio, sample_rate, 16000)
    return audio.numpy()


def transcribe_medium(audio):
    from faster_whisper import WhisperModel
    model = WhisperModel("medium", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio, language="de")
    return " ".join(segment.text for segment in segments).strip()


def transcribe_swiss(audio):
    from transformers import WhisperForConditionalGeneration, WhisperProcessor
    processor = WhisperProcessor.from_pretrained(SWISS_MODEL)
    model = WhisperForConditionalGeneration.from_pretrained(SWISS_MODEL, low_cpu_mem_usage=True)
    model.eval()
    features = processor(audio, sampling_rate=16000, return_tensors="pt").input_features
    with torch.no_grad():
        ids = model.generate(features, language="de", task="transcribe")
    return processor.batch_decode(ids, skip_special_tokens=True)[0].strip()


def voice_score(reference, test):
    model = SpeakerRecognition.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir="model",
        local_strategy=LocalStrategy.COPY,
    )
    score, _ = model.verify_files(reference, test)
    return float(score)


def write_log(row):
    new_file = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        if new_file:
            writer.writerow(["timestamp", "reference", "test", "passphrase", "asr_engine",
                             "recognized_text", "text_similarity", "voice_score",
                             "voice_threshold", "result"])
        writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="Voice login with passphrase check")
    parser.add_argument("reference", help="reference recording of the real person (WAV)")
    parser.add_argument("test", help="recording to check (WAV)")
    parser.add_argument("passphrase", help="expected passphrase in Standard German")
    parser.add_argument("threshold", nargs="?", type=float, default=VOICE_THRESHOLD,
                        help=f"voice threshold (default {VOICE_THRESHOLD})")
    parser.add_argument("--asr", choices=["medium", "swiss"], default="medium",
                        help="speech recognition engine (default: medium)")
    args = parser.parse_args()

    # 1) WHAT was said?
    print(f"Recognizing speech with engine '{args.asr}' ...")
    audio = load_16k_mono(args.test)
    recognized = transcribe_swiss(audio) if args.asr == "swiss" else transcribe_medium(audio)
    text_similarity = SequenceMatcher(None, normalize(recognized), normalize(args.passphrase)).ratio()
    text_ok = text_similarity >= TEXT_THRESHOLD

    # 2) WHO said it?
    print("Checking voice ...")
    score = voice_score(args.reference, args.test)
    voice_ok = score >= args.threshold

    granted = text_ok and voice_ok

    print()
    print(f"Passphrase:       {args.passphrase}")
    print(f"Recognized text:  {recognized}   [{args.asr}]")
    print(f"Text match:       {text_similarity * 100:.0f} %  ->", "OK" if text_ok else "WRONG")
    print(f"Voice score:      {score:.2f} (threshold {args.threshold})  ->", "OK" if voice_ok else "WRONG")
    print("RESULT:          ", "ACCESS GRANTED" if granted else "ACCESS DENIED")

    try:
        write_log([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), args.reference, args.test,
            args.passphrase, args.asr, recognized, f"{text_similarity:.2f}", f"{score:.2f}",
            args.threshold, "GRANTED" if granted else "DENIED",
        ])
    except PermissionError:
        print(f"\nWARNING: could not write to {LOG_FILE}. It is probably open in Excel.")
        print("Close it and run this attempt again, otherwise it is missing from the log.")


if __name__ == "__main__":
    main()
