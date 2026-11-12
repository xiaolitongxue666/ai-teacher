#!/usr/bin/env python3
"""夸克网盘小学资料阶段。

核心约束（全部实测，不是猜测）：
  - `sharepage/token` 与 `sharepage/detail` 无需登录即可调用，能翻完整个分享目录。
  - `sharepage/save` 与 `file/download` 无论带不带匿名身份都返回
    `401 code 31001 require login`，即**匿名态无法取下载直链**。
  - 因此本模块分两条路：有 Cookie 就走登录态取直链下载；无 Cookie 就只产清单
    （fid / share_fid_token / size / 相对路径都已能从 detail 接口拿到），
    并把可直接执行的续传命令写进报告。

登录态下载的五个坑（每个都是实测撞出来的，不是预想）：
  1) `sharepage/save` 返回的是 `task_id`，不是 fid。必须轮询 `/1/clouddrive/task`
     到 `status == 2`，再从 `save_as.save_as_top_fids` 取**转存后的新 fid**。
     拿分享里的原 fid 去 `file/download` 必然失败——那是别人的文件 id。
  2) `file/download` 用浏览器 UA 会返回 `400 code 23018 download file size limit`，
     非会员与 Svip 都会（官方限制 Web 端下载 >100 MB）。换夸克 PC 客户端 UA 即通。
  3) 直链本身也要带 Cookie，否则 CDN 返回 `412 Precondition Failed`。
  4) 非会员单连接被限速到约 100 KB/s，且是**账号级**限速、与代理无关
     （实测直连与走代理同为 101 KB/s；并发 1/4/8 都不变）。用 HTTP Range
     分片 + 高并发可以线性叠加：64 并发 613 KB/s、256 并发 2.15 MB/s、
     512 并发 2.90 MB/s；1024 并发反而退化到 0.8 MB/s。故并发封顶 512。
  5) 非会员总容量只有 10 GB，而小学资料 119.42 GB，必须「转存 → 下载 → 删除」
     逐文件闭环，不能先把整个分享转存进来。

为什么不直接依赖 netdisk MCP：
  netdisk-mcp-server 的 `view` 免登录但固定只回 100 条且不翻页，
  `transfer` 是转存不是下载，没有任何 download 工具。要拿直链必须自己调接口。

提取码来源：resources.json 的 note 字段里写着。`primary_1000_words` 的码是 YhRG，
`phonics_270` 的码是 ab8M；这两条的分享页本身不要求输码，但接口要。
"""

from __future__ import annotations

import http.cookiejar
import json
import pathlib
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from . import common

QUARK_API_BASE = "https://drive-h.quark.cn"
QUARK_TOKEN_PATH = "/1/clouddrive/share/sharepage/token"
QUARK_DETAIL_PATH = "/1/clouddrive/share/sharepage/detail"
QUARK_SAVE_PATH = "/1/clouddrive/share/sharepage/save"
QUARK_TASK_PATH = "/1/clouddrive/task"
QUARK_FILE_DELETE_PATH = "/1/clouddrive/file/delete"
QUARK_MEMBER_PATH = "/1/clouddrive/member"
QUARK_FILE_DOWNLOAD_PATH = "/1/clouddrive/file/download"
QUARK_CONFIG_PATH = "/1/clouddrive/config"

QUARK_SHARE_PATTERN = re.compile(r"pan\.quark\.cn/s/([a-zA-Z0-9]+)")
# 服务端单页硬限 100，必须翻页
QUARK_PAGE_SIZE = 100
# 单分享请求上限。p_math 实测在 800 次时仍有 25 个目录没翻，所以放到 3000。
QUARK_REQUEST_BUDGET = 3000
QUARK_MAX_PAGES = 200
QUARK_MAX_DEPTH = 12
QUARK_PAGE_RETRIES = 3
QUARK_PASSCODE_REQUIRED_CODE = 41008
QUARK_CONTENT_BLOCKED_CODE = 41010
QUARK_SHARE_MISSING_CODE = 41006
# 浏览器 UA 取直链会被「Web 端下载 >100 MB」限制拦下，换 PC 客户端 UA 才通
QUARK_DOWNLOAD_SIZE_LIMIT_CODE = 23018
# 转存完成但文件暂不可见时 file/download 回这个码，需要退避重试
QUARK_FILE_NOT_FOUND_CODE = 23001
QUARK_SAVE_TASK_STATUS_DONE = 2
# 转存是小文件元数据操作，实测 147 KB 与 113 MB 都在 2s 内完成；给足余量
QUARK_SAVE_TASK_TIMEOUT = 120
QUARK_SAVE_TASK_INTERVAL = 0.5

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
# 夸克 PC 客户端 UA。必须带 quark-cloud-drive/<ver>，服务端据此判断不是 Web 端，
# 才不给 23018 的文件大小限制。改版本号前先实测 /file/download 是否仍返回 code 0。
DOWNLOAD_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) quark-cloud-drive/3.14.2 Chrome/112.0.5615.165 "
    "Electron/24.1.3.8 Safari/537.36 Channel/pckk_other_ch"
)

