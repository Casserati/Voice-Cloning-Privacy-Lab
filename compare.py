"""Compare two voice recordings with SpeechBrain (ECAPA-TDNN, trained on VoxCeleb).

Usage:   python compare.py original.wav clone.wav [threshold]
Example: python compare.py original.wav clone.wav 0.5
Tip:     convert MP3 files first:  ffmpeg -i clone.mp3 -ac 1 -ar 16000 clone.wav
"""
import sys

from speechbrain.inference.speaker import SpeakerRecognition
from speechbrain.utils.fetching import LocalStrategy

THRESHOLD = 0.25  # SpeechBrain's default threshold for this model


def main():
    if len(sys.argv) not in (3, 4):
        print("Usage: python compare.py <reference.wav> <test.wav> [threshold]")
        sys.exit(1)
    reference, test = sys.argv[1], sys.argv[2]
    threshold = float(sys.argv[3]) if len(sys.argv) == 4 else THRESHOLD

    # Downloads the model once into the "model" folder.
    # COPY avoids the symlink error on Windows.
    model = SpeakerRecognition.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir="model",
        local_strategy=LocalStrategy.COPY,
    )

    score, _ = model.verify_files(reference, test)
    score = float(score)
    accepted = score >= threshold

    print(f"Reference:   {reference}")
    print(f"Test:        {test}")
    print(f"Score:       {score:.2f}   (threshold {threshold})")
    print(f"Similarity:  {score * 100:.0f} %")
    print("Decision:   ", "ACCEPTED - same person" if accepted else "REJECTED - different person")


if __name__ == "__main__":
    main()
