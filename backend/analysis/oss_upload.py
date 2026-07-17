# backend/analysis/oss_upload.py
# 把报告图表传到阿里云 OSS,换取公网可访问的 URL。
#
# 为什么非要传 OSS:钉钉 markdown 的图片只能给 URL,且去拉图的不是查看者本人,
# 私有地址(10.x/192.168.x)谁都拉不到。图表必须挂在公网可达的地方。
#
# 凭据只从环境变量读,不落 config.py —— 那个文件在 git 里。
import logging
import os

from config.config import (OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET,
                           OSS_BUCKET, OSS_ENDPOINT, OSS_PREFIX,
                           OSS_SIGN_EXPIRE_SEC, OSS_USE_SIGNED_URL)

logger = logging.getLogger(__name__)


class OssNotConfigured(RuntimeError):
    pass


def is_configured() -> bool:
    return all([OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET, OSS_BUCKET, OSS_ENDPOINT])


def _host() -> str:
    """endpoint 去掉协议后的纯主机名。"""
    return OSS_ENDPOINT.strip().removeprefix("https://").removeprefix("http://").rstrip("/")


def _bucket():
    if not is_configured():
        raise OssNotConfigured(
            "OSS 未配置,需要 OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET "
            "/ OSS_ENDPOINT / OSS_BUCKET")
    import oss2  # 惰性导入:没装 oss2 时不影响后端启动
    auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
    # 必须显式带上 https:// —— endpoint 不写协议时 oss2 默认签出 http:// 的 URL,
    # 钉钉多半拒绝抓取 http 图片,而且签名和图片内容会明文过网。
    return oss2.Bucket(auth, f"https://{_host()}", OSS_BUCKET)


def upload(local_path: str, key_name: str) -> str:
    """上传单个文件,返回可访问的 URL。

    OSS_USE_SIGNED_URL=1 时返回带签名的临时 URL(bucket 可保持私有);
    否则返回公开 URL(要求 bucket/对象 ACL 为 public-read)。
    """
    bucket = _bucket()
    key = f"{OSS_PREFIX.strip('/')}/{key_name}" if OSS_PREFIX else key_name

    with open(local_path, "rb") as f:
        bucket.put_object(key, f, headers={"Content-Type": "image/png"})

    if OSS_USE_SIGNED_URL:
        # 签名 URL 必须活得够久:钉钉是服务端抓图并转存的,抓取时机不完全可控,
        # 过期时间太短会导致图拉不到。
        url = bucket.sign_url("GET", key, OSS_SIGN_EXPIRE_SEC, slash_safe=True)
    else:
        url = f"https://{OSS_BUCKET}.{_host()}/{key}"
    if url.startswith("http://"):
        raise RuntimeError(f"签出了 http URL,钉钉可能拒抓: {url[:60]}")
    logger.info("OSS 上传成功: %s", key)
    return url


def upload_charts(charts: list, chart_dir: str) -> list:
    """给 render_report_charts() 的结果补上 OSS url 字段。

    单张失败只丢那一张(该图裂),不影响整条推送 —— 报告的文字部分才是主体。
    """
    out = []
    for c in charts:
        local = os.path.join(chart_dir, c["file"])
        try:
            out.append({**c, "url": upload(local, c["file"])})
        except Exception:
            logger.exception("OSS 上传失败,跳过该图: %s", c["file"])
    return out
