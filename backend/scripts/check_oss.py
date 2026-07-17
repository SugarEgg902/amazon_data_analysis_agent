#!/usr/bin/env python
"""OSS 连通性自检。填完 config/config.py 的 OSS_* 后跑:

    backend/venv/bin/python backend/scripts/check_oss.py

逐层验证并在失败处指出原因,避免"图裂了但不知道卡在哪一层"。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import requests

from backend.analysis.oss_upload import is_configured, upload
from config.config import (OSS_BUCKET, OSS_ENDPOINT, OSS_PREFIX,
                           OSS_SIGN_EXPIRE_SEC, OSS_USE_SIGNED_URL)


def main() -> int:
    print("=== 1. 配置检查 ===")
    if not is_configured():
        print("  ✗ OSS_* 未填全,请编辑 config/config.py")
        return 1
    print(f"  bucket   : {OSS_BUCKET}")
    print(f"  endpoint : {OSS_ENDPOINT}")
    print(f"  prefix   : {OSS_PREFIX}")
    print(f"  签名URL  : {OSS_USE_SIGNED_URL} (有效期 {OSS_SIGN_EXPIRE_SEC // 86400} 天)")
    if "-internal." in OSS_ENDPOINT:
        print("  ✗ endpoint 是内网地址,钉钉在公网拉不到,图会裂。改用外网 endpoint。")
        return 1

    print("=== 2. 上传一张测试图 ===")
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_oss_probe.png")
    # 1x1 透明 PNG
    with open(local, "wb") as f:
        f.write(bytes.fromhex(
            "89504e470d0a1a0a0000000d494844520000000100000001080600000"
            "01f15c4890000000a49444154789c63000100000500010d0a2db40000"
            "000049454e44ae426082"))
    try:
        url = upload(local, "_connectivity_probe.png")
    except Exception as e:
        print(f"  ✗ 上传失败: {type(e).__name__}: {e}")
        print("    常见原因: AccessKey 错 / RAM 缺 oss:PutObject / bucket 名或地域不对")
        return 1
    finally:
        os.path.exists(local) and os.remove(local)
    print("  ✓ 上传成功")

    if not url.startswith("https://"):
        print(f"  ✗ 签出的是非 https URL,钉钉可能拒抓: {url[:60]}")
        return 1
    print("  ✓ URL 是 https")

    print("=== 3. 从公网拉取(模拟钉钉抓图) ===")
    print(f"  URL: {url[:90]}{'…' if len(url) > 90 else ''}")
    try:
        r = requests.get(url, timeout=15)
    except Exception as e:
        print(f"  ✗ 请求失败: {e}")
        return 1
    if r.status_code != 200:
        print(f"  ✗ HTTP {r.status_code}: {r.text[:200]}")
        if r.status_code == 403:
            print("    403 多半是 RAM 缺 oss:GetObject —— 签名 URL 被访问时,")
            print("    OSS 会校验该 AccessKeyId 身份有没有读权限,只给 PutObject 不够。")
        return 1
    print(f"  ✓ HTTP 200, {len(r.content)} bytes, {r.headers.get('Content-Type')}")

    print("\n全部通过 —— 可以把 REPORT_EMBED_CHARTS 设为 1 了。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
