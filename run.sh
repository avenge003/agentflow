#!/bin/bash
# 激活conda环境
source ~/anaconda3/etc/profile.d/conda.sh
conda activate ragflowapi

# 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8002 --workers 1
