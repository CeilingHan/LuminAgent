"""
测试 LuminAgent 的浏览器和搜索工具能力
运行: cd OpenManus && python test_browser_search.py
"""
import asyncio
import sys
import os

# 确保项目路径正确
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.tool.web_search import WebSearch
from app.tool.browser_use_tool import BrowserUseTool
from app.config import config


async def test_web_search():
    """测试 1: WebSearch 直接搜索"""
    print("=" * 60)
    print("🔍 测试 1: WebSearch - 独立搜索功能")
    print("=" * 60)

    ws = WebSearch()

    # 显示当前搜索配置
    if config.search_config:
        print(f"  主引荐: {config.search_config.engine}")
        print(f"  备用引荐: {config.search_config.fallback_engines}")
        print(f"  语言/国家: {config.search_config.lang}/{config.search_config.country}")
    else:
        print("  ⚠️ 未配置 [search] 段，使用默认值 (Google, en/us)")

    print("\n  正在搜索: 'Python asyncio tutorial'...")
    result = await ws.execute(
        query="Python asyncio tutorial",
        num_results=3,
        fetch_content=False,
    )

    if result.error:
        print(f"  ❌ 搜索失败: {result.error}")
    else:
        print(f"  ✅ 搜索成功! 返回 {len(result.results)} 条结果:")
        for i, r in enumerate(result.results, 1):
            print(f"    {i}. [{r.source}] {r.title[:60]}...")
            print(f"       URL: {r.url}")

    return result


async def test_web_search_with_content():
    """测试 2: WebSearch 搜索 + 抓取页面内容"""
    print("\n" + "=" * 60)
    print("📄 测试 2: WebSearch - 搜索并抓取页面内容")
    print("=" * 60)

    ws = WebSearch()
    print("  正在搜索并抓取内容: '今日天气'...")
    result = await ws.execute(
        query="今日天气",
        num_results=1,
        fetch_content=True,
        lang="zh",
        country="cn",
    )

    if result.error:
        print(f"  ❌ 失败: {result.error}")
    else:
        print(f"  ✅ 成功! 返回 {len(result.results)} 条结果")
        for r in result.results:
            print(f"  标题: {r.title}")
            print(f"  URL: {r.url}")
            print(f"  来源: {r.source}")
            if r.raw_content:
                print(f"  页面内容(前200字): {r.raw_content[:200]}...")
            else:
                print("  ⚠️ 未获取到页面内容")

    return result


