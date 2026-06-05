#!/usr/bin/env python
"""自动刷新卖家精灵 cookie。

打开浏览器 → 用户手动登录(或浏览器自动填充) → 登录成功后自动
抓取 cookie → 更新 config/config.py → 关闭浏览器。

用法:
    cd /Users/wei/Desktop/amazon
    backend/venv/bin/python scripts/refresh_sellersprite_cookie.py
"""

import asyncio
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "config.py")
LOGIN_URL = "https://www.sellersprite.com/v2/login"
DASHBOARD_URL = "https://www.sellersprite.com/v2/welcome"


async def main():
    from playwright.async_api import async_playwright

    print("正在打开浏览器...")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="zh-CN",
        )
        page = await context.new_page()

        print(f"打开登录页: {LOGIN_URL}")
        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        print("\n请在浏览器中完成登录(浏览器已保存密码,点一下登录即可)")
        print("等待跳转到 welcome 页面...\n")

        # 等待登录成功并跳转
        try:
            await page.wait_for_url(
                f"{DASHBOARD_URL}**", timeout=120000
            )
            await asyncio.sleep(2)  # 等页面完全加载
            print("✓ 检测到已登录成功")
        except Exception:
            # 可能直接用 cookie 恢复登录了
            await page.goto(DASHBOARD_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            if "welcome" in page.url:
                print("✓ 检测到已登录状态")
            else:
                print("⚠ 可能未成功登录,尝试继续...")

        cookies = await context.cookies()
        if not cookies:
            print("✗ 没有获取到 cookie")
            await browser.close()
            return

        cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
        print(f"✓ 获取到 {len(cookies)} 个 cookie\n")

        # 更新 config/config.py
        with open(CONFIG_PATH, "r") as f:
            content = f.read()

        pattern = r'(SELLERSPRITE_COOKIE\s*=\s*\()[\s\S]*?(\))'
        replacement = f'SELLERSPRITE_COOKIE = (\n    "{cookie_str}"\n)'
        new_content = re.sub(pattern, replacement, content)

        with open(CONFIG_PATH, "w") as f:
            f.write(new_content)

        print(f"✓ 已更新 {CONFIG_PATH}")
        print("\n关闭浏览器...")
        await browser.close()
        print("完成! 重启后端使新 cookie 生效。")


if __name__ == "__main__":
    asyncio.run(main())
