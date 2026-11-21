#!/bin/bash
# Restore the pod's AI equipment after a recycle. Idempotent: safe to re-run.
#
# The libraries are ~hundreds of MB; the MODEL WEIGHTS (~5 GB) are NOT installed
# here -- they download on first use, so nothing big lives only in the pod:
#   stabilityai/sd-turbo         (ai_scene / gen_scenes)
#   facebook/musicgen-small      (ai_music / mg.py)
#   RealESRGAN_x4plus.pth        (upscale.py, fetched to /tmp by ai_scene)
set -e
python3 -m pip install --quiet --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
python3 -m pip install --quiet --no-cache-dir \
  diffusers spandrel transformers accelerate safetensors scipy soundfile edge-tts
echo "restored: torch(cpu)/diffusers/spandrel/transformers/accelerate/edge-tts"
echo "models download on first run: stabilityai/sd-turbo, facebook/musicgen-small, RealESRGAN_x4plus.pth"