# 分片下载参数。非会员是账号级限速（单连接约 100 KB/s），实际吞吐完全由
# **并发连接数**决定，所以切片必须按并发数倒推，而不能固定 1 MB：
# 实测 20 MB 文件固定 1 MB 切片只切出 21 片 → 21 并发 → 202 KB/s；
# 改 128 KB 切片 → 163 并发 → 1.50 MB/s，同一文件快 7.4 倍。
# 512 KB 是「片够多」与「请求数别太碎」之间的折中：20 MB → 40 片（略少但可接受），
# 因此下限压到 128 KB 保证小文件也能跑满并发。
QUARK_DOWNLOAD_WORKERS = 256
QUARK_DOWNLOAD_MAX_WORKERS = 512
QUARK_RANGE_MAX_CHUNK_BYTES = 4 * 1024 * 1024
# 下限给小文件让路：3.67 MB 文件若按 128 KB 切片只有 29 片 → 29 并发 → 299 KB/s；
# 降到 32 KB 可切出 117 片，接近跑满 256 线程。请求变碎但都是小 Range，
# 服务端实测未出现限流或失败增加。
QUARK_RANGE_MIN_CHUNK_BYTES = 32 * 1024
QUARK_RANGE_ATTEMPTS = 3
# 分片看门狗。`urlopen` 的 timeout 只管连接与首包，长连接中途静默掉线时
# 不会抛异常，线程会永远阻塞在 read 上（实测 `.part` 冻结超过 100 秒）。
QUARK_RANGE_STALL_SECONDS = 60
QUARK_RANGE_TOTAL_TIMEOUT_SECONDS = 1800
# 低于此体积走单连接：分片开销（几百个请求）不划算。
# 1 MB 而不是 4 MB：网盘里大量 5–20 MB 的课时片段，4 MB 门槛会让它们全走
# 单连接（100 KB/s），而分片能到 1.5 MB/s。
QUARK_MIN_RANGE_BYTES = 1024 * 1024

# 账号容量很小（非会员 10 GB），转存前留出余量给并发在途文件
QUARK_STAGING_HEADROOM_BYTES = 512 * 1024 ** 2
# 剩余容量每查一次是一次 HTTP 往返，逐个文件查会拖慢小文件居多的分享
QUARK_CAPACITY_PROBE_EVERY = 20

# 转存被风控封禁时的处理。
# 实测现象（2026-11-11）：`sharepage/save` 间歇性返回「当前用户封禁转存功能受限」，
# 几十分钟后自行解除；封禁期间每个文件都失败，但循环只记 last_error 继续下一个，
# 于是整条分享被记成 `ok` 却静默缺了大批文件（p_math 缺 1882 个、p_eng 缺 615 个）。
# 因此单文件要退避重试，整条要能识别出来并停下，而不是一路记 ok。
QUARK_SAVE_BANNED_MESSAGE = "封禁转存功能受限"
# 每轮退避秒数；轮数即重试次数。放在后台跑，等一小时比缺一半文件划算。
QUARK_SAVE_BAN_BACKOFF_SECONDS = (120, 600, 1800)

# 本次范围：只下小学。初中/高中/雅思等按用户口径暂不下载。
PRIMARY_ITEM_IDS = frozenset({
    "fan_geometry_900", "primary_1000_words", "phonics_270", "scratch_174",
    "word_posters", "p_chn", "p_math", "p_eng", "p_morality", "p_sci",
    "j_curriculum",
})
# note 里提到、但接口真需要的提取码。写死在这里而不是从 note 里正则提取：
# note 文本格式不稳定，正则会在文案改动时静默失效，比写死更危险。
PASSCODES = {
    "primary_1000_words": "YhRG",
    "phonics_270": "ab8M",
}


class QuarkError(RuntimeError):
    """夸克接口的业务错误，带业务码便于调用方分流。"""

    def __init__(self, message: str, code: int = 0) -> None:
        super().__init__(message)
        self.code = code

    @property
    def is_save_banned(self) -> bool:
        """是否为转存被风控封禁。

        判据只用消息文本，不认业务码：实测封禁返回的 code 每次可能不同，
        而中文提示固定包含「封禁转存功能受限」。业务码在变、文案没变。
        """
        return QUARK_SAVE_BANNED_MESSAGE in str(self)


def _opener_with_cookie(cookie: str) -> urllib.request.OpenerDirector:
    """把整段 Cookie 头灌进 opener，后续请求自动带上。

    显式禁用系统代理：直链在 CDN 上，走代理与直连实测同为 100 KB/s，
    但代理会额外引入一个故障点（curl 走代理拿 412、直连正常）。下载是
    大流量场景，不该被无关代理链路拖累。
    """
    jar = http.cookiejar.CookieJar()
    for chunk in str(cookie).split(";"):
        name, separator, value = chunk.strip().partition("=")
        if not separator or not name:
            continue
        jar.set_cookie(http.cookiejar.Cookie(
            version=0, name=name.strip(), value=value.strip(), port=None,
            port_specified=False, domain=".quark.cn", domain_specified=True,
            domain_initial_dot=True, path="/", path_specified=True,
            secure=True, expires=None, discard=False, comment=None,
            comment_url=None, rest={}, rfc2109=False,
        ))
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPCookieProcessor(jar),
    )


