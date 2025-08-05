sudo apt-get update &&  apt install portaudio19-dev libsox-dev ffmpeg
pip install -e .
huggingface-cli download fishaudio/openaudio-s1-mini --local-dir checkpoints/openaudio-s1-mini