#!/usr/bin/env bash
set -euo pipefail

# 每个 GPU 上要启动的实例数量
INSTANCES_PER_GPU=5

# 日志目录
LOG_DIR=logs/tts_servers
mkdir -p "$LOG_DIR"

# 基础命令参数（请根据实际路径调整 checkpoint 路径）
BASE_CMD="python -m tools.api_server \
  --llama-checkpoint-path checkpoints/openaudio-s1-mini \
  --decoder-checkpoint-path checkpoints/openaudio-s1-mini/codec.pth \
  --decoder-config-name modded_dac_vq"

# 端口起始号（你可以改成 8080 或者别的）
BASE_PORT=8080

for GPU in {0..7}; do
  for INSTANCE in $(seq 0 $((INSTANCES_PER_GPU - 1))); do
    # 计算实际监听端口：GPU * INSTANCES_PER_GPU + INSTANCE
    PORT=$(( BASE_PORT + GPU * INSTANCES_PER_GPU + INSTANCE ))
    LOGFILE=$LOG_DIR/server_gpu${GPU}_inst${INSTANCE}_port${PORT}.log

    echo "Launching GPU $GPU instance $INSTANCE on port $PORT, log → $LOGFILE"
    CUDA_VISIBLE_DEVICES=$GPU nohup bash -c "\
      $BASE_CMD --listen 0.0.0.0:${PORT}" \
      > "$LOGFILE" 2>&1 &

    # 防止短时间内并发太多造成资源抢占失败
    sleep 0.2
  done
done

echo "✅ Launched $((8 * INSTANCES_PER_GPU)) servers."
echo "查看进程：ps aux | grep tools.api_server"
echo "实时日志：tail -f $LOG_DIR/*.log"