async def test_browser_use_tool():
    """测试 3: BrowserUseTool 基础功能"""
    print("\n" + "=" * 60)
    print("🌐 测试 3: BrowserUseTool - 浏览器基础操作")
    print("=" * 60)

    browser = BrowserUseTool()

    # 显示浏览器配置
    if config.browser_config:
        print(f"  headless: {config.browser_config.headless}")
        print(f"  disable_security: {config.browser_config.disable_security}")
        print(f"  max_content_length: {config.browser_config.max_content_length}")
        print(f"  chrome_instance_path: {config.browser_config.chrome_instance_path}")
    else:
        print("  ⚠️ 未配置 [browser] 段，使用默认值 (headless=False)")

    try:
        # 测试 3a: 打开网页
        print("\n  --- 3a: 打开网页 ---")
        result = await browser.execute(action="go_to_url", url="https://www.baidu.com")
        print(f"  {result.output if result.output else result.error}")

        # 测试 3b: 获取浏览器状态 (含截图)
        print("\n  --- 3b: 获取浏览器状态 ---")
        state = await browser.get_current_state()
        if state.error:
            print(f"  ❌ {state.error}")
        else:
            state_data = state.output
            # 显示部分状态信息
            lines = state_data.split("\n")
            for line in lines[:15]:
                print(f"  {line}")
            has_screenshot = bool(state.base64_image)
            print(f"  ... (截图: {'✅ 已生成' if has_screenshot else '❌ 无截图'})")

        # 测试 3c: 浏览器内搜索
        print("\n  --- 3c: 浏览器内 Web 搜索 ---")
        result = await browser.execute(
            action="web_search", query="OpenAI GPT-4"
        )
        if result.error:
            print(f"  ❌ 搜索失败: {result.error}")
        else:
            # SearchResponse 有 results 属性
            if hasattr(result, 'results') and result.results:
                print(f"  ✅ 搜索成功! 已导航到: {result.results[0].url}")
            else:
                print(f"  结果: {result.output[:300] if result.output else '无输出'}")

    except Exception as e:
        print(f"  ❌ 浏览器测试异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理浏览器
        print("\n  🧹 清理浏览器资源...")
        await browser.cleanup()
        print("  ✅ 浏览器已关闭")

    return browser


async def test_crawl4ai():
    """测试 4: Crawl4ai 爬虫"""
    print("\n" + "=" * 60)
    print("🕷️ 测试 4: Crawl4aiTool - 网页爬虫")
    print("=" * 60)

    try:
        from app.tool.crawl4ai import Crawl4aiTool

        crawler = Crawl4aiTool()
        result = await crawler.execute(
            urls=["https://www.example.com"],
            timeout=15,
        )
        if result.error:
            print(f"  ❌ 失败: {result.error}")
        else:
            print(f"  {result.output[:500]}...")
    except ImportError as e:
        print(f"  ⚠️ crawl4ai 库未安装: {e}")
        print("  安装命令: pip install crawl4ai")


async def test_agent_tool_list():
    """测试 5: 检查 Agent 可用工具列表"""
    print("\n" + "=" * 60)
    print("🤖 测试 5: Manus Agent 工具列表")
    print("=" * 60)

    from app.agent.manus import Manus

    agent = Manus()
    print(f"  Agent: {agent.name}")
    print(f"  最大步数: {agent.max_steps}")
    print(f"  可用工具 ({len(agent.available_tools.tools)}):")

    for tool in agent.available_tools.tools:
        has_search = "search" in tool.name.lower() or "browser" in tool.name.lower()
        marker = "🔍" if has_search else "  "
        print(f"  {marker} {tool.name}: {tool.description[:80]}...")

    # 检查 browser_use 的参数列表
    browser_tool = None
    for tool in agent.available_tools.tools:
        if tool.name == "browser_use":
            browser_tool = tool
            break

    if browser_tool:
        actions = browser_tool.parameters.get("properties", {}).get("action", {}).get("enum", [])
        print(f"\n  🔥 browser_use 支持的操作 ({len(actions)}):")
        for a in actions:
            deps = browser_tool.parameters.get("dependencies", {}).get(a, [])
            print(f"    - {a}" + (f" (参数: {', '.join(deps)})" if deps else ""))

    await agent.cleanup()


async def main():
    print("╔══════════════════════════════════════════════════════════╗")
    print("║   LuminAgent 浏览器 & 搜索能力测试                       ║")
    print("╚══════════════════════════════════════════════════════════╝")

    # 检查依赖
    print("\n📦 检查 Python 版本...")
    print(f"  Python {sys.version}")

    try:
        import browser_use
        print(f"  ✅ browser-use 已安装")
    except ImportError:
        print(f"  ❌ browser-use 未安装 (浏览器功能不可用)")

    try:
        import playwright
        print(f"  ✅ playwright 已安装")
    except ImportError:
        print(f"  ⚠️ playwright 未安装")

    try:
        import requests
        print(f"  ✅ requests 已安装")
    except ImportError:
        print(f"  ❌ requests 未安装")

    # 运行测试
    results = {}

    # 测试 1: 搜索
    try:
        results["search"] = await test_web_search()
    except Exception as e:
        print(f"  ❌ 搜索测试失败: {e}")

    # 测试 2: 搜索+内容
    try:
        results["search_content"] = await test_web_search_with_content()
    except Exception as e:
        print(f"  ❌ 搜索内容测试失败: {e}")

    # 测试 3: 浏览器 (这个会打开真实浏览器窗口)
    try:
        results["browser"] = await test_browser_use_tool()
    except Exception as e:
        print(f"  ❌ 浏览器测试失败: {e}")

    # 测试 4: 爬虫
    try:
        results["crawl4ai"] = await test_crawl4ai()
    except Exception as e:
        print(f"  ❌ 爬虫测试失败: {e}")

    # 测试 5: Agent工具列表
    try:
        results["agent"] = await test_agent_tool_list()
    except Exception as e:
        print(f"  ❌ Agent工具列表测试失败: {e}")

    # 总结
    print("\n" + "=" * 60)
    print("📊 测试总结")
    print("=" * 60)
    for name, result in results.items():
        status = "✅" if result else "❌"
        print(f"  {status} {name}")


if __name__ == "__main__":
    asyncio.run(main())