def _request_json(opener, url: str, payload: dict | None = None,
                  user_agent: str = BROWSER_USER_AGENT,
                  attempts: int = 3) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "User-Agent": user_agent,
        "Referer": "https://pan.quark.cn/",
    }
    request = urllib.request.Request(url, data=data, headers=headers,
                                     method="POST" if data else "GET")
    for attempt in range(attempts):
        try:
            with opener.open(request, timeout=25) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as http_error:
            # 违规下架会返回 HTTP 404，但业务码在响应体里，必须读出来
            try:
                return json.loads(http_error.read().decode("utf-8"))
            except Exception:  # noqa: BLE001 - 响应体不是 JSON
                raise QuarkError(f"HTTP {http_error.code}") from http_error
        except urllib.error.URLError as network_error:
            # 长时间跑批时 DNS 偶发失效（实测一次 getaddrinfo failed 让整个阶段
            # 剩余 8 个条目全判 failed）。这类错误是瞬时的，重试而不是放弃。
            if attempt == attempts - 1:
                raise
            time.sleep(2.0 * (attempt + 1))
    raise QuarkError("请求重试耗尽")


def share_token(opener, share_id: str, passcode: str = "") -> str:
    body = _request_json(
        opener,
        f"{QUARK_API_BASE}{QUARK_TOKEN_PATH}?pr=ucpro&fr=pc",
        {"pwd_id": share_id, "passcode": passcode},
    )
    stoken = ((body.get("data") or {}).get("stoken") or "")
    if stoken:
        return stoken
    code = int(body.get("code") or 0)
    if code == QUARK_PASSCODE_REQUIRED_CODE:
        raise QuarkError("需要提取码", code)
    if code == QUARK_CONTENT_BLOCKED_CODE:
        raise QuarkError("文件涉及违规内容（已下架）", code)
    if code == QUARK_SHARE_MISSING_CODE:
        raise QuarkError("分享不存在", code)
    raise QuarkError(str(body.get("message") or "取 stoken 失败")[:80], code)


def list_page(opener, share_id: str, stoken: str, pdir_fid: str, page: int) -> tuple[list[dict], bool]:
    """取一页。返回 (条目, 是否成功)。

    必须区分「目录到底了」与「这次请求失败」：混为一谈会让翻页提前终止、
    静默漏文件。实测同一分享两次统计差 40 个文件，就是超时被当成空页。
    """
    query = urllib.parse.urlencode({
        "pr": "ucpro", "fr": "pc",
        "pwd_id": share_id, "stoken": stoken,
        "pdir_fid": pdir_fid,
        "force": "0",
        "_page": str(page), "_size": str(QUARK_PAGE_SIZE),
        "_fetch_total": "1",
        "_sort": "file_type:asc,file_name:asc",
    })
    for attempt in range(QUARK_PAGE_RETRIES):
        try:
            body = _request_json(opener, f"{QUARK_API_BASE}{QUARK_DETAIL_PATH}?{query}")
            return (body.get("data") or {}).get("list") or [], True
        except Exception:  # noqa: BLE001 - 失败要如实上报，不能伪装成空页
            if attempt == QUARK_PAGE_RETRIES - 1:
                return [], False
            time.sleep(0.4 * (attempt + 1))
    return [], False


def walk_share(share_id: str, passcode: str,
               progress: common.Progress | None = None,
               opener=None) -> dict:
    """递归 + 翻页遍历分享，返回完整文件清单。

    返回结构：
      {"entries": [{rel_path, size, fid, share_fid_token}], "truncated": bool,
       "failed_pages": int, "requests": int, "bytes": int}

    `opener` 必须与后续转存用的是同一个身份。匿名拿到的 share_fid_token
    在登录态 save 时会被判 `code 41020 转存文件token校验异常`（实测：
    两条路径返回的 token 每条都不同），所以登录下载时必须把登录 opener 传进来。
    """
    if opener is None:
        opener = _opener_with_cookie("")
    stoken = share_token(opener, share_id, passcode)

    budget = {"remaining": QUARK_REQUEST_BUDGET}
    truncated = {"value": False}
    failed_pages = {"value": 0}
    collected: list[dict] = []

    def _walk(pdir_fid: str, prefix: str, depth: int) -> None:
        if depth > QUARK_MAX_DEPTH:
            return
        for page_number in range(1, QUARK_MAX_PAGES + 1):
            if budget["remaining"] <= 0:
                truncated["value"] = True
                return
            budget["remaining"] -= 1
            entries, page_ok = list_page(opener, share_id, stoken, pdir_fid, page_number)
            if not page_ok:
                failed_pages["value"] += 1
                return
            for entry in entries:
                name = str(entry.get("file_name") or "")
                relative = f"{prefix}/{name}" if prefix else name
                if entry.get("dir"):
                    _walk(str(entry.get("fid")), relative, depth + 1)
                else:
                    collected.append({
                        "rel_path": relative,
                        "size": int(entry.get("size") or 0),
                        "fid": str(entry.get("fid") or ""),
                        "share_fid_token": str(entry.get("share_fid_token") or ""),
                    })
            if len(entries) < QUARK_PAGE_SIZE:
                return

    _walk("0", "", 0)
    return {
        "entries": collected,
        # stoken 必须随清单一起返回：它每取一次就换新值且只有最新有效，
        # 后续 save 必须复用这一个，重取会让所有 share_fid_token 失效
        "stoken": stoken,
        "truncated": truncated["value"],
        "failed_pages": failed_pages["value"],
        "requests": QUARK_REQUEST_BUDGET - budget["remaining"],
        "bytes": sum(item["size"] for item in collected),
    }


