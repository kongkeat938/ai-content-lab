#!/usr/bin/env bash
# Rebuild the OpenVoice tone converter after a pod recycle.
#
# The pod is recycled about 20 minutes after the session goes idle and nothing in
# it survives, so /workspace/OpenVoice and work/k_voice/k_se.pth vanish. This
# script puts them back. It needs ~1.5 GB of disk and about 3 minutes.
#
#   bash scripts/setup_openvoice.sh            # install the converter
#   bash scripts/setup_openvoice.sh --se FILE  # also extract K's embedding
#
# Thai works here because OpenVoice is a tone converter, not a text-to-speech
# clone: it repaints a waveform, so it never sees Thai phonemes. Every
# Thai-capable cloning model needs a GPU; this pod has none.
set -u

OV_DIR="${OPENVOICE_DIR:-/workspace/OpenVoice}"
HF=https://huggingface.co/myshell-ai/OpenVoiceV2/resolve/main
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== python deps (torch CPU, then the text/audio extras)"
pip install --quiet torch torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install --quiet librosa soundfile inflect unidecode pypinyin eng_to_ipa jieba cn2an wavmark

if [ ! -d "$OV_DIR" ]; then
  echo "== clone OpenVoice"
  git clone --depth 1 https://github.com/myshell-ai/OpenVoice.git "$OV_DIR"
fi

echo "== checkpoints (the old S3 bucket is gone; HuggingFace is the live copy)"
mkdir -p "$OV_DIR/checkpoints_v2/converter" "$OV_DIR/checkpoints_v2/base_speakers/ses"
curl -fsSL -o "$OV_DIR/checkpoints_v2/converter/config.json" "$HF/converter/config.json"
curl -fsSL -o "$OV_DIR/checkpoints_v2/converter/checkpoint.pth" "$HF/converter/checkpoint.pth"
for lang in en-newest en-us kr jp zh es fr; do
  curl -fsSL -o "$OV_DIR/checkpoints_v2/base_speakers/ses/$lang.pth" "$HF/base_speakers/ses/$lang.pth"
done

echo "== verify it loads"
python3 - "$OV_DIR" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from openvoice.api import ToneColorConverter
c = ToneColorConverter(f"{sys.argv[1]}/checkpoints_v2/converter/config.json", device="cpu")
c.load_ckpt(f"{sys.argv[1]}/checkpoints_v2/converter/checkpoint.pth")
print(f"converter ready, sample rate {c.hps.data.sampling_rate}")
PY

if [ "${1:-}" = "--se" ] && [ -n "${2:-}" ]; then
  echo "== K's speaker embedding from $2"
  python3 "$REPO_ROOT/scripts/tts_ktone.py" --build-se "$2"
fi

echo "done. narrate with: python3 scripts/tts_ktone.py --text '...' --out /tmp/a.mp3"
