import requests
import ormsgpack
import json
import hashlib
import time
from pathlib import Path
from pydub import AudioSegment
from pydub.playback import play
from concurrent.futures import ThreadPoolExecutor, as_completed

def format_time(seconds: float) -> str:
    secs = int(seconds)
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

# ===== 用户配置 =====
# 本地 20 个服务端地址，端口从 8080 到 8099
SERVERS = [f"127.0.0.1:{port}" for port in range(8080, 8080 + 40)]

API_KEY = "YOUR_API_KEY"
INPUT_JSON_PATH = "beavertails_critiques_aug.json"
OUTPUT_DIR = Path("beavertails_audio")
AUDIO_FORMAT = "wav"
PLAY_AUDIO = False

def extract_user_query(example: dict) -> str:
    for line in example.get("input", "").splitlines():
        if line.startswith("User:"):
            return line[len("User:"):].strip()
    return ""

def tts_request(entry: dict, server: str):
    raw_input = entry.get("input", "")
    file_id = hashlib.md5(raw_input.encode("utf-8")).hexdigest()
    input_text = raw_input
    if not input_text:
        return (file_id, server, False, "No User query found")

    payload = {
        "text": input_text,
        "references": [],
        "reference_id": None,
        "format": AUDIO_FORMAT,
        "max_new_tokens": 1024,
        "chunk_length": 300,
        "top_p": 0.8,
        "repetition_penalty": 1.1,
        "temperature": 0.8,
        "streaming": False,
        "use_memory_cache": "off",
        "seed": None
    }

    url = f"http://{server}/v1/tts"
    headers = {
        "authorization": f"Bearer {API_KEY}",
        "content-type": "application/msgpack"
    }

    try:
        resp = requests.post(url, data=ormsgpack.packb(payload), headers=headers, timeout=3600)
        if resp.status_code == 200:
            out_path = OUTPUT_DIR / f"{file_id}.{AUDIO_FORMAT}"
            with open(out_path, "wb") as f:
                f.write(resp.content)
            if PLAY_AUDIO:
                audio = AudioSegment.from_file(out_path, format=AUDIO_FORMAT)
                play(audio)
            return (file_id, server, True, str(out_path))
        else:
            return (file_id, server, False, f"HTTP {resp.status_code}")
    except Exception as e:
        return (file_id, server, False, str(e))

def main():
    # 加载数据并准备输出目录
    with open(INPUT_JSON_PATH, "r", encoding="utf-8") as f:
        data_list = json.load(f)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total = len(data_list)
    print(f"Loaded {total} items, dispatching to {len(SERVERS)} servers...")

    start_time = time.time()
    completed = 0
    failed_entries = []

    # 第一次并发提交
    with ThreadPoolExecutor(max_workers=len(SERVERS)) as exe:
        futures = []
        for idx, entry in enumerate(data_list):
            server = SERVERS[idx % len(SERVERS)]
            futures.append(exe.submit(tts_request, entry, server))

        for future in as_completed(futures):
            file_id, server, success, info = future.result()
            completed += 1
            elapsed = time.time() - start_time
            remaining = (elapsed / completed) * (total - completed)
            status = "✓" if success else "✗"
            print(
                f"[{status}] {file_id} @ {server} :: {info}  "
                f"({completed}/{total})  "
                f"Elapsed: {format_time(elapsed)}  "
                f"Remaining: {format_time(remaining)}"
            )
            if not success:
                # 记录整个 entry 用于重试
                idx_failed = completed - 1
                failed_entries.append(data_list[idx_failed])

    # 如果有失败，串行在第一个 server 重新执行一次
    if failed_entries:
        print(f"\nRe-running {len(failed_entries)} failed items on {SERVERS[0]}...\n")
        for entry in failed_entries:
            file_id, server, success, info = tts_request(entry, SERVERS[0])
            status = "✓" if success else "✗"
            print(f"[Retry {status}] {file_id} @ {SERVERS[0]} :: {info}")

if __name__ == "__main__":
    main()