def save_to_drive(opener, share_id: str, stoken: str, entry: dict) -> str:
    """把分享里的单个文件转存进自己网盘，返回**转存后的新 fid**。

    save 接口只返回 task_id，必须轮询到 status==2 才能从 save_as 里取新 fid。
    新 fid 与分享里的原 fid 不同，拿原 fid 去取直链会失败。
    """
    save_body = _request_json(
        opener,
        f"{QUARK_API_BASE}{QUARK_SAVE_PATH}?pr=ucpro&fr=pc",
        {
            "pwd_id": share_id, "stoken": stoken,
            "fid_list": [entry["fid"]],
            "fid_token_list": [entry.get("share_fid_token") or ""],
            "to_pdir_fid": "0", "pdir_fid": "0", "scene": "link",
        },
    )
    task_id = str((save_body.get("data") or {}).get("task_id") or "")
    if not task_id:
        code = int(save_body.get("code") or 0)
        raise QuarkError(str(save_body.get("message") or "转存未返回 task_id")[:80], code)

    deadline = time.time() + QUARK_SAVE_TASK_TIMEOUT
    # 先立刻查一次，再按间隔轮询。转存是小文件元数据操作，实测 2s 内就完成，
    # 无条件先 sleep 一个间隔会让每个文件白等 0.5s；剩余几千个小文件时
    # 这个固定开销比下载本身还长（3949 个文件 ≈ 33 分钟）。
    while True:
        task_body = _request_json(
            opener, f"{QUARK_API_BASE}{QUARK_TASK_PATH}?pr=ucpro&fr=pc&task_id={task_id}")
        detail = task_body.get("data") or {}
        if int(detail.get("status") or 0) == QUARK_SAVE_TASK_STATUS_DONE:
            new_fids = (detail.get("save_as") or {}).get("save_as_top_fids") or []
            if new_fids:
                return str(new_fids[0])
            # 容量不足等业务失败会以 status==2 结束但 save_as 为空
            raise QuarkError(f"转存完成但没有产出 fid（可能容量不足）：{task_id}"[:120])
        if time.time() >= deadline:
            break
        time.sleep(QUARK_SAVE_TASK_INTERVAL)
    raise QuarkError(f"转存任务轮询超时（{QUARK_SAVE_TASK_TIMEOUT}s）：{task_id}"[:120])


def download_url_for(opener, fid: str, attempts: int = 6) -> str:
    """取直链。必须用 PC 客户端 UA，否则 >100 MB 的文件返回 code 23018。

    转存任务报 status==2 之后，文件在网盘侧仍可能有短暂不可见窗口，
    立刻取直链会返回 `file not found`。实测需要退避重试约 1–3 秒。
    """
    last_message = ""
    for attempt in range(attempts):
        body = _request_json(
            opener,
            f"{QUARK_API_BASE}{QUARK_FILE_DOWNLOAD_PATH}?pr=ucpro&fr=pc",
            {"fids": [fid]},
            user_agent=DOWNLOAD_USER_AGENT,
        )
        code = int(body.get("code") or 0)
        if code == QUARK_DOWNLOAD_SIZE_LIMIT_CODE:
            raise QuarkError("被 Web 端下载大小限制拦下（UA 未生效）", code)
        if code == 0:
            download_url = ((body.get("data") or [{}])[0] or {}).get("download_url")
            if download_url:
                return str(download_url)
            last_message = "直链为空"
        else:
            last_message = str(body.get("message") or "未取到直链")[:80]
            # 只有「文件暂不可见」值得重试；其它业务错误立刻上报
            if "not found" not in last_message.lower() and code != QUARK_FILE_NOT_FOUND_CODE:
                raise QuarkError(last_message, code)
        if attempt < attempts - 1:
            time.sleep(0.6 * (attempt + 1))
    raise QuarkError(f"取直链失败：{last_message}", QUARK_FILE_NOT_FOUND_CODE)


def delete_drive_file(opener, fid: str, attempts: int = 3) -> bool:
    """删除自己网盘里的转存件，释放容量。失败不抛，只返回结果。

    非会员只有 10 GB 容量，转存件不清理会在几个大文件之后就卡死。
    删除是异步 task，偶发 5xx；重试后仍失败就交给下一次容量探测兜底，
    但必须让调用方知道——静默失败会以「容量不足」的形式在很久以后爆出来。
    """
    for attempt in range(attempts):
        try:
            body = _request_json(
                opener,
                f"{QUARK_API_BASE}{QUARK_FILE_DELETE_PATH}?pr=ucpro&fr=pc",
                {"action_type": 2, "filelist": [fid], "exclude_fids": []},
            )
            if int(body.get("code") or 0) == 0:
                return True
        except Exception:  # noqa: BLE001 - 清理失败不该覆盖下载结果
            pass
        if attempt < attempts - 1:
            time.sleep(0.5 * (attempt + 1))
    return False


def remain_capacity(opener) -> int | None:
    """查询账号剩余容量。取不到时返回 None，调用方按「不限制」处理。"""
    try:
        body = _request_json(opener, f"{QUARK_API_BASE}{QUARK_MEMBER_PATH}?pr=ucpro&fr=pc")
        member = body.get("data") or {}
        total = int(member.get("total_capacity") or 0)
        used = int(member.get("use_capacity") or 0)
        if total:
            return max(total - used, 0)
        return None
    except Exception:  # noqa: BLE001
        return None


def _fetch_range(opener, url: str, start: int, end: int, attempts: int) -> bytes:
    """取一段字节。CDN 偶发 412/超时，重试后仍失败才抛。"""
    last_error: Exception | None = None
    for attempt in range(attempts):
        request = urllib.request.Request(url, headers={
            "User-Agent": DOWNLOAD_USER_AGENT,
            "Range": f"bytes={start}-{end}",
        })
        try:
            with opener.open(request, timeout=120) as response:
                payload = response.read()
            expected = end - start + 1
            # 服务端忽略 Range 时会回整份文件，此时切窗口保证写盘偏移正确
            if len(payload) < expected:
                raise QuarkError(
                    f"分片返回长度不足 {len(payload)} < {expected}（{start}-{end}）")
            return payload[:expected]
        except Exception as unexpected:  # noqa: BLE001
            last_error = unexpected
            time.sleep(0.5 * (attempt + 1))
    raise QuarkError(f"分片下载失败 {start}-{end}：{last_error}"[:160])


def _download_ranged(opener, url: str, destination: pathlib.Path,
                     total_size: int) -> int:
    """Range 分片并发下载。返回写入字节数。

    非会员是账号级限速，单连接固定 ~100 KB/s，吞吐完全由并发连接数决定
    （实测 256 并发 2.15 MB/s、512 并发 2.90 MB/s；1024 并发反而退化并出现失败）。
    所以切片大小要按并发数倒推，保证片数能喂满线程池；固定 1 MB 切片会让
    小文件只切出个位数分片，并发上不去（20 MB 文件实测只有 202 KB/s）。
    """
    workers = QUARK_DOWNLOAD_WORKERS
    # 目标：片数 ≈ 并发数；同时片不小于 MIN（避免请求过碎），不大于 MAX
    chunk = -(-total_size // workers)
    chunk = min(max(chunk, QUARK_RANGE_MIN_CHUNK_BYTES), QUARK_RANGE_MAX_CHUNK_BYTES)
    ranges: list[tuple[int, int]] = []
    offset = 0
    while offset < total_size:
        ranges.append((offset, min(offset + chunk, total_size) - 1))
        offset += chunk

    partial = destination.with_suffix(destination.suffix + ".part")
    partial.parent.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    # 已完成的分片数。不能用 `.part` 的文件大小判进度：文件一开始就
    # truncate 到 total_size，大小恒定不变，看门狗会立刻误判停滞。
    completed_chunks = {"count": 0}

    def worker(index: int) -> None:
        # 每个线程持有自己的句柄：各句柄文件指针独立，而分片区间互不重叠，
        # 所以无需加锁写盘。若在锁内每次 open/seek/write，256 个线程会
        # 把全部磁盘写入串行化，抵消掉并发下载带来的收益。
        try:
            handle = partial.open("r+b")
        except OSError:
            return
        try:
            for start, end in ranges[index::QUARK_DOWNLOAD_WORKERS]:
                try:
                    payload = _fetch_range(opener, url, start, end, QUARK_RANGE_ATTEMPTS)
                except Exception as unexpected:  # noqa: BLE001
                    failures.append(f"{start}-{end}: {unexpected}")
                    return
                handle.seek(start)
                handle.write(payload)
                completed_chunks["count"] += 1
        finally:
            handle.close()

    thread_count = min(QUARK_DOWNLOAD_WORKERS, len(ranges))
    with partial.open("wb") as allocation:
        # 预分配，避免多线程各写远端偏移时反复扩文件
        allocation.truncate(total_size)

    threads = [threading.Thread(target=worker, args=(index,), daemon=True)
               for index in range(thread_count)]
    for thread in threads:
        thread.start()

    # 看门狗：不能无限 join。实测 `.part` 大小冻结在某个值超过 100 秒，
    # 卡住的线程阻塞在 socket 读取上，`urlopen` 的 timeout 只管连接与首包，
    # 长连接中途静默掉线时不会抛异常。这里按「总耗时」与「进度停滞」双判据。
    started = time.monotonic()
    last_count = -1
    last_progress = started
    stall_reason = ""
    total_chunks = len(ranges)
    while any(thread.is_alive() for thread in threads):
        time.sleep(1.0)
        now = time.monotonic()
        current_count = completed_chunks["count"]
        if current_count != last_count:
            last_count = current_count
            last_progress = now
        # 全部片都收完但线程还没退：它们在收尾，不该判停滞
        if total_chunks and current_count >= total_chunks:
            last_progress = now
            continue
        if now - last_progress > QUARK_RANGE_STALL_SECONDS:
            stall_reason = (f"分片进度停滞 {QUARK_RANGE_STALL_SECONDS}s"
                            f"（{current_count}/{total_chunks} 片）")
            break
        if now - started > QUARK_RANGE_TOTAL_TIMEOUT_SECONDS:
            stall_reason = f"分片整体超时 {QUARK_RANGE_TOTAL_TIMEOUT_SECONDS}s"
            break

    if stall_reason:
        # 线程是 daemon，强退不阻塞进程；清掉半成品让本次算失败而非留坏文件
        partial.unlink(missing_ok=True)
        raise QuarkError(stall_reason)

    for thread in threads:
        thread.join(timeout=5)

    if failures:
        partial.unlink(missing_ok=True)
        raise QuarkError(f"分片失败 {len(failures)} 段，首条：{failures[0]}"[:160])

    written = partial.stat().st_size
    if written != total_size:
        partial.unlink(missing_ok=True)
        raise QuarkError(f"落盘体积不符 {written} != {total_size}")
    partial.replace(destination)
    return written


def download_entry(opener, share_id: str, stoken: str, entry: dict,
                   destination: pathlib.Path,
                   progress: common.Progress | None = None) -> None:
    """单个文件闭环：转存 → 取直链 → 分片下载 → 删除转存件。

    删除放在 finally 里：下载失败也必须清掉，否则大文件失败几次就把
    10 GB 的账号容量塞满，后续所有文件都会在转存一步失败。
    """
    staged_fid = ""
    try:
        staged_fid = save_to_drive(opener, share_id, stoken, entry)
        url = download_url_for(opener, staged_fid)
        size = int(entry.get("size") or 0)
        if size >= QUARK_MIN_RANGE_BYTES:
            _download_ranged(opener, url, destination, size)
        else:
            _stream_to_file(opener, url, destination, size)
    finally:
        if staged_fid and not delete_drive_file(opener, staged_fid):
            # 清不掉会让后续文件撞容量不足，必须在当场留下痕迹
            if progress:
                progress.record_error(
                    f"转存件清理失败（容量会被占用）：{entry['rel_path']}")


def share_root_prefix(entries: list[dict]) -> str:
    """找出分享里唯一的顶层目录名，用于从 rel_path 中剥掉。

    夸克分享常把内容套在一层「分享标题」目录下，而 target_dir 已经带了
    `<id>__<资料名>`，不剥掉就会变成
    `<id>__<资料名>/<同一串标题>/文件.mp4`，每层都重复一次长标题。

    判据必须严格：**所有**条目都以同一个第一段开头才剥。
    混杂多目录的分享（如初中全科 48 个教辅品牌）剥掉会丢分类信息。
    """
    heads = set()
    for entry in entries:
        head = str(entry.get("rel_path") or "").replace("\\", "/").split("/")[0]
        if not head:
            continue
        heads.add(head)
        if len(heads) > 1:
            return ""
    if len(heads) != 1:
        return ""
    head = heads.pop()
    # 只有当所有条目都真的有第二段（即它确实是目录而非根上的单文件）时才剥
    for entry in entries:
        parts = str(entry.get("rel_path") or "").replace("\\", "/").split("/")
        if len(parts) < 2:
            return ""
    return head


def relative_after_root(entry: dict, root: str) -> str:
    """返回剥掉分享根目录后的相对路径。"""
    text = str(entry.get("rel_path") or "").replace("\\", "/")
    if root and text.startswith(root + "/"):
        return text[len(root) + 1:]
    return text


def download_with_login(share_id: str, passcode: str, cookie: str,
                        entries: list[dict], target_dir: pathlib.Path,
                        progress: common.Progress | None = None,
                        opener=None, stoken: str = "") -> dict:
    """登录态下取直链下载。

    每个文件走「转存 → 取直链 → 下载 → 删除」闭环，而不是先把整个分享
    转存进来：非会员容量只有 10 GB，而小学资料总量 119.42 GB。

    `stoken` 必须与 `entries` 一起产出。`share_token` 每调一次就换新值，
    且服务端只认最新那个——重取会让 `entries` 里的 share_fid_token 全部失效，
    save 报 `41020 转存文件token校验异常`（实测 st1 != st2 后立刻失败）。
    """
    if opener is None:
        opener = _opener_with_cookie(cookie)
    if not stoken:
        stoken = share_token(opener, share_id, passcode)
    saved = 0
    failed = 0
    skipped = 0
    missing: list[str] = []
    # 容量查询每次是一个 HTTP 往返，逐个文件查会拖慢小文件居多的分享；
    # 完全不查又会在容量耗尽时连续失败。改成每 N 个查一次。
    remaining: int | None = None
    probed_since = QUARK_CAPACITY_PROBE_EVERY
    # 剥掉分享根目录，避免 target_dir 与 rel_path 第一层重复长标题
    root = share_root_prefix(entries)
    for entry in entries:
        if not entry.get("fid"):
            continue
        relative = relative_after_root(entry, root)
        destination = target_dir / common.sanitize_relative_path(relative)
        # 已存在且体积一致就跳过，这是断点续传的判据
        if destination.is_file() and destination.stat().st_size == entry["size"]:
            skipped += 1
            continue
        if progress:
            progress.set_current(entry["rel_path"])

        pending = int(entry.get("size") or 0) + QUARK_STAGING_HEADROOM_BYTES
        if remaining is None or probed_since >= QUARK_CAPACITY_PROBE_EVERY:
            remaining = remain_capacity(opener)
            probed_since = 0
        if remaining is not None and remaining < pending:
            failed += 1
            missing.append(relative)
            message = (f"账号剩余容量 {common.format_bytes(remaining)} 不足"
                       f"（需要 {common.format_bytes(pending)}）")
            if progress:
                progress.record_error(f"{entry['rel_path']}: {message}")
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            _download_entry_with_ban_backoff(
                opener, share_id, stoken, entry, destination, progress)
            saved += 1
            if remaining is not None:
                # 只扣文件本身大小，不能扣 headroom：早先按 pending 扣会让每个
                # 文件白扣 512 MB，几十个文件后把 8 GB 剩余算成 84 MB，全阶段停摆。
                # 扣除后是偏保守的估计（删除是异步 task，容量实际会更快释放）。
                remaining = max(remaining - int(entry.get("size") or 0), 0)
            probed_since += 1
        except QuarkError as quark_error:
            failed += 1
            missing.append(relative)
            # 立刻重查容量：连续失败常常是容量/配额耗尽导致
            probed_since = QUARK_CAPACITY_PROBE_EVERY
            if progress:
                progress.record_error(f"{entry['rel_path']}: {quark_error}")
            if quark_error.is_save_banned:
                # 退避全部用完仍在封禁，说明这次风控短时间不会解除。
                # 继续跑只会把剩余文件全刷成失败并记 ok，所以停下整条，
                # 交给调用方标成 incomplete 让补漏环节接手。
                break
        except Exception as unexpected:  # noqa: BLE001 - 单文件失败不该中断整批
            failed += 1
            missing.append(relative)
            probed_since = QUARK_CAPACITY_PROBE_EVERY
            if progress:
                progress.record_error(f"{entry['rel_path']}: {unexpected}")
    return {"saved": saved, "failed": failed, "skipped": skipped,
            "missing": missing, "total": len(entries)}


def _download_entry_with_ban_backoff(opener, share_id: str, stoken: str,
                                     entry: dict, destination: pathlib.Path,
                                     progress: common.Progress | None) -> None:
    """下载单个文件，遇到转存封禁按等级退避重试。

    封禁是账号级、间歇性的，单次失败不代表这个文件下不了。直接放弃会让
    整条分享静默缺失大批文件，所以宁可等。退避阶梯见
    QUARK_SAVE_BAN_BACKOFF_SECONDS；全部用完仍封禁才向上抛。
    """
    for wait_seconds in (0,) + QUARK_SAVE_BAN_BACKOFF_SECONDS:
        if wait_seconds:
            if progress:
                progress.record_error(
                    f"{entry['rel_path']}: 转存被封禁，等待 {wait_seconds}s 后重试")
            time.sleep(wait_seconds)
        try:
            download_entry(opener, share_id, stoken, entry, destination, progress)
            return
        except QuarkError as quark_error:
            if not quark_error.is_save_banned:
                raise
    raise QuarkError(
        f"转存持续被封禁，已退避 {sum(QUARK_SAVE_BAN_BACKOFF_SECONDS)}s 仍失败", 0)



def _stream_to_file(opener, url: str, destination: pathlib.Path,
                    expected_size: int = 0) -> None:
    """小文件的单连接流式落盘，先写 .part 再改名。

    直链在 CDN 上，必须带 Cookie，否则返回 412 Precondition Failed。
    """
    partial = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": DOWNLOAD_USER_AGENT})
    with opener.open(request, timeout=120) as response:
        with partial.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                handle.write(chunk)
    written = partial.stat().st_size
    if expected_size and written != expected_size:
        partial.unlink(missing_ok=True)
        raise QuarkError(f"落盘体积不符 {written} != {expected_size}")
    partial.replace(destination)


def login_state(cookie: str) -> tuple[bool, str]:
    """用一次 config 调用探测 Cookie 是否有效。无效时返回 401 业务码 31001。"""
    if not cookie:
        return False, "未配置 NETDISK_QUARK_COOKIE"
    opener = _opener_with_cookie(cookie)
    try:
        body = _request_json(opener, f"{QUARK_API_BASE}{QUARK_CONFIG_PATH}?pr=ucpro&fr=pc")
    except QuarkError as error:
        return False, str(error)
    except Exception as unexpected:  # noqa: BLE001
        return False, f"{type(unexpected).__name__}: {unexpected}"
    if int(body.get("code") or 0) == 0:
        return True, "登录态有效"
    return False, str(body.get("message") or "登录态无效")[:80]


def plan_netdisk() -> list[dict]:
    """挑出小学范围的夸克分享，带上提取码。"""
    resources = common.load_resources()
    planned: list[dict] = []
    for record in resources.get("collections", []):
        item_id = str(record.get("id") or "")
        if item_id not in PRIMARY_ITEM_IDS:
            continue
        url = str(record.get("url_official") or "")
        match = QUARK_SHARE_PATTERN.search(url)
        if not match:
            # word_posters 的夸克源已 404，只能走 nameishare 中转，本阶段跳过
            planned.append({
                "id": item_id, "name": record.get("name"), "share_id": "",
                "status": "no_quark_source", "url": url,
            })
            continue
        planned.append({
            "id": item_id,
            "name": record.get("name"),
            "share_id": match.group(1),
            "passcode": PASSCODES.get(item_id, ""),
            "url": url,
            "status": "planned",
        })
    return planned


def target_dir_for(item: dict) -> pathlib.Path:
    label = common.sanitize_segment(f"{item['id']}__{item.get('name') or '未命名'}")
    return common.DOWNLOADS_ROOT / "netdisk" / "quark" / "小学" / label


def run(progress: common.Progress | None = None, manifest_only: bool = False) -> list[dict]:
    """跑网盘阶段。无 Cookie 时自动降级为只产清单。"""
    credentials = common.read_credentials()
    cookie = credentials.get("NETDISK_QUARK_COOKIE", "")
    logged_in, login_note = login_state(cookie)
    if not logged_in and not manifest_only:
        manifest_only = True

    # 登录态下目录与转存必须共用同一个 opener：匿名取到的 share_fid_token
    # 在登录态 save 时会被判 41020，即便立刻紧接着调用也一样。
    shared_opener = _opener_with_cookie(cookie) if logged_in else None

    planned = plan_netdisk()
    if progress:
        progress.set_totals(item_total=len(planned))

    results: list[dict] = []
    for item in planned:
        if item["status"] == "no_quark_source":
            results.append({**item, "status": "skipped_no_source"})
            _append_manifest(results[-1])
            continue
        try:
            inventory = walk_share(item["share_id"], item["passcode"], progress,
                                   opener=shared_opener)
        except QuarkError as quark_error:
            results.append({**item, "status": "unavailable",
                            "error": str(quark_error), "code": quark_error.code})
            _append_manifest(results[-1])
            if progress:
                progress.record_error(f"{item['id']}: {quark_error}")
            continue
        except Exception as unexpected:  # noqa: BLE001
            results.append({**item, "status": "failed",
                            "error": f"{type(unexpected).__name__}: {unexpected}"})
            _append_manifest(results[-1])
            continue

        target = target_dir_for(item)
        record = {
            **item,
            "status": "manifest_only" if manifest_only else "planned_download",
            "files": len(inventory["entries"]),
            "bytes": inventory["bytes"],
            "truncated": inventory["truncated"],
            "failed_pages": inventory["failed_pages"],
            "target_dir": str(target),
        }

        if manifest_only:
            _write_inventory(target, item, inventory)
        else:
            # 只按「还缺多少」判磁盘，不按整条分享体积。断点续传时已完成部分
            # 占了体积，按全量判会把本可以下完的条目误判成 skipped_disk ——
            # 分享越接近完成，误判越容易发生。
            needed_bytes = _remaining_bytes(item, inventory)
            try:
                common.assert_disk_headroom(needed_bytes, f"下载 {item['id']}")
            except common.InsufficientDisk as disk_error:
                record.update({"status": "skipped_disk", "error": str(disk_error)})
                results.append(record)
                _append_manifest(record)
                if progress:
                    progress.record_error(str(disk_error))
                break
            target.mkdir(parents=True, exist_ok=True)
            outcome = download_with_login(
                item["share_id"], item["passcode"], cookie,
                inventory["entries"], target, progress,
                opener=shared_opener, stoken=inventory["stoken"],
            )
            # 有失败就不能记 ok：早期版本只要循环跑完就记 ok，结果 p_math
            # 缺 1882 个、p_eng 缺 615 个都被「成功」掩盖，只剩 last_error
            # 里最后一条错误可查。缺文件必须体现成状态，并落一份缺失清单。
            incomplete = bool(outcome["failed"])
            record.update({
                "status": "incomplete" if incomplete else "ok",
                "saved": outcome["saved"],
                "failed": outcome["failed"],
                "skipped_existing": outcome["skipped"],
                "missing_files": len(outcome["missing"]),
            })
            if incomplete:
                _write_missing(target, item, outcome["missing"])

        results.append(record)
        _append_manifest(record)
        if progress:
            # 清单模式下 bytes_done 记的是「已盘点的待下载体积」，
            # 写 0 会让人误以为什么都没扫到（实测网盘 9 条是 119.42 GB）。
            progress.state["bytes_done"] = sum(
                int(item.get("bytes") or 0) for item in results)
            progress.add_pages(
                count=0, byte_delta=0,
                item_done=1 if record["status"] in {"ok", "incomplete", "manifest_only"} else 0)
            progress.flush()
    if manifest_only and progress:
        progress.state["note"] = f"仅产清单：{login_note}"
        progress.flush()
    return results


def _write_inventory(target: pathlib.Path, item: dict, inventory: dict) -> None:
    """无登录时的产物：完整文件清单，可据此生成断点续传命令。"""
    target.mkdir(parents=True, exist_ok=True)
    payload = {
        "item_id": item["id"],
        "name": item.get("name"),
        "share_id": item["share_id"],
        "passcode": item.get("passcode") or "",
        "collected_at": common.now_iso(),
        "files": len(inventory["entries"]),
        "bytes": inventory["bytes"],
        "truncated": inventory["truncated"],
        "failed_pages": inventory["failed_pages"],
        "entries": inventory["entries"],
    }
    common.write_json_atomic(target / "_inventory.json", payload)


def _remaining_bytes(item: dict, inventory: dict) -> int:
    """算出该分享里还没落盘的文件总体积，用于磁盘守卫。

    已有且体积一致的文件不会重新下载，不该计入需要的空间。
    """
    base = target_dir_for(item)
    root_prefix = share_root_prefix(inventory["entries"])
    remaining = 0
    for entry in inventory["entries"]:
        relative = relative_after_root(entry, root_prefix)
        destination = base / common.sanitize_relative_path(relative)
        if destination.is_file() and destination.stat().st_size == entry.get("size"):
            continue
        remaining += int(entry.get("size") or 0)
    return remaining


def _write_missing(target: pathlib.Path, item: dict, missing: list[str]) -> None:
    """把本次没下成的相对路径落成清单，供补漏环节读取。

    只记路径。体积、fid、share_fid_token 由补漏时重新 walk 分享得到，
    写在这里会让文件很快过期（stoken 每调一次就换新值）。
    """
    payload = {
        "item_id": item["id"],
        "name": item.get("name"),
        "share_id": item.get("share_id"),
        "passcode": item.get("passcode") or "",
        "recorded_at": common.now_iso(),
        "missing": missing,
    }
    common.write_json_atomic(target / "_missing.json", payload)


def _append_manifest(record: dict) -> None:
    manifest_dir = common.DOWNLOADS_ROOT / "netdisk"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    entry = {"recorded_at": common.now_iso(),
             **{key: value for key, value in record.items() if key != "entries"}}
    with (manifest_dir / "_manifest.jsonl").open("a", encoding="utf-8") as manifest:
        manifest.write(json.dumps(entry, ensure_ascii=False) + "\n")
